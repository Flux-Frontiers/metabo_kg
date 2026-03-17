#!/usr/bin/env python3
"""
wire_kegg_enzymes.py — Wire enzyme→reaction links in downloaded KEGG KGML files.

Standard KEGG KGML files express enzyme-reaction catalysis via a ``reaction``
attribute on gene/ortholog <entry> elements:

    <entry id="18" name="hsa:226 hsa:229 hsa:230" type="gene" reaction="rn:R01068" .../>

The MetaKG parser currently handles two strategies:
  Strategy A: custom enzyme="N" attribute on <reaction> (used by sample data)
  Strategy B: reaction element id equals gene entry id (one-to-one id match)

Strategy B works when a gene entry and its reaction share the same KGML id,
which is the common KEGG convention for a single enzyme per reaction.  It
misses cases where:
  - Multiple gene entries catalyse the same reaction (isozymes) and only one
    has a matching id.
  - The gene entry id and reaction element id differ for any other reason.

This script scans all KGML files in the downloaded KEGG data directory and
patches <reaction> elements that have no enzyme coverage by adding an
enzyme="N" attribute pointing to the correct gene/ortholog entry id.  This
lets the existing parser wire the CATALYZES edge without any parser changes.

Run from the repo root BEFORE building the knowledge graph:

    python scripts/wire_kegg_enzymes.py
    python scripts/wire_kegg_enzymes.py --data data/hsa_pathways --dry-run

Author: Claude (automated from KEGG KGML standard)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


def _parse_file(path: Path) -> ET.Element | None:
    """Parse a KGML file and return root element, or None on parse error."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
        if tag != "pathway":
            return None
        return root
    except ET.ParseError:
        return None


