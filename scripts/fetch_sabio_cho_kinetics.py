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
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

SABIO_BASE = "https://sabiork.h-its.org/sabioRestWebServices"
ORGANISM_QUERY = 'Organism:"Cricetulus griseus"'


def fetch_entry_ids(query: str) -> list[str]:
    """Fetch list of SABIO-RK entry IDs matching query."""
    url = f"{SABIO_BASE}/searchKineticLaws/entryIDs?q={quote(query)}"
    req = Request(url, headers={"Accept": "text/plain"})
    try:
        with urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8").strip()
            if "no data found" in text.lower():
                return []
            # Response is XML: <SabioEntryIDs><SabioEntryID>14351</SabioEntryID>...
            if text.startswith("<"):
                import re

                return re.findall(r"<SabioEntryID>(\d+)</SabioEntryID>", text)
            return [
                eid.strip() for eid in text.split("\n") if eid.strip() and eid.strip().isdigit()
            ]
    except URLError as e:
        print(f"Error fetching entry IDs: {e}", file=sys.stderr)
        sys.exit(1)


def fetch_kinetic_laws_sbml(query: str) -> str:
    """Fetch all SBML kinetic laws matching query in one request."""
    url = f"{SABIO_BASE}/searchKineticLaws/sbml?q={quote(query)}"
    req = Request(url, headers={"Accept": "application/xml"})
    try:
        with urlopen(req, timeout=120) as resp:
            return resp.read().decode("utf-8")
    except URLError as e:
        print(f"  Warning: SBML fetch failed: {e}", file=sys.stderr)
        return ""


def _strip_ns(tag: str) -> str:
    """Remove XML namespace prefix from a tag."""
    return tag.split("}")[-1] if "}" in tag else tag


def parse_sabio_sbml(sbml_text: str) -> list[dict]:
    """Parse SABIO-RK SBML response into flat parameter records.

    Handles any SBML level/version by stripping namespaces.
    Resolves enzyme names from listOfSpecies using ENZ_* modifier references.
    """
    import re

    if not sbml_text.strip():
        return []

    try:
        root = ET.fromstring(sbml_text)
    except ET.ParseError as e:
        print(f"  Warning: XML parse error: {e}", file=sys.stderr)
        return []

    # Build species id → name map (covers ENZ_*, SPC_*, etc.)
    species_map: dict[str, str] = {}
    for elem in root.iter():
        if _strip_ns(elem.tag) == "species":
            sid = elem.get("id", "")
            sname = elem.get("name", "")
            if sid:
                species_map[sid] = sname

    records = []

    for elem in root.iter():
        if _strip_ns(elem.tag) != "reaction":
            continue

        rxn_elem = elem
        rxn_id = rxn_elem.get("id", "")

        ec_number = ""
        kegg_rxn_id = ""
        pubmed_id = ""
        temperature = ""
        ph_val = ""

        # Reaction-level annotation: EC code, KEGG reaction, PubMed
        for ann in rxn_elem:
            if _strip_ns(ann.tag) != "annotation":
                continue
            ann_text = ET.tostring(ann, encoding="unicode")
            ec_m = re.findall(r"ec-code/(\d+\.\d+\.\d+[\.\d]*)", ann_text)
            if ec_m:
                ec_number = ec_m[0]
            kegg_m = re.findall(r"kegg\.reaction/(R\d+)", ann_text)
            if kegg_m:
                kegg_rxn_id = kegg_m[0]
            pm_m = re.findall(r"pubmed/(\d+)", ann_text, re.IGNORECASE)
            if pm_m:
                pubmed_id = pm_m[0]
            break

        # Enzyme name: modifier species with sboTerm SBO:0000460 (enzyme)
        enzyme_name = ""
        for mods in rxn_elem:
            if _strip_ns(mods.tag) != "listOfModifiers":
                continue
            for mod in mods:
                if mod.get("sboTerm", "") == "SBO:0000460":
                    enzyme_name = species_map.get(mod.get("species", ""), "")
                    break
            break

        # kineticLaw: sabiork annotation for pH/temperature + parameters
        for kl in rxn_elem:
            if _strip_ns(kl.tag) != "kineticLaw":
                continue

            for kl_child in kl:
                local = _strip_ns(kl_child.tag)
                if local == "annotation":
                    kl_text = ET.tostring(kl_child, encoding="unicode")
                    ph_m = re.findall(r"<[^>]*startValuepH[^>]*>([^<]+)<", kl_text)
                    if ph_m:
                        ph_val = ph_m[0].strip()
                    temp_m = re.findall(r"<[^>]*startValueTemperature[^>]*>([^<]+)<", kl_text)
                    if temp_m:
                        temperature = temp_m[0].strip()

                elif local in ("listOfLocalParameters", "listOfParameters"):
                    for param in kl_child:
                        param_id = param.get("id", "")
                        param_name = param.get("name", "")
                        param_value = param.get("value", "")
                        param_units = param.get("units", "")

                        if not param_value:
                            continue

                        param_type = _classify_param(param_id, param_name)

                        # Substrate name from parameter ID (e.g. Km_SPC_1776_Cell)
                        substrate = ""
                        spc_m = re.match(r"(?:Km|Ki|kcat)_(\S+)", param_id, re.IGNORECASE)
                        if spc_m:
                            substrate = species_map.get(spc_m.group(1), param_name)

                        records.append(
                            {
                                "sabio_entry_id": rxn_id,
                                "ec_number": ec_number,
                                "kegg_reaction_id": kegg_rxn_id,
                                "enzyme_name": enzyme_name,
                                "parameter_type": param_type,
                                "parameter_value": param_value,
                                "parameter_unit": param_units,
                                "substrate": substrate,
                                "organism": "Cricetulus griseus",
                                "tissue": "",
                                "temperature": temperature,
                                "ph": ph_val,
                                "pubmed_id": pubmed_id,
                            }
                        )
            break

    return records


