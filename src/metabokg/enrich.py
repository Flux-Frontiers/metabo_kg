"""
enrich.py — Post-build name enrichment for the MetaKG knowledge graph.

After ``metabokg-build`` has populated the SQLite database, compound, reaction,
and enzyme nodes carry bare KEGG accessions as their ``name`` field.  This
module replaces those with human-readable names in three phases:

Phase 1 — no network required, uses data already in the graph:
    • Reaction nodes: labelled with the gene symbols of their catalysing enzyme,
      taken from existing CATALYZES edges (e.g. "R00710" → "ADH1A/ADH1B/ADH1C").

Phase 2 — requires downloaded KEGG name TSV files (see download_kegg_names.py):
    • Compound nodes: names from ``data/kegg_compound_names.tsv``
      (e.g. "C00031" → "D-Glucose").
    • Reaction nodes: canonical KEGG reaction names from
      ``data/kegg_reaction_names.tsv``
      (e.g. "R00710" → "Acetaldehyde:NAD+ oxidoreductase").
      Always replaces Phase 1 enzyme-labels with canonical names (if available).

Phase 3 — requires per-organism gene name TSV files (see download_kegg_names.py):
    • Enzyme nodes: gene IDs resolved to gene symbols from
      ``data/{org}_gene_names.tsv`` (e.g. "100689064" → "Ldha").
      Organisms are detected automatically from enzyme node IDs in the graph.
      Enables ``--knockout ldha`` and ``resolve_id("ldha")`` at query time.

All phases are idempotent. Phase 2 always prioritizes canonical KEGG names
over Phase 1 gene-symbol labels.

Public API
----------
    enrich(store, data_dir=None, *, quiet=False) -> EnrichStats
    enrich_reactions_from_graph(store, *, quiet=False) -> int
    enrich_from_tsv(store, tsv_path, kind, *, quiet=False) -> int
    enrich_enzyme_names(store, data_dir, *, quiet=False) -> int

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import csv
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
    enzymes_from_tsv: int = 0

    def __str__(self) -> str:
        return (
            f"Enrichment: {self.reactions_from_graph} reaction names from graph, "
            f"{self.compounds_from_tsv} compound names from TSV, "
            f"{self.reactions_from_tsv} reaction names from TSV, "
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
    cur = conn.execute("SELECT id, name FROM meta_nodes WHERE kind = ?", (kind,))
    rows = [(r["id"], r["name"]) for r in cur]

    updated = 0
    cur2 = conn.cursor()
    for node_id, old_name in rows:
        # Extract bare KEGG accession from node ID
        # Format: cpd:kegg:C00031 or rxn:kegg:R00710 → last segment
        parts = node_id.split(":")
        if len(parts) >= 3 and parts[1] == "kegg":
            accession = parts[-1]  # e.g., "C00031" or "R00710"
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
            # Symbol is always in the last column, before first comma or semicolon
            symbol = re.split(r"[,;]", row[-1])[0].strip()
            if gene_id and symbol and symbol != "CDS":
                mapping[gene_id] = symbol
    return mapping


def enrich_enzyme_names(store, data_dir: Path, *, quiet: bool = False) -> int:
    """
    Resolve enzyme gene IDs to gene symbols using per-organism KEGG gene TSVs.

    Detects which organisms are present in the graph from enzyme node IDs of
    the form ``enz:kegg:{org}:{gene_id}``, then loads
    ``data/{org}_gene_names.tsv`` for each and updates any enzyme whose name
    is still a bare gene ID (pure digits) or KEGG ortholog ID (``K\\d{5}``).

    Requires TSV files downloaded by ``download_kegg_names.py --genes``.

    :param store: Open :class:`~metabokg.store.MetaStore` instance.
    :param data_dir: Directory containing ``{org}_gene_names.tsv`` files.
    :param quiet: Suppress progress output.
    :return: Number of enzyme names updated.
    """
    conn = store._conn

    # Detect organisms present: enz:kegg:{org}:{gene_id} where org != K (orthologs)
    cur = conn.execute("SELECT id, name FROM meta_nodes WHERE kind = 'enzyme'")
    enzyme_rows = [(r["id"], r["name"]) for r in cur]

    orgs: set[str] = set()
    for eid, _ in enzyme_rows:
        parts = eid.split(":")
        # enz:kegg:{org}:{gene_id} → parts[2] is organism code
        if len(parts) == 4 and parts[0] == "enz" and parts[1] == "kegg":
            org = parts[2]
            if not org.startswith("K"):  # skip ortholog stubs
                orgs.add(org)

    if not orgs:
        return 0

    # Load gene name maps for all detected organisms
    gene_map: dict[str, str] = {}
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

    if not gene_map:
        return 0

    updated = 0
    cur2 = conn.cursor()
    for eid, name in enzyme_rows:
        parts = eid.split(":")
        if len(parts) != 4:
            continue
        gene_id = parts[3]
        symbol = gene_map.get(gene_id)
        if not symbol:
            continue
        # Update if: bare gene ID, KEGG ortholog, truncated KGML name (ends in
        # "..."), generic "CDS" placeholder, or name doesn't yet equal symbol.
        bare = not name or _BARE_ENZYME.match(name) or name.endswith("...") or name == "CDS"
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

    # Phase 3 — enzyme gene IDs → gene symbols from per-organism TSVs
    if not quiet:
        print("  Enriching enzyme names from gene TSVs...", flush=True)
    stats.enzymes_from_tsv = enrich_enzyme_names(store, data_root, quiet=quiet)
    if not quiet:
        print(f"    → {stats.enzymes_from_tsv} enzyme names updated")

    return stats
