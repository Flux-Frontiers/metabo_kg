# Release Notes -- v0.16.0

> Released: 2026-09-21

MetaboKG's MCP server now closes the pathway database when it shuts down. No
index rebuild, no migration, no CLI change.

## What changed

**The MCP server closes the graph on shutdown.** `metabokg mcp` wires an
`asynccontextmanager` into `FastMCP(lifespan=...)`, so the SQLite connection is
released when the server stops rather than left to process exit. One hook
covers both the stdio and SSE transports, because both route through the same
underlying `Server.run()`.

MetaboKG's server is built by a factory that is handed the `MetaKG` instance,
so the hook closes that object directly rather than looking up a module-level
global the way the other modules in the fleet do. The behaviour is the same;
only the wiring differs.

This is the resource-cleanup pattern the fleet standardised on, verified
against a real server run rather than a stubbed `close`.

## Upgrading

Nothing to do. If you run `metabokg mcp` inside a long-lived process, it now
leaves no database handle behind when it stops.

The architectural analysis under `docs/` has been regenerated for this release
and is now `docs/analysis_v0.16.0.md`.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