FIELDNAMES = [
    "sabio_entry_id",
    "ec_number",
    "kegg_reaction_id",
    "enzyme_name",
    "parameter_type",
    "parameter_value",
    "parameter_unit",
    "substrate",
    "organism",
    "tissue",
    "temperature",
    "ph",
    "pubmed_id",
]


def _classify_param(param_id: str, param_name: str) -> str:
    """Map a SABIO-RK parameter ID/name to a standard kinetic type."""
    pid, pname = param_id.lower(), param_name.lower()
    if "km_" in pid or (pid.startswith("km") and "_" in pid):
        return "Km"
    if "vmax" in pid or "maximum velocity" in pname:
        return "Vmax"
    if "kcat" in pid or "turnover" in pname:
        return "kcat"
    if pid.startswith("ki_") or ("ki" in pid and "inhibit" in pname):
        return "Ki"
    return param_name or param_id


def main():
    """Fetch CHO kinetic parameters from SABIO-RK and write to TSV."""
    parser = argparse.ArgumentParser(description="Fetch CHO kinetic parameters from SABIO-RK")
    parser.add_argument(
        "--output",
        "-o",
        default="data/sabio_cho_kinetics.tsv",
        help="Output TSV path (default: data/sabio_cho_kinetics.tsv)",
    )
    parser.add_argument(
        "--query",
        default=ORGANISM_QUERY,
        help=f"SABIO-RK query string (default: {ORGANISM_QUERY!r})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch entry IDs only, don't download full records",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
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

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Fetching SBML for {len(entry_ids)} entries...", end=" ", flush=True)
    sbml_text = fetch_kinetic_laws_sbml(args.query)
    all_records = parse_sabio_sbml(sbml_text)
    print(f"→ {len(all_records)} params")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(all_records)

    print(f"\n{'=' * 60}")
    print(f"Wrote {len(all_records)} kinetic parameter records")
    print(f"Output: {output_path.absolute()}")
    print("\nNext steps:")
    print("  # Review the TSV, then import into MetaboKG:")
    print(f"  python scripts/import_sabio_kinetics.py --input {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
