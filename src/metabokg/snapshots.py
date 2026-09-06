"""
snapshots.py — Temporal Snapshots of MetaKG Metrics

Thin layer over the shared ``kg_utils.snapshots`` module.

``Snapshot``, ``SnapshotManifest`` and ``PruneResult`` are re-exported from
``kg_utils.snapshots`` unchanged.  A snapshot's ``metrics``, ``vs_previous``
and ``vs_baseline`` are plain dicts, which is what the shared manager reads
and writes.

This module adds:

  - ``SnapshotMetrics`` / ``SnapshotDelta`` — domain dataclasses, used as
    converters by callers that want attribute access.  Convert with
    ``metrics_from_dict`` / ``metrics_to_dict`` and ``delta_from_dict`` /
    ``delta_to_dict``; a ``Snapshot`` never holds one.
  - a ``SnapshotManager`` subclass that sets ``package_name="metabo-kg"``,
    queries the graph, kinetic parameters, pathway categories and hub
    metabolites in ``capture()``, and adds ``kinetic_params_delta`` and
    ``pathway_delta`` to deltas.

Top hub metabolites are stored in the shared ``hotspots`` field.  Snapshots
written before this module adopted the shared model carry them in a top-level
``hub_metabolites`` key instead; ``load_snapshot`` back-fills those so both
shapes read the same way.

This module used to define its own ``Snapshot``, ``SnapshotMetrics``,
``SnapshotDelta`` and ``SnapshotManifest`` dataclasses and override every
public manager method to operate on them.  That parallel model is what kept
the fleet's snapshot fixes from reaching this repo, and in two sibling repos
the equivalent ``save_snapshot`` override dropped ``snapshot_key``, ``subject``
and ``tool`` on the way to disk.

Usage
-----
>>> from metabokg.snapshots import SnapshotManager, metrics_from_dict
>>> mgr = SnapshotManager(".metabokg/snapshots", db_path=".metabokg/hsa.sqlite")
>>> snapshot = mgr.capture(version="1.0.0", key="v1.0.0", subject="corpus:hsa")
>>> mgr.save_snapshot(snapshot)
>>> metrics_from_dict(snapshot.metrics).pathway_count
0
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kg_utils.snapshots import PruneResult as PruneResult  # noqa: F401 — re-export
from kg_utils.snapshots import Snapshot as Snapshot  # noqa: F401 — re-export
from kg_utils.snapshots import SnapshotManager as _BaseSnapshotManager
from kg_utils.snapshots import SnapshotManifest as SnapshotManifest  # noqa: F401 — re-export

__all__ = [
    "PruneResult",
    "Snapshot",
    "SnapshotDelta",
    "SnapshotManager",
    "SnapshotManifest",
    "SnapshotMetrics",
    "delta_from_dict",
    "delta_to_dict",
    "metrics_from_dict",
    "metrics_to_dict",
]


# ---------------------------------------------------------------------------
# Domain dataclasses — converters, not storage
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def metrics_to_dict(m: SnapshotMetrics) -> dict[str, Any]:
    """Convert a ``SnapshotMetrics`` dataclass to a plain dict."""
    return {
        "total_nodes": m.total_nodes,
        "total_edges": m.total_edges,
        "node_counts": m.node_counts,
        "edge_counts": m.edge_counts,
        "kinetic_params": m.kinetic_params,
        "pathway_count": m.pathway_count,
        "dead_end_count": m.dead_end_count,
        "category_counts": m.category_counts,
    }


def metrics_from_dict(d: dict[str, Any]) -> SnapshotMetrics:
    """Reconstruct a ``SnapshotMetrics`` dataclass from a plain dict.

    Absent keys take the dataclass defaults, so a snapshot written before a
    field existed still converts.
    """
    return SnapshotMetrics(
        total_nodes=int(d.get("total_nodes", 0)),
        total_edges=int(d.get("total_edges", 0)),
        node_counts=d.get("node_counts", {}),
        edge_counts=d.get("edge_counts", {}),
        kinetic_params=int(d.get("kinetic_params", 0)),
        pathway_count=int(d.get("pathway_count", 0)),
        dead_end_count=int(d.get("dead_end_count", 0)),
        category_counts=d.get("category_counts", {}),
    )


def delta_to_dict(delta: SnapshotDelta | None) -> dict[str, Any] | None:
    """Convert a ``SnapshotDelta`` to a plain dict, or return ``None``."""
    if delta is None:
        return None
    return {
        "nodes": delta.nodes,
        "edges": delta.edges,
        "kinetic_params_delta": delta.kinetic_params_delta,
        "pathway_delta": delta.pathway_delta,
    }


def delta_from_dict(d: dict[str, Any] | None) -> SnapshotDelta | None:
    """Reconstruct a ``SnapshotDelta`` from a plain dict, or return ``None``."""
    if d is None:
        return None
    return SnapshotDelta(
        nodes=int(d.get("nodes", 0)),
        edges=int(d.get("edges", 0)),
        kinetic_params_delta=int(d.get("kinetic_params_delta", 0)),
        pathway_delta=int(d.get("pathway_delta", 0)),
    )


# ---------------------------------------------------------------------------
# SnapshotManager — metabo-kg specialisation of the shared manager
# ---------------------------------------------------------------------------


class SnapshotManager(_BaseSnapshotManager):
    """MetaKG snapshot manager.

    Subclasses the shared ``kg_utils.snapshots.SnapshotManager`` and adds:

    * ``package_name="metabo-kg"`` default for version detection.
    * A ``capture()`` that queries graph stats, the kinetic-parameter count,
      pathway categories and hub metabolites from SQLite when they are not
      supplied.
    * ``_compute_delta_from_metrics`` extended with ``kinetic_params_delta``
      and ``pathway_delta``.
    * ``load_snapshot`` back-filling ``hotspots`` from the legacy top-level
      ``hub_metabolites`` key.

    Everything else -- saving, listing, pruning, key handling, the manifest --
    is inherited unchanged.  This class used to override all of it to operate
    on a parallel data model, which is why fleet-wide snapshot fixes did not
    reach this repo.
    """

    def __init__(
        self,
        snapshots_dir: Path | str,
        db_path: Path | str | None = None,
        *,
        package_name: str = "metabo-kg",
    ) -> None:
        """Initialize the manager rooted at ``snapshots_dir``.

        :param snapshots_dir: Directory holding snapshot JSON and the manifest.
        :param db_path: Optional path to the MetaKG SQLite database.  When
            provided, ``capture()`` queries kinetic params, categories, and
            hub metabolites automatically.
        :param package_name: Package name used for version detection.
        """
        super().__init__(snapshots_dir, package_name=package_name, db_path=db_path)

    # ------------------------------------------------------------------
    # capture — query the graph, then delegate
    # ------------------------------------------------------------------

    def capture(
        self,
        version: str | None = None,
        branch: str | None = None,
        graph_stats_dict: dict[str, Any] | None = None,
        tree_hash: str = "",
        hotspots: list[dict[str, Any]] | None = None,
        issues: list[str] | None = None,
        key: str = "",
        subject: str = "",
        *,
        dead_end_count: int = 0,
        hub_metabolites: list[dict[str, Any]] | None = None,
        **extra_metrics: Any,
    ) -> Snapshot:
        """Capture a snapshot from current database state.

        :param version: Version string; auto-detected from the installed
            ``metabo-kg`` package if not provided.
        :param branch: Git branch name; auto-detected if ``None``.
        :param graph_stats_dict: Output from ``MetaStore.stats()``; queried
            from ``db_path`` if not provided.
        :param tree_hash: Git tree hash, recorded as provenance; auto-detected
            if empty. It is not the snapshot's key.
        :param hotspots: Top hub compounds. Alias for ``hub_metabolites``,
            which is the name this repo has always used; queried from
            ``db_path`` when neither is given.
        :param issues: Issue description strings.
        :param key: Snapshot identifier. Pass the release tag at release time;
            omit it and the snapshot is keyed on a UTC timestamp, which is the
            right answer for a corpus. Named explicitly rather than left to
            ``**extra_metrics``, which would silently record it as a metric
            instead of passing it to the base.
        :param subject: What was measured, e.g. ``corpus:hsa``. Recorded
            separately from ``version``, which names the measuring tool.
        :param dead_end_count: Number of dead-end metabolites from analysis.
        :param hub_metabolites: Top hub compounds with reaction counts.
        :param extra_metrics: Additional domain-specific metric fields.
        :return: New :class:`~kg_utils.snapshots.Snapshot` (not yet persisted).
        """
        stats = graph_stats_dict if graph_stats_dict is not None else self._collect_graph_stats()
        hubs = hub_metabolites if hub_metabolites is not None else hotspots
        if hubs is None:
            hubs = self._collect_hub_metabolites()

        node_counts: dict[str, int] = stats.get("node_counts", {})

        return super().capture(
            version=version,
            branch=branch,
            graph_stats_dict={
                "total_nodes": stats.get("total_nodes", 0),
                "total_edges": stats.get("total_edges", 0),
                "node_counts": node_counts,
                "edge_counts": stats.get("edge_counts", {}),
                "kinetic_params": self._collect_kinetic_params_count(),
                "pathway_count": node_counts.get("pathway", 0),
                "dead_end_count": dead_end_count,
                "category_counts": self._collect_category_counts(),
            },
            tree_hash=tree_hash,
            hotspots=hubs,
            issues=issues,
            key=key,
            subject=subject,
            **extra_metrics,
        )

    # ------------------------------------------------------------------
    # load_snapshot — back-fill hotspots from the legacy field
    # ------------------------------------------------------------------

    def load_snapshot(self, key: str) -> Snapshot | None:
        """Load a snapshot, back-filling ``hotspots`` for legacy files.

        Snapshots written before this module adopted the shared model store
        the top hub compounds in a top-level ``hub_metabolites`` key, which
        the shared model does not know about. They are read into ``hotspots``
        so both shapes present the same way.

        :param key: Snapshot key, or ``"latest"`` for the most recent.
        :return: The snapshot, or ``None`` if no file matches.
        """
        snap = super().load_snapshot(key)
        if snap is None or snap.hotspots:
            return snap

        snapshot_file = self.snapshots_dir / f"{snap.key}.json"
        if not snapshot_file.exists():
            return snap
        try:
            raw = json.loads(snapshot_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return snap
        legacy = raw.get("hub_metabolites")
        if legacy:
            snap.hotspots = legacy
        return snap

    # ------------------------------------------------------------------
    # Delta computation — adds kinetic_params_delta and pathway_delta
    # ------------------------------------------------------------------

    def _compute_delta_from_metrics(
        self, new_m: dict[str, Any], old_m: dict[str, Any]
    ) -> dict[str, Any]:
        """Compute delta dict including metabo-kg specific fields."""
        return {
            "nodes": new_m.get("total_nodes", 0) - old_m.get("total_nodes", 0),
            "edges": new_m.get("total_edges", 0) - old_m.get("total_edges", 0),
            "kinetic_params_delta": (
                new_m.get("kinetic_params", 0) - old_m.get("kinetic_params", 0)
            ),
            "pathway_delta": new_m.get("pathway_count", 0) - old_m.get("pathway_count", 0),
        }

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _collect_graph_stats(self) -> dict[str, Any]:
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

    def _collect_hub_metabolites(self, top: int = 10) -> list[dict[str, Any]]:
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
