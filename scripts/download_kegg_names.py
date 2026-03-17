#!/usr/bin/env python3
"""
download_kegg_names.py — Bulk-download KEGG compound and reaction name lists.

Downloads two flat TSV files from the KEGG REST API and saves them to the
``data/`` directory.  These are used by ``metakg-enrich`` (and
``metakg-build --enrich``) to replace bare KEGG accessions with human-readable
names in the knowledge graph.

Files written
-------------
data/kegg_compound_names.tsv   KEGG_ID<TAB>name  (e.g. C00031<TAB>D-Glucose)
data/kegg_reaction_names.tsv   KEGG_ID<TAB>name  (e.g. R00710<TAB>Acetaldehyde:NAD+...)

KEGG REST endpoints used
------------------------
https://rest.kegg.jp/list/compound   — ~18 000 rows
https://rest.kegg.jp/list/reaction   — ~12 000 rows

Both are served as plain text, one entry per line, with no authentication
requirement.  KEGG asks that automated tools sleep 1 s between requests.

Usage
-----
    python scripts/download_kegg_names.py [--data DIR]

Options
-------
--data DIR   Directory to write TSV files (default: data/)
--force      Overwrite existing files even if they are already present
--quiet      Suppress progress output

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from pathlib import Path

# KEGG REST list endpoints
_ENDPOINTS: dict[str, str] = {
    "kegg_compound_names.tsv": "https://rest.kegg.jp/list/compound",
    "kegg_reaction_names.tsv": "https://rest.kegg.jp/list/reaction",
}

_DEFAULT_DATA = Path(__file__).parent.parent / "data"


def _fetch(url: str, quiet: bool = False) -> str:
    """
    Download *url* and return the response body as a UTF-8 string.

    :param url: URL to fetch.
    :param quiet: Suppress progress messages.
    :return: Response body text.
    :raises SystemExit: On HTTP or network error.
    """
    if not quiet:
        print(f"  GET {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "metakg/0.1 (research)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8")
    except Exception as exc:
        print(f"ERROR: failed to download {url}: {exc}", file=sys.stderr)
        sys.exit(1)


def _count_lines(path: Path) -> int:
    """Count non-empty lines in *path*."""
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def download_kegg_names(
    data_dir: Path = _DEFAULT_DATA,
    *,
    force: bool = False,
    quiet: bool = False,
) -> dict[str, Path]:
    """
    Download KEGG compound and reaction name lists into *data_dir*.

    :param data_dir: Directory to write TSV files.
    :param force: Overwrite existing files.
    :param quiet: Suppress progress output.
    :return: Dict mapping filename → Path of the written file.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    for filename, url in _ENDPOINTS.items():
        dest = data_dir / filename
        if dest.exists() and not force:
            if not quiet:
                n = _count_lines(dest)
                print(
                    f"  SKIP  {dest}  ({n} rows already present, use --force to re-download)",
                    file=sys.stderr,
                )
            written[filename] = dest
            continue

        text = _fetch(url, quiet=quiet)
        dest.write_text(text, encoding="utf-8")
        n = _count_lines(dest)
        if not quiet:
            print(f"  OK    {dest}  ({n} entries)", file=sys.stderr)
        written[filename] = dest

        # KEGG rate-limit courtesy pause between requests
        time.sleep(1)

    return written


def main(argv: list[str] | None = None) -> int:
    """
    CLI entry point.

    :param argv: Argument list (defaults to sys.argv[1:]).
    :return: Exit code.
    """
    p = argparse.ArgumentParser(
        prog="download_kegg_names",
        description="Bulk-download KEGG compound and reaction name lists to data/.",
    )
    p.add_argument(
        "--data",
        default=str(_DEFAULT_DATA),
        metavar="DIR",
        help=f"Output directory (default: {_DEFAULT_DATA})",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if files already exist",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    args = p.parse_args(argv)

    data_dir = Path(args.data)
    if not args.quiet:
        print(f"Downloading KEGG name lists to {data_dir}/", file=sys.stderr)

    download_kegg_names(data_dir, force=args.force, quiet=args.quiet)

    if not args.quiet:
        print("Done.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
