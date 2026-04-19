#!/usr/bin/env python3
"""
Fetch Chinese Hamster / CHO kinetic parameters from SABIO-RK REST API.

SABIO-RK (https://sabiork.h-its.org) is a curated database of biochemical
reaction kinetics. This script queries it for all entries with
Organism:"Chinese hamster", parses the SBML response, and writes a TSV of
Km, Vmax, kcat, and related fields keyed by EC number and KEGG reaction ID.

The output TSV can be used to extend cho_kinetics.py or imported directly
into a MetaboKG store via upsert_kinetic_param().

Usage:
    python scripts/fetch_sabio_cho_kinetics.py --output data/sabio_cho_kinetics.tsv
    python scripts/fetch_sabio_cho_kinetics.py --dry-run

Output columns (TSV):
    sabio_entry_id, ec_number, kegg_reaction_id, enzyme_name,
    parameter_type, parameter_value, parameter_unit,
    substrate, organism, tissue, temperature, ph, pubmed_id

Reference:
    Wittig et al. (2012) SABIO-RK, NAR 40:D790-D796. PMID:22102587
    API docs: https://sabiork.h-its.org/layouts/content/docuRESTfulWeb/manual.gsp
"""

import argparse
import csv
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen, Request

SABIO_BASE = "https://sabiork.h-its.org/sabioRestWebServices"
ORGANISM_QUERY = 'Organism:"Chinese hamster"'

# SBML/SABIO XML namespaces
NS = {
    "sbml": "http://www.sbml.org/sbml/level2/version4",
    "html": "http://www.w3.org/1999/xhtml",
    "sabio": "http://sabiork.h-its.org",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "bqbiol": "http://biomodels.net/biology-qualifiers/",
}


def fetch_entry_ids(query: str) -> list[str]:
    """Fetch list of SABIO-RK entry IDs matching query."""
    url = f"{SABIO_BASE}/searchKineticLaws/entryIDs?q={quote(query)}"
    req = Request(url, headers={"Accept": "text/plain"})
    try:
        with urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8").strip()
            return [eid.strip() for eid in text.split("\n") if eid.strip()]
    except URLError as e:
        print(f"Error fetching entry IDs: {e}", file=sys.stderr)
        sys.exit(1)


def fetch_kinetic_laws_sbml(entry_ids: list[str]) -> str:
    """Fetch SBML for a batch of SABIO-RK entry IDs."""
    ids_param = ",".join(entry_ids)
    url = f"{SABIO_BASE}/kineticLaws/{ids_param}?format=sbml"
    req = Request(url, headers={"Accept": "application/xml"})
    try:
        with urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8")
    except URLError as e:
        print(f"  Warning: batch fetch failed: {e}", file=sys.stderr)
        return ""


