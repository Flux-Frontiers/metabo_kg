# Release Notes — v0.9.1

> Released: 2026-07-29

A dependency-correctness release. The headline is a hard upper bound on `mcp`: a clean
install of MetaboKG could resolve mcp 2.x, which breaks the MCP server the moment it is
built. If `metabokg mcp` failed to start with an error about `mcp.server.fastmcp`,
upgrading fixes it.

## What changed

**`mcp` bounded below 2.0.** mcp 2.0 split FastMCP out into a standalone `fastmcp` package
and removed the bundled `mcp.server.fastmcp` module, so the previous unbounded
`mcp>=1.0.0` let a fresh install pick up 2.x. Developers never saw it — a pinned lock file
keeps every local checkout working, which is exactly how this reached the index across the
KG family before anyone noticed. The bound stays until the server is ported to the
standalone package.

**Regression tests shaped to how MetaKG actually builds its server.** MetaboKG differs from
its sibling KGs in a way that matters here: it does not construct the server at module
import. `create_server()` builds `FastMCP` behind a function-level import and
`register_tools()` attaches the tools imperatively. An import-only test — the pattern used
in the sibling repos — would therefore pass against an incompatible `mcp` while
`metabokg mcp` stayed dead on arrival. The new `tests/test_mcp_server.py` calls
`create_server()` for real and asserts all thirteen tools register. Building a throwaway
server costs nothing, because `MetaKG.__init__` only resolves paths — no database or index
is opened.

**Housekeeping: `.gitignore` normalized across the KG fleet.** All eleven KG repos now
share one canonical set of ignore rules — databases, vector indexes and model caches are
ignored; `snapshots/` never is. The rules are written so MetaboKG's nested snapshot store
at `data/hsa_pathways/.metabokg/snapshots/` stays tracked.

## Upgrading

Nothing to do beyond upgrading. No rebuild, no migration, no API change. If you had pinned
`mcp` yourself to work around the crash, you can drop that pin.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
