# Release Notes -- v0.18.0

> Released: 2026-10-26

MetaboKG's MCP server now runs on the fleet's shared base, `kg_utils.mcp`, so
its first five tools have the same names on every fleet KG server: `stats`,
`query`, `pack`, `get_node` and `neighbors`. Its twelve metabolic tools
(`query_pathway`, `find_path`, the FBA, ODE and what-if simulators, the
kinetics and snapshot tools) are unchanged. `MetaKG.stats()` now returns the
fleet's statistics shape.

## What changed

**Canonical tools.** `stats`, `query`, `pack`, `get_node` and `neighbors` come
first, then the twelve domain tools: 13 tools become 17. `pack` takes `q`
instead of `text` and gains `max_nodes` and `rels`; `query`, `get_node` and
`neighbors` are new on the server. The server's instructions are generated
from the tools' docstrings.

**One command, standard flags.** `metabokg mcp` takes the fleet's `--repo`,
`--db`, `--vectors`, `--model`, `--transport stdio|streamable-http`, `--host`,
`--port` and `--manifest`. `--db` and `--vectors` still fall back to
`METABOKG_DB` / `METABOKG_VECTORS` and then the bundled human corpus, so
existing configs keep working. `metabokg-mcp` is the same command. The graph
opens per session, and a database that does not exist is refused instead of
served empty.

**Statistics in the fleet shape.** `MetaKG.stats()` returns `kind`
(`metabolic`), `nodes` (`total`, `by_kind`) and `edges` (`total`, `by_rel`),
plus `pathway_count`, `compound_count` and `reaction_count`. Snapshots keep
their flat keys.

**New graph methods.** `MetaKG.node()` and `MetaKG.neighbors()` read one node
and its edges without loading the embedding model.

## Upgrading

Pass `q` instead of `text` to `pack`, and drop `--transport sse` from any
config. Code that read `MetaKG.stats()["node_count"]` reads `["nodes"]["total"]`
instead. `metabokg.mcp_tools.create_server()` and `register_tools()` are gone:
use `build_server(db, vectors, model)`, or mount `EXTRA_TOOLS` on another
`kg_utils.mcp` server. metabo-kg now needs kgmodule-utils 0.29.0, whose
`[mcp]` extra brings the MCP SDK.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
