"""
downloader.py — KEGG REST download utilities and TSV integrity checks.

Provides the download functions used by ``metabokg init`` to fetch and
validate the KEGG name/annotation TSV files required for enrichment.

All downloads respect KEGG's 1-second rate-limit courtesy pause.  The
``sabio_cho_kinetics.tsv`` file is credentials-gated (SABIO-RK) and is
therefore excluded from auto-download; ``check_integrity`` will warn if it
is missing for the ``cge`` corpus.

Public API
----------
    check_integrity(data_dir, corpora) -> list[TsvIntegrityResult]
    download_kegg_names(data_dir, *, force, quiet) -> dict[str, Path]
    download_gene_names(organisms, data_dir, *, force, quiet) -> dict[str, Path]
    download_reaction_detail(data_dir, kgml_dirs, *, force, delay, quiet) -> int

Author: Eric G. Suchanek, PhD
Last Revision: 2026-04-30
License: Elastic 2.0
"""

from __future__ import annotations

import csv
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_KEGG_BASE = "https://rest.kegg.jp"
_DEFAULT_DATA = Path(__file__).parent.parent.parent / "data"

_LIST_ENDPOINTS: dict[str, str] = {
    "kegg_compound_names.tsv": f"{_KEGG_BASE}/list/compound",
    "kegg_reaction_names.tsv": f"{_KEGG_BASE}/list/reaction",
    "kegg_glycan_names.tsv": f"{_KEGG_BASE}/list/glycan",
    "kegg_ko_names.tsv": f"{_KEGG_BASE}/list/ko",
}

_RXN_ID_RE = re.compile(r"\bR\d{5}\b")

# ---------------------------------------------------------------------------
# TSV manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TsvSpec:
    """Descriptor for a single required TSV file in ``data/``.

    :param filename: Bare filename, e.g. ``"kegg_compound_names.tsv"``.
    :param min_rows: Integrity threshold — ``"thin"`` warning below this count.
    :param corpora: Corpus names that require this file, or ``None`` for all.
    :param download_group: How to fetch this file:
        ``"names"`` (KEGG list endpoint), ``"reactions"`` (per-reaction detail),
        ``"genes:{org}"`` (KEGG organism list), ``"manual"`` (cannot auto-fetch).
    """

    filename: str
    min_rows: int
    corpora: frozenset[str] | None
    download_group: str


TSV_MANIFEST: tuple[TsvSpec, ...] = (
    TsvSpec("kegg_compound_names.tsv", 15_000, None, "names"),
    TsvSpec("kegg_reaction_names.tsv", 10_000, None, "names"),
    TsvSpec("kegg_glycan_names.tsv", 5_000, None, "names"),
    TsvSpec("kegg_ko_names.tsv", 20_000, None, "names"),
    TsvSpec("kegg_reaction_detail.tsv", 1_500, None, "reactions"),
    TsvSpec("hsa_gene_names.tsv", 30_000, frozenset({"hsa"}), "genes:hsa"),
    TsvSpec("cge_gene_names.tsv", 20_000, frozenset({"cge"}), "genes:cge"),
    TsvSpec("sabio_cho_kinetics.tsv", 100, frozenset({"cge"}), "manual"),
)

# ---------------------------------------------------------------------------
# Corpus descriptors
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusSpec:
    """Descriptor for a buildable MetaboKG corpus.

    :param name: Short corpus key, e.g. ``"hsa"``.
    :param data_subdir: Path relative to CWD (repo root), e.g. ``"data/hsa_pathways"``.
    :param org: KEGG organism code for gene-name download, or ``None``.
    :param has_kinetics: Whether to run ``seed_kinetics()`` after build.
    :param has_cho_kinetics: Whether to additionally run ``seed_cho_kinetics()`` after build.
    """

    name: str
    data_subdir: str
    org: str | None
    has_kinetics: bool
    has_cho_kinetics: bool


CORPUS_SPECS: tuple[CorpusSpec, ...] = (
    CorpusSpec("hsa", "data/hsa_pathways", "hsa", has_kinetics=True, has_cho_kinetics=False),
    CorpusSpec("cge", "data/cge_pathways", "cge", has_kinetics=True, has_cho_kinetics=True),
    CorpusSpec("icho", "data/icho_model", None, has_kinetics=False, has_cho_kinetics=False),
)

CORPUS_BY_NAME: dict[str, CorpusSpec] = {c.name: c for c in CORPUS_SPECS}

# ---------------------------------------------------------------------------
# Integrity check
# ---------------------------------------------------------------------------


