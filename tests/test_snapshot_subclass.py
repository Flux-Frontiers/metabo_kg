"""
test_metabo_subclass.py — Verify metabokg.SnapshotManager inherits correctly.

Option A migration: all MetaKG domain types (SnapshotMetrics, SnapshotDelta,
Snapshot, SnapshotManifest) are unchanged.  Only git helpers are inherited.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from kg_utils.snapshots import SnapshotManager as BaseSnapshotManager

from metabokg.snapshots import (
    Snapshot,
    SnapshotDelta,
    SnapshotManager,
    SnapshotMetrics,
)


@pytest.fixture
def mgr(tmp_path: Path) -> SnapshotManager:
    return SnapshotManager(tmp_path / "snapshots")


@pytest.fixture
def graph_stats() -> dict:
    return {
        "total_nodes": 500,
        "total_edges": 800,
        "node_counts": {"compound": 200, "reaction": 150, "enzyme": 100, "pathway": 50},
        "edge_counts": {"SUBSTRATE_OF": 400, "PRODUCT_OF": 300, "CATALYZED_BY": 100},
    }


def test_inherits_from_base() -> None:
    assert issubclass(SnapshotManager, BaseSnapshotManager)


def test_git_helpers_inherited(mgr: SnapshotManager) -> None:
    branch = mgr._get_current_branch()
    tree_hash = mgr._get_current_tree_hash()
    assert isinstance(branch, str) and len(branch) > 0
    assert isinstance(tree_hash, str) and len(tree_hash) > 0


def test_capture_returns_meta_snapshot(mgr: SnapshotManager, graph_stats: dict) -> None:
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap = mgr.capture(version="1.0.0", graph_stats_dict=graph_stats, key="hash001")

    assert isinstance(snap, Snapshot)
    assert isinstance(snap.metrics, SnapshotMetrics)


def test_metrics_attribute_access(mgr: SnapshotManager, graph_stats: dict) -> None:
    """Attribute-style access on SnapshotMetrics must not break (Option A guarantee)."""
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap = mgr.capture(version="1.0.0", graph_stats_dict=graph_stats, key="hash001")

    assert snap.metrics.total_nodes == 500
    assert snap.metrics.total_edges == 800
    assert snap.metrics.node_counts["compound"] == 200
    assert snap.metrics.pathway_count == 50


def test_save_and_load_preserves_typed_metrics(mgr: SnapshotManager, graph_stats: dict) -> None:
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap = mgr.capture(
            version="1.0.0",
            graph_stats_dict=graph_stats,
            dead_end_count=12,
            hub_metabolites=[{"id": "atp", "reaction_count": 42}],
            key="hash001",
        )
    mgr.save_snapshot(snap)

    loaded = mgr.load_snapshot("hash001")
    assert loaded is not None
    assert isinstance(loaded.metrics, SnapshotMetrics)
    assert loaded.metrics.total_nodes == 500
    assert loaded.metrics.dead_end_count == 12
    assert loaded.hub_metabolites[0]["id"] == "atp"


def test_delta_backfilled_on_load(mgr: SnapshotManager, graph_stats: dict) -> None:
    """vs_previous is backfilled from manifest on load, not set at capture time."""
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap_a = mgr.capture(version="1.0.0", graph_stats_dict=graph_stats, key="hash001")
    mgr.save_snapshot(snap_a)

    stats_b = dict(graph_stats, total_nodes=550, total_edges=860)
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash002"),
    ):
        snap_b = mgr.capture(version="1.0.1", graph_stats_dict=stats_b, key="hash002")
    mgr.save_snapshot(snap_b)

    loaded = mgr.load_snapshot("hash002")
    assert loaded is not None
    assert isinstance(loaded.vs_previous, SnapshotDelta)
    assert loaded.vs_previous.nodes == 50
    assert loaded.vs_previous.edges == 60


def test_save_rejects_zero_nodes(mgr: SnapshotManager) -> None:
    empty_stats = {"total_nodes": 0, "total_edges": 0, "node_counts": {}, "edge_counts": {}}
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash000"),
    ):
        snap = mgr.capture(version="0.0.0", graph_stats_dict=empty_stats, key="hash000")
    with pytest.raises(ValueError, match="0 nodes"):
        mgr.save_snapshot(snap)


def test_diff_snapshots(mgr: SnapshotManager, graph_stats: dict) -> None:
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        mgr.save_snapshot(mgr.capture(graph_stats_dict=graph_stats, key="hash001"))

    stats_b = dict(graph_stats, total_nodes=600, total_edges=900)
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash002"),
    ):
        mgr.save_snapshot(mgr.capture(graph_stats_dict=stats_b, key="hash002"))

    diff = mgr.diff_snapshots("hash001", "hash002")
    assert diff["delta"]["nodes"] == 100
    assert diff["delta"]["edges"] == 100


# ---------------------------------------------------------------------------
# Key scheme (matches kgmodule-utils >= 0.19.0)
# ---------------------------------------------------------------------------


def test_capture_does_not_key_on_the_tree_hash(mgr: SnapshotManager, graph_stats: dict) -> None:
    """The tree hash is provenance, not an identifier.

    It is read before ``git add`` stages the snapshot, so it names a tree that
    is never committed.
    """
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="c" * 40),
    ):
        snap = mgr.capture(version="0.13.0", graph_stats_dict=graph_stats)

    assert snap.key != "c" * 40
    assert snap.tree_hash == "c" * 40
    assert snap.to_dict()["tree_hash"] == "c" * 40


def test_capture_uses_a_supplied_release_key(mgr: SnapshotManager, graph_stats: dict) -> None:
    with patch.object(SnapshotManager, "_get_current_branch", return_value="main"):
        snap = mgr.capture(
            version="0.13.0",
            graph_stats_dict=graph_stats,
            key="v0.13.0",
            subject="corpus:hsa",
        )
    mgr.save_snapshot(snap)

    assert snap.key == "v0.13.0"
    assert snap.subject == "corpus:hsa"
    assert snap.tool == "metabo-kg"
    assert mgr.load_snapshot("v0.13.0") is not None


def test_from_dict_dual_reads_a_legacy_tree_hash_key() -> None:
    """Entries written before the key change stay addressable."""
    key = "d" * 40
    snap = Snapshot.from_dict(
        {
            "key": key,
            "branch": "main",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "metrics": {
                "total_nodes": 1,
                "total_edges": 1,
                "node_counts": {},
                "edge_counts": {},
                "kinetic_params": 0,
                "pathway_count": 0,
            },
        }
    )
    assert snap.key == key
    assert snap.tree_hash == key  # a real hash is kept as provenance


def test_from_dict_does_not_mistake_a_tag_for_a_tree_hash() -> None:
    snap = Snapshot.from_dict(
        {
            "key": "v0.13.0",
            "branch": "main",
            "timestamp": "",
            "metrics": {
                "total_nodes": 1,
                "total_edges": 1,
                "node_counts": {},
                "edge_counts": {},
                "kinetic_params": 0,
                "pathway_count": 0,
            },
        }
    )
    assert snap.key == "v0.13.0"
    assert snap.tree_hash == ""
