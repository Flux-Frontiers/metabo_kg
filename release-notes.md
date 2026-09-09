# Release Notes — v0.15.0

> Released: 2026-09-08

MetaboKG 0.15.0 finishes the move onto the fleet's shared snapshot model that
0.14.0 started. The module no longer carries its own `SnapshotManager`
constructor, and it now requires the `kgmodule-utils` release that makes that
possible. The tooling pins on `doc-kg` and `pycode-kg` are raised to match.

## What changed

**The snapshot manager loses its constructor.** `SnapshotManager.__init__`
existed only to forward a package name to the base class, the same one-string
override that seven of the fleet's eight KG modules were carrying.
`kgmodule-utils` 0.20.0 added a `package_name` class attribute for exactly
this, so the override is gone. `capture()` stays, because it does more than
build a metrics dict: it back-fills the `hotspots` field from the hub
metabolites, and that field lives outside the metrics the shared hook can
supply. `load_snapshot()` also stays, still reading the legacy
`hub_metabolites` key from the snapshots committed under `data/hsa_pathways/`.

**A hard floor on `kgmodule-utils`.** The dependency now requires 0.20.0 or
later. Against 0.19.x the base class has no `package_name` attribute, so every
snapshot's `tool` field would silently read `"kg-utils"` instead of
`"metabo-kg"`.

**Tooling pins catch up.** The optional `kg` group pinned `doc-kg` and
`pycode-kg` four and five releases behind. Both now floor on the releases that
retired their own snapshot overrides (doc-kg 0.26.0, pycode-kg 0.27.0), so
`poetry install --with kg` cannot resolve a `dockg` or `pycodekg` that predates
the shared extension points into an environment that depends on them.

## Upgrading

Run `poetry install` (or `pip install --upgrade metabo-kg`) to pick up the
`kgmodule-utils` floor. No rebuild of any corpus is needed, and existing
snapshot files load unchanged. If your code subclassed `SnapshotManager` and
called its `__init__` with a package name, drop that call: the base
constructor takes no arguments and the name comes from the class attribute.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
