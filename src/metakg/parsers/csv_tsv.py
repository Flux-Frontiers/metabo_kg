"""
csv_tsv.py — Tabular reaction table (CSV/TSV) parser.

Expects a flat table where each row describes one reaction participant
or a full reaction. Column names are configurable via ``CSVParserConfig``.

Default expected columns::

    reaction_id, reaction_name, substrate, product, enzyme,
    stoich_substrate, stoich_product, pathway, ec_number,
    substrate_formula, enzyme_uniprot

All columns except ``substrate`` and ``product`` are optional.

Rows with the same ``reaction_id`` are merged into a single reaction node.

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

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
    node_id,
    synthetic_id,
)


@dataclass
class CSVParserConfig:
    """
    Column-name mapping configuration for :class:`CSVParser`.

    Override field names to match your CSV/TSV schema.

    :param reaction_id: Column for the reaction identifier.
    :param reaction_name: Column for a human-readable reaction name.
    :param substrate: Column for substrate compound name or ID.
    :param product: Column for product compound name or ID.
    :param enzyme: Column for enzyme name or gene symbol.
    :param stoich_substrate: Column for substrate stoichiometric coefficient.
    :param stoich_product: Column for product stoichiometric coefficient.
    :param pathway: Column for pathway name.
    :param ec_number: Column for enzyme EC number.
    :param substrate_formula: Column for substrate molecular formula.
    :param enzyme_uniprot: Column for enzyme UniProt accession.
    :param delimiter: Field delimiter (``','`` for CSV, ``'\t'`` for TSV).
    :param db_namespace: Namespace prefix used when building node IDs
        (e.g. ``"custom"`` produces ``cpd:custom:<name>``).
    """

    reaction_id: str = "reaction_id"
    reaction_name: str = "reaction_name"
    substrate: str = "substrate"
    product: str = "product"
    enzyme: str = "enzyme"
    stoich_substrate: str = "stoich_substrate"
    stoich_product: str = "stoich_product"
    pathway: str = "pathway"
    ec_number: str = "ec_number"
    substrate_formula: str = "substrate_formula"
    enzyme_uniprot: str = "enzyme_uniprot"
    delimiter: str = ","
    db_namespace: str = "csv"


class CSVParser(PathwayParser):
    """
    Parser for flat CSV/TSV reaction tables.

    Uses only stdlib ``csv``.  One row per reaction participant;
    rows sharing the same ``reaction_id`` are merged.

    :param config: :class:`CSVParserConfig` instance controlling column mapping.
    """

    def __init__(self, config: CSVParserConfig | None = None) -> None:
        """
        Initialise the CSV parser.

        :param config: Column-mapping configuration. Defaults to :class:`CSVParserConfig`
            with standard column names and comma delimiter.
        """
        self.config = config or CSVParserConfig()

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv", ".tsv", ".txt")

    def parse(self, path: Path) -> tuple[list[MetaNode], list[MetaEdge]]:
        """
        Parse a tabular reaction file.

        :param path: Path to the CSV/TSV file.
        :return: ``(nodes, edges)`` tuple.
        :raises ValueError: If the file is missing required columns.
        """
        cfg = self.config
        delim = "\t" if path.suffix.lower() == ".tsv" else cfg.delimiter

        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh, delimiter=delim)
            rows = list(reader)

        if not rows:
            return [], []

        fieldnames = set(rows[0].keys())
        required = {cfg.substrate, cfg.product}
        missing = required - fieldnames
        if missing:
            raise ValueError(
                f"CSV {path} is missing required columns: {missing}. Available: {fieldnames}"
            )

        nodes: dict[str, MetaNode] = {}
        edges: list[MetaEdge] = []
        # Accumulate per-reaction data for stoichiometry blob
        rxn_substrates: dict[str, list[dict]] = {}
        rxn_products: dict[str, list[dict]] = {}

        def _get(row: dict, col: str) -> str:
            return row.get(col, "").strip()

        # Pathway node (optional, created lazily)
        pathway_nodes: dict[str, str] = {}

        def _ensure_pathway(pwy_name: str) -> str:
            if pwy_name not in pathway_nodes:
                pwy_nid = synthetic_id(KIND_PATHWAY, pwy_name)
                pathway_nodes[pwy_name] = pwy_nid
                if pwy_nid not in nodes:
                    nodes[pwy_nid] = MetaNode(
                        id=pwy_nid,
                        kind=KIND_PATHWAY,
                        name=pwy_name,
                        description=f"Pathway: {pwy_name}",
                        source_format="csv",
                        source_file=str(path),
                    )
            return pathway_nodes[pwy_name]

        for row in rows:
            sub_name = _get(row, cfg.substrate)
            prod_name = _get(row, cfg.product)
            rxn_raw_id = _get(row, cfg.reaction_id) or synthetic_id(
                KIND_REACTION, f"{sub_name}->{prod_name}"
            )
            rxn_name = _get(row, cfg.reaction_name) or rxn_raw_id
            enzyme_name = _get(row, cfg.enzyme)
            ec = _get(row, cfg.ec_number)
            stoich_sub = float(_get(row, cfg.stoich_substrate) or "1")
            stoich_prod = float(_get(row, cfg.stoich_product) or "1")
            pwy_name = _get(row, cfg.pathway)
            sub_formula = _get(row, cfg.substrate_formula)
            enz_uniprot = _get(row, cfg.enzyme_uniprot)

            # Reaction node ID
            rxn_nid = synthetic_id(KIND_REACTION, rxn_raw_id)

            # --- Substrate compound ---
            sub_nid = synthetic_id(KIND_COMPOUND, sub_name)
            if sub_nid not in nodes:
                nodes[sub_nid] = MetaNode(
                    id=sub_nid,
                    kind=KIND_COMPOUND,
                    name=sub_name,
                    description=f"Compound: {sub_name}",
                    formula=sub_formula or None,
                    source_format="csv",
                    source_file=str(path),
                )

            # --- Product compound ---
            prod_nid = synthetic_id(KIND_COMPOUND, prod_name)
            if prod_nid not in nodes:
                nodes[prod_nid] = MetaNode(
                    id=prod_nid,
                    kind=KIND_COMPOUND,
                    name=prod_name,
                    description=f"Compound: {prod_name}",
                    source_format="csv",
                    source_file=str(path),
                )

            # Accumulate stoichiometry
            rxn_substrates.setdefault(rxn_nid, [])
            rxn_products.setdefault(rxn_nid, [])
            if not any(s["id"] == sub_nid for s in rxn_substrates[rxn_nid]):
                rxn_substrates[rxn_nid].append({"id": sub_nid, "stoich": stoich_sub})
            if not any(p["id"] == prod_nid for p in rxn_products[rxn_nid]):
                rxn_products[rxn_nid].append({"id": prod_nid, "stoich": stoich_prod})

            # --- Reaction node ---
            if rxn_nid not in nodes:
                nodes[rxn_nid] = MetaNode(
                    id=rxn_nid,
                    kind=KIND_REACTION,
                    name=rxn_name,
                    description=f"Reaction: {rxn_name}",
                    source_format="csv",
                    source_file=str(path),
                )

            # Edges: substrate → reaction, reaction → product
            edges.append(
                MetaEdge(
                    src=sub_nid,
                    rel=REL_SUBSTRATE_OF,
                    dst=rxn_nid,
                    evidence=json.dumps({"stoich": stoich_sub}),
                )
            )
            edges.append(
                MetaEdge(
                    src=rxn_nid,
                    rel=REL_PRODUCT_OF,
                    dst=prod_nid,
                    evidence=json.dumps({"stoich": stoich_prod}),
                )
            )

            # --- Enzyme ---
            if enzyme_name:
                if enz_uniprot:
                    enz_nid = node_id(KIND_ENZYME, "uniprot", enz_uniprot)
                else:
                    enz_nid = synthetic_id(KIND_ENZYME, enzyme_name)
                if enz_nid not in nodes:
                    xrefs = {}
                    if enz_uniprot:
                        xrefs["uniprot"] = enz_uniprot
                    nodes[enz_nid] = MetaNode(
                        id=enz_nid,
                        kind=KIND_ENZYME,
                        name=enzyme_name,
                        description=f"Enzyme: {enzyme_name}" + (f" (EC {ec})" if ec else ""),
                        ec_number=ec or None,
                        xrefs=json.dumps(xrefs) if xrefs else None,
                        source_format="csv",
                        source_file=str(path),
                    )
                edges.append(
                    MetaEdge(
                        src=enz_nid,
                        rel=REL_CATALYZES,
                        dst=rxn_nid,
                        evidence=json.dumps({"ec": ec}) if ec else None,
                    )
                )

            # --- Pathway ---
            if pwy_name:
                pwy_nid = _ensure_pathway(pwy_name)
                # Avoid duplicate CONTAINS edges
                contains_edge = MetaEdge(src=pwy_nid, rel=REL_CONTAINS, dst=rxn_nid)
                if contains_edge not in edges:
                    edges.append(contains_edge)

        # Back-fill stoichiometry blobs onto reaction nodes
        for rxn_nid, node in nodes.items():
            if node.kind == KIND_REACTION and node.stoichiometry is None:
                stoich_blob = json.dumps(
                    {
                        "substrates": rxn_substrates.get(rxn_nid, []),
                        "products": rxn_products.get(rxn_nid, []),
                    }
                )
                nodes[rxn_nid] = MetaNode(
                    id=node.id,
                    kind=node.kind,
                    name=node.name,
                    description=node.description,
                    stoichiometry=stoich_blob,
                    xrefs=node.xrefs,
                    source_format=node.source_format,
                    source_file=node.source_file,
                )

        return list(nodes.values()), edges
