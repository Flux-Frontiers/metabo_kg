"""
Tests for metabokg.orchestrator — MetaKG top-level orchestrator and result types.
"""

import json
from unittest.mock import MagicMock

import pytest

from metabokg import MetabolicRuntimeStats, MetaKG
from metabokg.embed import SeedHit
from metabokg.primitives import (
    KIND_COMPOUND,
    KIND_ENZYME,
    KIND_PATHWAY,
    KIND_REACTION,
    MetaEdge,
    MetaNode,
    node_id,
)


@pytest.fixture()
def kg_with_data(tmp_path):
    """Create a MetaKG instance with some test data."""
    kg = MetaKG(
        db_path=tmp_path / "test.sqlite",
        lancedb_dir=tmp_path / "lancedb",
    )

    # Write test data
    nodes = [
        MetaNode(
            id=node_id(KIND_COMPOUND, "kegg", "C00031"),
            kind=KIND_COMPOUND,
            name="D-Glucose",
            formula="C6H12O6",
            xrefs='{"kegg": "C00031"}',
            source_format="csv",
        ),
        MetaNode(
            id=node_id(KIND_COMPOUND, "kegg", "C00022"),
            kind=KIND_COMPOUND,
            name="Pyruvate",
            formula="C3H4O3",
            xrefs='{"kegg": "C00022"}',
            source_format="csv",
        ),
        MetaNode(
            id=node_id(KIND_REACTION, "kegg", "R00200"),
            kind=KIND_REACTION,
            name="Pyruvate dehydrogenase",
            stoichiometry=json.dumps(
                {
                    "substrates": [{"id": node_id(KIND_COMPOUND, "kegg", "C00022"), "stoich": 1.0}],
                    "products": [{"id": node_id(KIND_COMPOUND, "kegg", "C00031"), "stoich": 1.0}],
                }
            ),
            xrefs='{"kegg": "R00200"}',
            source_format="csv",
        ),
        MetaNode(
            id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
            kind=KIND_PATHWAY,
            name="Glycolysis",
            source_format="csv",
        ),
        MetaNode(
            id=node_id(KIND_ENZYME, "ec", "2.7.1.1"),
            kind=KIND_ENZYME,
            name="Hexokinase",
            ec_number="2.7.1.1",
            xrefs='{"ec": "2.7.1.1"}',
            source_format="csv",
        ),
    ]

    edges = [
        MetaEdge(
            src=node_id(KIND_COMPOUND, "kegg", "C00022"),
            rel="SUBSTRATE_OF",
            dst=node_id(KIND_REACTION, "kegg", "R00200"),
            evidence='{"stoich": 1.0}',
        ),
        MetaEdge(
            src=node_id(KIND_REACTION, "kegg", "R00200"),
            rel="PRODUCT_OF",
            dst=node_id(KIND_COMPOUND, "kegg", "C00031"),
            evidence='{"stoich": 1.0}',
        ),
        MetaEdge(
            src=node_id(KIND_ENZYME, "ec", "2.7.1.1"),
            rel="CATALYZES",
            dst=node_id(KIND_REACTION, "kegg", "R00200"),
        ),
        MetaEdge(
            src=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
            rel="CONTAINS",
            dst=node_id(KIND_REACTION, "kegg", "R00200"),
        ),
    ]

    kg.store.write(nodes, edges)
    yield kg
    kg.close()


@pytest.fixture()
def empty_kg(tmp_path):
    """Create an empty MetaKG instance."""
    kg = MetaKG(
        db_path=tmp_path / "empty.sqlite",
        lancedb_dir=tmp_path / "empty_lancedb",
    )
    yield kg
    kg.close()


