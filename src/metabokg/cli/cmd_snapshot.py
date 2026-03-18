"""
cmd_snapshot.py — Click subcommands for managing MetaKG temporal snapshots.

  snapshot save   — capture current graph metrics and save snapshot
  snapshot list   — show all snapshots in reverse chronological order
  snapshot show   — display full snapshot details
  snapshot diff   — compare two snapshots side-by-side
"""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path

import click

from metabokg.cli.main import cli
from metabokg.cli.options import db_option
from metabokg.snapshots import SnapshotManager
from metabokg.store import MetaStore


@cli.group("snapshot")
def snapshot() -> None:
    """Manage temporal snapshots of MetaKG metrics."""


# ---------------------------------------------------------------------------
# snapshot save
# ---------------------------------------------------------------------------


@snapshot.command("save")
@click.argument("version", metavar="VERSION", default="", required=False)
@db_option
@click.option(
    "--snapshots-dir",
    default=None,
    type=click.Path(),
    help="Snapshots directory (default: .metabokg/snapshots).",
)
@click.option(
    "--branch",
    default=None,
    type=str,
    help="Branch name; auto-detected if not provided.",
)
@click.option(
    "--tree-hash",
    default="",
    type=str,
    help="Git tree hash; auto-detected if not provided.",
)
def save_snapshot(
    version: str,
    db: str,
    snapshots_dir: str | None,
    branch: str | None,
    tree_hash: str,
) -> None:
    """
    Capture current MetaKG graph metrics and save as a temporal snapshot.

    VERSION is optional — defaults to the installed package version.

    Reads graph statistics, kinetic parameter counts, and hub metabolites
    from the SQLite database, then saves a snapshot tagged with VERSION.
    Snapshots are keyed by git tree hash and stored in .metabokg/snapshots/.

    Example:
        metabokg snapshot save 1.2.0
        metabokg snapshot save          # uses installed package version
    """
    if not version:
        try:
            version = importlib.metadata.version("metabo-kg")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"

    db_path = Path(db)
    if not db_path.exists():
        click.echo(
            f"ERROR: database not found at '{db_path}'. Run 'metabokg-build' first.", err=True
        )
        raise click.Abort()

    snapshots_path = (
        Path(snapshots_dir).resolve() if snapshots_dir else db_path.parent / "snapshots"
    )

    store = MetaStore(db_path)
    try:
        stats = store.stats()
    finally:
        store.close()

    mgr = SnapshotManager(snapshots_path, db_path=db_path)
    snapshot_obj = mgr.capture(
        version=version,
        branch=branch,
        graph_stats_dict=stats,
        tree_hash=tree_hash,
    )

    snapshot_file = mgr.save_snapshot(snapshot_obj)
    click.echo(f"OK Snapshot saved: {snapshot_file}")
    click.echo(f"  Key:      {snapshot_obj.key}")
    click.echo(f"  Version:  {snapshot_obj.version}")
    click.echo(f"  Branch:   {snapshot_obj.branch}")
    click.echo(f"  Nodes:    {snapshot_obj.metrics.total_nodes}")
    click.echo(f"  Edges:    {snapshot_obj.metrics.total_edges}")
    click.echo(f"  Pathways: {snapshot_obj.metrics.pathway_count}")
    click.echo(f"  Kinetics: {snapshot_obj.metrics.kinetic_params}")


# ---------------------------------------------------------------------------
# snapshot list
# ---------------------------------------------------------------------------


@snapshot.command("list")
@click.option(
    "--snapshots-dir",
    default=None,
    type=click.Path(exists=True),
    help="Snapshots directory (default: .metabokg/snapshots).",
)
@click.option("--limit", type=int, default=None, help="Max snapshots to show.")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON.")
def list_snapshots(snapshots_dir: str | None, limit: int | None, output_json: bool) -> None:
    """
    List all temporal snapshots in reverse chronological order.

    Shows key, timestamp, version, and key metrics (nodes, edges, pathways,
    kinetic parameters) for each snapshot.
    """
    snapshots_path = (
        Path(snapshots_dir).resolve() if snapshots_dir else Path.cwd() / ".metabokg" / "snapshots"
    )
    mgr = SnapshotManager(snapshots_path)
    snapshots = mgr.list_snapshots(limit=limit)

    if not snapshots:
        click.echo("No snapshots found.")
        return

    if output_json:
        click.echo(json.dumps(snapshots, indent=2))
        return

    click.echo(
        f"{'Key':<12} {'Timestamp':<17} {'Branch':<12} {'Ver':<8}"
        f" {'Nodes':>6} {'Edges':>6} {'Pwy':>5} {'Kin':>5}"
    )
    click.echo("-" * 80)
    for snap in snapshots:
        key = snap["key"][:12]
        ts = snap["timestamp"][:16].replace("T", " ")
        branch = snap["branch"][:12]
        ver = snap["version"][:8]
        m = snap["metrics"]
        nodes = m["total_nodes"]
        edges = m["total_edges"]
        pwy = m.get("pathway_count", m.get("node_counts", {}).get("pathway", 0))
        kin = m.get("kinetic_params", 0)
        click.echo(
            f"{key:<12} {ts:<17} {branch:<12} {ver:<8} {nodes:>6} {edges:>6} {pwy:>5} {kin:>5}"
        )


# ---------------------------------------------------------------------------
# snapshot show
# ---------------------------------------------------------------------------


