# MetaboKG MCP Integration Guide

**Exposing the metabolic knowledge graph to Claude Code, Claude Desktop, and other MCP agents**

*Author: Eric G. Suchanek, PhD*

---

## Overview

MetaboKG ships a built-in MCP server (`metabokg-mcp`) that exposes the graph,
the semantic index, and the simulation engine as structured tools consumable by
any MCP-compatible agent — Claude Code, Claude Desktop, GitHub Copilot, Cline,
or a custom client that speaks the Model Context Protocol.

The server is a thin wrapper over the same `MetaKG` orchestrator that the CLI
and the Python API use, so there is exactly one code path per capability. `mcp`
is a **core dependency** — there is no optional extra to install and no
separate server package.

---

## Quick start

```bash
# 1. Install (mcp is core — no extra needed)
poetry install

# 2. Build a corpus; this writes both the graph and the vector store
metabokg-init                            # all bundled corpora
# ...or a single corpus:
metabokg-build --data data/hsa_pathways

# 3. Point your agent at the server (see the per-agent sections below)

# 4. Restart the agent — the metabokg tools become available
```

Verify the server is installed before wiring any agent to it:

```bash
metabokg-mcp --help
```

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Server options](#2-server-options)
3. [Claude Code / Kilo Code](#3-claude-code--kilo-code)
4. [GitHub Copilot](#4-github-copilot)
5. [Claude Desktop](#5-claude-desktop)
6. [Multi-corpus setup](#6-multi-corpus-setup)
7. [Tool reference](#7-tool-reference)
8. [Query strategy](#8-query-strategy)
9. [Rebuilding after data changes](#9-rebuilding-after-data-changes)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

The server reads two artifacts, both produced by a build:

| Artifact | Default path | Produced by |
|---|---|---|
| Graph database | `data/hsa_pathways/.metabokg/hsa.sqlite` | `metabokg-build` / `metabokg-init` |
| Vector store | `data/hsa_pathways/.metabokg/vectors.sqlite` | the same build, unless `--no-index` |

Check what exists without modifying anything:

```bash
metabokg info
metabokg-init --check
```

`metabokg info` prints the resolved paths and marks each store `[exists]` or
`[not built]`. The server still starts without them, but semantic tools return
nothing until a build has run.

---

## 2. Server options

```bash
metabokg-mcp [--db PATH] [--vectors PATH] [--model NAME] [--transport stdio|sse]
```

| Flag | Default | Description |
|---|---|---|
| `--db PATH` | `data/hsa_pathways/.metabokg/hsa.sqlite`, or `METABOKG_DB` | Graph database |
| `--vectors PATH` | `data/hsa_pathways/.metabokg/vectors.sqlite`, or `METABOKG_VECTORS` | sqlite-vec vector store |
| `--model NAME` | `BAAI/bge-small-en-v1.5` | Sentence-transformer model |
| `--transport` | `stdio` | `stdio` for Claude Desktop/Code, `sse` for HTTP |

Both paths also resolve from the environment:

```bash
export METABOKG_DB="/data/hsa.sqlite"
export METABOKG_VECTORS="/data/vectors.sqlite"
metabokg-mcp --transport sse
```

> As of 0.10.0 the vector store is a single `vectors.sqlite` **file**, not a
> directory. Configs that predate the migration pass `--lancedb` and now fail
> with `no such option`. See the [CHANGELOG](../CHANGELOG.md) `[0.10.0]` entry.

---

## 3. Claude Code / Kilo Code

Both read MCP servers from **`.mcp.json`** in the project root.

```json
{
  "mcpServers": {
    "metabokg": {
      "command": "poetry",
      "args": [
        "run", "metabokg-mcp",
        "--db", "data/hsa_pathways/.metabokg/hsa.sqlite",
        "--vectors", "data/hsa_pathways/.metabokg/vectors.sqlite"
      ]
    }
  }
}
```

If `.mcp.json` already lists servers, add `metabokg` to the existing
`mcpServers` object rather than replacing the file.

> **Per-repo only.** Do not add `metabokg` to a global settings file. Global
> config is shared across every window, so hardcoded corpus paths would point
> all of them at one repo.

Restart Claude Code (or reload the Kilo Code MCP panel) to pick up the change.

---

## 4. GitHub Copilot

Copilot reads **`.vscode/mcp.json`**, which uses a `servers` key rather than
`mcpServers`. This repo ships a working example:

```json
{
  "servers": {
    "metabokg": {
      "type": "stdio",
      "command": "poetry",
      "args": [
        "run", "metabokg-mcp",
        "--db", "data/hsa_pathways/.metabokg/hsa.sqlite",
        "--vectors", "data/hsa_pathways/.metabokg/vectors.sqlite"
      ],
      "env": { "POETRY_VIRTUALENVS_IN_PROJECT": "false" }
    }
  }
}
```

VS Code prompts to **Trust** the server on first load; the tools appear in
Copilot Chat afterwards.

---

## 5. Claude Desktop

Claude Desktop's config is global and does not inherit your shell, so it needs
absolute paths — including an absolute path to the executable.

Find the binary:

```bash
poetry run which metabokg-mcp
```

Then add it to `claude_desktop_config.json` (macOS:
`~/Library/Application Support/Claude/`):

```json
{
  "mcpServers": {
    "metabokg": {
      "command": "/absolute/path/to/venv/bin/metabokg-mcp",
      "args": [
        "--db", "/absolute/path/to/metabo_kg/data/hsa_pathways/.metabokg/hsa.sqlite",
        "--vectors", "/absolute/path/to/metabo_kg/data/hsa_pathways/.metabokg/vectors.sqlite"
      ]
    }
  }
}
```

Restart Claude Desktop to activate it.

---

## 6. Multi-corpus setup

Each organism or model builds into its own graph and vector store, so run one
server per corpus and give each a distinct key:

```json
{
  "mcpServers": {
    "metabokg-hsa": {
      "command": "/abs/path/to/venv/bin/metabokg-mcp",
      "args": [
        "--db", "/abs/path/data/hsa_pathways/.metabokg/hsa.sqlite",
        "--vectors", "/abs/path/data/hsa_pathways/.metabokg/vectors.sqlite"
      ]
    },
    "metabokg-cge": {
      "command": "/abs/path/to/venv/bin/metabokg-mcp",
      "args": [
        "--db", "/abs/path/data/cge_pathways/.metabokg/cge.sqlite",
        "--vectors", "/abs/path/data/cge_pathways/.metabokg/vectors.sqlite"
      ]
    }
  }
}
```

For federated queries spanning corpora — and across sibling knowledge graphs —
register each corpus with KGRAG instead of wiring N servers by hand. See the
[multi-corpus convention](../CLAUDE.md#multi-corpus-convention-kgrag).

---

## 7. Tool reference

The server registers **13** tools. Required parameters are shown in **bold**.

### Retrieval and search

| Tool | Parameters | Purpose |
|---|---|---|
| `pack` | **`text`**, `k`, `hop` | Build a context-rich metabolic pack from a semantic query |
| `query_pathway` | **`name`**, `k` | Find pathways by name or description using semantic search |
| `get_compound` | **`compound_id`** | Retrieve a compound by internal or external database ID |
| `get_reaction` | **`reaction_id`** | Retrieve a reaction with full substrate/product/enzyme context |
| `find_path` | **`compound_a`**, **`compound_b`**, `max_hops` | Shortest metabolic path between two compounds |

### Simulation

| Tool | Parameters | Purpose |
|---|---|---|
| `simulate_fba` | **`pathway_id`**, `objective_reaction`, `maximize` | Flux Balance Analysis (steady state) |
| `simulate_ode` | **`pathway_id`**, `t_end`, `t_points`, `initial_concentrations_json`, `default_concentration` | Kinetic ODE simulation with Michaelis-Menten rates |
| `simulate_whatif` | **`pathway_id`**, **`scenario_json`**, `mode` | Perturbation analysis: baseline vs. modified scenario |

### Kinetics

| Tool | Parameters | Purpose |
|---|---|---|
| `get_kinetic_params` | **`reaction_id`** | Retrieve stored kinetic parameters for a reaction |
| `seed_kinetics` | `force` | Seed the database with curated literature kinetic parameters |

### Snapshots

| Tool | Parameters | Purpose |
|---|---|---|
| `snapshot_list` | `limit` | List metric snapshots, newest first |
| `snapshot_show` | **`key`** | Full details for a single snapshot |
| `snapshot_diff` | **`key_a`**, **`key_b`** | Compare two snapshots (B − A) |

> ODE simulations are stiff. The default solver is `BDF`; **RK45 will hang** on
> metabolic pathways.

Node IDs follow `<kind>:<source>:<accession>` — for example `cpd:kegg:C00031`
(D-glucose), `rxn:kegg:R00200`, `pwy:kegg:hsa00010` (glycolysis),
`enz:kegg:hsa:2539`.

---

## 8. Query strategy

`pack` is the workhorse: one call returns matched nodes plus their biological
context, replacing many KEGG API round-trips.

| Goal | Call |
|---|---|
| Broad orientation | `pack(text="glucose metabolism", k=8, hop=1)` |
| Deep context on a pathway | `pack(text="fatty acid oxidation", k=5, hop=2)` |
| Just the ranked pathway hits | `query_pathway(name="glycolysis", k=10)` |
| A specific entity you already know | `get_compound` / `get_reaction` |
| Connectivity between metabolites | `find_path(compound_a=..., compound_b=...)` |

`hop` expands BFS steps along typed edges (`SUBSTRATE_OF`, `PRODUCT_OF`,
`CATALYZES`, `CONTAINS`, `INHIBITS`, `ACTIVATES`, `XREF`), so reaction context
arrives alongside whatever matched semantically. `hop=0` returns seeds only.

---

## 9. Rebuilding after data changes

A full build wipes and rebuilds both stores:

```bash
metabokg-build --data data/hsa_pathways
```

To merge new pathway files without wiping:

```bash
metabokg-update --data data/hsa_pathways
```

Restart the MCP server afterwards — it holds an open handle to the graph.

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `database not found` | No build has run | `metabokg-init`, or `metabokg-build --data DIR` |
| `Vector index not found` | Built with `--no-index` | Rebuild without `--no-index` |
| `no such option: --lancedb` | Config predates 0.10.0 | Use `--vectors PATH` (a file, not a directory) |
| Semantic tools return nothing | Vector store empty or stale | `metabokg info` to check, then rebuild |
| Server missing from the agent | Config not reloaded | Restart the agent fully |
| Claude Desktop cannot start it | Relative paths in a global config | Use absolute paths for the binary and both stores |
| ODE simulation hangs | Non-stiff solver selected | Use `BDF` or `Radau`, never `RK45` |
| Results look stale | Data changed since the build | Rebuild, then restart the server |

---

## Summary

| Question | Answer |
|---|---|
| What must exist first? | `<corpus>.sqlite` and `vectors.sqlite` under `.metabokg/` |
| How do I build them? | `metabokg-init`, or `metabokg-build --data DIR` |
| How do I start the server? | `metabokg-mcp [--db PATH] [--vectors PATH]` |
| How many tools? | 13 — retrieval, simulation, kinetics, snapshots |
| Where does per-repo config live? | `.mcp.json` (Claude Code/Kilo), `.vscode/mcp.json` (Copilot) |
| Is the server stateful? | Yes — one `MetaKG` instance per server process |
| What transport should I use? | `stdio` for Claude Code / Desktop; `sse` for HTTP clients |

**See also:** [INSTALL.md](INSTALL.md) for full installation,
[CHEATSHEET.md](CHEATSHEET.md) for CLI flags, and
[`.claude/skills/metabokg/SKILL.md`](../.claude/skills/metabokg/SKILL.md) for
the agent-facing skill.
