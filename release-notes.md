# Release Notes — v0.13.0

> Released: 2026-09-06

MetaboKG doesn't subclass the fleet's shared snapshot model — it has its own
dataclass, and this release brings its snapshot keying up to the same
standard the rest of the fleet just adopted, by hand rather than by
inheritance.

## What changed

**Snapshots are keyed on a release tag or timestamp, not a git tree hash.**
The tree hash was read before `git add` staged the snapshot, so it named a
tree that was never committed — across the fleet, only 63 of 605 snapshot
keys ever resolved. Because this repo's `Snapshot` predates and doesn't
inherit from `kgmodule-utils`'s shared model, the fix couldn't arrive as a
dependency bump: the same semantics — a supplied key with a timestamp
fallback, `tree_hash` kept as provenance rather than identity, and a
manifest reader that stays backward-compatible with old tree-hash keys — are
implemented directly here. `metabokg snapshot save VERSION` now uses VERSION
as the key; pass it explicitly at release time, since an omitted VERSION is
auto-detected from the installed package and would key the snapshot on the
*tool's* version rather than the thing it measured. `subject`, `tool` and
`tool_version` are new fields that make that distinction explicit going
forward.

**`watchdoc` is gone.** It was a declared runtime dependency that nothing in
this codebase imports — a leftover, unrelated to `watchdog`, that every
install of the published package paid for regardless.

**Two `ty` suppression cycles are resolved.** Nine `# ty: ignore` comments in
`snapshots.py` were removed as dead weight, then restored days later when a
dependency floor bump made the type checker start flagging the same
intentional Liskov mismatch it always had. Both states are in the historical
record here for anyone who finds the diff confusing later.

**A real commit-time test failure is fixed.** `tests/test_hooks.py` built
throwaway repos and committed inside them — which broke specifically when run
from an actual git hook, because git had already pointed `GIT_DIR` and
`GIT_INDEX_FILE` at the outer repo. The inner commits inherited those and
wrote into the wrong tree. Neither `pre-commit run --all-files` nor CI ever
reproduced it, since neither runs mid-commit; it failed only for real
commits, every time.

**Dependency floors move again**: `kgmodule-utils` to `>=0.19.0` for the
snapshot work above, continuing the `>=0.13.1` → `>=0.13.2` correction from
earlier this cycle that fixed a read-only `repo_root` property breaking this
repo's `SnapshotManager` subclass.

## Upgrading

Nothing to migrate. Existing snapshots keep their keys and stay addressable.
This release is GitHub-only, matching how every prior MetaboKG release has
shipped — it is not published to PyPI.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