class TestMetabolicRuntimeStats:
    """Tests for MetabolicRuntimeStats dataclass."""

    def test_basic_construction(self):
        """Test basic instantiation with required fields."""
        stats = MetabolicRuntimeStats(
            total_nodes=10,
            total_edges=15,
            node_counts={"compound": 5, "reaction": 3, "enzyme": 2},
            edge_counts={"SUBSTRATE_OF": 8, "CATALYZES": 7},
        )
        assert stats.total_nodes == 10
        assert stats.total_edges == 15
        assert stats.node_counts["compound"] == 5
        assert stats.edge_counts["SUBSTRATE_OF"] == 8

    def test_with_index_stats(self):
        """Test instantiation with index stats."""
        stats = MetabolicRuntimeStats(
            total_nodes=100,
            total_edges=200,
            node_counts={"compound": 50},
            edge_counts={"SUBSTRATE_OF": 200},
            indexed_rows=50,
            index_dim=384,
        )
        assert stats.indexed_rows == 50
        assert stats.index_dim == 384

    def test_index_stats_optional(self):
        """Test that index stats are optional (None by default)."""
        stats = MetabolicRuntimeStats(
            total_nodes=10,
            total_edges=15,
            node_counts={"compound": 5},
            edge_counts={"SUBSTRATE_OF": 8},
        )
        assert stats.indexed_rows is None
        assert stats.index_dim is None

    def test_to_dict(self):
        """Test serialization to dictionary."""
        stats = MetabolicRuntimeStats(
            total_nodes=10,
            total_edges=15,
            node_counts={"compound": 5},
            edge_counts={"SUBSTRATE_OF": 8},
            indexed_rows=5,
            index_dim=384,
        )
        d = stats.to_dict()
        assert d["total_nodes"] == 10
        assert d["total_edges"] == 15
        assert d["node_counts"] == {"compound": 5}
        assert d["edge_counts"] == {"SUBSTRATE_OF": 8}
        assert d["indexed_rows"] == 5
        assert d["index_dim"] == 384

    def test_str_without_index(self):
        """Test string representation without index stats."""
        stats = MetabolicRuntimeStats(
            total_nodes=10,
            total_edges=15,
            node_counts={"compound": 5, "reaction": 3},
            edge_counts={"SUBSTRATE_OF": 8, "CATALYZES": 7},
        )
        s = str(stats)
        assert "nodes" in s
        assert "edges" in s
        assert "10" in s
        assert "15" in s
        assert "indexed" not in s

    def test_str_with_index(self):
        """Test string representation with index stats."""
        stats = MetabolicRuntimeStats(
            total_nodes=10,
            total_edges=15,
            node_counts={"compound": 5},
            edge_counts={"SUBSTRATE_OF": 8},
            indexed_rows=5,
            index_dim=384,
        )
        s = str(stats)
        assert "indexed" in s
        assert "384" in s


class TestMetaKGGetStats:
    """Tests for MetaKG.get_stats() method."""

    def test_get_stats_returns_runtime_stats(self, kg_with_data):
        """Test that get_stats returns MetabolicRuntimeStats."""
        stats = kg_with_data.get_stats()
        assert isinstance(stats, MetabolicRuntimeStats)

    def test_get_stats_correct_node_counts(self, kg_with_data):
        """Test that node counts are correct."""
        stats = kg_with_data.get_stats()
        assert stats.total_nodes == 5
        assert stats.node_counts["compound"] == 2
        assert stats.node_counts["reaction"] == 1
        assert stats.node_counts["enzyme"] == 1
        assert stats.node_counts["pathway"] == 1

    def test_get_stats_correct_edge_counts(self, kg_with_data):
        """Test that edge counts are correct."""
        stats = kg_with_data.get_stats()
        assert stats.total_edges == 4
        assert stats.edge_counts["SUBSTRATE_OF"] == 1
        assert stats.edge_counts["PRODUCT_OF"] == 1
        assert stats.edge_counts["CATALYZES"] == 1
        assert stats.edge_counts["CONTAINS"] == 1

    def test_get_stats_empty_database(self, empty_kg):
        """Test get_stats on empty database."""
        stats = empty_kg.get_stats()
        assert stats.total_nodes == 0
        assert stats.total_edges == 0
        assert len(stats.node_counts) == 0
        assert len(stats.edge_counts) == 0

    def test_get_stats_multiple_calls_consistent(self, kg_with_data):
        """Test that multiple calls to get_stats return consistent results."""
        stats1 = kg_with_data.get_stats()
        stats2 = kg_with_data.get_stats()
        assert stats1.total_nodes == stats2.total_nodes
        assert stats1.total_edges == stats2.total_edges
        assert stats1.node_counts == stats2.node_counts
        assert stats1.edge_counts == stats2.edge_counts

    def test_get_stats_no_internal_exposure(self, kg_with_data):
        """Test that get_stats provides API without internal `.store` access."""
        # This test ensures users don't need to access kg.store
        stats = kg_with_data.get_stats()
        # User can access everything they need from stats object
        assert hasattr(stats, "total_nodes")
        assert hasattr(stats, "total_edges")
        assert hasattr(stats, "node_counts")
        assert hasattr(stats, "edge_counts")
        assert hasattr(stats, "indexed_rows")
        assert hasattr(stats, "index_dim")

    def test_get_stats_printable(self, kg_with_data):
        """Test that stats can be printed nicely."""
        stats = kg_with_data.get_stats()
        output = str(stats)
        assert len(output) > 0
        assert "nodes" in output.lower()
        assert "edges" in output.lower()

    def test_get_stats_serializable(self, kg_with_data):
        """Test that stats can be serialized to dict."""
        stats = kg_with_data.get_stats()
        d = stats.to_dict()
        assert isinstance(d, dict)
        assert "total_nodes" in d
        assert "total_edges" in d
        assert "node_counts" in d
        assert "edge_counts" in d


