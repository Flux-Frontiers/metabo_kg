#!/usr/bin/env python3
"""
Download human KEGG pathways (organism code 'hsa') from KEGG FTP server.

This script fetches all human pathway KGML files from KEGG and saves them
to a local directory for use with metakg-build.

Usage:
    poetry run python scripts/download_human_kegg.py --output data/hsa_pathways

KEGG data license: See https://www.kegg.jp/kegg/legal.html
Free for academic and non-profit use.
"""

import argparse
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

KEGG_FTP_BASE = "https://rest.kegg.jp"
ORGANISM = "hsa"  # Homo sapiens


def get_pathway_list(organism: str) -> list[str]:
    """
    Fetch list of all pathway IDs for an organism from KEGG REST API.

    :param organism: KEGG organism code (e.g., 'hsa' for human).
    :return: List of pathway IDs (e.g., ['path:hsa00010', 'path:hsa00020']).
    """
    print(f"Fetching pathway list for {organism}...")
    try:
        url = f"{KEGG_FTP_BASE}/list/pathway/{organism}"
        with urlopen(url, timeout=10) as response:
            lines = response.read().decode("utf-8").strip().split("\n")
            pathways = [line.split("\t")[0] for line in lines if line]
            return pathways
    except URLError as e:
        print(f"Error fetching pathway list: {e}", file=sys.stderr)
        sys.exit(1)


def download_pathway_kgml(pathway_id: str) -> bytes:
    """
    Download KGML representation of a pathway.

    :param pathway_id: KEGG pathway ID (e.g., 'path:hsa00010').
    :return: KGML file content as bytes.
    """
    try:
        url = f"{KEGG_FTP_BASE}/get/{pathway_id}/kgml"
        with urlopen(url, timeout=10) as response:
            return response.read()
    except URLError as e:
        print(f"Error downloading {pathway_id}: {e}", file=sys.stderr)
        return b""


def main():
    parser = argparse.ArgumentParser(description="Download human KEGG pathways")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="data/hsa_pathways",
        help="Output directory for KGML files (default: data/hsa_pathways)",
    )
    parser.add_argument(
        "--organism", type=str, default=ORGANISM, help=f"KEGG organism code (default: {ORGANISM})"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be downloaded without downloading"
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Fetch pathway list
    pathways = get_pathway_list(args.organism)
    print(f"Found {len(pathways)} {args.organism} pathways")

    if args.dry_run:
        print("\nWould download:")
        for pathway_id in pathways[:5]:
            print(f"  {pathway_id}")
        if len(pathways) > 5:
            print(f"  ... and {len(pathways) - 5} more")
        return

    # Download each pathway
    print(f"\nDownloading to {output_dir.absolute()}...\n")
    success_count = 0
    for i, pathway_id in enumerate(pathways, 1):
        # Extract short ID for filename
        # API returns 'hsa00010', not 'path:hsa00010'
        if ":" in pathway_id:
            short_id = pathway_id.split(":")[1]
            download_id = pathway_id
        else:
            short_id = pathway_id
            download_id = f"path:{pathway_id}"

        filename = output_dir / f"{short_id}.kgml"

        # Skip if already exists
        if filename.exists():
            print(f"[{i:3}/{len(pathways)}] {short_id} (cached)")
            success_count += 1
            continue

        # Download
        print(f"[{i:3}/{len(pathways)}] Downloading {short_id}...", end=" ")
        content = download_pathway_kgml(download_id)
        if content:
            filename.write_bytes(content)
            print(f"✓ ({len(content)} bytes)")
            success_count += 1
        else:
            print("✗ (failed)")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Downloaded {success_count}/{len(pathways)} pathways")
    print(f"Location: {output_dir.absolute()}")
    print("\nNext step:")
    print(f"  poetry run metakg-build --data {output_dir} --wipe")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
