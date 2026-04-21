"""
enrich.py — Post-build name enrichment for the MetaKG knowledge graph.

After ``metabokg-build`` has populated the SQLite database, compound, reaction,
and enzyme nodes carry bare KEGG accessions as their ``name`` field.  This
module replaces those with human-readable names across three phases and seven
sub-phases:

Phase 1 — graph-local, no network required:
    • Reaction nodes: labelled with the gene symbols of their catalysing
      enzymes, taken from existing CATALYZES edges
      (e.g. "R00710" → "ADH1A / ADH1B / ADH1C").

Phase 2 — requires downloaded KEGG name TSV files (see download_kegg_names.py):
    2a  Compound nodes: canonical names from ``data/kegg_compound_names.tsv``
        (e.g. "C00031" → "D-Glucose").
    2b  Reaction nodes: canonical KEGG reaction names from
        ``data/kegg_reaction_names.tsv``
        (e.g. "R00710" → "Acetaldehyde:NAD+ oxidoreductase").
        Overrides Phase 1 gene-symbol labels where a canonical name exists.
    2c  Reaction nodes (fallback): reactions still carrying bare IDs after 2b
        are resolved via ``data/kegg_reaction_detail.tsv``
        (e.g. "R02736" → "ATP:pyruvate 2-O-phosphotransferase").
    2d  Glycan compound nodes: names from ``data/kegg_glycan_names.tsv``
        for the ``gl:G#####`` namespace (e.g. "G13086" → "Lactosylceramide").
    2e  KO enzyme nodes: KEGG Orthology descriptions from
        ``data/kegg_ko_names.tsv`` for ``enz:kegg:K#####`` stubs
        (e.g. "K00001" → "alcohol dehydrogenase").

Phase 3 — requires per-organism gene name TSV files (see download_kegg_names.py):
    • Enzyme nodes: organism gene IDs resolved to gene symbols from
      ``data/{org}_gene_names.tsv`` (e.g. "100689064" → "Ldha").
      Organisms are detected automatically from enzyme node IDs in the graph.
      Enables ``--knockout ldha`` and ``resolve_id("ldha")`` at query time.

All phases are idempotent. Phase 2 always prioritises canonical KEGG names
over Phase 1 gene-symbol labels.

Public API
----------
    enrich(store, data_dir=None, *, quiet=False) -> EnrichStats
    enrich_reactions_from_graph(store, *, quiet=False) -> int
    enrich_from_tsv(store, tsv_path, kind, *, quiet=False) -> int
    enrich_glycans_from_tsv(store, glycan_tsv, *, quiet=False) -> int
    enrich_reactions_from_detail(store, detail_tsv, *, quiet=False) -> int
    enrich_ko_enzymes_from_tsv(store, ko_tsv, *, quiet=False) -> int
    enrich_enzyme_names(store, data_dir, *, quiet=False) -> int

Author: Eric G. Suchanek, PhD
Last Revision: 2026-04-19
License: Elastic 2.0
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

_DEFAULT_DATA = Path(__file__).parent.parent.parent / "data"  # repo root / data/


@dataclass
class EnrichStats:
    """
    Counts of name updates applied during an enrichment run.

    :param reactions_from_graph: Reaction names set from CATALYZES enzyme labels.
    :param compounds_from_tsv: Compound names set from KEGG compound TSV.
    :param reactions_from_tsv: Reaction names updated from KEGG reaction TSV.
    :param enzymes_from_tsv: Enzyme names resolved from per-organism gene TSVs.
    """

    reactions_from_graph: int = 0
    compounds_from_tsv: int = 0
    reactions_from_tsv: int = 0
    reactions_from_detail: int = 0
    glycans_from_tsv: int = 0
    ko_enzymes_from_tsv: int = 0
    enzymes_from_tsv: int = 0

    def __str__(self) -> str:
        return (
            f"Enrichment: {self.reactions_from_graph} reaction names from graph, "
            f"{self.compounds_from_tsv} compound names from TSV, "
            f"{self.reactions_from_tsv} reaction names from TSV, "
            f"{self.reactions_from_detail} reaction names from detail TSV, "
            f"{self.glycans_from_tsv} glycan names from TSV, "
            f"{self.ko_enzymes_from_tsv} KO enzyme names from TSV, "
            f"{self.enzymes_from_tsv} enzyme names from gene TSV"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Patterns for "bare KEGG accession" names — these are the ones we want to replace.
# _BARE_COMPOUND matches standard KEGG compound IDs (e.g. "C00031").
# _BARE_REACTION matches standard KEGG reaction IDs (e.g. "R00710") AND
#   synthetic-style short IDs produced by KGML parser when a reaction element
#   lacks an "rn:" name attribute (e.g. "1662", "pj1662", "12").
_BARE_COMPOUND = re.compile(r"^C\d{5}$")
_BARE_REACTION = re.compile(r"^R\d{5}$")
_BARE_REACTION_SYNTHETIC = re.compile(r"^[A-Za-z]{0,4}\d{1,6}$")


def _is_bare_compound(name: str) -> bool:
    return bool(_BARE_COMPOUND.match(name))


def _is_bare_reaction(name: str) -> bool:
    """
    Return True if *name* looks like an un-enriched reaction identifier.

    Matches:
    - Standard KEGG reaction accessions: ``R00710``
    - Short synthetic IDs from KGML parser (no ``rn:`` attribute): ``1662``, ``pj1662``
    """
    return bool(_BARE_REACTION.match(name)) or bool(_BARE_REACTION_SYNTHETIC.match(name))


# ---------------------------------------------------------------------------
# Phase 1: reactions from CATALYZES edges
# ---------------------------------------------------------------------------


def enrich_reactions_from_graph(store, *, quiet: bool = False) -> int:
    """
    Set reaction ``name`` to the gene symbols of catalysing enzymes.

    For each reaction node whose name is still a bare KEGG accession (e.g.
    "R00710"), look up all CATALYZES edges pointing to it and join the enzyme
    names with " / " (e.g. "ADH1A / ADH1B / ADH1C").

    Reactions with no CATALYZES edges are left unchanged.

    :param store: Open :class:`~metabokg.store.MetaStore` instance.
    :param quiet: Suppress progress output.
    :return: Number of reaction names updated.
    """
    conn = store._conn

    # Fetch all reaction IDs still carrying a bare accession name
    cur = conn.execute("SELECT id, name FROM meta_nodes WHERE kind = 'reaction'")
    bare_rxns = [(r["id"], r["name"]) for r in cur if _is_bare_reaction(r["name"])]

    if not bare_rxns:
        if not quiet:
            print("  SKIP  no bare reaction names found — nothing to enrich from graph")
        return 0

    # Build enzyme-label map in one query
    rxn_ids = [r[0] for r in bare_rxns]
    placeholders = ",".join("?" * len(rxn_ids))
    cur2 = conn.execute(
        f"""
        SELECT e.dst AS rxn_id, GROUP_CONCAT(n.name, ' / ') AS enz_label
        FROM meta_edges e
        JOIN meta_nodes n ON n.id = e.src
        WHERE e.rel = 'CATALYZES' AND e.dst IN ({placeholders})
        GROUP BY e.dst
        """,
        rxn_ids,
    )
    enz_map: dict[str, str] = {row["rxn_id"]: row["enz_label"] for row in cur2}

    # Update only those reactions that have enzyme coverage
    updated = 0
    cur3 = conn.cursor()
    for rxn_id, _old_name in bare_rxns:
        label = enz_map.get(rxn_id)
        if label:
            cur3.execute(
                "UPDATE meta_nodes SET name = ? WHERE id = ?",
                (label, rxn_id),
            )
            updated += 1

    conn.commit()
    if not quiet:
        print(f"  OK    {updated} reaction names enriched from CATALYZES edges")
    return updated


# ---------------------------------------------------------------------------
# Phase 2: names from KEGG TSV files
# ---------------------------------------------------------------------------


def _load_kegg_tsv(tsv_path: Path) -> dict[str, str]:
    """
    Parse a KEGG list TSV file into a ``{accession: name}`` dict.

    The KEGG ``/list/compound`` and ``/list/reaction`` endpoints return lines of
    the form::

        cpd:C00031    D-Glucose; Glucose; ...
        rn:R00710     Acetaldehyde:NAD+ oxidoreductase; ...

    We strip the ``cpd:`` / ``rn:`` prefix and take only the first semicolon-
    delimited synonym as the canonical name.

    :param tsv_path: Path to the downloaded TSV file.
    :return: Dict mapping bare accession (e.g. "C00031") to canonical name.
    """
    mapping: dict[str, str] = {}
    with tsv_path.open(encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter="\t")
        for row in reader:
            if len(row) < 2:
                continue
            # Strip namespace prefix (cpd:, rn:, etc.)
            accession = row[0].split(":")[-1].strip()
            # Take first synonym only
            canonical = row[1].split(";")[0].strip()
            if accession and canonical:
                mapping[accession] = canonical
    return mapping


def enrich_from_tsv(store, tsv_path: Path, kind: str, *, quiet: bool = False) -> int:
    """
    Update node names from a KEGG list TSV file.

    Extracts the bare KEGG accession from each node's ID (e.g., "C00031" from
    "cpd:kegg:C00031") and looks it up in the TSV. This allows Phase 2 to
    override Phase 1 enrichment (gene symbols) with canonical KEGG names,
    ensuring structural/canonical names take priority over enriched labels.

    :param store: Open :class:`~metabokg.store.MetaStore` instance.
    :param tsv_path: Path to the TSV file (kegg_compound_names.tsv or
        kegg_reaction_names.tsv).
    :param kind: Node kind to update (``"compound"`` or ``"reaction"``).
    :param quiet: Suppress progress output.
    :return: Number of names updated.
    """
    if not tsv_path.exists():
        if not quiet:
            print(f"  SKIP  {tsv_path.name} not found — run download_kegg_names.py first")
        return 0

    kegg_names = _load_kegg_tsv(tsv_path)
    conn = store._conn

    # Extract all nodes of the target kind
    cur = conn.execute("SELECT id, name, xrefs FROM meta_nodes WHERE kind = ?", (kind,))
    rows = [(r["id"], r["name"], r["xrefs"]) for r in cur]

    updated = 0
    cur2 = conn.cursor()
    for node_id, _, xrefs_json in rows:
        # Primary: extract KEGG accession from node ID (cpd:kegg:C00031 → C00031)
        parts = node_id.split(":")
        if len(parts) >= 3 and parts[1] == "kegg":
            accession = parts[-1]
        else:
            # Fallback: check xrefs JSON for a stored kegg cross-reference
            try:
                accession = (json.loads(xrefs_json) if xrefs_json else {}).get("kegg", "")
            except (json.JSONDecodeError, AttributeError):
                accession = ""
        if not accession:
            continue
        canonical = kegg_names.get(accession)
        if canonical:
            cur2.execute(
                "UPDATE meta_nodes SET name = ? WHERE id = ?",
                (canonical, node_id),
            )
            updated += 1

    conn.commit()
    return updated


# ---------------------------------------------------------------------------
# Phase 2d: glycan compound names from kegg_glycan_names.tsv
# ---------------------------------------------------------------------------


def enrich_glycans_from_tsv(store, glycan_tsv: Path, *, quiet: bool = False) -> int:
    """
    Update glycan compound names from ``kegg_glycan_names.tsv``.

    The KEGG glycan list uses ``gl:G00001`` prefixed IDs; node IDs in the graph
    use ``cpd:kegg:gl:G00001``.  This phase strips the ``gl:`` prefix to extract
    the bare accession for lookup.

    :param store: Open :class:`~metabokg.store.MetaStore` instance.
    :param glycan_tsv: Path to ``kegg_glycan_names.tsv``.
    :param quiet: Suppress progress output.
    :return: Number of glycan names updated.
    """
    if not glycan_tsv.exists():
        if not quiet:
            print(f"  SKIP  {glycan_tsv.name} not found — run download_kegg_names.py first")
        return 0

    glycan_names: dict[str, str] = {}
    with glycan_tsv.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                # KEGG format: "gl:G00001\tname; alias"
                raw_id = parts[0].strip()
                accession = raw_id.split(":")[-1]  # "G00001"
                name = parts[1].split(";")[0].strip()
                if accession and name:
                    glycan_names[accession] = name

    conn = store._conn
    cur = conn.execute(
        "SELECT id FROM meta_nodes WHERE kind = 'compound' AND id LIKE 'cpd:kegg:gl:%'"
    )
    rows = [r["id"] for r in cur]

    updated = 0
    cur2 = conn.cursor()
    for node_id in rows:
        accession = node_id.split(":")[-1]  # "G00001"
        canonical = glycan_names.get(accession)
        if canonical:
            cur2.execute("UPDATE meta_nodes SET name = ? WHERE id = ?", (canonical, node_id))
            updated += 1

    conn.commit()
    return updated


# ---------------------------------------------------------------------------
# Phase 2c: reaction names from kegg_reaction_detail.tsv (fallback)
# ---------------------------------------------------------------------------


def enrich_reactions_from_detail(store, detail_tsv: Path, *, quiet: bool = False) -> int:
    """
    Fallback enrichment for reactions still carrying bare KEGG IDs after Phases 1 & 2b.

    Reads ``kegg_reaction_detail.tsv`` (columns: reaction_id, name, ...) and
    updates only reactions whose name is still a bare accession.

    :param store: Open :class:`~metabokg.store.MetaStore` instance.
    :param detail_tsv: Path to ``kegg_reaction_detail.tsv``.
    :param quiet: Suppress progress output.
    :return: Number of reaction names updated.
    """
    if not detail_tsv.exists():
        if not quiet:
            print(f"  SKIP  {detail_tsv.name} not found — run download_kegg_reactions.py first")
        return 0

    # Parse reaction_id → name from the detail TSV (tab-separated, first two columns)
    detail_map: dict[str, str] = {}
    with detail_tsv.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("reaction_id"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0] and parts[1]:
                detail_map[parts[0]] = parts[1]

    conn = store._conn
    cur = conn.execute("SELECT id, name, xrefs FROM meta_nodes WHERE kind = 'reaction'")
    bare_rxns = [(r["id"], r["name"], r["xrefs"]) for r in cur if _is_bare_reaction(r["name"])]

    updated = 0
    cur2 = conn.cursor()
    for node_id, _old_name, xrefs_json in bare_rxns:
        parts = node_id.split(":")
        if len(parts) >= 3 and parts[1] == "kegg":
            accession = parts[-1]
        else:
            try:
                accession = (json.loads(xrefs_json) if xrefs_json else {}).get("kegg", "")
            except (json.JSONDecodeError, AttributeError):
                accession = ""
        if not accession:
            continue
        name = detail_map.get(accession)
        if name:
            cur2.execute("UPDATE meta_nodes SET name = ? WHERE id = ?", (name, node_id))
            updated += 1

    conn.commit()
    return updated


# ---------------------------------------------------------------------------
# Phase 2e: KO enzyme names from kegg_ko_names.tsv
# ---------------------------------------------------------------------------


def enrich_ko_enzymes_from_tsv(store, ko_tsv: Path, *, quiet: bool = False) -> int:
    """
    Update KO enzyme names (``enz:kegg:K#####``) from ``kegg_ko_names.tsv``.

    KEGG KO list format: ``K00001\\tE1.1.1.1, adh; alcohol dehydrogenase [EC:...]``
    We use the gene symbol(s) before the semicolon as the enzyme name.

    :param store: Open :class:`~metabokg.store.MetaStore` instance.
    :param ko_tsv: Path to ``kegg_ko_names.tsv``.
    :param quiet: Suppress progress output.
    :return: Number of enzyme names updated.
    """
    if not ko_tsv.exists():
        if not quiet:
            print(f"  SKIP  {ko_tsv.name} not found — run download_kegg_names.py first")
        return 0

    ko_names: dict[str, str] = {}
    with ko_tsv.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                ko_id = parts[0].strip()  # e.g. "K00001"
                label = parts[1].split(";")[0].strip()  # symbols before ";"
                if ko_id and label:
                    ko_names[ko_id] = label

    conn = store._conn
    cur = conn.execute("SELECT id FROM meta_nodes WHERE kind = 'enzyme' AND id LIKE 'enz:kegg:K%'")
    rows = [r["id"] for r in cur]

    updated = 0
    cur2 = conn.cursor()
    for node_id in rows:
        ko_id = node_id.split(":")[-1]  # "K00001"
        name = ko_names.get(ko_id)
        if name:
            cur2.execute("UPDATE meta_nodes SET name = ? WHERE id = ?", (name, node_id))
            updated += 1

    conn.commit()
    return updated


# ---------------------------------------------------------------------------
# Phase 3: enzyme names from per-organism gene TSV files
# ---------------------------------------------------------------------------

# KEGG /list/{org} lines: "{org}:{gene_id}\t{symbol}[, alias]; description"
# A bare enzyme name is a pure integer gene ID or a KEGG ortholog ID (K\d{5}).
_BARE_ENZYME = re.compile(r"^\d+$|^K\d{5}$")


def _load_gene_names_tsv(tsv_path: Path) -> dict[str, str]:
    """
    Parse a KEGG ``/list/{org}`` TSV into a ``{gene_id: symbol}`` dict.

    KEGG gene list lines have 2 or 4 columns::

        # 2-column (older format):
        hsa:672    BRCA1, RNF53; breast cancer 1 [KO:K10605]

        # 4-column (current format):
        cge:100689064    CDS    3:145001207..145009531    Ldha; L-lactate dehydrogenase A chain

    The gene symbol is always in the last column, before the first ``,`` or ``;``.

    :param tsv_path: Path to ``data/{org}_gene_names.tsv``.
    :return: Dict mapping bare gene ID string to gene symbol.
    """
    mapping: dict[str, str] = {}
    with tsv_path.open(encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter="\t")
        for row in reader:
            if len(row) < 2:
                continue
            gene_id = row[0].split(":")[-1].strip()
            # Strip the description portion (after first ";") then take the
            # first alias (before first ",").  Examples:
            #   "Ldha; L-lactate dehydrogenase A chain"  → "Ldha"
            #   "BRCA1, RNF53; breast cancer 1 [KO:K10605]"  → "BRCA1"
            #   "amiloride-sensitive amine oxidase [copper-containing]"  → skip (has spaces)
            #   "1,25-dihydroxyvitamin D(3)…"  → skip (starts with digit)
            last_col = row[-1]
            name_part = last_col.split(";")[0]  # drop description
            symbol = name_part.split(",")[0].strip()  # first alias only
            # Reject placeholders and anything that isn't a plausible gene symbol.
            if not gene_id or not symbol or symbol == "CDS":
                continue
            if " " in symbol or symbol[0].isdigit():
                continue
            mapping[gene_id] = symbol
    return mapping


def enrich_enzyme_names(store, data_dir: Path, *, quiet: bool = False) -> int:
    """
    Resolve enzyme gene IDs to gene symbols using per-organism KEGG gene TSVs.

    Handles two enzyme ID schemes:

    - ``enz:kegg:{org}:{gene_id}`` — organism is auto-detected from the ID;
      loads ``data/{org}_gene_names.tsv`` for each detected organism.
    - ``enz:syn:{hash}`` with ``xrefs = {"gene_id": "…"}`` — produced by the
      SBML FBC parser (e.g. iCHO2441); all available ``*_gene_names.tsv`` files
      in *data_dir* are loaded and the gene ID from xrefs is looked up.

    Requires TSV files downloaded by ``download_kegg_names.py --genes``.

    :param store: Open :class:`~metabokg.store.MetaStore` instance.
    :param data_dir: Directory containing ``{org}_gene_names.tsv`` files.
    :param quiet: Suppress progress output.
    :return: Number of enzyme names updated.
    """
    conn = store._conn

    cur = conn.execute("SELECT id, name, xrefs FROM meta_nodes WHERE kind = 'enzyme'")
    enzyme_rows = [(r["id"], r["name"], r["xrefs"]) for r in cur]

    # --- Partition into kegg: and syn: enzymes ---
    kegg_enzymes: list[tuple[str, str]] = []  # (eid, name)
    syn_enzymes: list[tuple[str, str, str]] = []  # (eid, name, gene_id)

    orgs: set[str] = set()
    for eid, name, xrefs_json in enzyme_rows:
        parts = eid.split(":")
        if len(parts) == 4 and parts[0] == "enz" and parts[1] == "kegg":
            org = parts[2]
            if not org.startswith("K"):  # skip ortholog stubs
                orgs.add(org)
            kegg_enzymes.append((eid, name))
        elif len(parts) == 3 and parts[0] == "enz" and parts[1] == "syn":
            try:
                gene_id = (json.loads(xrefs_json) if xrefs_json else {}).get("gene_id", "")
            except (json.JSONDecodeError, AttributeError):
                gene_id = ""
            if gene_id:
                syn_enzymes.append((eid, name, gene_id))

    if not orgs and not syn_enzymes:
        return 0

    # --- Load gene name maps ---
    gene_map: dict[str, str] = {}

    # kegg: enzymes — load org-specific TSVs
    for org in sorted(orgs):
        tsv = data_dir / f"{org}_gene_names.tsv"
        if tsv.exists():
            org_map = _load_gene_names_tsv(tsv)
            gene_map.update(org_map)
            if not quiet:
                print(f"    loaded {len(org_map)} gene names for {org}")
        else:
            if not quiet:
                print(f"    SKIP {tsv.name} not found — run download_kegg_names.py --genes {org}")

    # syn: enzymes — scan all available *_gene_names.tsv files (organism unknown from ID)
    if syn_enzymes:
        for tsv in sorted(data_dir.glob("*_gene_names.tsv")):
            org = tsv.stem.replace("_gene_names", "")
            if org not in orgs:  # avoid double-loading
                org_map = _load_gene_names_tsv(tsv)
                gene_map.update(org_map)
                if not quiet:
                    print(f"    loaded {len(org_map)} gene names for {org} (syn fallback)")

    if not gene_map:
        return 0

    updated = 0
    cur2 = conn.cursor()

    # Update kegg: enzymes (existing logic)
    for eid, name in kegg_enzymes:
        gene_id = eid.split(":")[-1]
        symbol = gene_map.get(gene_id)
        if not symbol:
            continue
        bare = not name or _BARE_ENZYME.match(name) or name.endswith("...") or name == "CDS"
        if bare or name != symbol:
            cur2.execute("UPDATE meta_nodes SET name = ? WHERE id = ?", (symbol, eid))
            updated += 1

    # Update syn: enzymes (FBC gene products — name is currently bare G_<entrez_id>)
    for eid, name, gene_id in syn_enzymes:
        symbol = gene_map.get(gene_id)
        if not symbol:
            continue
        bare = not name or _BARE_ENZYME.match(name) or name.startswith("G_") or name == "CDS"
        if bare or name != symbol:
            cur2.execute("UPDATE meta_nodes SET name = ? WHERE id = ?", (symbol, eid))
            updated += 1

    conn.commit()
    return updated


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def enrich(store, data_dir: Path | str | None = None, *, quiet: bool = False) -> EnrichStats:
    """
    Run all enrichment phases against *store*.

    Phase 1 (always runs): set reaction names from CATALYZES enzyme labels.
    Phase 2 (runs when TSV files exist): update compound and reaction names
    from downloaded KEGG name lists.

    :param store: Open :class:`~metabokg.store.MetaStore` instance.
    :param data_dir: Directory containing ``kegg_compound_names.tsv`` and
        ``kegg_reaction_names.tsv``.  Defaults to the repo-level ``data/``
        directory.
    :param quiet: Suppress progress output.
    :return: :class:`EnrichStats` with counts of updated names.
    """
    data_root = Path(data_dir) if data_dir else _DEFAULT_DATA
    stats = EnrichStats()

    # Phase 1 — no network, uses existing graph edges
    if not quiet:
        print("  Enriching reaction names from CATALYZES edges...", flush=True)
    stats.reactions_from_graph = enrich_reactions_from_graph(store, quiet=quiet)
    if not quiet:
        print(f"    → {stats.reactions_from_graph} reaction names updated")

    # Phase 2a — compound names from TSV
    cpd_tsv = data_root / "kegg_compound_names.tsv"
    if not quiet:
        print(f"  Enriching compound names from {cpd_tsv.name}...", flush=True)
    stats.compounds_from_tsv = enrich_from_tsv(store, cpd_tsv, "compound", quiet=quiet)
    if not quiet:
        print(f"    → {stats.compounds_from_tsv} compound names updated")

    # Phase 2b — reaction names from TSV (overrides Phase-1 enzyme labels with
    # canonical KEGG reaction names where available)
    rxn_tsv = data_root / "kegg_reaction_names.tsv"
    if not quiet:
        print(f"  Enriching reaction names from {rxn_tsv.name}...", flush=True)
    stats.reactions_from_tsv = enrich_from_tsv(store, rxn_tsv, "reaction", quiet=quiet)
    if not quiet:
        print(f"    → {stats.reactions_from_tsv} reaction names updated")

    # Phase 2c — fallback for reactions still bare after 2b (uses detail TSV)
    detail_tsv = data_root / "kegg_reaction_detail.tsv"
    if not quiet:
        print(f"  Enriching bare reactions from {detail_tsv.name}...", flush=True)
    stats.reactions_from_detail = enrich_reactions_from_detail(store, detail_tsv, quiet=quiet)
    if not quiet:
        print(f"    → {stats.reactions_from_detail} reaction names updated from detail")

    # Phase 2d — glycan compound names (gl:G##### namespace)
    glycan_tsv = data_root / "kegg_glycan_names.tsv"
    if not quiet:
        print(f"  Enriching glycan names from {glycan_tsv.name}...", flush=True)
    stats.glycans_from_tsv = enrich_glycans_from_tsv(store, glycan_tsv, quiet=quiet)
    if not quiet:
        print(f"    → {stats.glycans_from_tsv} glycan names updated")

    # Phase 2e — KO enzyme names (enz:kegg:K##### namespace)
    ko_tsv = data_root / "kegg_ko_names.tsv"
    if not quiet:
        print(f"  Enriching KO enzyme names from {ko_tsv.name}...", flush=True)
    stats.ko_enzymes_from_tsv = enrich_ko_enzymes_from_tsv(store, ko_tsv, quiet=quiet)
    if not quiet:
        print(f"    → {stats.ko_enzymes_from_tsv} KO enzyme names updated")

    # Phase 3 — enzyme gene IDs → gene symbols from per-organism TSVs
    if not quiet:
        print("  Enriching enzyme names from gene TSVs...", flush=True)
    stats.enzymes_from_tsv = enrich_enzyme_names(store, data_root, quiet=quiet)
    if not quiet:
        print(f"    → {stats.enzymes_from_tsv} enzyme names updated")

    return stats