class TestMetaKGStats:
    """Tests for MetaKG.stats() — KGRAG adapter contract."""

    def test_returns_dict(self, kg_with_data):
        s = kg_with_data.stats()
        assert isinstance(s, dict)

    def test_standard_envelope_keys_present(self, kg_with_data):
        s = kg_with_data.stats()
        assert "node_count" in s
        assert "total_edges" in s

    def test_domain_keys_present(self, kg_with_data):
        s = kg_with_data.stats()
        assert "pathway_count" in s
        assert "compound_count" in s
        assert "reaction_count" in s

    def test_domain_counts_correct(self, kg_with_data):
        s = kg_with_data.stats()
        assert s["pathway_count"] == 1
        assert s["compound_count"] == 2
        assert s["reaction_count"] == 1

    def test_node_and_edge_counts_correct(self, kg_with_data):
        s = kg_with_data.stats()
        assert s["node_count"] == 5
        assert s["total_edges"] == 4

    def test_empty_kg_returns_zeros(self, empty_kg):
        s = empty_kg.stats()
        assert s["node_count"] == 0
        assert s["total_edges"] == 0
        assert s["pathway_count"] == 0
        assert s["compound_count"] == 0
        assert s["reaction_count"] == 0

    def test_never_raises(self, empty_kg):
        s = empty_kg.stats()
        assert isinstance(s, dict)

    def test_consistent_with_get_stats(self, kg_with_data):
        flat = kg_with_data.stats()
        runtime = kg_with_data.get_stats()
        assert flat["node_count"] == runtime.total_nodes
        assert flat["total_edges"] == runtime.total_edges
        assert flat["pathway_count"] == runtime.node_counts.get("pathway", 0)
        assert flat["compound_count"] == runtime.node_counts.get("compound", 0)
        assert flat["reaction_count"] == runtime.node_counts.get("reaction", 0)


# ---------------------------------------------------------------------------
# Helpers for query tests — inject a mock index so no model load is needed
# ---------------------------------------------------------------------------


def _mock_index(hits: list[SeedHit]) -> MagicMock:
    idx = MagicMock()
    idx.search.return_value = hits
    return idx


def _seed(node_id_val: str, kind: str, name: str, distance: float = 0.1) -> SeedHit:
    return SeedHit(id=node_id_val, kind=kind, name=name, distance=distance, rank=0)


