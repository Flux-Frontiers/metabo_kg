"""
test_snapshots.py — Verify metabokg uses the shared snapshot model.

metabokg defined its own Snapshot, SnapshotMetrics, SnapshotDelta and
SnapshotManifest dataclasses and overrode every public manager method to
operate on them. Those types are now converters: a Snapshot is the shared
kg_utils one and carries plain dicts, and only the metabo-kg specific
behaviour is overridden.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from kg_utils.snapshots import Snapshot as SharedSnapshot
from kg_utils.snapshots import SnapshotManager as BaseSnapshotManager

from metabokg.snapshots import (
    Snapshot,
    SnapshotDelta,
    SnapshotManager,
    SnapshotMetrics,
    delta_from_dict,
    metrics_from_dict,
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
    assert isinstance(snap.metrics, dict)


def test_snapshot_is_the_shared_class() -> None:
    """The parallel data model is what kept fleet-wide snapshot fixes out of this repo."""
    assert Snapshot is SharedSnapshot


def test_metrics_attribute_access(mgr: SnapshotManager, graph_stats: dict) -> None:
    """Callers that want attribute access convert; the Snapshot holds a dict."""
    with (
        patch.object(SnapshotManager, "_get_current_branch", return_value="main"),
        patch.object(SnapshotManager, "_get_current_tree_hash", return_value="hash001"),
    ):
        snap = mgr.capture(version="1.0.0", graph_stats_dict=graph_stats, key="hash001")

    m = metrics_from_dict(snap.metrics)
    assert isinstance(m, SnapshotMetrics)
    assert m.total_nodes == 500
    assert m.total_edges == 800
    assert m.node_counts["compound"] == 200
    assert m.pathway_count == 50


def test_save_and_load_preserves_metrics_and_hubs(mgr: SnapshotManager, graph_stats: dict) -> None:
    """Hub metabolites live in the shared ``hotspots`` field."""
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
    assert isinstance(loaded.metrics, dict)
    lm = metrics_from_dict(loaded.metrics)
    assert lm.total_nodes == 500
    assert lm.dead_end_count == 12
    assert loaded.hotspots[0]["id"] == "atp"


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
    assert loaded.vs_previous is not None
    assert loaded.vs_previous["nodes"] == 50
    assert loaded.vs_previous["edges"] == 60

    delta = delta_from_dict(loaded.vs_previous)
    assert isinstance(delta, SnapshotDelta)
    assert delta.nodes == 50
    assert delta.kinetic_params_delta == 0  # absent from a back-filled delta


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


def test_load_back_fills_hotspots_from_the_legacy_field(tmp_path: Path) -> None:
    """Snapshots written before the migration carry a top-level hub_metabolites key.

    The shared model does not know that name, so ``load_snapshot`` reads it
    into ``hotspots``. Every snapshot committed to this repo before the
    migration has this shape.
    """
    snapshots_dir = tmp_path / "snapshots"
    snapshots_dir.mkdir(parents=True)
    legacy = {
        "key": "e" * 40,
        "branch": "main",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "version": "0.12.1",
        "metrics": {
            "total_nodes": 500,
            "total_edges": 800,
            "node_counts": {"compound": 200, "pathway": 50},
            "edge_counts": {"SUBSTRATE_OF": 400},
            "kinetic_params": 7,
            "pathway_count": 50,
            "dead_end_count": 3,
            "category_counts": {"Metabolism": 50},
        },
        "hub_metabolites": [{"id": "atp", "name": "ATP", "reaction_count": 42}],
        "vs_previous": None,
        "vs_baseline": None,
    }
    (snapshots_dir / f"{'e' * 40}.json").write_text(json.dumps(legacy), encoding="utf-8")
    (snapshots_dir / "manifest.json").write_text(
        json.dumps(
            {
                "format": "1.0",
                "last_update": "2026-01-01T00:00:00+00:00",
                "snapshots": [
                    {
                        "key": "e" * 40,
                        "branch": "main",
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "version": "0.12.1",
                        "file": f"{'e' * 40}.json",
                        "metrics": legacy["metrics"],
                        "deltas": {"vs_previous": None, "vs_baseline": None},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    mgr = SnapshotManager(snapshots_dir)
    loaded = mgr.load_snapshot("e" * 40)
    assert loaded is not None
    assert loaded.hotspots == [{"id": "atp", "name": "ATP", "reaction_count": 42}]
    assert metrics_from_dict(loaded.metrics).kinetic_params == 7
    # A 40-char hex key is also recorded as tree-hash provenance.
    assert loaded.tree_hash == "e" * 40


def test_save_snapshot_persists_key_subject_and_tool(
    mgr: SnapshotManager, graph_stats: dict
) -> None:
    """The key, subject and tool provenance survive the trip to disk."""
    tree_hash = "f" * 40
    snap = mgr.capture(
        version="0.14.0",
        branch="main",
        graph_stats_dict=graph_stats,
        tree_hash=tree_hash,
        key="v0.14.0",
        subject="corpus:hsa",
        hub_metabolites=[{"id": "atp", "reaction_count": 42}],
    )
    assert snap.key == "v0.14.0"

    saved = mgr.save_snapshot(snap)
    assert saved is not None

    on_disk = json.loads(Path(saved).read_text(encoding="utf-8"))
    assert on_disk["key"] == "v0.14.0"
    assert on_disk["subject"] == "corpus:hsa"
    assert on_disk["tree_hash"] == tree_hash
    assert on_disk["tool"] == "metabo-kg"
    assert on_disk["tool_version"]
    assert on_disk["hotspots"][0]["id"] == "atp"

    entry = json.loads(mgr.manifest_path.read_text(encoding="utf-8"))["snapshots"][0]
    assert entry["key"] == "v0.14.0"
    assert entry["subject"] == "corpus:hsa"