@dataclass
class TsvIntegrityResult:
    """Result of an integrity check for a single TSV file.

    :param spec: The :class:`TsvSpec` that was checked.
    :param path: Resolved filesystem path.
    :param status: ``"ok"`` | ``"thin"`` | ``"empty"`` | ``"missing"``.
    :param rows: Number of non-empty lines (0 if missing).
    """

    spec: TsvSpec
    path: Path
    status: str
    rows: int

    @property
    def needs_fetch(self) -> bool:
        """True when the file must be downloaded before the build can proceed."""
        return self.status in ("missing", "empty") and self.spec.download_group != "manual"

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def check_integrity(
    data_dir: Path,
    corpora: set[str] | None = None,
) -> list[TsvIntegrityResult]:
    """Check the presence and row-count of each required TSV file.

    :param data_dir: Directory containing the TSV files (usually ``data/``).
    :param corpora: Corpus names whose TSVs should be checked.  ``None``
        checks all entries in :data:`TSV_MANIFEST`.
    :return: One :class:`TsvIntegrityResult` per applicable TSV, in manifest order.
    """
    results: list[TsvIntegrityResult] = []
    for spec in TSV_MANIFEST:
        if spec.corpora is not None and corpora is not None:
            if not spec.corpora.intersection(corpora):
                continue

        path = data_dir / spec.filename
        if not path.exists():
            results.append(TsvIntegrityResult(spec, path, "missing", 0))
            continue

        rows = _count_lines(path)
        if rows == 0:
            status = "empty"
        elif rows < spec.min_rows:
            status = "thin"
        else:
            status = "ok"
        results.append(TsvIntegrityResult(spec, path, status, rows))

    return results


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _count_lines(path: Path) -> int:
    """Count non-empty lines in *path*."""
    return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())


def _fetch(url: str, *, quiet: bool = False) -> str:
    """Download *url* and return the response body as a UTF-8 string.

    :param url: URL to fetch.
    :param quiet: Suppress progress messages.
    :return: Response body text.
    :raises RuntimeError: On HTTP or network error.
    """
    if not quiet:
        print(f"  GET {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "metabokg/1.0 (research)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"download failed: {url}: {exc}") from exc


# ---------------------------------------------------------------------------
# Download: universal KEGG name-list TSVs
# ---------------------------------------------------------------------------


def download_kegg_names(
    data_dir: Path = _DEFAULT_DATA,
    *,
    force: bool = False,
    quiet: bool = False,
) -> dict[str, Path]:
    """Download the four universal KEGG name-list TSVs into *data_dir*.

    Files written: ``kegg_compound_names.tsv``, ``kegg_reaction_names.tsv``,
    ``kegg_glycan_names.tsv``, ``kegg_ko_names.tsv``.  Already-present files
    are skipped unless *force* is ``True``.

    :param data_dir: Destination directory.
    :param force: Overwrite existing files.
    :param quiet: Suppress progress output.
    :return: Dict mapping filename → written :class:`~pathlib.Path`.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    for filename, url in _LIST_ENDPOINTS.items():
        dest = data_dir / filename
        if dest.exists() and not force:
            if not quiet:
                n = _count_lines(dest)
                print(
                    f"  SKIP  {filename}  ({n} rows, use --force to re-download)", file=sys.stderr
                )
            written[filename] = dest
            continue

        text = _fetch(url, quiet=quiet)
        dest.write_text(text, encoding="utf-8")
        n = _count_lines(dest)
        if not quiet:
            print(f"  OK    {filename}  ({n} entries)", file=sys.stderr)
        written[filename] = dest
        time.sleep(1)

    return written


# ---------------------------------------------------------------------------
# Download: per-organism gene name TSVs
# ---------------------------------------------------------------------------


def download_gene_names(
    organisms: list[str],
    data_dir: Path = _DEFAULT_DATA,
    *,
    force: bool = False,
    quiet: bool = False,
) -> dict[str, Path]:
    """Download KEGG gene name lists for *organisms* into *data_dir*.

    Produces ``{org}_gene_names.tsv`` for each organism code.  Used by
    Phase 3 of ``metabokg enrich`` to resolve bare gene IDs to symbols
    (enabling ``--knockout ldha`` style queries).

    :param organisms: KEGG organism codes, e.g. ``["hsa", "cge"]``.
    :param data_dir: Destination directory.
    :param force: Overwrite existing files.
    :param quiet: Suppress progress output.
    :return: Dict mapping organism code → written :class:`~pathlib.Path`.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    for org in organisms:
        filename = f"{org}_gene_names.tsv"
        dest = data_dir / filename
        if dest.exists() and not force:
            if not quiet:
                n = _count_lines(dest)
                print(
                    f"  SKIP  {filename}  ({n} rows, use --force to re-download)", file=sys.stderr
                )
            written[org] = dest
            continue

        text = _fetch(f"{_KEGG_BASE}/list/{org}", quiet=quiet)
        dest.write_text(text, encoding="utf-8")
        n = _count_lines(dest)
        if not quiet:
            print(f"  OK    {filename}  ({n} entries)", file=sys.stderr)
        written[org] = dest
        time.sleep(1)

    return written


