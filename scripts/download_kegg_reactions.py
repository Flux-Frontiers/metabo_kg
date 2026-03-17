#!/usr/bin/env python3
"""
download_kegg_reactions.py — Download detailed reaction data from the KEGG REST API.

Fetches per-reaction records (name, definition, equation, EC numbers) for all
reactions that appear in human (hsa) metabolic pathways and writes them to a TSV
file suitable for use with the MetaKG enrichment pipeline.

Workflow
--------
1. Collect reaction IDs from one of two sources (in priority order):

   a. KGML files in a local pathway directory (e.g. data/hsa_pathways/).
      Reaction IDs are read from ``<reaction name="rn:RXXXXX ...">`` attributes
      without making any network requests.

   b. KEGG ``/link/reaction/hsa`` endpoint — returns every reaction linked to
      any human pathway (~2 000 reactions).

2. Fetch ``https://rest.kegg.jp/get/rn:RXXXXX`` for each unseen reaction.
   Parses the flat-text response for:
   - ENTRY  — reaction ID
   - NAME   — one or more semicolon-separated names (first taken as canonical)
   - DEFINITION — human-readable equation with compound names
   - EQUATION  — stoichiometric equation with KEGG accessions
   - ENZYME — one or more EC numbers (space-separated)

3. Writes ``data/kegg_reaction_detail.tsv`` (tab-separated, one row per reaction)
   with columns::

       reaction_id  name  definition  equation  ec_numbers

   Rows with all-empty fields beyond ``reaction_id`` are omitted.

Files written
-------------
data/kegg_reaction_detail.tsv

KEGG REST endpoints used
------------------------
https://rest.kegg.jp/link/reaction/hsa   — reaction IDs for human pathways
https://rest.kegg.jp/get/rn:RXXXXX      — per-reaction detail

Rate limiting
-------------
KEGG asks automated tools to sleep at least 1 second between requests.
Default delay is 1.0 s; use ``--delay`` to adjust.

Usage
-----
    python scripts/download_kegg_reactions.py [OPTIONS]

    # From local KGML files (no extra network call for ID list):
    python scripts/download_kegg_reactions.py --kgml-dir data/hsa_pathways

    # From KEGG link endpoint (broader, ~2000 reactions):
    python scripts/download_kegg_reactions.py

    # Re-download everything even if output already exists:
    python scripts/download_kegg_reactions.py --force

    # Dry-run: show IDs that would be fetched, do not download:
    python scripts/download_kegg_reactions.py --dry-run

Options
-------
--kgml-dir DIR    Directory of KGML/XML files to extract reaction IDs from.
                  If omitted, IDs are fetched from KEGG /link/reaction/hsa.
--data DIR        Output directory for TSV file (default: data/).
--delay SECS      Seconds between per-reaction API requests (default: 1.0).
--force           Re-download even if the output file already exists.
--dry-run         Print the reaction IDs that would be fetched, then exit.
--quiet           Suppress progress output.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KEGG_REST_BASE = "https://rest.kegg.jp"
_HSA_LINK_URL = f"{KEGG_REST_BASE}/link/reaction/hsa"
_GET_REACTION_URL = f"{KEGG_REST_BASE}/get/rn:{{rxn_id}}"
_OUTPUT_FILENAME = "kegg_reaction_detail.tsv"
_DEFAULT_DATA = Path(__file__).parent.parent / "data"

# Matches a canonical KEGG reaction ID (R followed by exactly 5 digits)
_RXN_ID_RE = re.compile(r"\bR\d{5}\b")

# TSV output columns
_COLUMNS = ("reaction_id", "name", "definition", "equation", "ec_numbers")

# ---------------------------------------------------------------------------
# Reaction ID collection
# ---------------------------------------------------------------------------


def collect_ids_from_kgml(kgml_dir: Path) -> list[str]:
    """
    Extract unique KEGG reaction IDs from KGML/XML pathway files.

    Scans every ``<reaction name="...">`` attribute in each file for tokens
    of the form ``rn:RXXXXX`` and collects the bare IDs.

    :param kgml_dir: Directory containing KGML or XML files.
    :return: Sorted list of unique reaction IDs (e.g. ``["R00001", "R00010", ...]``).
    :raises SystemExit: If the directory does not exist or contains no KGML files.
    """
    if not kgml_dir.is_dir():
        print(f"ERROR: KGML directory not found: {kgml_dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted(kgml_dir.glob("*.kgml")) + sorted(kgml_dir.glob("*.xml"))
    if not files:
        print(f"ERROR: No KGML/XML files found in {kgml_dir}", file=sys.stderr)
        sys.exit(1)

    ids: set[str] = set()
    for path in files:
        try:
            tree = ET.parse(path)
        except ET.ParseError:
            continue
        for elem in tree.iter("reaction"):
            name_attr = elem.attrib.get("name", "")
            for token in name_attr.split():
                if token.startswith("rn:"):
                    rxn_id = token[3:].strip()
                    if _RXN_ID_RE.fullmatch(rxn_id):
                        ids.add(rxn_id)

    return sorted(ids)


def collect_ids_from_kegg(*, quiet: bool = False) -> list[str]:
    """
    Fetch reaction IDs for all human pathways from the KEGG link endpoint.

    Uses ``GET /link/reaction/hsa`` which returns tab-separated lines of the form::

        path:hsa00010   rn:R00010

    :param quiet: Suppress progress messages.
    :return: Sorted list of unique reaction IDs.
    :raises SystemExit: On HTTP or network error.
    """
    if not quiet:
        print(f"  GET {_HSA_LINK_URL}", file=sys.stderr)

    req = urllib.request.Request(
        _HSA_LINK_URL,
        headers={"User-Agent": "metakg/0.1 (research)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8")
    except Exception as exc:
        print(f"ERROR: failed to fetch reaction list: {exc}", file=sys.stderr)
        sys.exit(1)

    ids: set[str] = set()
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            token = parts[1].strip()
            if token.startswith("rn:"):
                rxn_id = token[3:]
                if _RXN_ID_RE.fullmatch(rxn_id):
                    ids.add(rxn_id)

    return sorted(ids)


# ---------------------------------------------------------------------------
# Per-reaction detail fetching and parsing
# ---------------------------------------------------------------------------


def _fetch_reaction_text(rxn_id: str, *, timeout: int = 30) -> str | None:
    """
    Fetch the flat-text record for a single KEGG reaction.

    :param rxn_id: Bare reaction ID (e.g. ``"R00710"``).
    :param timeout: Request timeout in seconds.
    :return: Response text, or ``None`` on error.
    """
    url = _GET_REACTION_URL.format(rxn_id=rxn_id)
    req = urllib.request.Request(url, headers={"User-Agent": "metakg/0.1 (research)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None  # Reaction not in KEGG — skip silently
        print(f"  HTTP {exc.code} for {rxn_id}: {exc.reason}", file=sys.stderr)
        return None
    except urllib.error.URLError as exc:
        print(f"  URL error for {rxn_id}: {exc.reason}", file=sys.stderr)
        return None
    except TimeoutError:
        print(f"  Timeout for {rxn_id}", file=sys.stderr)
        return None


def _parse_kegg_flat(text: str) -> dict[str, str]:
    """
    Parse a KEGG flat-text reaction record into a dict of field values.

    Handles multi-line continuation lines (lines that start with spaces after
    the first field line).

    Fields extracted: ``ENTRY``, ``NAME``, ``DEFINITION``, ``EQUATION``,
    ``ENZYME``.

    :param text: Raw text from ``/get/rn:RXXXXX``.
    :return: Dict with keys ``entry``, ``name``, ``definition``, ``equation``,
        ``enzyme``.  Missing fields are empty strings.
    """
    fields: dict[str, list[str]] = {}
    current: str | None = None

    for line in text.splitlines():
        if line.startswith("///"):
            break
        if line.startswith(" ") or line.startswith("\t"):
            # Continuation of the previous field
            if current is not None:
                fields[current].append(line.strip())
        else:
            # New field: first 12 chars are the field name (left-padded)
            field_name = line[:12].strip()
            value = line[12:].strip()
            if field_name:
                current = field_name.upper()
                fields.setdefault(current, [])
                if value:
                    fields[current].append(value)

    def _join(key: str) -> str:
        return " ".join(fields.get(key, []))

    return {
        "entry": _join("ENTRY").split()[0] if fields.get("ENTRY") else "",
        "name": _join("NAME"),
        "definition": _join("DEFINITION"),
        "equation": _join("EQUATION"),
        "enzyme": _join("ENZYME"),
    }


def _parse_reaction(text: str) -> dict[str, str] | None:
    """
    Convert a KEGG flat-text record into a TSV-ready dict.

    Returns ``None`` if the text is empty or yields no useful fields.

    :param text: Raw text from the KEGG ``/get/`` endpoint.
    :return: Dict with keys matching :data:`_COLUMNS`, or ``None``.
    """
    if not text or not text.strip():
        return None

    parsed = _parse_kegg_flat(text)

    rxn_id = parsed["entry"]
    if not rxn_id:
        return None

    # Take only the first semicolon-delimited synonym as canonical name
    name = parsed["name"].split(";")[0].strip()

    # EC numbers: the ENZYME field may be space-separated (e.g. "1.1.1.1 1.1.1.2")
    ec_raw = parsed["enzyme"].strip()
    ec_numbers = "; ".join(ec_raw.split()) if ec_raw else ""

    return {
        "reaction_id": rxn_id,
        "name": name,
        "definition": parsed["definition"],
        "equation": parsed["equation"],
        "ec_numbers": ec_numbers,
    }


# ---------------------------------------------------------------------------
# Existing-output helpers
# ---------------------------------------------------------------------------


def _load_existing(tsv_path: Path) -> set[str]:
    """
    Return the set of reaction IDs already present in *tsv_path*.

    :param tsv_path: Path to an existing output TSV.
    :return: Set of reaction IDs.
    """
    ids: set[str] = set()
    if not tsv_path.exists():
        return ids
    with tsv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            rxn_id = row.get("reaction_id", "").strip()
            if rxn_id:
                ids.add(rxn_id)
    return ids


def _count_lines(path: Path) -> int:
    """Count non-empty, non-header lines in *path*."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return sum(1 for ln in lines[1:] if ln.strip())