def extract_enzyme_reaction_map(
    root: ET.Element,
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """
    Extract gene/ortholog entry information from a parsed KGML root.

    Returns:
        rxn_to_entries: kegg_rxn_id → [entry_id, ...] (ordered: genes first)
        entry_types:    entry_id → "gene" | "ortholog"
    """
    rxn_to_entries: dict[str, list[str]] = {}
    entry_types: dict[str, str] = {}

    for entry in root.findall("entry"):
        etype = entry.attrib.get("type", "")
        if etype not in ("gene", "ortholog"):
            continue

        entry_id = entry.attrib.get("id", "")
        reaction_attr = entry.attrib.get("reaction", "")

        if not entry_id or not reaction_attr:
            continue

        entry_types[entry_id] = etype

        for token in reaction_attr.split():
            kegg_rxn_id = token.replace("rn:", "").strip()
            if kegg_rxn_id:
                rxn_to_entries.setdefault(kegg_rxn_id, []).append(entry_id)

    # Sort each list so gene entries come before ortholog entries (prefer genes)
    for rxn_id, eids in rxn_to_entries.items():
        rxn_to_entries[rxn_id] = sorted(
            eids, key=lambda eid: (0 if entry_types.get(eid) == "gene" else 1)
        )

    return rxn_to_entries, entry_types


def find_patches(
    root: ET.Element,
    rxn_to_entries: dict[str, list[str]],
    entry_types: dict[str, str],
) -> dict[str, str]:
    """
    Determine which <reaction> elements need an enzyme="N" patch.

    A reaction needs patching when:
      1. It does NOT already have an enzyme="N" attribute (Strategy A).
      2. Its own id does NOT match any gene/ortholog entry id (Strategy B would
         already wire it correctly in those cases).
      3. At least one gene/ortholog entry declares it in its reaction attribute.

    Returns: {reaction_element_id: chosen_enzyme_entry_id}
    """
    gene_entry_ids = set(entry_types.keys())
    patches: dict[str, str] = {}

    for rxn_elem in root.findall("reaction"):
        rxn_elem_id = rxn_elem.attrib.get("id", "")
        rxn_name_attr = rxn_elem.attrib.get("name", "")

        # Skip if already patched (Strategy A — enzyme attribute present)
        if rxn_elem.attrib.get("enzyme"):
            continue

        # Skip if Strategy B already covers this reaction
        # (reaction element id equals a gene/ortholog entry id)
        if rxn_elem_id in gene_entry_ids:
            continue

        # Collect all KEGG reaction IDs in this element's name attribute
        # (some elements have space-separated names like "rn:R00431 rn:R00726")
        kegg_rxn_ids = [
            token.replace("rn:", "").strip()
            for token in rxn_name_attr.split()
            if token.startswith("rn:")
        ]

        # Find the best gene entry for any of these reactions
        chosen: str | None = None
        for kegg_rxn_id in kegg_rxn_ids:
            candidates = rxn_to_entries.get(kegg_rxn_id, [])
            # candidates are pre-sorted: genes before orthologs
            if candidates:
                chosen = candidates[0]
                break

        if chosen:
            patches[rxn_elem_id] = chosen

    return patches


def patch_file(path: Path, patches: dict[str, str]) -> int:
    """
    Add ``enzyme="N"`` to each ``<reaction id="M">`` where M is in patches.

    Uses the same regex strategy as wire_enzymes.py to avoid mangling XML
    formatting or stripping KEGG DOCTYPE declarations.

    Returns the number of reaction elements patched.
    """
    content = path.read_text(encoding="utf-8")
    patched = 0

    for rxn_id, enz_entry_id in patches.items():
        # Match <reaction id="N" ...> — avoid adding enzyme twice
        pattern = rf'(<reaction\s+id="{re.escape(rxn_id)}"(?![^>]*\benzyme\b)[^>]*)(>)'
        replacement = rf'\1 enzyme="{enz_entry_id}"\2'
        new_content, n = re.subn(pattern, replacement, content)
        if n:
            content = new_content
            patched += n

    if patched:
        path.write_text(content, encoding="utf-8")

    return patched


def process_directory(data_dir: Path, dry_run: bool) -> int:
    """
    Process all KGML files in data_dir.  Returns 0 on success, 1 on error.
    """
    kgml_files = sorted(data_dir.glob("*.kgml")) + sorted(data_dir.glob("*.xml"))
    if not kgml_files:
        print(f"ERROR: no KGML/XML files found in {data_dir}", file=sys.stderr)
        return 1

    total_files_patched = 0
    total_reactions_patched = 0
    total_files_skipped = 0

    for path in kgml_files:
        root = _parse_file(path)
        if root is None:
            total_files_skipped += 1
            continue

        rxn_to_entries, entry_types = extract_enzyme_reaction_map(root)
        if not rxn_to_entries:
            # No gene/ortholog entries with reaction attributes — nothing to do
            continue

        patches = find_patches(root, rxn_to_entries, entry_types)
        if not patches:
            continue

        total_files_patched += 1
        total_reactions_patched += len(patches)

        if dry_run:
            print(f"  DRY-RUN  {path.name}  — {len(patches)} reactions to wire:")
            for rxn_id, enz_id in sorted(patches.items(), key=lambda kv: int(kv[0])):
                etype = entry_types.get(enz_id, "?")
                print(f"           reaction id={rxn_id} → {etype} entry id={enz_id}")
        else:
            n = patch_file(path, patches)
            print(f"  OK  {path.name}  — {n} reactions wired")

    action = "would wire" if dry_run else "wired"
    print(
        f"\nSummary: {action} {total_reactions_patched} enzyme–reaction links "
        f"across {total_files_patched} files."
    )
    if total_files_skipped:
        print(f"         {total_files_skipped} files skipped (parse errors or non-KGML)")
    if dry_run:
        print("(dry-run — no files were modified)")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--data",
        default="data/hsa_pathways",
        metavar="DIRECTORY",
        help="Directory containing downloaded KGML files (default: data/hsa_pathways)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be patched without modifying any files",
    )
    args = parser.parse_args()

    data_dir = Path(args.data)
    if not data_dir.is_dir():
        print(f"ERROR: data directory not found: {data_dir}", file=sys.stderr)
        print("       Run from the repo root, or pass --data <path>", file=sys.stderr)
        return 1

    return process_directory(data_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
