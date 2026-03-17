"""
sbml.py — SBML (Systems Biology Markup Language) pathway parser.

Supports SBML Level 2 and Level 3 files using stdlib xml.etree.ElementTree.
Optional python-libsbml is NOT required.

SBML structure:
  <listOfSpecies>   → compound nodes
  <listOfReactions> → reaction nodes
    <listOfReactants> → SUBSTRATE_OF edges
    <listOfProducts>  → PRODUCT_OF edges
    <listOfModifiers> → CATALYZES or INHIBITS/ACTIVATES (via SBO term)

Reference: https://sbml.org/software/libsbml/libsbml-docs/api/python/

SBML detection: root element tag ends with ``sbml`` (may have namespace prefix).

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from metakg.parsers.base import PathwayParser
from metakg.primitives import (
    KIND_COMPOUND,
    KIND_ENZYME,
    KIND_PATHWAY,
    KIND_REACTION,
    REL_ACTIVATES,
    REL_CATALYZES,
    REL_CONTAINS,
    REL_INHIBITS,
    REL_PRODUCT_OF,
    REL_SUBSTRATE_OF,
    MetaEdge,
    MetaNode,
    node_id,
    synthetic_id,
)

# SBO term ranges for modifier roles
# SBO:0000020 = inhibitor, SBO:0000013 = catalyst, SBO:0000459 = stimulator
_SBO_INHIBITOR = re.compile(r"SBO:000002[0-9]", re.I)
_SBO_ACTIVATOR = re.compile(r"SBO:000045[0-9]", re.I)


def _strip_ns(tag: str) -> str:
    """Remove XML namespace prefix from a tag."""
    return tag.split("}")[-1] if "}" in tag else tag


class SBMLParser(PathwayParser):
    """
    Parser for SBML Level 2/3 files.

    Uses only stdlib ``xml.etree.ElementTree``.  For Level 3 features that
    require libsbml (e.g., hierarchical models), a ``ValueError`` is raised
    with a descriptive message so the dispatcher can skip the file gracefully.
    """

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".xml", ".sbml")

    def can_handle(self, path: Path) -> bool:
        if path.suffix.lower() not in self.supported_extensions:
            return False
        try:
            for _evt, elem in ET.iterparse(path, events=("start",)):
                tag = _strip_ns(elem.tag)
                return tag == "sbml"
        except ET.ParseError:
            return False
        return False

    def parse(self, path: Path) -> tuple[list[MetaNode], list[MetaEdge]]:
        """
        Parse an SBML file into MetaNode and MetaEdge objects.

        :param path: Path to the ``.sbml`` or ``.xml`` file.
        :return: ``(nodes, edges)`` tuple.
        :raises ValueError: If the file is not valid SBML or uses unsupported features.
        """
        try:
            tree = ET.parse(path)
        except ET.ParseError as exc:
            raise ValueError(f"Invalid XML in {path}: {exc}") from exc

        root = tree.getroot()
        root_tag = _strip_ns(root.tag)
        if root_tag != "sbml":
            raise ValueError(f"Root element is <{root_tag}>, expected <sbml>")

        ns = root.tag[: root.tag.index("}") + 1] if "}" in root.tag else ""
        nodes: dict[str, MetaNode] = {}
        edges: list[MetaEdge] = []

        def _tag(local: str) -> str:
            return f"{ns}{local}"

        # --- Model element ---
        model = root.find(_tag("model"))
        if model is None:
            model = root  # Level 2 fallback: model is root's first child

        model_id = model.attrib.get("id", path.stem)
        model_name = model.attrib.get("name", model_id)

        pwy_id = synthetic_id(KIND_PATHWAY, model_id)
        nodes[pwy_id] = MetaNode(
            id=pwy_id,
            kind=KIND_PATHWAY,
            name=model_name,
            description=f"SBML model: {model_name}",
            source_format="sbml",
            source_file=str(path),
        )

        # --- Species → compound nodes ---
        species_id_map: dict[str, str] = {}  # SBML species id → MetaNode id

        for species_list in model.findall(_tag("listOfSpecies")):
            for sp in species_list.findall(_tag("species")):
                sp_id = sp.attrib.get("id", "")
                sp_name = sp.attrib.get("name", sp_id)
                compartment = sp.attrib.get("compartment", "")

                # Try to extract ChEBI or KEGG from annotation
                sp_xrefs: dict[str, str] = {}
                annotation = sp.find(_tag("annotation"))
                if annotation is not None:
                    ann_text = ET.tostring(annotation, encoding="unicode")
                    for m in re.finditer(r"identifiers\.org/chebi/([A-Z0-9_:]+)", ann_text):
                        sp_xrefs["chebi"] = m.group(1)
                    for m in re.finditer(r"identifiers\.org/kegg\.compound/([A-Z0-9]+)", ann_text):
                        sp_xrefs["kegg"] = m.group(1)

                if "chebi" in sp_xrefs:
                    nid = node_id(KIND_COMPOUND, "chebi", sp_xrefs["chebi"])
                elif "kegg" in sp_xrefs:
                    nid = node_id(KIND_COMPOUND, "kegg", sp_xrefs["kegg"])
                else:
                    nid = synthetic_id(KIND_COMPOUND, sp_id)

                species_id_map[sp_id] = nid
                if nid not in nodes:
                    desc_parts = [f"SBML species: {sp_name}"]
                    if compartment:
                        desc_parts.append(f"Compartment: {compartment}")
                    nodes[nid] = MetaNode(
                        id=nid,
                        kind=KIND_COMPOUND,
                        name=sp_name,
                        description=". ".join(desc_parts),
                        xrefs=json.dumps(sp_xrefs) if sp_xrefs else None,
                        source_format="sbml",
                        source_file=str(path),
                    )

        # --- Reactions ---
        for rxn_list in model.findall(_tag("listOfReactions")):
            for rxn_elem in rxn_list.findall(_tag("reaction")):
                rxn_id_raw = rxn_elem.attrib.get("id", "")
                rxn_name = rxn_elem.attrib.get("name", rxn_id_raw)
                reversible = rxn_elem.attrib.get("reversible", "false").lower() == "true"

                xrefs: dict[str, str] = {}
                annotation = rxn_elem.find(_tag("annotation"))
                if annotation is not None:
                    ann_text = ET.tostring(annotation, encoding="unicode")
                    for m in re.finditer(r"identifiers\.org/kegg\.reaction/([A-Z0-9]+)", ann_text):
                        xrefs["kegg"] = m.group(1)
                    for m in re.finditer(r"identifiers\.org/rhea/([0-9]+)", ann_text):
                        xrefs["rhea"] = m.group(1)

                if "kegg" in xrefs:
                    rxn_nid = node_id(KIND_REACTION, "kegg", xrefs["kegg"])
                else:
                    rxn_nid = synthetic_id(KIND_REACTION, rxn_id_raw)

                substrates: list[dict] = []
                products: list[dict] = []

                for reactants_list in rxn_elem.findall(_tag("listOfReactants")):
                    for sr in reactants_list.findall(_tag("speciesReference")):
                        sp_ref = sr.attrib.get("species", "")
                        stoich = float(sr.attrib.get("stoichiometry", "1"))
                        cid = species_id_map.get(sp_ref)
                        if cid:
                            substrates.append({"id": cid, "stoich": stoich})

                for products_list in rxn_elem.findall(_tag("listOfProducts")):
                    for sr in products_list.findall(_tag("speciesReference")):
                        sp_ref = sr.attrib.get("species", "")
                        stoich = float(sr.attrib.get("stoichiometry", "1"))
                        cid = species_id_map.get(sp_ref)
                        if cid:
                            products.append({"id": cid, "stoich": stoich})

                stoich_blob = json.dumps(
                    {
                        "substrates": substrates,
                        "products": products,
                        "direction": "reversible" if reversible else "forward",
                    }
                )

                if rxn_nid not in nodes:
                    nodes[rxn_nid] = MetaNode(
                        id=rxn_nid,
                        kind=KIND_REACTION,
                        name=rxn_name,
                        description=f"SBML reaction: {rxn_name}"
                        + (" (reversible)" if reversible else ""),
                        stoichiometry=stoich_blob,
                        xrefs=json.dumps(xrefs) if xrefs else None,
                        source_format="sbml",
                        source_file=str(path),
                    )

                edges.append(MetaEdge(src=pwy_id, rel=REL_CONTAINS, dst=rxn_nid))

                for s in substrates:
                    edges.append(
                        MetaEdge(
                            src=s["id"],
                            rel=REL_SUBSTRATE_OF,
                            dst=rxn_nid,
                            evidence=json.dumps({"stoich": s["stoich"]}),
                        )
                    )
                for p in products:
                    edges.append(
                        MetaEdge(
                            src=rxn_nid,
                            rel=REL_PRODUCT_OF,
                            dst=p["id"],
                            evidence=json.dumps({"stoich": p["stoich"]}),
                        )
                    )

                # Modifiers (enzymes/inhibitors/activators)
                for mods_list in rxn_elem.findall(_tag("listOfModifiers")):
                    for mod in mods_list.findall(_tag("modifierSpeciesReference")):
                        mod_sp = mod.attrib.get("species", "")
                        sbo = mod.attrib.get("sboTerm", "")
                        mod_cid = species_id_map.get(mod_sp)
                        if not mod_cid:
                            continue
                        if _SBO_INHIBITOR.match(sbo):
                            rel = REL_INHIBITS
                        elif _SBO_ACTIVATOR.match(sbo):
                            rel = REL_ACTIVATES
                        else:
                            rel = REL_CATALYZES
                        # Modifier could be enzyme or compound — promote to enzyme kind
                        if (
                            mod_cid in nodes
                            and nodes[mod_cid].kind == KIND_COMPOUND
                            and rel == REL_CATALYZES
                        ):
                            old = nodes[mod_cid]
                            nodes[mod_cid] = MetaNode(
                                id=old.id,
                                kind=KIND_ENZYME,
                                name=old.name,
                                description=old.description,
                                xrefs=old.xrefs,
                                source_format=old.source_format,
                                source_file=old.source_file,
                            )
                        edges.append(
                            MetaEdge(
                                src=mod_cid,
                                rel=rel,
                                dst=rxn_nid,
                                evidence=json.dumps({"sbo": sbo}) if sbo else None,
                            )
                        )

        return list(nodes.values()), edges
