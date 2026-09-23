# Release Notes -- v0.17.0

> Released: 2026-09-23

A graph-only rebuild no longer leaves the previous graph's vector index in
place. Before this release, `metabokg build --no-index` wiped and rewrote the
graph but kept `vectors.sqlite`, so later semantic queries were answered from
vectors that described a graph that no longer existed.

## What changed

**Wiping the graph now drops the index it invalidates.** When `MetaKG.build()`
wipes the graph and is told not to rebuild the index, it now deletes the
sqlite-vec store and its `-wal`, `-shm` and `-journal` sidecars. A query run
afterwards fails with "vector index not found" and tells you to rebuild,
instead of returning results from the old graph. An unwiped build, such as
`metabokg update --no-index`, keeps the existing index as before, because the
graph it describes is still there.

The same defect was fixed for every `KGModule` in `kgmodule-utils` 0.24.0.
`MetaKG` runs its own build pipeline rather than inheriting that one, so it
needed its own fix. The new public `MetaKG.drop_index()` matches the SDK's
method of the same name and returns the paths it removed. It never loads the
embedding model, so a graph-only rebuild stays fast. `MetaIndex` gains a
`close()` method.

**Dependency floor.** `kgmodule-utils` now requires 0.24.0, and the lock has
moved onto it. No other locked package changed.

## Upgrading

Nothing to do for a normal build. If you built with `--no-index` after a wipe
on an earlier version, your `vectors.sqlite` may describe an older graph; run
`metabokg build` without `--no-index` once to bring it back in line.

The architectural analysis under `docs/` has been regenerated for this release
and is now `docs/analysis_v0.17.0.md`.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
