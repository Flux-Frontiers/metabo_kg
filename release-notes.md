# Release Notes — v0.14.0

> Released: 2026-09-06

MetaboKG's snapshot support moves onto the fleet's shared model, replacing a
parallel data model that had stood since before the fleet adopted a common
snapshot schema.

## What changed

**The standalone `Snapshot`, `SnapshotMetrics`, `SnapshotDelta`, and
`SnapshotManifest` dataclasses are gone.** MetaboKG defined its own copies of
all four, none derived from `kg_utils.snapshots`, and overrode every public
manager method to operate on them. That parallel model meant fleet-wide
snapshot fixes reached this repo only by being reimplemented here — the
0.19.0 key-scheme fix had to be hand-copied into this module's own logic
rather than simply inherited.

`Snapshot`, `SnapshotManifest`, and `PruneResult` are now re-exported from
`kg_utils.snapshots` unchanged. A snapshot's `metrics`, `vs_previous`, and
`vs_baseline` are plain dicts. `SnapshotMetrics` and `SnapshotDelta` remain
available as converters for code that wants attribute access. Top hub
metabolites move into the shared `hotspots` field; snapshots written before
this release carry them under a legacy `hub_metabolites` key, which
`load_snapshot` still reads transparently.

**The `kgmodule-utils` 0.19.1 delta-backfill fix now reaches MetaboKG.**
Loading a saved snapshot previously reported `kinetic_params_delta` and
`pathway_delta` as absent, even though listing and diffing snapshots
computed them correctly for the same pair — the exact read path
`snapshot show` uses was the one giving the wrong answer. With the floor
resolving to 0.19.1, `snapshot show` now reports the same numbers as every
other view of a snapshot.

## Upgrading

No action required for normal use — snapshot files, the CLI, and the MCP
tools are unchanged. If your code accessed `Snapshot.metrics` as an object
with attributes (`snap.metrics.total_nodes`), switch to dict access
(`snap.metrics["total_nodes"]`) or call `metrics_from_dict(snap.metrics)`
for the old style with attribute access.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
