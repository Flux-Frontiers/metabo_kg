"""
Tests for code_kg.metakg.store — MetaStore SQLite persistence layer.
"""

import json
import sqlite3

import pytest

from metakg.primitives import (
    KIND_COMPOUND,
    KIND_ENZYME,
    KIND_PATHWAY,
    KIND_REACTION,
    PATHWAY_CATEGORY_DISEASE,
    PATHWAY_CATEGORY_METABOLIC,
    MetaEdge,
    MetaNode,
    node_id,
)
from metakg.store import MetaStore


@pytest.fixture()
def store(tmp_path):
    s = MetaStore(tmp_path / "test.sqlite")
    yield s
    s.close()


def _make_nodes():
    glucose = MetaNode(
        id=node_id(KIND_COMPOUND, "kegg", "C00031"),
        kind=KIND_COMPOUND,
        name="D-Glucose",
        description="Hexose sugar",
        formula="C6H12O6",
        xrefs='{"kegg": "C00031", "chebi": "CHEBI_4167"}',
        source_format="csv",
    )
    pyruvate = MetaNode(
        id=node_id(KIND_COMPOUND, "kegg", "C00022"),
        kind=KIND_COMPOUND,
        name="Pyruvate",
        description="End product of glycolysis",
        formula="C3H4O3",
        xrefs='{"kegg": "C00022"}',
        source_format="csv",
    )
    rxn = MetaNode(
        id=node_id(KIND_REACTION, "kegg", "R00200"),
        kind=KIND_REACTION,
        name="Glycolysis reaction",
        stoichiometry=json.dumps(
            {
                "substrates": [{"id": node_id(KIND_COMPOUND, "kegg", "C00031"), "stoich": 1.0}],
                "products": [{"id": node_id(KIND_COMPOUND, "kegg", "C00022"), "stoich": 2.0}],
            }
        ),
        xrefs='{"kegg": "R00200"}',
        source_format="csv",
    )
    pwy = MetaNode(
        id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        kind=KIND_PATHWAY,
        name="Glycolysis / Gluconeogenesis",
        source_format="csv",
    )
    enz = MetaNode(
        id=node_id(KIND_ENZYME, "ec", "2.7.1.1"),
        kind=KIND_ENZYME,
        name="Hexokinase",
        ec_number="2.7.1.1",
        xrefs='{"ec": "2.7.1.1"}',
        source_format="csv",
    )
    return [glucose, pyruvate, rxn, pwy, enz]


def _make_edges():
    glucose_id = node_id(KIND_COMPOUND, "kegg", "C00031")
    pyruvate_id = node_id(KIND_COMPOUND, "kegg", "C00022")
    rxn_id = node_id(KIND_REACTION, "kegg", "R00200")
    pwy_id = node_id(KIND_PATHWAY, "kegg", "hsa00010")
    enz_id = node_id(KIND_ENZYME, "ec", "2.7.1.1")
    return [
        MetaEdge(src=glucose_id, rel="SUBSTRATE_OF", dst=rxn_id, evidence='{"stoich": 1.0}'),
        MetaEdge(src=rxn_id, rel="PRODUCT_OF", dst=pyruvate_id, evidence='{"stoich": 2.0}'),
        MetaEdge(src=enz_id, rel="CATALYZES", dst=rxn_id),
        MetaEdge(src=pwy_id, rel="CONTAINS", dst=rxn_id),
    ]


class TestMetaStoreBasic:
    def test_write_and_read_node(self, store):
        nodes = _make_nodes()
        store.write(nodes, [])
        n = store.node(node_id(KIND_COMPOUND, "kegg", "C00031"))
        assert n is not None
        assert n["name"] == "D-Glucose"
        assert n["formula"] == "C6H12O6"

    def test_stats_after_write(self, store):
        store.write(_make_nodes(), _make_edges())
        s = store.stats()
        assert s["total_nodes"] == 5
        assert s["total_edges"] == 4
        assert s["node_counts"]["compound"] == 2
        assert s["node_counts"]["reaction"] == 1

    def test_wipe_clears_data(self, store):
        store.write(_make_nodes(), _make_edges())
        store.write([], [], wipe=True)
        assert store.stats()["total_nodes"] == 0

    def test_node_returns_none_for_missing(self, store):
        assert store.node("nonexistent:id") is None

    def test_edges_of_node(self, store):
        store.write(_make_nodes(), _make_edges())
        rxn_id = node_id(KIND_REACTION, "kegg", "R00200")
        edges = store.edges_of(rxn_id)
        rels = {e["rel"] for e in edges}
        assert "SUBSTRATE_OF" in rels
        assert "PRODUCT_OF" in rels

    def test_edges_within(self, store):
        store.write(_make_nodes(), _make_edges())
        rxn_id = node_id(KIND_REACTION, "kegg", "R00200")
        glucose_id = node_id(KIND_COMPOUND, "kegg", "C00031")
        edges = store.edges_within({rxn_id, glucose_id})
        assert len(edges) == 1
        assert edges[0]["rel"] == "SUBSTRATE_OF"