@snapshot.command("show")
@click.argument("key", metavar="KEY")
@click.option(
    "--snapshots-dir",
    default=None,
    type=click.Path(exists=True),
    help="Snapshots directory (default: .metabokg/snapshots).",
)
def show_snapshot(key: str, snapshots_dir: str | None) -> None:
    """
    Display full details for a single snapshot by key (tree hash) or 'latest'.

    Shows all metrics, top hub metabolites, and deltas vs. previous and
    baseline snapshots.
    """
    snapshots_path = (
        Path(snapshots_dir).resolve() if snapshots_dir else Path.cwd() / ".metabokg" / "snapshots"
    )
    mgr = SnapshotManager(snapshots_path)
    snap = mgr.load_snapshot(key)

    if not snap:
        click.echo(f"Snapshot not found: {key}", err=True)
        raise click.Abort()

    click.echo(f"Key:       {snap.key}")
    click.echo(f"Branch:    {snap.branch}")
    click.echo(f"Timestamp: {snap.timestamp}")
    click.echo(f"Version:   {snap.version}")
    click.echo()

    click.echo("Metrics:")
    click.echo(f"  Total Nodes:    {snap.metrics.total_nodes}")
    click.echo(f"  Total Edges:    {snap.metrics.total_edges}")
    click.echo(f"  Pathways:       {snap.metrics.pathway_count}")
    click.echo(f"  Kinetic Params: {snap.metrics.kinetic_params}")
    click.echo(f"  Dead Ends:      {snap.metrics.dead_end_count}")
    click.echo()

    click.echo("Node Breakdown:")
    for kind, count in sorted(snap.metrics.node_counts.items()):
        click.echo(f"  {kind}: {count}")
    click.echo()

    click.echo("Edge Breakdown:")
    for rel, count in sorted(snap.metrics.edge_counts.items()):
        click.echo(f"  {rel}: {count}")
    click.echo()

    if snap.metrics.category_counts:
        click.echo("Pathways by Category:")
        for cat, count in sorted(snap.metrics.category_counts.items(), key=lambda x: -x[1]):
            click.echo(f"  {cat}: {count}")
        click.echo()

    if snap.hub_metabolites:
        click.echo("Top Hub Metabolites:")
        for i, hub in enumerate(snap.hub_metabolites[:5], 1):
            name = hub.get("name", hub.get("id", "?"))
            rxns = hub.get("reaction_count", 0)
            formula = hub.get("formula") or ""
            click.echo(f"  {i}. {name} ({formula}) — {rxns} reactions")
        click.echo()

    if snap.vs_previous:
        d = snap.vs_previous
        click.echo("Delta vs. Previous:")
        click.echo(f"  Nodes:          {d.nodes:+d}")
        click.echo(f"  Edges:          {d.edges:+d}")
        click.echo(f"  Kinetic Params: {d.kinetic_params_delta:+d}")
        click.echo(f"  Pathways:       {d.pathway_delta:+d}")
        click.echo()

    if snap.vs_baseline:
        d = snap.vs_baseline
        click.echo("Delta vs. Baseline:")
        click.echo(f"  Nodes:          {d.nodes:+d}")
        click.echo(f"  Edges:          {d.edges:+d}")
        click.echo(f"  Kinetic Params: {d.kinetic_params_delta:+d}")
        click.echo(f"  Pathways:       {d.pathway_delta:+d}")


# ---------------------------------------------------------------------------
# snapshot diff
# ---------------------------------------------------------------------------


@snapshot.command("diff")
@click.argument("key_a", metavar="KEY_A")
@click.argument("key_b", metavar="KEY_B")
@click.option(
    "--snapshots-dir",
    default=None,
    type=click.Path(exists=True),
    help="Snapshots directory (default: .metabokg/snapshots).",
)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON.")
def diff_snapshots(key_a: str, key_b: str, snapshots_dir: str | None, output_json: bool) -> None:
    """
    Compare two snapshots side-by-side (B − A).

    Shows metrics from both snapshots and computed deltas.

    Example:
        metabokg snapshot diff abc123 def456
    """
    snapshots_path = (
        Path(snapshots_dir).resolve() if snapshots_dir else Path.cwd() / ".metabokg" / "snapshots"
    )
    mgr = SnapshotManager(snapshots_path)
    result = mgr.diff_snapshots(key_a, key_b)

    if "error" in result:
        click.echo(f"Error: {result['error']}", err=True)
        raise click.Abort()

    if output_json:
        click.echo(json.dumps(result, indent=2))
        return

    a = result["a"]
    b = result["b"]
    click.echo(f"Comparing {a['key'][:10]} → {b['key'][:10]}")
    click.echo()
    click.echo(f"{'Metric':<22} {'A':>10} {'B':>10} {'Δ':>10}")
    click.echo("-" * 56)

    for metric_key in ["total_nodes", "total_edges", "pathway_count", "kinetic_params"]:
        val_a = a["metrics"].get(metric_key, 0)
        val_b = b["metrics"].get(metric_key, 0)
        delta = val_b - val_a
        label = metric_key.replace("_", " ").title()
        click.echo(f"{label:<22} {val_a:>10} {val_b:>10} {delta:>+10d}")

    ncd = result.get("node_counts_delta", {})
    if any(v != 0 for v in ncd.values()):
        click.echo()
        click.echo("Node Count Changes:")
        for kind, delta in sorted(ncd.items()):
            if delta != 0:
                click.echo(f"  {kind}: {delta:+d}")

    ecd = result.get("edge_counts_delta", {})
    if any(v != 0 for v in ecd.values()):
        click.echo()
        click.echo("Edge Count Changes:")
        for rel, delta in sorted(ecd.items()):
            if delta != 0:
                click.echo(f"  {rel}: {delta:+d}")


# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------

snapshot_main = snapshot
