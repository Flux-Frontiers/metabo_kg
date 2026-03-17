"""
biopax.py — BioPAX Level 3 (RDF/OWL) pathway parser.

BioPAX (Biological Pathway Exchange) Level 3 encodes pathways as RDF/OWL.
This parser uses ``rdflib`` to load the graph and extract:

  - ``SmallMolecule``  → compound nodes
  - ``Protein``        → enzyme nodes
  - ``BiochemicalReaction`` → reaction nodes
  - ``Pathway``        → pathway container nodes
  - ``left/right`` properties → SUBSTRATE_OF / PRODUCT_OF edges
  - ``controller``     → CATALYZES / INHIBITS / ACTIVATES edges
  - ``memberPathwayComponent`` → CONTAINS edges

Reference: https://www.biopax.org/release/biopax-level3-documentation.pdf

Requires: ``rdflib`` (``pip install rdflib``).
If rdflib is not installed, ``BioPAXParser.parse()`` raises ``ImportError``
with an install hint.

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28
"""

from __future__ import annotations

import json
from pathlib import Path

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

# Lazy import: rdflib is optional
_rdflib_available = False
try:
    import rdflib
    from rdflib import RDF, URIRef

    _rdflib_available = True
except ImportError:
    pass

# BioPAX Level 3 namespace
_BP = "http://www.biopax.org/release/biopax-level3.owl#"


def _uri(local: str) -> URIRef:
    return URIRef(_BP + local)