class TestXrefIndex:
    def test_build_xref_index(self, store):
        store.write(_make_nodes(), [])
        count = store.build_xref_index()
        assert count > 0

    def test_node_by_xref(self, store):
        store.write(_make_nodes(), [])
        store.build_xref_index()
        n = store.node_by_xref("kegg", "C00031")
        assert n is not None
        assert n["name"] == "D-Glucose"

    def test_resolve_id_internal(self, store):
        store.write(_make_nodes(), [])
        nid = node_id(KIND_COMPOUND, "kegg", "C00031")
        assert store.resolve_id(nid) == nid

    def test_resolve_id_shorthand(self, store):
        store.write(_make_nodes(), [])
        store.build_xref_index()
        nid = store.resolve_id("kegg:C00031")
        assert nid == node_id(KIND_COMPOUND, "kegg", "C00031")

    def test_resolve_id_by_name(self, store):
        store.write(_make_nodes(), [])
        nid = store.resolve_id("D-Glucose")
        assert nid == node_id(KIND_COMPOUND, "kegg", "C00031")

    def test_resolve_id_unknown_returns_none(self, store):
        store.write(_make_nodes(), [])
        assert store.resolve_id("nonexistent") is None


class TestReactionDetail:
    def test_reaction_detail(self, store):
        store.write(_make_nodes(), _make_edges())
        rxn_id = node_id(KIND_REACTION, "kegg", "R00200")
        detail = store.reaction_detail(rxn_id)
        assert detail is not None
        assert detail["name"] == "Glycolysis reaction"
        assert len(detail["substrates"]) == 1
        assert len(detail["products"]) == 1
        assert detail["substrates"][0]["stoich"] == 1.0
        assert len(detail["enzymes"]) == 1
        assert detail["enzymes"][0]["role"] == "CATALYZES"

    def test_reaction_detail_missing(self, store):
        assert store.reaction_detail("rxn:kegg:MISSING") is None


class TestFindPath:
    def test_direct_path_two_hops(self, store):
        store.write(_make_nodes(), _make_edges())
        glucose_id = node_id(KIND_COMPOUND, "kegg", "C00031")
        pyruvate_id = node_id(KIND_COMPOUND, "kegg", "C00022")
        result = store.find_shortest_path(glucose_id, pyruvate_id)
        assert "error" not in result
        assert result["hops"] == 1
        ids_in_path = [n["id"] for n in result["path"]]
        assert glucose_id in ids_in_path
        assert pyruvate_id in ids_in_path

    def test_same_compound_zero_hops(self, store):
        store.write(_make_nodes(), [])
        nid = node_id(KIND_COMPOUND, "kegg", "C00031")
        result = store.find_shortest_path(nid, nid)
        assert result["hops"] == 0

    def test_no_path_returns_error(self, store):
        store.write(_make_nodes(), _make_edges())
        glucose_id = node_id(KIND_COMPOUND, "kegg", "C00031")
        pwy_id = node_id(KIND_PATHWAY, "kegg", "hsa00010")
        result = store.find_shortest_path(glucose_id, pwy_id, max_hops=2)
        assert "error" in result


class TestNodeCategory:
    """Tests for category persistence and all_nodes(category=) filtering."""

    def _pathway_with_category(self, cat: str | None) -> MetaNode:
        suffix = cat or "none"
        return MetaNode(
            id=f"pwy:kegg:hsa_test_{suffix}",
            kind=KIND_PATHWAY,
            name=f"Test pathway {suffix}",
            source_format="kgml",
            category=cat,
        )

    def test_category_persisted_and_retrieved(self, store):
        pwy = self._pathway_with_category(PATHWAY_CATEGORY_METABOLIC)
        store.write([pwy], [])
        row = store.node(pwy.id)
        assert row is not None
        assert row["category"] == PATHWAY_CATEGORY_METABOLIC

    def test_category_none_persisted_as_null(self, store):
        cpd = MetaNode(
            id=node_id(KIND_COMPOUND, "kegg", "C00022"),
            kind=KIND_COMPOUND,
            name="Pyruvate",
        )
        store.write([cpd], [])
        row = store.node(cpd.id)
        assert row["category"] is None

    def test_all_nodes_filter_by_category(self, store):
        m = self._pathway_with_category(PATHWAY_CATEGORY_METABOLIC)
        d = self._pathway_with_category(PATHWAY_CATEGORY_DISEASE)
        store.write([m, d], [])
        metabolic = store.all_nodes(category=PATHWAY_CATEGORY_METABOLIC)
        assert len(metabolic) == 1
        assert metabolic[0]["id"] == m.id

    def test_all_nodes_filter_kind_and_category(self, store):
        m_pwy = self._pathway_with_category(PATHWAY_CATEGORY_METABOLIC)
        cpd = MetaNode(
            id=node_id(KIND_COMPOUND, "kegg", "C00031"),
            kind=KIND_COMPOUND,
            name="D-Glucose",
        )
        store.write([m_pwy, cpd], [])
        result = store.all_nodes(kind=KIND_PATHWAY, category=PATHWAY_CATEGORY_METABOLIC)
        assert len(result) == 1
        assert result[0]["kind"] == KIND_PATHWAY

    def test_all_nodes_no_filter_returns_all(self, store):
        nodes = _make_nodes()
        store.write(nodes, [])
        all_n = store.all_nodes()
        assert len(all_n) == len(nodes)

    def test_migration_adds_category_column_to_existing_db(self, tmp_path):
        """Opening an old DB without the category column should auto-migrate."""
        db_path = tmp_path / "legacy.sqlite"
        # Create an old-style DB without the category column
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE meta_nodes (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
                description TEXT, formula TEXT, charge INTEGER,
                ec_number TEXT, stoichiometry TEXT, xrefs TEXT,
                source_format TEXT, source_file TEXT
            )
            """
        )
        conn.execute("INSERT INTO meta_nodes (id, kind, name) VALUES ('x', 'compound', 'X')")
        conn.commit()
        conn.close()

        # Open via MetaStore — migration should add the column
        store = MetaStore(db_path)
        row = store.node("x")
        assert row is not None
        assert "category" in row
        assert row["category"] is None
        store.close()