def parse_sabio_sbml(sbml_text: str) -> list[dict]:
    """Parse SABIO-RK SBML response into flat parameter records."""
    if not sbml_text.strip():
        return []

    try:
        root = ET.fromstring(sbml_text)
    except ET.ParseError as e:
        print(f"  Warning: XML parse error: {e}", file=sys.stderr)
        return []

    records = []

    # SABIO SBML embeds kinetic parameters in listOfParameters within each
    # kineticLaw element, with annotations carrying EC/KEGG/organism metadata.
    for rxn_elem in root.iter("{http://www.sbml.org/sbml/level2/version4}reaction"):
        rxn_id = rxn_elem.get("id", "")
        rxn_name = rxn_elem.get("name", "")

        # Extract EC number and KEGG reaction ID from annotation
        ec_number = ""
        kegg_rxn_id = ""
        pubmed_id = ""
        organism = ""
        tissue = ""
        temperature = ""
        ph_val = ""

        annotation = rxn_elem.find(
            "{http://www.sbml.org/sbml/level2/version4}annotation"
        )
        if annotation is not None:
            ann_text = ET.tostring(annotation, encoding="unicode")
            # Simple text scan for identifiers
            if "ec-code" in ann_text:
                import re
                ec_matches = re.findall(r'ec-code/(\d+\.\d+\.\d+\.\d+)', ann_text)
                if ec_matches:
                    ec_number = ec_matches[0]
            if "kegg.reaction" in ann_text:
                import re
                kegg_matches = re.findall(r'kegg\.reaction/(R\d+)', ann_text)
                if kegg_matches:
                    kegg_rxn_id = kegg_matches[0]
            if "pubmed" in ann_text.lower():
                import re
                pm_matches = re.findall(r'pubmed/(\d+)', ann_text, re.IGNORECASE)
                if pm_matches:
                    pubmed_id = pm_matches[0]

        # Extract kinetic parameters
        kinetic_law = rxn_elem.find(
            "{http://www.sbml.org/sbml/level2/version4}kineticLaw"
        )
        if kinetic_law is None:
            continue

        param_list = kinetic_law.find(
            "{http://www.sbml.org/sbml/level2/version4}listOfParameters"
        )
        if param_list is None:
            continue

        for param in param_list:
            param_id = param.get("id", "")
            param_name = param.get("name", "")
            param_value = param.get("value", "")
            param_units = param.get("units", "")

            # Map common SABIO parameter IDs to standard names
            param_type = param_name or param_id
            if "km" in param_id.lower() or "michaelis" in param_name.lower():
                param_type = "Km"
            elif "vmax" in param_id.lower() or "maximum" in param_name.lower():
                param_type = "Vmax"
            elif "kcat" in param_id.lower() or "turnover" in param_name.lower():
                param_type = "kcat"
            elif "ki" in param_id.lower() and "inhibit" in param_name.lower():
                param_type = "Ki"

            if not param_value:
                continue

            records.append({
                "sabio_entry_id": rxn_id,
                "ec_number": ec_number,
                "kegg_reaction_id": kegg_rxn_id,
                "enzyme_name": rxn_name,
                "parameter_type": param_type,
                "parameter_value": param_value,
                "parameter_unit": param_units,
                "substrate": "",
                "organism": organism or "Chinese hamster",
                "tissue": tissue,
                "temperature": temperature,
                "ph": ph_val,
                "pubmed_id": pubmed_id,
            })

    return records


FIELDNAMES = [
    "sabio_entry_id", "ec_number", "kegg_reaction_id", "enzyme_name",
    "parameter_type", "parameter_value", "parameter_unit",
    "substrate", "organism", "tissue", "temperature", "ph", "pubmed_id",
]

BATCH_SIZE = 50  # SABIO-RK recommended batch size
DELAY = 1.0      # seconds between batches (be a good citizen)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch CHO kinetic parameters from SABIO-RK"
    )
    parser.add_argument(
        "--output", "-o",
        default="data/sabio_cho_kinetics.tsv",
        help="Output TSV path (default: data/sabio_cho_kinetics.tsv)",
    )
    parser.add_argument(
        "--query",
        default=ORGANISM_QUERY,
        help=f'SABIO-RK query string (default: {ORGANISM_QUERY!r})',
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch entry IDs only, don't download full records",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Max entries to fetch (0 = all)",
    )
    args = parser.parse_args()

    print(f"Querying SABIO-RK: {args.query}")
    entry_ids = fetch_entry_ids(args.query)
    print(f"Found {len(entry_ids)} kinetic law entries for Chinese hamster")

    if args.dry_run:
        print(f"\nFirst 10 entry IDs: {entry_ids[:10]}")
        print(f"Would write to: {args.output}")
        return

    if args.limit:
        entry_ids = entry_ids[:args.limit]
        print(f"Limiting to first {args.limit} entries")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_records: list[dict] = []
    n_batches = (len(entry_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(entry_ids), BATCH_SIZE):
        batch = entry_ids[i: i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(
            f"  Batch {batch_num}/{n_batches} ({len(batch)} entries)...",
            end=" ", flush=True,
        )
        sbml_text = fetch_kinetic_laws_sbml(batch)
        records = parse_sabio_sbml(sbml_text)
        all_records.extend(records)
        print(f"→ {len(records)} params")
        if batch_num < n_batches:
            time.sleep(DELAY)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(all_records)

    print(f"\n{'=' * 60}")
    print(f"Wrote {len(all_records)} kinetic parameter records")
    print(f"Output: {output_path.absolute()}")
    print(f"\nNext steps:")
    print(f"  # Review the TSV, then import into MetaboKG:")
    print(f"  python scripts/import_sabio_kinetics.py --input {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