class BioPAXParser(PathwayParser):
    """
    Parser for BioPAX Level 3 RDF/OWL files.

    Requires ``rdflib``. Install with::

        pip install rdflib
        # or: poetry add rdflib --optional

    Handles ``.owl`` and ``.rdf`` files.
    """

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".owl", ".rdf")

    def parse(self, path: Path) -> tuple[list[MetaNode], list[MetaEdge]]:
        """
        Parse a BioPAX Level 3 OWL/RDF file.

        :param path: Path to the ``.owl`` or ``.rdf`` file.
        :return: ``(nodes, edges)`` tuple.
        :raises ImportError: If ``rdflib`` is not installed.
        :raises ValueError: If the file is not parseable as RDF.
        """
        if not _rdflib_available:
            raise ImportError(
                "rdflib is required for BioPAX parsing. Install it with: pip install rdflib"
            )

        g = rdflib.Graph()
        try:
            g.parse(str(path))
        except Exception as exc:
            raise ValueError(f"Failed to parse RDF in {path}: {exc}") from exc

        nodes: dict[str, MetaNode] = {}
        edges: list[MetaEdge] = []

        def _str(ref) -> str:
            return str(ref) if ref is not None else ""

        def _local(uri_str: str) -> str:
            """Extract local name from a URI."""
            if "#" in uri_str:
                return uri_str.split("#")[-1]
            return uri_str.split("/")[-1]

        def _get_literal(subject, predicate) -> str:
            val = g.value(subject, predicate)
            return str(val) if val else ""

        bp_name = _uri("displayName")
        bp_std_name = _uri("standardName")
        bp_comment = _uri("comment")
        bp_left = _uri("left")
        bp_right = _uri("right")
        bp_xref = _uri("xref")
        bp_db = _uri("db")
        bp_id = _uri("id")
        bp_ec_number = _uri("eCNumber")
        bp_formula = _uri("chemicalFormula")
        bp_charge = _uri("charge")
        bp_controller = _uri("controller")
        bp_controlled = _uri("controlled")
        bp_control_type = _uri("controlType")
        bp_member = _uri("memberPathwayComponent")

        def _xrefs(subject) -> dict[str, str]:
            result: dict[str, str] = {}
            for xref_uri in g.objects(subject, bp_xref):
                db_val = _get_literal(xref_uri, bp_db).lower()
                id_val = _get_literal(xref_uri, bp_id)
                if db_val and id_val:
                    result[db_val] = id_val
            return result

        def _name(subject) -> str:
            n = _get_literal(subject, bp_name) or _get_literal(subject, bp_std_name)
            return n or _local(_str(subject))

        def _desc(subject) -> str:
            return _get_literal(subject, bp_comment)

        def _make_meta_id(kind: str, uri_ref, xrefs_dict: dict[str, str]) -> str:
            for db in ("chebi", "uniprot", "kegg", "kegg.compound", "kegg.reaction"):
                if db in xrefs_dict:
                    clean_db = db.replace(".", "_")
                    return node_id(kind, clean_db, xrefs_dict[db])
            return synthetic_id(kind, _local(_str(uri_ref)))

        # --- SmallMolecule → compound ---
        for subj in g.subjects(RDF.type, _uri("SmallMolecule")):
            xr = _xrefs(subj)
            nid = _make_meta_id(KIND_COMPOUND, subj, xr)
            name = _name(subj)
            formula = _get_literal(subj, bp_formula)
            charge_s = _get_literal(subj, bp_charge)
            charge = int(charge_s) if charge_s.lstrip("-").isdigit() else None
            if nid not in nodes:
                nodes[nid] = MetaNode(
                    id=nid,
                    kind=KIND_COMPOUND,
                    name=name,
                    description=_desc(subj) or f"BioPAX compound: {name}",
                    formula=formula or None,
                    charge=charge,
                    xrefs=json.dumps(xr) if xr else None,
                    source_format="biopax",
                    source_file=str(path),
                )

        # --- Protein → enzyme ---
        for subj in g.subjects(RDF.type, _uri("Protein")):
            xr = _xrefs(subj)
            nid = _make_meta_id(KIND_ENZYME, subj, xr)
            name = _name(subj)
            ec = _get_literal(subj, bp_ec_number)
            if nid not in nodes:
                nodes[nid] = MetaNode(
                    id=nid,
                    kind=KIND_ENZYME,
                    name=name,
                    description=_desc(subj) or f"BioPAX protein: {name}",
                    ec_number=ec or None,
                    xrefs=json.dumps(xr) if xr else None,
                    source_format="biopax",
                    source_file=str(path),
                )

        # --- Pathway ---
        pathway_nodes: dict[str, str] = {}  # URI str → MetaNode id
        for subj in g.subjects(RDF.type, _uri("Pathway")):
            xr = _xrefs(subj)
            nid = _make_meta_id(KIND_PATHWAY, subj, xr)
            name = _name(subj)
            pathway_nodes[_str(subj)] = nid
            if nid not in nodes:
                nodes[nid] = MetaNode(
                    id=nid,
                    kind=KIND_PATHWAY,
                    name=name,
                    description=_desc(subj) or f"BioPAX pathway: {name}",
                    xrefs=json.dumps(xr) if xr else None,
                    source_format="biopax",
                    source_file=str(path),
                )

        # --- BiochemicalReaction ---
        rxn_map: dict[str, str] = {}  # URI str → MetaNode id
        for subj in g.subjects(RDF.type, _uri("BiochemicalReaction")):
            xr = _xrefs(subj)
            nid = _make_meta_id(KIND_REACTION, subj, xr)
            name = _name(subj)
            rxn_map[_str(subj)] = nid

            substrates: list[dict] = []
            products: list[dict] = []

            for left in g.objects(subj, bp_left):
                left_xr = _xrefs(left)
                left_nid = _make_meta_id(KIND_COMPOUND, left, left_xr)
                substrates.append({"id": left_nid, "stoich": 1.0})

            for right in g.objects(subj, bp_right):
                right_xr = _xrefs(right)
                right_nid = _make_meta_id(KIND_COMPOUND, right, right_xr)
                products.append({"id": right_nid, "stoich": 1.0})

            stoich_blob = json.dumps({"substrates": substrates, "products": products})
            if nid not in nodes:
                nodes[nid] = MetaNode(
                    id=nid,
                    kind=KIND_REACTION,
                    name=name,
                    description=_desc(subj) or f"BioPAX reaction: {name}",
                    stoichiometry=stoich_blob,
                    xrefs=json.dumps(xr) if xr else None,
                    source_format="biopax",
                    source_file=str(path),
                )

            for s in substrates:
                edges.append(
                    MetaEdge(
                        src=s["id"],
                        rel=REL_SUBSTRATE_OF,
                        dst=nid,
                        evidence=json.dumps({"stoich": s["stoich"]}),
                    )
                )
            for p in products:
                edges.append(
                    MetaEdge(
                        src=nid,
                        rel=REL_PRODUCT_OF,
                        dst=p["id"],
                        evidence=json.dumps({"stoich": p["stoich"]}),
                    )
                )

        # --- Control → CATALYZES / INHIBITS / ACTIVATES ---
        for subj in g.subjects(RDF.type, _uri("Catalysis")):
            ctrl_type = _get_literal(subj, bp_control_type).upper()
            for controller in g.objects(subj, bp_controller):
                ctrl_xr = _xrefs(controller)
                ctrl_nid = _make_meta_id(KIND_ENZYME, controller, ctrl_xr)
                for controlled in g.objects(subj, bp_controlled):
                    rxn_nid = rxn_map.get(_str(controlled))
                    if rxn_nid:
                        if "INHIBIT" in ctrl_type:
                            rel = REL_INHIBITS
                        elif "ACTIVAT" in ctrl_type:
                            rel = REL_ACTIVATES
                        else:
                            rel = REL_CATALYZES
                        edges.append(MetaEdge(src=ctrl_nid, rel=rel, dst=rxn_nid))

        # --- Pathway CONTAINS reactions ---
        for pwy_uri, pwy_nid in pathway_nodes.items():
            for member in g.objects(URIRef(pwy_uri), bp_member):
                rxn_nid = rxn_map.get(_str(member))
                if rxn_nid:
                    edges.append(MetaEdge(src=pwy_nid, rel=REL_CONTAINS, dst=rxn_nid))

        return list(nodes.values()), edges