# ---------------------------------------------------------------------------
# Download: per-reaction detail TSV
# ---------------------------------------------------------------------------


def _collect_rxn_ids_from_kgml(kgml_dirs: list[Path]) -> list[str]:
    """Extract unique KEGG reaction IDs from KGML/XML files in *kgml_dirs*."""
    ids: set[str] = set()
    for d in kgml_dirs:
        for path in sorted(d.glob("*.kgml")) + sorted(d.glob("*.xml")):
            try:
                tree = ET.parse(path)
            except ET.ParseError:
                continue
            for elem in tree.iter("reaction"):
                for token in elem.attrib.get("name", "").split():
                    if token.startswith("rn:"):
                        rxn_id = token[3:].strip()
                        if _RXN_ID_RE.fullmatch(rxn_id):
                            ids.add(rxn_id)
    return sorted(ids)


def _parse_kegg_reaction_flat(text: str) -> dict[str, str] | None:
    """Parse a KEGG flat-text reaction record; return ``None`` if unusable."""
    if not text or not text.strip():
        return None
    fields: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("///"):
            break
        if line.startswith((" ", "\t")):
            if current is not None:
                fields[current].append(line.strip())
        else:
            field_name = line[:12].strip().upper()
            value = line[12:].strip()
            if field_name:
                current = field_name
                fields.setdefault(current, [])
                if value:
                    fields[current].append(value)

    def _join(key: str) -> str:
        return " ".join(fields.get(key, []))

    entry = _join("ENTRY").split()[0] if fields.get("ENTRY") else ""
    if not entry:
        return None
    name = _join("NAME").split(";")[0].strip()
    ec_raw = _join("ENZYME").strip()
    return {
        "reaction_id": entry,
        "name": name,
        "definition": _join("DEFINITION"),
        "equation": _join("EQUATION"),
        "ec_numbers": "; ".join(ec_raw.split()) if ec_raw else "",
    }


def download_reaction_detail(
    data_dir: Path = _DEFAULT_DATA,
    kgml_dirs: list[Path] | None = None,
    *,
    force: bool = False,
    delay: float = 1.0,
    quiet: bool = False,
) -> int:
    """Download per-reaction detail from KEGG into ``kegg_reaction_detail.tsv``.

    Reaction IDs are extracted from KGML files in *kgml_dirs*.  Reactions
    already present in the output file are skipped unless *force* is ``True``.
    This call makes one KEGG REST request per new reaction (~1 500 requests
    for all human pathways, ~25 minutes with a 1-second delay).

    :param data_dir: Destination directory for the TSV.
    :param kgml_dirs: Directories containing pathway KGML/XML files.
        Defaults to ``[data_dir / "hsa_pathways"]``.
    :param force: Re-fetch all reactions.
    :param delay: Seconds between KEGG API requests (default 1.0).
    :param quiet: Suppress progress output.
    :return: Number of new reaction records written.
    """
    out_path = data_dir / "kegg_reaction_detail.tsv"
    _columns = ("reaction_id", "name", "definition", "equation", "ec_numbers")

    if kgml_dirs is None:
        kgml_dirs = [data_dir / "hsa_pathways"]

    rxn_ids = _collect_rxn_ids_from_kgml(kgml_dirs)
    if not rxn_ids:
        if not quiet:
            print("  WARNING: no reaction IDs found in KGML dirs", file=sys.stderr)
        return 0

    # Determine which IDs are already cached
    existing: set[str] = set()
    if out_path.exists() and not force:
        with out_path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                rid = row.get("reaction_id", "").strip()
                if rid:
                    existing.add(rid)

    to_fetch = [r for r in rxn_ids if r not in existing]
    if not to_fetch:
        if not quiet:
            n = _count_lines(out_path) if out_path.exists() else 0
            print(f"  SKIP  kegg_reaction_detail.tsv  ({n} rows cached)", file=sys.stderr)
        return 0

    if not quiet:
        print(
            f"  Fetching {len(to_fetch)} reactions ({len(existing)} already cached)...",
            file=sys.stderr,
        )

    write_header = not out_path.exists() or force
    if force:
        out_path.unlink(missing_ok=True)

    data_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(_columns), delimiter="\t")
        if write_header:
            writer.writeheader()
        for i, rxn_id in enumerate(to_fetch, 1):
            try:
                text = _fetch(f"{_KEGG_BASE}/get/rn:{rxn_id}", quiet=True)
            except RuntimeError:
                continue
            record = _parse_kegg_reaction_flat(text)
            if record:
                writer.writerow(record)
                written += 1
            if not quiet and i % 100 == 0:
                print(f"  ... {i}/{len(to_fetch)} reactions fetched", file=sys.stderr)
            if i < len(to_fetch):
                time.sleep(delay)

    if not quiet:
        print(f"  OK    kegg_reaction_detail.tsv  ({written} new records)", file=sys.stderr)
    return written
