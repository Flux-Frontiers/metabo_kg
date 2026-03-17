"""
kgml.py — KEGG KGML (XML) pathway parser.

KGML is the native XML format exported by the KEGG PATHWAY database.
Each file describes one pathway map with:
  - <entry> elements: compounds (type="compound"), genes/enzymes (type="gene",
    "ortholog"), and other entities (type="map", "group").
  - <reaction> elements: biochemical reactions with <substrate> and <product>
    child elements.
  - <relation> elements: protein interactions (not parsed here).

Reference: https://www.genome.jp/kegg/xml/docs/

KGML detection heuristic: the root element tag is ``{...}pathway`` or
``pathway`` (no namespace), which distinguishes it from SBML's ``<sbml>`` root.

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

from metakg.parsers.base import PathwayParser
from metakg.primitives import (
    KIND_COMPOUND,
    KIND_ENZYME,
    KIND_PATHWAY,
    KIND_REACTION,
    REL_CATALYZES,
    REL_CONTAINS,
    REL_PRODUCT_OF,
    REL_SUBSTRATE_OF,
    MetaEdge,
    MetaNode,
    _kegg_pathway_category,
    node_id,
    synthetic_id,
)


class KGMLParser(PathwayParser):
    """
    Parser for KEGG KGML (XML) pathway files.

    Handles ``.xml`` and ``.kgml`` files whose root element is ``<pathway>``.
    Uses only stdlib ``xml.etree.ElementTree`` — no additional dependencies.
    """

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".xml", ".kgml")

    def can_handle(self, path: Path) -> bool:
        if path.suffix.lower() not in self.supported_extensions:
            return False
        try:
            for _evt, elem in ET.iterparse(path, events=("start",)):
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                return tag == "pathway"
        except ET.ParseError:
            return False
        return False

    def parse(self, path: Path) -> tuple[list[MetaNode], list[MetaEdge]]:
        """
        Parse a KGML file into MetaNode and MetaEdge objects.

        :param path: Path to the ``.kgml`` or ``.xml`` file.
        :return: ``(nodes, edges)`` tuple.
        :raises ValueError: If the file is not valid KGML.
        """
        try:
            tree = ET.parse(path)
        except ET.ParseError as exc:
            raise ValueError(f"Invalid XML in {path}: {exc}") from exc

        root = tree.getroot()
        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
        if tag != "pathway":
            raise ValueError(f"Root element is <{tag}>, expected <pathway>")

        nodes: dict[str, MetaNode] = {}
        edges: list[MetaEdge] = []

        pathway_kegg_id = root.attrib.get("name", "").replace("path:", "").strip()
        pathway_title = root.attrib.get("title", pathway_kegg_id)
        org = root.attrib.get("org", "")

        # Pathway container node
        pwy_id = (
            node_id(KIND_PATHWAY, "kegg", pathway_kegg_id)
            if pathway_kegg_id
            else synthetic_id(KIND_PATHWAY, pathway_title)
        )
        pwy_node = MetaNode(
            id=pwy_id,
            kind=KIND_PATHWAY,
            name=pathway_title,
            description=f"KEGG pathway {pathway_kegg_id} ({org}): {pathway_title}",
            xrefs=json.dumps({"kegg": pathway_kegg_id}) if pathway_kegg_id else None,
            source_format="kgml",
            source_file=str(path),
            category=_kegg_pathway_category(pathway_kegg_id),
        )
        nodes[pwy_id] = pwy_node

        # Map KGML entry id (integer) → MetaNode id for reaction wiring
        entry_map: dict[str, str] = {}

        # Strategy C: gene/ortholog reaction= attr → enzyme MetaNode id
        # (KEGG reaction accession like "R00200" → canonical enzyme node id)
        reaction_attr_map: dict[str, str] = {}

        # --- Entries ---
        for entry in root.findall("entry"):
            etype = entry.attrib.get("type", "")
            enames = entry.attrib.get("name", "")
            entry_id = entry.attrib.get("id", "")

            if etype == "compound":
                for raw_name in enames.split():
                    kegg_cid = raw_name.replace("cpd:", "").strip()
                    nid = node_id(KIND_COMPOUND, "kegg", kegg_cid)
                    if nid not in nodes:
                        graphics = entry.find("graphics")
                        label = (
                            graphics.attrib.get("name", kegg_cid)
                            if graphics is not None
                            else kegg_cid
                        )
                        nodes[nid] = MetaNode(
                            id=nid,
                            kind=KIND_COMPOUND,
                            name=label,
                            description=f"KEGG compound {kegg_cid}",
                            xrefs=json.dumps({"kegg": kegg_cid}),
                            source_format="kgml",
                            source_file=str(path),
                        )
                    entry_map[entry_id] = nid
                    # One entry typically has one compound; use last if multiple
            elif etype in ("gene", "ortholog"):
                # Collect all gene IDs in this entry.  A single KGML entry
                # often bundles multiple genes that KEGG treats as a functional
                # group (true isozymes or complex subunits for that pathway
                # step).  We represent the group as ONE enzyme node keyed on
                # the first (canonical) gene, with all members stored in xrefs.
                # This avoids creating orphaned enzyme nodes for non-canonical
                # genes that would never receive a CATALYZES edge.
                gene_ids = [
                    raw.replace("hsa:", "").replace("ko:", "").strip() for raw in enames.split()
                ]
                if not gene_ids:
                    continue

                canonical = gene_ids[0]
                nid = node_id(KIND_ENZYME, "kegg", canonical)

                graphics = entry.find("graphics")
                label = (
                    graphics.attrib.get("name", canonical) if graphics is not None else canonical
                )

                if nid not in nodes:
                    xrefs_val: str | list[str] = gene_ids if len(gene_ids) > 1 else gene_ids[0]
                    nodes[nid] = MetaNode(
                        id=nid,
                        kind=KIND_ENZYME,
                        name=label,
                        description=f"KEGG gene/enzyme group: {label}",
                        xrefs=json.dumps({"kegg": xrefs_val}),
                        source_format="kgml",
                        source_file=str(path),
                    )

                entry_map[entry_id] = nid

                # Strategy C: record reaction= attribute for fallback wiring
                reaction_attr = entry.attrib.get("reaction", "")
                for tok in reaction_attr.split():
                    kegg_rxn = tok.replace("rn:", "").strip()
                    if kegg_rxn:
                        # First match wins; genes preferred over orthologs
                        # (entry processing visits gene entries before orthologs
                        # for the same reaction in well-formed KGML files)
                        reaction_attr_map.setdefault(kegg_rxn, nid)

        # --- Reactions ---
        for rxn_elem in root.findall("reaction"):
            rxn_kegg_id = rxn_elem.attrib.get("name", "").replace("rn:", "").strip()
            rxn_type = rxn_elem.attrib.get("type", "irreversible")  # reversible|irreversible

            substrates: list[dict] = []
            products: list[dict] = []

            for sub in rxn_elem.findall("substrate"):
                sub_name = sub.attrib.get("name", "").replace("cpd:", "").strip()
                substrates.append({"id": node_id(KIND_COMPOUND, "kegg", sub_name), "stoich": 1.0})

            for prod in rxn_elem.findall("product"):
                prod_name = prod.attrib.get("name", "").replace("cpd:", "").strip()
                products.append({"id": node_id(KIND_COMPOUND, "kegg", prod_name), "stoich": 1.0})

            stoich_blob = json.dumps(
                {"substrates": substrates, "products": products, "direction": rxn_type}
            )
            rxn_id = (
                node_id(KIND_REACTION, "kegg", rxn_kegg_id)
                if rxn_kegg_id
                else synthetic_id(KIND_REACTION, rxn_elem.attrib.get("id", ""))
            )
            rxn_name = rxn_kegg_id or rxn_elem.attrib.get("id", "unknown")

            if rxn_id not in nodes:
                nodes[rxn_id] = MetaNode(
                    id=rxn_id,
                    kind=KIND_REACTION,
                    name=rxn_name,
                    description=f"KEGG reaction {rxn_kegg_id} ({rxn_type})",
                    stoichiometry=stoich_blob,
                    xrefs=json.dumps({"kegg": rxn_kegg_id}) if rxn_kegg_id else None,
                    source_format="kgml",
                    source_file=str(path),
                )

            # Pathway CONTAINS reaction
            edges.append(MetaEdge(src=pwy_id, rel=REL_CONTAINS, dst=rxn_id))

            # Substrate edges
            for s in substrates:
                cid = s["id"]
                # Ensure compound node exists (may not be in entries if only in reaction)
                if cid not in nodes:
                    kegg_cid = cid.split(":")[-1]
                    nodes[cid] = MetaNode(
                        id=cid,
                        kind=KIND_COMPOUND,
                        name=kegg_cid,
                        description=f"KEGG compound {kegg_cid}",
                        xrefs=json.dumps({"kegg": kegg_cid}),
                        source_format="kgml",
                        source_file=str(path),
                    )
                edges.append(
                    MetaEdge(
                        src=cid,
                        rel=REL_SUBSTRATE_OF,
                        dst=rxn_id,
                        evidence=json.dumps({"stoich": s["stoich"]}),
                    )
                )

            # Product edges
            for p in products:
                cid = p["id"]
                if cid not in nodes:
                    kegg_cid = cid.split(":")[-1]
                    nodes[cid] = MetaNode(
                        id=cid,
                        kind=KIND_COMPOUND,
                        name=kegg_cid,
                        description=f"KEGG compound {kegg_cid}",
                        xrefs=json.dumps({"kegg": kegg_cid}),
                        source_format="kgml",
                        source_file=str(path),
                    )
                edges.append(
                    MetaEdge(
                        src=rxn_id,
                        rel=REL_PRODUCT_OF,
                        dst=cid,
                        evidence=json.dumps({"stoich": p["stoich"]}),
                    )
                )

        # --- Wire enzymes to reactions ---
        # Strategy A: MetaKG extension — <reaction ... enzyme="N"> references
        #   the id of a gene entry that catalyses this reaction.
        # Strategy B: Real KEGG convention — the reaction element's own "id"
        #   matches the gene entry "id" (one gene entry per reaction).
        # Strategy C: gene/ortholog entry carries a reaction="rn:RXXXXX"
        #   attribute that directly names the reaction it catalyses.
        #   This is the standard KEGG way to express catalysis and serves as
        #   the fallback when A and B both fail (e.g. when the reaction
        #   element id differs from the gene entry id).
        for rxn_elem in root.findall("reaction"):
            rxn_kegg_id = rxn_elem.attrib.get("name", "").replace("rn:", "").strip()
            rxn_nid = (
                node_id(KIND_REACTION, "kegg", rxn_kegg_id)
                if rxn_kegg_id
                else synthetic_id(KIND_REACTION, rxn_elem.attrib.get("id", ""))
            )
            if rxn_nid not in nodes:
                continue

            # Strategies A and B: entry_map-based lookup
            wired = False
            candidate_ids: list[str] = []
            enz_attr = rxn_elem.attrib.get("enzyme", "")
            if enz_attr:
                candidate_ids.append(enz_attr)
            rxn_id_attr = rxn_elem.attrib.get("id", "")
            if rxn_id_attr and rxn_id_attr not in candidate_ids:
                candidate_ids.append(rxn_id_attr)

            for cand in candidate_ids:
                if cand not in entry_map:
                    continue
                enz_nid = entry_map[cand]
                if enz_nid in nodes and nodes[enz_nid].kind == KIND_ENZYME:
                    edges.append(MetaEdge(src=enz_nid, rel=REL_CATALYZES, dst=rxn_nid))
                    wired = True
                    break  # one enzyme entry per reaction is enough

            # Strategy C: fall back to reaction= attribute map
            if not wired and rxn_kegg_id:
                enz_nid_c = reaction_attr_map.get(rxn_kegg_id)
                if (
                    enz_nid_c is not None
                    and enz_nid_c in nodes
                    and nodes[enz_nid_c].kind == KIND_ENZYME
                ):
                    edges.append(MetaEdge(src=enz_nid_c, rel=REL_CATALYZES, dst=rxn_nid))

        # --- Attach unreacted entry nodes to their pathway via CONTAINS ---
        # Gene/ortholog entries that were never linked to a reaction, and
        # compound entries not referenced as any substrate/product, would
        # otherwise become isolated nodes with zero edges.  Connecting them
        # to their source pathway via CONTAINS keeps them reachable and avoids
        # spurious "isolated node" counts in analysis reports.
        # (Also fixes isolated *pathway* nodes whose files have no reactions.)
        #
        # Note: compound entries may list multiple cpd: names (entry_map only
        # stores the last one); iterate the raw name attribute to catch all.
        wired_enz: set[str] = {e.src for e in edges if e.rel == REL_CATALYZES}
        wired_cpd: set[str] = {
            nid
            for e in edges
            for nid in (e.src, e.dst)
            if e.rel in (REL_SUBSTRATE_OF, REL_PRODUCT_OF)
        }
        pwy_contains: set[str] = {e.dst for e in edges if e.src == pwy_id and e.rel == REL_CONTAINS}
        for entry in root.findall("entry"):
            etype = entry.attrib.get("type", "")
            eid = entry.attrib.get("id", "")
            if etype == "compound":
                # Handle all compound IDs in this entry (not just the last one)
                for raw_name in entry.attrib.get("name", "").split():
                    cid = node_id(KIND_COMPOUND, "kegg", raw_name.replace("cpd:", "").strip())
                    if cid in nodes and cid not in pwy_contains and cid not in wired_cpd:
                        edges.append(MetaEdge(src=pwy_id, rel=REL_CONTAINS, dst=cid))
                        pwy_contains.add(cid)
                        wired_cpd.add(cid)
            elif etype in ("gene", "ortholog"):
                if eid not in entry_map:
                    continue
                nid = entry_map[eid]
                if nid in nodes and nid not in pwy_contains and nid not in wired_enz:
                    edges.append(MetaEdge(src=pwy_id, rel=REL_CONTAINS, dst=nid))
                    pwy_contains.add(nid)
                    wired_enz.add(nid)

        return list(nodes.values()), edges
