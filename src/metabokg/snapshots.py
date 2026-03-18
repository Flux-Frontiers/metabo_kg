"""
snapshots.py — Temporal Snapshots of MetaKG Metrics

Captures, stores, and compares metrics snapshots of the metabolic knowledge
graph over time.  Each snapshot is keyed by git tree hash and contains:

  - Timestamp and branch metadata
  - Full store.stats() output (node/edge counts by kind/relation)
  - Kinetic parameter and pathway counts
  - Top hub metabolites (compounds in the most reactions)
  - Dead-end metabolite count (quality signal)
  - Deltas vs. previous and baseline snapshots

Snapshots are stored in .metabokg/snapshots/ as JSON blobs, with a
manifest index (manifest.json) tracking all snapshots and their metadata.

Usage
-----
>>> from metabokg.snapshots import SnapshotManager
>>> from metabokg.store import MetaStore
>>> store = MetaStore(".metabokg/meta.sqlite")
>>> mgr = SnapshotManager(".metabokg/snapshots", db_path=".metabokg/meta.sqlite")
>>> snapshot = mgr.capture("v1.0.0", graph_stats_dict=store.stats())
>>> mgr.save_snapshot(snapshot)
>>> mgr.list_snapshots()
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class SnapshotMetrics:
    """Core metrics captured in a MetaKG snapshot."""

    total_nodes: int
    total_edges: int
    node_counts: dict[str, int]  # compound, reaction, enzyme, pathway
    edge_counts: dict[str, int]  # by relation
    kinetic_params: int  # rows in kinetic_parameters table
    pathway_count: int
    dead_end_count: int = 0  # dead-end metabolites (quality signal)
    category_counts: dict[str, int] = field(default_factory=dict)  # pathways by category


@dataclass
class SnapshotDelta:
    """Deltas comparing this snapshot to a baseline or previous snapshot."""

    nodes: int = 0
    edges: int = 0
    kinetic_params_delta: int = 0
    pathway_delta: int = 0


@dataclass
class Snapshot:
    """A temporal snapshot of MetaKG metrics."""

    branch: str  # git branch name
    timestamp: str  # ISO 8601 UTC
    version: str  # e.g., "1.0.0"
    metrics: SnapshotMetrics
    hub_metabolites: list[dict[str, Any]] = field(default_factory=list)  # top hub compounds
    vs_previous: SnapshotDelta | None = None
    vs_baseline: SnapshotDelta | None = None
    tree_hash: str = ""  # git tree hash; stable file key

    @property
    def key(self) -> str:
        """Stable file key: tree hash."""
        return self.tree_hash

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "key": self.tree_hash,
            "branch": self.branch,
            "timestamp": self.timestamp,
            "version": self.version,
            "metrics": asdict(self.metrics),
            "hub_metabolites": self.hub_metabolites,
            "vs_previous": asdict(self.vs_previous) if self.vs_previous else None,
            "vs_baseline": asdict(self.vs_baseline) if self.vs_baseline else None,
        }

    @staticmethod
    def from_dict(data: dict) -> Snapshot:
        """Reconstruct from dict loaded from JSON."""
        data = dict(data)
        metrics_data = data.pop("metrics")
        metrics = SnapshotMetrics(**metrics_data)

        vs_prev_data = data.pop("vs_previous", None)
        vs_prev = SnapshotDelta(**vs_prev_data) if vs_prev_data else None

        vs_base_data = data.pop("vs_baseline", None)
        vs_base = SnapshotDelta(**vs_base_data) if vs_base_data else None

        key = data.pop("key", "")
        data.pop("tree_hash", None)

        return Snapshot(
            tree_hash=key,
            metrics=metrics,
            vs_previous=vs_prev,
            vs_baseline=vs_base,
            **data,
        )


@dataclass
class SnapshotManifest:
    """Index of all snapshots, with fast lookup by tree hash."""

    format_version: str = "1.0"
    last_update: str = ""
    snapshots: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "format": self.format_version,
            "last_update": self.last_update,
            "snapshots": self.snapshots,
        }

    @staticmethod
    def from_dict(data: dict) -> SnapshotManifest:
        """Reconstruct from dict."""
        return SnapshotManifest(
            format_version=data.get("format", "1.0"),
            last_update=data.get("last_update", ""),
            snapshots=data.get("snapshots", []),
        )


class SnapshotManager:
    """Manages MetaKG snapshot storage, retrieval, and comparison."""

    def __init__(self, snapshots_dir: Path | str, db_path: Path | str | None = None):
        """
        Initialize snapshot manager.

        :param snapshots_dir: Directory to store snapshot JSON files and manifest.
        :param db_path: Optional path to the MetaKG SQLite database.  When
            provided, ``capture()`` queries kinetic params, categories, and
            hub metabolites automatically.
        """
        self.snapshots_dir = Path(snapshots_dir)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.snapshots_dir / "manifest.json"
        self.db_path = Path(db_path) if db_path else None

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def capture(
        self,
        version: str,
        branch: str | None = None,
        graph_stats_dict: dict | None = None,
        tree_hash: str = "",
        dead_end_count: int = 0,
        hub_metabolites: list[dict] | None = None,
    ) -> Snapshot:
        """
        Capture a snapshot from current database state.

        :param version: Version string (e.g., ``"1.0.0"``).
        :param branch: Git branch name; auto-detected if ``None``.
        :param graph_stats_dict: Output from ``MetaStore.stats()``; queried
            from ``db_path`` if not provided.
        :param tree_hash: Git tree hash; auto-detected if empty.
        :param dead_end_count: Number of dead-end metabolites from analysis.
        :param hub_metabolites: Top hub compounds with reaction counts.
        :return: New :class:`Snapshot` instance.
        """
        if branch is None:
            branch = self._get_current_branch()
        if not tree_hash:
            tree_hash = self._get_current_tree_hash()
        if graph_stats_dict is None:
            graph_stats_dict = self._collect_graph_stats()

        timestamp = datetime.now(UTC).isoformat()
        kinetic_params = self._collect_kinetic_params_count()
        category_counts = self._collect_category_counts()

        metrics = SnapshotMetrics(
            total_nodes=graph_stats_dict.get("total_nodes", 0),
            total_edges=graph_stats_dict.get("total_edges", 0),
            node_counts=graph_stats_dict.get("node_counts", {}),
            edge_counts=graph_stats_dict.get("edge_counts", {}),
            kinetic_params=kinetic_params,
            pathway_count=graph_stats_dict.get("node_counts", {}).get("pathway", 0),
            dead_end_count=dead_end_count,
            category_counts=category_counts,
        )

        if hub_metabolites is None:
            hub_metabolites = self._collect_hub_metabolites()

        snapshot = Snapshot(
            branch=branch,
            timestamp=timestamp,
            version=version,
            metrics=metrics,
            hub_metabolites=hub_metabolites,
            tree_hash=tree_hash,
        )

        prev = self.get_previous(tree_hash)
        if prev:
            snapshot.vs_previous = self._compute_delta(snapshot, prev)

        baseline = self.get_baseline()
        if baseline:
            snapshot.vs_baseline = self._compute_delta(snapshot, baseline)

        return snapshot

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_snapshot(self, snapshot: Snapshot) -> Path:
        """
        Save snapshot to ``.metabokg/snapshots/{key}.json`` and update manifest.

        :param snapshot: Snapshot to save.
        :return: Path to saved snapshot file.
        :raises ValueError: If the snapshot has zero nodes.
        """
        if snapshot.metrics.total_nodes == 0:
            raise ValueError(
                "Refusing to save degenerate snapshot with 0 nodes. "
                "Run 'metabokg-build' before capturing a snapshot."
            )

        snapshot_file = self.snapshots_dir / f"{snapshot.key}.json"
        with open(snapshot_file, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

        manifest = self.load_manifest()
        existing_idx = next(
            (i for i, s in enumerate(manifest.snapshots) if s.get("key") == snapshot.key),
            None,
        )

        manifest_entry = {
            "key": snapshot.key,
            "branch": snapshot.branch,
            "timestamp": snapshot.timestamp,
            "version": snapshot.version,
            "file": snapshot_file.name,
            "metrics": asdict(snapshot.metrics),
            "deltas": {
                "vs_previous": asdict(snapshot.vs_previous) if snapshot.vs_previous else None,
                "vs_baseline": asdict(snapshot.vs_baseline) if snapshot.vs_baseline else None,
            },
        }

        if existing_idx is not None:
            manifest.snapshots[existing_idx] = manifest_entry
        else:
            manifest.snapshots.append(manifest_entry)

        manifest.last_update = datetime.now(UTC).isoformat()
        self._save_manifest(manifest)
        return snapshot_file

    def load_manifest(self) -> SnapshotManifest:
        """Load manifest.json; return empty manifest if it doesn't exist."""
        if not self.manifest_path.exists():
            return SnapshotManifest()
        with open(self.manifest_path) as f:
            return SnapshotManifest.from_dict(json.load(f))

    def _save_manifest(self, manifest: SnapshotManifest) -> None:
        with open(self.manifest_path, "w") as f:
            json.dump(manifest.to_dict(), f, indent=2)

    def load_snapshot(self, key: str) -> Snapshot | None:
        """
        Load a snapshot by key (tree hash) or ``"latest"``.

        :param key: Tree hash key, or the string ``"latest"`` for the most
            recent snapshot.
        :return: :class:`Snapshot` or ``None`` if not found.
        """
        if key == "latest":
            manifest = self.load_manifest()
            if not manifest.snapshots:
                return None
            key = max(manifest.snapshots, key=lambda s: s["timestamp"])["key"]

        snapshot_file = self.snapshots_dir / f"{key}.json"
        if not snapshot_file.exists():
            return None
        with open(snapshot_file) as f:
            snap = Snapshot.from_dict(json.load(f))

        # Backfill deltas for legacy snapshots
        if snap.vs_previous is None or snap.vs_baseline is None:
            manifest = self.load_manifest()
            entries = sorted(manifest.snapshots, key=lambda x: x.get("timestamp", ""), reverse=True)
            idx = next((i for i, s in enumerate(entries) if s.get("key") == key), None)

            if idx is not None:
                if snap.vs_previous is None and idx + 1 < len(entries):
                    prev = entries[idx + 1].get("metrics", {})
                    snap.vs_previous = SnapshotDelta(
                        nodes=snap.metrics.total_nodes - prev.get("total_nodes", 0),
                        edges=snap.metrics.total_edges - prev.get("total_edges", 0),
                        kinetic_params_delta=snap.metrics.kinetic_params
                        - prev.get("kinetic_params", 0),
                        pathway_delta=snap.metrics.pathway_count - prev.get("pathway_count", 0),
                    )
                if snap.vs_baseline is None and entries:
                    base = entries[-1].get("metrics", {})
                    snap.vs_baseline = SnapshotDelta(
                        nodes=snap.metrics.total_nodes - base.get("total_nodes", 0),
                        edges=snap.metrics.total_edges - base.get("total_edges", 0),
                        kinetic_params_delta=snap.metrics.kinetic_params
                        - base.get("kinetic_params", 0),
                        pathway_delta=snap.metrics.pathway_count - base.get("pathway_count", 0),
                    )

        return snap

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------

    def get_previous(self, key: str) -> Snapshot | None:
        """Get the snapshot immediately before this one (by timestamp)."""
        manifest = self.load_manifest()
        current_ts = next((s["timestamp"] for s in manifest.snapshots if s.get("key") == key), None)
        if not current_ts:
            return None
        prev_entry = None
        for s in sorted(manifest.snapshots, key=lambda x: x["timestamp"], reverse=True):
            if s["timestamp"] < current_ts:
                prev_entry = s
                break
        return self.load_snapshot(prev_entry["key"]) if prev_entry else None

    def get_baseline(self) -> Snapshot | None:
        """Get the oldest snapshot (baseline for comparison)."""
        manifest = self.load_manifest()
        if not manifest.snapshots:
            return None
        baseline_entry = min(manifest.snapshots, key=lambda x: x["timestamp"])
        return self.load_snapshot(baseline_entry["key"])

    def list_snapshots(self, limit: int | None = None) -> list[dict]:
        """
        List all snapshots in reverse chronological order.

        Missing ``vs_previous`` deltas are computed on-the-fly from adjacent
        manifest entries.

        :param limit: Max number to return; ``None`` = all.
        :return: List of snapshot metadata dicts.
        """
        manifest = self.load_manifest()
        all_snaps = sorted(manifest.snapshots, key=lambda x: x["timestamp"], reverse=True)

        for i, snap in enumerate(all_snaps):
            if snap.get("deltas", {}).get("vs_previous") is None and i + 1 < len(all_snaps):
                prev = all_snaps[i + 1]
                snap.setdefault("deltas", {})["vs_previous"] = {
                    "nodes": snap["metrics"]["total_nodes"] - prev["metrics"]["total_nodes"],
                    "edges": snap["metrics"]["total_edges"] - prev["metrics"]["total_edges"],
                    "kinetic_params_delta": snap["metrics"].get("kinetic_params", 0)
                    - prev["metrics"].get("kinetic_params", 0),
                    "pathway_delta": snap["metrics"].get("pathway_count", 0)
                    - prev["metrics"].get("pathway_count", 0),
                }

        return all_snaps[:limit] if limit else all_snaps

    def diff_snapshots(self, key_a: str, key_b: str) -> dict:
        """
        Compare two snapshots side-by-side.

        :param key_a: First snapshot key.
        :param key_b: Second snapshot key.
        :return: Dict with metrics from both and computed deltas (B − A).
        """
        snap_a = self.load_snapshot(key_a)
        snap_b = self.load_snapshot(key_b)

        if not snap_a or not snap_b:
            return {"error": "One or both snapshots not found"}

        all_node_kinds = set(snap_a.metrics.node_counts) | set(snap_b.metrics.node_counts)
        all_edge_rels = set(snap_a.metrics.edge_counts) | set(snap_b.metrics.edge_counts)

        return {
            "a": {"key": snap_a.key, "metrics": asdict(snap_a.metrics)},
            "b": {"key": snap_b.key, "metrics": asdict(snap_b.metrics)},
            "delta": asdict(self._compute_delta(snap_b, snap_a)),
            "node_counts_delta": {
                k: snap_b.metrics.node_counts.get(k, 0) - snap_a.metrics.node_counts.get(k, 0)
                for k in all_node_kinds
            },
            "edge_counts_delta": {
                k: snap_b.metrics.edge_counts.get(k, 0) - snap_a.metrics.edge_counts.get(k, 0)
                for k in all_edge_rels
            },
        }

    # ------------------------------------------------------------------
    # Delta computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_delta(snap_new: Snapshot, snap_old: Snapshot) -> SnapshotDelta:
        """Compute metrics delta (new − old)."""
        return SnapshotDelta(
            nodes=snap_new.metrics.total_nodes - snap_old.metrics.total_nodes,
            edges=snap_new.metrics.total_edges - snap_old.metrics.total_edges,
            kinetic_params_delta=snap_new.metrics.kinetic_params - snap_old.metrics.kinetic_params,
            pathway_delta=snap_new.metrics.pathway_count - snap_old.metrics.pathway_count,
        )

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _collect_graph_stats(self) -> dict:
        """Query graph stats from SQLite if db_path is available."""
        if not self.db_path or not self.db_path.exists():
            return {}
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                node_counts = {
                    r[0]: r[1]
                    for r in conn.execute(
                        "SELECT kind, COUNT(*) FROM meta_nodes GROUP BY kind"
                    ).fetchall()
                }
                edge_counts = {
                    r[0]: r[1]
                    for r in conn.execute(
                        "SELECT rel, COUNT(*) FROM meta_edges GROUP BY rel"
                    ).fetchall()
                }
            return {
                "total_nodes": sum(node_counts.values()),
                "total_edges": sum(edge_counts.values()),
                "node_counts": node_counts,
                "edge_counts": edge_counts,
            }
        except sqlite3.Error:
            return {}

    def _collect_kinetic_params_count(self) -> int:
        """Count rows in kinetic_parameters table."""
        if not self.db_path or not self.db_path.exists():
            return 0
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                row = conn.execute("SELECT COUNT(*) FROM kinetic_parameters").fetchone()
            return row[0] if row else 0
        except sqlite3.Error:
            return 0

    def _collect_category_counts(self) -> dict[str, int]:
        """Count pathways per category."""
        if not self.db_path or not self.db_path.exists():
            return {}
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                rows = conn.execute(
                    "SELECT category, COUNT(*) FROM meta_nodes "
                    "WHERE kind='pathway' GROUP BY category"
                ).fetchall()
            return {r[0] or "uncategorized": r[1] for r in rows}
        except sqlite3.Error:
            return {}

    def _collect_hub_metabolites(self, top: int = 10) -> list[dict]:
        """Return top compounds by total reaction participation."""
        if not self.db_path or not self.db_path.exists():
            return []
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT n.id, n.name, n.formula,
                           COUNT(DISTINCT e.dst) AS reaction_count
                    FROM   meta_nodes n
                    JOIN   meta_edges e ON e.src = n.id AND e.rel = 'SUBSTRATE_OF'
                    WHERE  n.kind = 'compound'
                    GROUP  BY n.id
                    ORDER  BY reaction_count DESC
                    LIMIT  ?
                    """,
                    (top,),
                ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error:
            return []

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_current_tree_hash() -> str:
        """Get current git tree hash (HEAD^{tree})."""
        try:
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD^{tree}"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    @staticmethod
    def _get_current_branch() -> str:
        """Get current git branch name."""
        try:
            return subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"
