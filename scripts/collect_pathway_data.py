#!/usr/bin/env python3
"""
collect_pathway_data.py — Download real metabolic pathway data for MetaKG.

Downloads KEGG KGML files for a curated set of key human metabolic pathways
from the KEGG REST API (https://rest.kegg.jp).  Files are saved to the
``data/hsa_pathways/`` directory, ready for ingestion by ``metakg-build``.

Usage::

    python scripts/collect_pathway_data.py
    python scripts/collect_pathway_data.py --out data/hsa_pathways --delay 1.2
    python scripts/collect_pathway_data.py --list          # show pathways, don't download

KEGG Usage Terms:
    KEGG REST API is freely accessible for academic/non-commercial use.
    See https://www.kegg.jp/kegg/legal.html for details.
    This script imposes a polite delay between requests (default: 1 second).
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Curated pathway set
# ---------------------------------------------------------------------------

# Format: (kegg_pathway_id, human_readable_name, category)
PATHWAYS: list[tuple[str, str, str]] = [
    # --- Core energy metabolism ---
    ("hsa00010", "Glycolysis / Gluconeogenesis", "energy"),
    ("hsa00020", "Citrate cycle (TCA cycle)", "energy"),
    ("hsa00030", "Pentose phosphate pathway", "energy"),
    ("hsa00190", "Oxidative phosphorylation", "energy"),
    ("hsa00620", "Pyruvate metabolism", "energy"),
    ("hsa00630", "Glyoxylate and dicarboxylate metabolism", "energy"),
    ("hsa00640", "Propanoate metabolism", "energy"),
    ("hsa00650", "Butanoate metabolism", "energy"),
    # --- Fatty acid metabolism ---
    ("hsa00061", "Fatty acid biosynthesis", "lipid"),
    ("hsa00071", "Fatty acid degradation", "lipid"),
    ("hsa00100", "Steroid biosynthesis", "lipid"),
    ("hsa00600", "Sphingolipid metabolism", "lipid"),
    # --- Amino acid metabolism ---
    ("hsa00250", "Alanine, aspartate and glutamate metabolism", "amino_acid"),
    ("hsa00260", "Glycine, serine and threonine metabolism", "amino_acid"),
    ("hsa00270", "Cysteine and methionine metabolism", "amino_acid"),
    ("hsa00280", "Valine, leucine and isoleucine degradation", "amino_acid"),
    ("hsa00330", "Arginine and proline metabolism", "amino_acid"),
    ("hsa00340", "Histidine metabolism", "amino_acid"),
    ("hsa00350", "Tyrosine metabolism", "amino_acid"),
    ("hsa00360", "Phenylalanine metabolism", "amino_acid"),
    ("hsa00380", "Tryptophan metabolism", "amino_acid"),
    ("hsa00480", "Glutathione metabolism", "amino_acid"),
    # --- Nucleotide metabolism ---
    ("hsa00230", "Purine metabolism", "nucleotide"),
    ("hsa00240", "Pyrimidine metabolism", "nucleotide"),
    # --- Cofactor / vitamin metabolism ---
    ("hsa00670", "One carbon pool by folate", "cofactor"),
    ("hsa00760", "Nicotinate and nicotinamide metabolism", "cofactor"),
    ("hsa00770", "Pantothenate and CoA biosynthesis", "cofactor"),
    ("hsa00860", "Porphyrin metabolism", "cofactor"),
    # --- Carbohydrate metabolism ---
    ("hsa00500", "Starch and sucrose metabolism", "carbohydrate"),
    ("hsa00051", "Fructose and mannose metabolism", "carbohydrate"),
]

KEGG_KGML_URL = "https://rest.kegg.jp/get/{pathway_id}/kgml"


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------


def fetch_kgml(pathway_id: str, *, timeout: int = 30) -> bytes | None:
    """
    Download a KGML file from the KEGG REST API.

    :param pathway_id: KEGG pathway ID (e.g. ``"hsa00010"``).
    :param timeout: Request timeout in seconds.
    :return: Raw KGML bytes, or ``None`` on error.
    """
    url = KEGG_KGML_URL.format(pathway_id=pathway_id)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MetaKG-data-collector/0.1 (research; https://github.com/Flux-Frontiers/meta_kg)"
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        print(f"  HTTP {exc.code} for {pathway_id}: {exc.reason}", file=sys.stderr)
        return None
    except urllib.error.URLError as exc:
        print(f"  URL error for {pathway_id}: {exc.reason}", file=sys.stderr)
        return None
    except TimeoutError:
        print(f"  Timeout for {pathway_id}", file=sys.stderr)
        return None


def download_all(
    out_dir: Path,
    *,
    delay: float = 1.0,
    skip_existing: bool = True,
    pathways: list[tuple[str, str, str]] | None = None,
) -> dict[str, str]:
    """
    Download all KGML files to *out_dir*.

    :param out_dir: Destination directory.
    :param delay: Seconds to wait between requests (be polite to KEGG).
    :param skip_existing: Skip files that already exist on disk.
    :param pathways: List of (id, name, category) tuples; defaults to :data:`PATHWAYS`.
    :return: Dict mapping pathway_id → status (``"ok"``, ``"skipped"``, ``"error"``).
    """
    if pathways is None:
        pathways = PATHWAYS
    out_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, str] = {}
    total = len(pathways)

    for i, (pid, name, category) in enumerate(pathways, start=1):
        out_path = out_dir / f"{pid}.xml"
        prefix = f"[{i:2d}/{total}] {pid}"

        if skip_existing and out_path.exists() and out_path.stat().st_size > 0:
            print(f"{prefix}  SKIP  (already exists)  {name}")
            results[pid] = "skipped"
            continue

        print(f"{prefix}  Downloading  {name} ...", end=" ", flush=True)
        data = fetch_kgml(pid)
        if data is None:
            print("ERROR")
            results[pid] = "error"
        else:
            out_path.write_bytes(data)
            kb = len(data) / 1024
            print(f"OK  ({kb:.1f} KB)")
            results[pid] = "ok"

        # Polite delay (skip after last item)
        if i < total:
            time.sleep(delay)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="collect_pathway_data",
        description=(
            "Download KEGG KGML files for a curated set of metabolic pathways. "
            "Files are saved to the output directory, ready for metakg-build."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--out",
        default="data/hsa_pathways",
        metavar="DIR",
        help="Output directory for KGML files (default: ./data/hsa_pathways)",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=1.0,
        metavar="SECS",
        help="Seconds between KEGG API requests (default: 1.0)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the file already exists",
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="Print the list of pathways and exit (no downloads)",
    )
    p.add_argument(
        "--category",
        metavar="CAT",
        help=(
            "Only download pathways in this category: "
            "energy, lipid, amino_acid, nucleotide, cofactor, carbohydrate"
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # Filter by category if requested
    pathways = PATHWAYS
    if args.category:
        pathways = [(pid, name, cat) for pid, name, cat in PATHWAYS if cat == args.category]
        if not pathways:
            print(f"No pathways found for category '{args.category}'", file=sys.stderr)
            return 1

    # --list mode
    if args.list:
        _print_table(pathways)
        return 0

    out_dir = Path(args.out)
    print(f"Output directory : {out_dir.resolve()}")
    print(f"Pathways to fetch: {len(pathways)}")
    print(f"Request delay    : {args.delay}s")
    print()

    results = download_all(
        out_dir,
        delay=args.delay,
        skip_existing=not args.force,
        pathways=pathways,
    )

    # Summary
    ok = sum(1 for s in results.values() if s == "ok")
    skipped = sum(1 for s in results.values() if s == "skipped")
    errors = sum(1 for s in results.values() if s == "error")

    print()
    print(f"Done: {ok} downloaded, {skipped} skipped, {errors} errors.")
    if errors:
        print("Failed pathway IDs:")
        for pid, status in results.items():
            if status == "error":
                print(f"  {pid}")
        return 1

    print()
    print("Next step — build the knowledge graph:")
    print(f"  metakg-build --data {out_dir} --db .metakg/meta.sqlite --wipe")
    return 0


def _print_table(pathways: list[tuple[str, str, str]]) -> None:
    """Print a formatted table of pathways."""
    categories: dict[str, list[tuple[str, str, str]]] = {}
    for entry in pathways:
        cat = entry[2]
        categories.setdefault(cat, []).append(entry)

    cat_labels = {
        "energy": "Core Energy Metabolism",
        "lipid": "Fatty Acid & Lipid Metabolism",
        "amino_acid": "Amino Acid Metabolism",
        "nucleotide": "Nucleotide Metabolism",
        "cofactor": "Cofactor & Vitamin Metabolism",
        "carbohydrate": "Carbohydrate Metabolism",
    }

    total = 0
    for cat, entries in categories.items():
        label = cat_labels.get(cat, cat)
        print(f"\n  {label}")
        print(f"  {'─' * len(label)}")
        for pid, name, _ in entries:
            print(f"  {pid:12s}  {name}")
        total += len(entries)

    print(f"\n  Total: {total} pathways")


if __name__ == "__main__":
    sys.exit(main())
