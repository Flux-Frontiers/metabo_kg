# Release Notes — v0.12.0

> Released: 2026-08-15

A packaging-hygiene release, and the one that removes the per-subcommand console
scripts. If you invoke `metabokg-build`, `metabokg-analyze`, `metabokg-simulate` or any
of their siblings from a script, a Makefile or a shell alias, those commands are gone in
this version — use `metabokg <subcommand>` instead. `metabokg-mcp` deliberately survives.
Everything else here is about what the published wheel offers a consumer versus what the
repo needs for its own maintenance, a line that had blurred.

## What changed

**The per-subcommand aliases are gone.** Fourteen console scripts each had an identical
`metabokg <subcommand>` form already exposed by the Click group, so they bought nothing
but a saved keystroke — while making every new command ask whether it needed an alias, a
question that had already drifted (`install-hooks` never got one). `metabokg-mcp` is the
exception and stays: the documented Claude Desktop and Copilot setups write that path
into users' config files, so removing it would break their MCP server on upgrade with a
"command not found" that reads as a broken install. This matches pycode_kg 0.23.0.

**Dev tooling left the published metadata.** `metabo-kg[dev]` advertised the maintainer
toolchain — pytest, ruff, ty, and repo-reasoned pins such as `ruff<0.16` — in wheel
metadata, offering it to every consumer. An extra is a feature of the package; dev
tooling is a property of the repo. It now lives in an optional Poetry group. There is no
pip path for it on purpose.

**The `all` aggregate extra is removed.** It re-listed every other extra *plus* the dev
tooling, so `pip install metabo-kg[all]` quietly installed a test and lint stack. An
aggregate also duplicates each package in the marker space, which is what sends
`poetry lock` into resolution restarts. The wheel now advertises four extras — `biopax`,
`simulate`, `viz`, `viz3d` — and no dev tooling in `Requires-Dist`.

**Version reporting can no longer drift.** `metabokg.__version__` is derived from
installed package metadata rather than a hardcoded literal. 0.11.0 fixed the symptom —
the literal had reached 0.9.1 while `pyproject.toml` said 0.10.0, mislabelling every
analysis report in between — but left the mechanism intact. A third stale literal,
`metabokg.cli.__version__`, sat at 0.4.0 and is deleted rather than corrected.

**Dependency floors moved to the current fleet releases.** `kgmodule-utils` is now
`>=0.13.1` specifically, because 0.13.1 is the release that stops snapshots recording
absolute paths — this repo's committed `.dockg` snapshots are rewritten to relative form
in the same change, and against 0.13.0 the pre-commit hook would restore the absolute
paths on the next run.

**`.mcp.json` addressed the wrong workspace.** `WORKSPACE_ID` was `code_kg`, so this
repo's copilot-memory and task-copilot state was filed under a sibling project's
namespace. It is now `metabo_kg`.

## Upgrading

Replace any `metabokg-<subcommand>` invocation with `metabokg <subcommand>` — the
arguments are unchanged. Leave `metabokg-mcp` alone; it still works and your MCP client
config needs no edit.

If you installed with `pip install metabo-kg[all]`, that extra no longer exists; use
`poetry install --all-extras`, or name the extras you actually want. Maintainers who used
`poetry install --extras dev` want `poetry install --with dev` now, and
`poetry install --extras kgdeps` became `poetry install --with kg`.

No database rebuild, no migration, and no change to the Python API or the MCP tools.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
