#!/usr/bin/env python3
"""
Download Chinese Hamster Ovary (CHO) KEGG pathways (organism code 'cge').

KEGG organism code for Cricetulus griseus (Chinese hamster): cge
The cge KGML files are structurally identical to hsa — MetaboKG ingests
them without any code changes.

Usage:
    python scripts/download_cho_kegg.py --output data/cge_pathways
    python scripts/download_cho_kegg.py --output data/cge_pathways --dry-run

After downloading, build the CHO knowledge graph:
    metabokg-build --data ./data/cge_pathways

Or merge CHO pathways into an existing human graph:
    metabokg-update --data ./data/cge_pathways

KEGG data license: https://www.kegg.jp/kegg/legal.html
Free for academic and non-profit use.
"""

import sys
from pathlib import Path

# Reuse the generic download script with cge defaults
sys.path.insert(0, str(Path(__file__).parent))

from download_human_kegg import get_pathway_list, download_pathway_kgml  # noqa: E402

import argparse

ORGANISM = "cge"  # Cricetulus griseus — Chinese hamster (CHO cells)


def main():
    parser = argparse.ArgumentParser(
        description="Download CHO (Cricetulus griseus / cge) KEGG pathways"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="data/cge_pathways",
        help="Output directory for KGML files (default: data/cge_pathways)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without downloading",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.34,
        help="Seconds between requests (default: 0.34 — ~3 req/s, within KEGG limit)",
    )
    args = parser.parse_args()

    import time

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    pathways = get_pathway_list(ORGANISM)
    print(f"Found {len(pathways)} {ORGANISM} (CHO) pathways")

    if args.dry_run:
        print("\nWould download:")
        for pid in pathways[:8]:
            print(f"  {pid}")
        if len(pathways) > 8:
            print(f"  ... and {len(pathways) - 8} more")
        return

    print(f"\nDownloading to {output_dir.absolute()}...\n")
    success, skipped = 0, 0
    for i, pathway_id in enumerate(pathways, 1):
        short_id = pathway_id.split(":")[-1] if ":" in pathway_id else pathway_id
        download_id = pathway_id if ":" in pathway_id else f"path:{pathway_id}"
        filename = output_dir / f"{short_id}.kgml"

        if filename.exists():
            print(f"[{i:3}/{len(pathways)}] {short_id} (cached)")
            skipped += 1
            success += 1
            continue

        print(f"[{i:3}/{len(pathways)}] Downloading {short_id}...", end=" ", flush=True)
        content = download_pathway_kgml(download_id)
        if content:
            filename.write_bytes(content)
            print(f"✓ ({len(content):,} bytes)")
            success += 1
        else:
            print("✗ (failed or no KGML)")

        time.sleep(args.delay)

    print(f"\n{'=' * 60}")
    print(f"Downloaded {success}/{len(pathways)} pathways ({skipped} cached)")
    print(f"Location: {output_dir.absolute()}")
    print("\nNext steps:")
    print(f"  metabokg-build --data {output_dir}             # CHO-only graph")
    print(f"  metabokg-update --data {output_dir}            # merge into existing graph")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
