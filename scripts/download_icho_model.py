#!/usr/bin/env python3
"""
Download the iCHO2441 consensus CHO genome-scale metabolic model from BioModels.

iCHO2441 is the largest consensus reconstruction of Chinese Hamster Ovary (CHO)
cell metabolism (Hefzi et al. 2016 updated; BioModels ID: MODEL2206100001).
It contains 6,663 reactions, 2,441 genes, and 4,456 metabolites across
subcellular compartments — making it the most complete CHO stoichiometric model
available.

MetaboKG's SBML parser ingests this file directly:

    metabokg-build --data ./data/icho_model

Usage:
    python scripts/download_icho_model.py --output data/icho_model
    python scripts/download_icho_model.py --output data/icho_model --dry-run

After downloading, build the CHO knowledge graph:
    metabokg-build --data ./data/icho_model

Or merge into an existing graph:
    metabokg-update --data ./data/icho_model

Reference:
    Hefzi et al. (2016) Cell Systems 3:434-443. PMID:27883890
    BioModels: https://www.ebi.ac.uk/biomodels/MODEL2206100001
"""

import argparse
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen, Request

BIOMODELS_BASE = "https://www.ebi.ac.uk/biomodels"
MODEL_ID = "MODEL2206100001"
MODEL_FILENAME = f"{MODEL_ID}.xml"


def fetch_model_info() -> dict:
    """Fetch metadata for iCHO2441 from BioModels REST API."""
    url = f"{BIOMODELS_BASE}/{MODEL_ID}"
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            import json
            return json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        print(f"Error fetching model info: {e}", file=sys.stderr)
        return {}


def download_sbml(output_path: Path) -> bool:
    """Download iCHO2441 SBML file from BioModels."""
    # BioModels REST API download endpoint
    url = f"{BIOMODELS_BASE}/{MODEL_ID}/download?filename={MODEL_FILENAME}"
    req = Request(url, headers={"Accept": "application/xml, text/xml"})
    try:
        print(f"Fetching {MODEL_ID} from BioModels...", end=" ", flush=True)
        with urlopen(req, timeout=120) as resp:
            content = resp.read()
        output_path.write_bytes(content)
        print(f"✓ ({len(content):,} bytes)")
        return True
    except URLError as e:
        print(f"✗\nError: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download iCHO2441 CHO genome-scale model (SBML) from BioModels"
    )
    parser.add_argument(
        "--output", "-o",
        default="data/icho_model",
        help="Output directory (default: data/icho_model)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be downloaded without downloading",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-download even if file already exists",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / MODEL_FILENAME

    if args.dry_run:
        print(f"Would download: {MODEL_ID} → {output_file}")
        print(f"  Source: {BIOMODELS_BASE}/{MODEL_ID}")
        print(f"  Model:  iCHO2441 — CHO consensus GEM (6,663 rxns, 2,441 genes)")
        print(f"  Ref:    Hefzi et al. 2016, PMID:27883890")
        return

    if output_file.exists() and not args.force:
        print(f"Already downloaded: {output_file} (use --force to re-download)")
    else:
        if not download_sbml(output_file):
            sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"iCHO2441 saved to: {output_file.absolute()}")
    print(f"\nNext steps:")
    print(f"  metabokg-build --data {output_dir}    # CHO GEM-only graph")
    print(f"  metabokg-update --data {output_dir}   # merge into existing graph")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