class TestMetaKGQuery:
    """Tests for MetaKG.query(text, k, hop)."""

    def test_query_returns_seed_hits(self, kg_with_data):
        glucose_id = node_id(KIND_COMPOUND, "kegg", "C00031")
        pyruvate_id = node_id(KIND_COMPOUND, "kegg", "C00022")
        kg_with_data._index = _mock_index(
            [
                _seed(glucose_id, KIND_COMPOUND, "D-Glucose"),
                _seed(pyruvate_id, KIND_COMPOUND, "Pyruvate", distance=0.2),
            ]
        )
        result = kg_with_data.query("glucose", k=2)
        assert len(result.hits) == 2
        ids = {h["id"] for h in result.hits}
        assert glucose_id in ids
        assert pyruvate_id in ids

    def test_query_attaches_distance(self, kg_with_data):
        glucose_id = node_id(KIND_COMPOUND, "kegg", "C00031")
        kg_with_data._index = _mock_index(
            [_seed(glucose_id, KIND_COMPOUND, "D-Glucose", distance=0.42)]
        )
        result = kg_with_data.query("glucose", k=1)
        assert result.hits[0]["_distance"] == pytest.approx(0.42)

    def test_query_skips_missing_nodes(self, kg_with_data):
        kg_with_data._index = _mock_index([_seed("cpd:kegg:MISSING", KIND_COMPOUND, "Ghost")])
        result = kg_with_data.query("ghost", k=1)
        assert result.hits == []

    def test_query_hop0_returns_seeds_only(self, kg_with_data):
        glucose_id = node_id(KIND_COMPOUND, "kegg", "C00031")
        kg_with_data._index = _mock_index([_seed(glucose_id, KIND_COMPOUND, "D-Glucose")])
        result = kg_with_data.query("glucose", k=1, hop=0)
        assert len(result.hits) == 1
        assert result.hits[0]["id"] == glucose_id

    def test_query_hop1_expands_to_reaction(self, kg_with_data):
        glucose_id = node_id(KIND_COMPOUND, "kegg", "C00031")
        rxn_id = node_id(KIND_REACTION, "kegg", "R00200")
        kg_with_data._index = _mock_index([_seed(glucose_id, KIND_COMPOUND, "D-Glucose")])
        result = kg_with_data.query("glucose", k=1, hop=1)
        ids = {h["id"] for h in result.hits}
        assert glucose_id in ids
        assert rxn_id in ids

    def test_query_hop2_expands_further(self, kg_with_data):
        glucose_id = node_id(KIND_COMPOUND, "kegg", "C00031")
        pyruvate_id = node_id(KIND_COMPOUND, "kegg", "C00022")
        kg_with_data._index = _mock_index([_seed(glucose_id, KIND_COMPOUND, "D-Glucose")])
        result = kg_with_data.query("glucose", k=1, hop=2)
        ids = {h["id"] for h in result.hits}
        assert pyruvate_id in ids

    def test_query_result_query_field(self, kg_with_data):
        kg_with_data._index = _mock_index([])
        result = kg_with_data.query("my query text", k=5)
        assert result.query == "my query text"


class TestMetaKGQueryPathway:
    """Tests for MetaKG.query_pathway(name, k, hop)."""

    def test_query_pathway_returns_only_pathways(self, kg_with_data):
        glucose_id = node_id(KIND_COMPOUND, "kegg", "C00031")
        pwy_id = node_id(KIND_PATHWAY, "kegg", "hsa00010")
        # Index returns both; only the pathway node should survive the kind filter
        kg_with_data._index = _mock_index(
            [
                _seed(glucose_id, KIND_COMPOUND, "D-Glucose"),
                _seed(pwy_id, KIND_PATHWAY, "Glycolysis"),
            ]
        )
        result = kg_with_data.query_pathway("glycolysis", k=2)
        assert all(h["kind"] == KIND_PATHWAY for h in result.hits)
        assert len(result.hits) == 1

    def test_query_pathway_includes_member_count(self, kg_with_data):
        pwy_id = node_id(KIND_PATHWAY, "kegg", "hsa00010")
        kg_with_data._index = _mock_index([_seed(pwy_id, KIND_PATHWAY, "Glycolysis")])
        result = kg_with_data.query_pathway("glycolysis", k=1)
        assert "member_count" in result.hits[0]
        assert result.hits[0]["member_count"] == 1  # one CONTAINS edge in fixture

    def test_query_pathway_hop1_expands(self, kg_with_data):
        pwy_id = node_id(KIND_PATHWAY, "kegg", "hsa00010")
        rxn_id = node_id(KIND_REACTION, "kegg", "R00200")
        kg_with_data._index = _mock_index([_seed(pwy_id, KIND_PATHWAY, "Glycolysis")])
        result = kg_with_data.query_pathway("glycolysis", k=1, hop=1)
        ids = {h["id"] for h in result.hits}
        assert rxn_id in ids

    def test_query_pathway_no_results(self, kg_with_data):
        kg_with_data._index = _mock_index([])
        result = kg_with_data.query_pathway("nonexistent pathway", k=5)
        assert result.hits == []