# ---------------------------------------------------------------------------
# Main download logic
# ---------------------------------------------------------------------------


def download_kegg_reactions(
    reaction_ids: list[str],
    out_path: Path,
    *,
    force: bool = False,
    delay: float = 1.0,
    quiet: bool = False,
) -> int:
    """
    Fetch per-reaction detail from KEGG and append to *out_path*.

    Already-downloaded reactions (those whose IDs are in *out_path*) are
    skipped unless ``force=True``.

    :param reaction_ids: List of bare KEGG reaction IDs to fetch.
    :param out_path: Destination TSV file.
    :param force: Re-fetch all reactions even if already present in *out_path*.
    :param delay: Seconds to wait between KEGG API requests.
    :param quiet: Suppress progress output.
    :return: Number of new reaction records written.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine which IDs still need fetching
    existing = set() if force else _load_existing(out_path)
    to_fetch = [rid for rid in reaction_ids if rid not in existing]

    if not to_fetch:
        if not quiet:
            n = _count_lines(out_path) if out_path.exists() else 0
            print(
                f"  SKIP  {out_path}  ({n} rows already present, use --force to re-download)",
                file=sys.stderr,
            )
        return 0

    if not quiet:
        print(
            f"  Fetching {len(to_fetch)} reactions ({len(existing)} already cached)...",
            file=sys.stderr,
        )

    # Open in append mode (write header only for new files)
    write_header = not out_path.exists() or force
    if force:
        out_path.unlink(missing_ok=True)

    written = 0
    with out_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(_COLUMNS), delimiter="\t")
        if write_header:
            writer.writeheader()

        for i, rxn_id in enumerate(to_fetch, start=1):
            label = f"[{i:4d}/{len(to_fetch)}] {rxn_id}"

            text = _fetch_reaction_text(rxn_id)
            if text is None:
                if not quiet:
                    print(f"  {label}  SKIP (not found or error)", file=sys.stderr)
                continue

            record = _parse_reaction(text)
            if record is None:
                if not quiet:
                    print(f"  {label}  SKIP (empty record)", file=sys.stderr)
                continue

            writer.writerow(record)
            fh.flush()
            written += 1

            if not quiet:
                ec_display = f"  EC {record['ec_numbers']}" if record["ec_numbers"] else ""
                print(f"  {label}  OK  {record['name'][:60]}{ec_display}", file=sys.stderr)

            # KEGG rate-limit courtesy pause (skip after the last request)
            if i < len(to_fetch):
                time.sleep(delay)

    if not quiet:
        print(f"  Wrote {written} new records to {out_path}", file=sys.stderr)

    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="download_kegg_reactions",
        description=(
            "Download detailed reaction records (name, definition, equation, EC numbers) "
            "from the KEGG REST API for all reactions in human metabolic pathways."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--kgml-dir",
        metavar="DIR",
        default=None,
        help=(
            "Directory of KGML/XML pathway files to extract reaction IDs from.  "
            "If omitted, IDs are fetched from KEGG /link/reaction/hsa."
        ),
    )
    p.add_argument(
        "--data",
        default=str(_DEFAULT_DATA),
        metavar="DIR",
        help=f"Output directory for the TSV file (default: {_DEFAULT_DATA})",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=1.0,
        metavar="SECS",
        help="Seconds between per-reaction KEGG API requests (default: 1.0)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-download all reactions even if the output file already exists",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the reaction IDs that would be fetched, then exit",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """
    CLI entry point.

    :param argv: Argument list (defaults to sys.argv[1:]).
    :return: Exit code.
    """
    args = _parse_args(argv)
    data_dir = Path(args.data)
    out_path = data_dir / _OUTPUT_FILENAME

    # --- Step 1: collect reaction IDs ---
    if not args.quiet:
        if args.kgml_dir:
            print(
                f"Collecting reaction IDs from KGML files in {args.kgml_dir}/",
                file=sys.stderr,
            )
        else:
            print(
                "Collecting reaction IDs from KEGG /link/reaction/hsa ...",
                file=sys.stderr,
            )

    if args.kgml_dir:
        reaction_ids = collect_ids_from_kgml(Path(args.kgml_dir))
    else:
        reaction_ids = collect_ids_from_kegg(quiet=args.quiet)

    if not reaction_ids:
        print("ERROR: no reaction IDs found — nothing to download.", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Found {len(reaction_ids)} unique reaction IDs.", file=sys.stderr)

    # --- Dry-run mode ---
    if args.dry_run:
        print(f"\nWould fetch {len(reaction_ids)} reactions → {out_path}\n")
        sample = reaction_ids[:10]
        for rid in sample:
            print(f"  {rid}")
        if len(reaction_ids) > 10:
            print(f"  ... and {len(reaction_ids) - 10} more")
        return 0

    # --- Step 2: download detail records ---
    if not args.quiet:
        print(
            f"\nDownloading reaction details to {out_path} "
            f"(delay={args.delay}s between requests)...\n",
            file=sys.stderr,
        )

    written = download_kegg_reactions(
        reaction_ids,
        out_path,
        force=args.force,
        delay=args.delay,
        quiet=args.quiet,
    )

    if not args.quiet:
        total = _count_lines(out_path) if out_path.exists() else 0
        print(
            f"\nDone. {written} new records added; {total} total in {out_path}.",
            file=sys.stderr,
        )
        print(
            "\nTo rebuild the knowledge graph with enriched reaction names:",
            file=sys.stderr,
        )
        print("  poetry run metakg-build --data data/hsa_pathways --wipe", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
