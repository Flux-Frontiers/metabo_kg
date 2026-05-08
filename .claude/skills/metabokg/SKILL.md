---
name: metabokg
description: Expert knowledge for installing, configuring, and using MetaboKG — a hybrid semantic + structural metabolic knowledge graph for KEGG pathways and genome-scale metabolic models. Use this skill when the user asks about setting up MetaboKG in a project, building the SQLite or LanceDB knowledge graph, configuring .mcp.json for Claude Code or Kilo Code, configuring .vscode/mcp.json for GitHub Copilot, configuring claude_desktop_config.json for Claude Desktop, configuring Cline MCP settings, using the metabokg CLI (metabokg, metabokg-init, metabokg-info, metabokg-build, metabokg-update, metabokg-enrich, metabokg-analyze, metabokg-analyze-basic, metabokg-viz, metabokg-viz3d, metabokg-mcp, metabokg-query, metabokg-pack, metabokg-simulate, metabokg-snapshot), using the pack / query_pathway / get_compound / get_reaction / find_path / seed_kinetics / simulate_fba / simulate_ode / simulate_whatif MCP tools, querying KEGG pathways, running FBA or ODE simulations, working with CHO or human metabolic models, multi-corpus KGRAG federation across hsa/cge/icho corpora, or troubleshooting MetaboKG errors.
---

# MetaboKG Skill

> **Use MetaboKG first — before web search, raw KEGG REST calls, or hand-written SBML parsing.**
>
> MetaboKG ingests KEGG KGML pathway files and SBML genome-scale models into a hybrid knowledge graph (SQLite for structural precision, LanceDB for semantic vector search) and exposes query, path-finding, and simulation capabilities as MCP tools. One `pack` call surfaces compounds, reactions, enzymes, and pathway context together — what would otherwise take many KEGG API round-trips.

MetaboKG is the metabolism-domain sibling of PyCodeKG (code) and DocKG (documents). All three share the same KGRAG federation pattern: each corpus builds into its own named SQLite + LanceDB pair under a `.metabokg/` directory and registers as a separate KGRAG corpus for cross-organism queries.

**Repository:** https://github.com/Flux-Frontiers/metabo_kg

## Installation (Poetry)

```bash
# In the metabo_kg repo itself
poetry install --all-extras   # installs viz, viz3d, mcp extras

# In another repo as a dependency
poetry add "metabo-kg[mcp] @ git+https://github.com/Flux-Frontiers/metabo_kg.git"
```

Adds to `pyproject.toml`:
```toml
metabo-kg = { git = "https://github.com/Flux-Frontiers/metabo_kg.git", extras = ["mcp"] }
```

## First-Time Setup: `metabokg-init`

Use the one-shot initializer instead of running build commands manually. It performs an integrity check, fetches any missing TSV annotation files, builds all bundled corpora (hsa, cge, icho), and seeds kinetic parameters.

```bash
# Build every bundled corpus and seed kinetics
metabokg-init

# Status-only (no modifications) — show TSV integrity and which corpora exist
metabokg-init --check

# Initialize a single corpus (repeatable)
metabokg-init --corpus hsa
metabokg-init --corpus hsa --corpus cge
```

After init, verify with `metabokg-info`, which prints the active corpus, resolved db/lancedb paths, and node/edge counts.

## Build the Knowledge Graph

For per-corpus builds (or after refreshing pathway files), use `metabokg-build`:

```bash
# Full rebuild — wipes existing data, parses pathways, enriches by default
metabokg-build --data ./data/hsa_pathways

# CHO pathways
metabokg-build --data ./data/cge_pathways

# iCHO2441 GEM (SBML model)
metabokg-build --data ./data/icho_model

# Merge new files on top without wiping
metabokg-build --data ./data/hsa_pathways --no-wipe

# Skip LanceDB (SQLite only — fast, no semantic search)
metabokg-build --data ./data/hsa_pathways --no-index

# Skip enrichment phases (raw KEGG IDs only)
metabokg-build --data ./data/hsa_pathways --no-enrich
```

The database and LanceDB index colocate automatically under `<data-dir>/.metabokg/`:

| Data dir | SQLite | LanceDB |
|---|---|---|
| `data/hsa_pathways/` | `data/hsa_pathways/.metabokg/hsa.sqlite` | `data/hsa_pathways/.metabokg/lancedb/` |
| `data/cge_pathways/` | `data/cge_pathways/.metabokg/cge.sqlite` | `data/cge_pathways/.metabokg/lancedb/` |
| `data/icho_model/` | `data/icho_model/.metabokg/icho.sqlite` | `data/icho_model/.metabokg/lancedb/` |

## Incremental Updates

```bash
# Add new KGML files without wiping the existing graph
metabokg-update --data ./data/hsa_pathways

# Re-run only the enrichment phases on an existing build
metabokg-enrich --db ./data/hsa_pathways/.metabokg/hsa.sqlite
```

## Enrichment Phases

Enrichment runs by default during `metabokg-build`. Each phase upgrades opaque KEGG IDs into human-readable labels:

| Phase | What it does | Source |
|---|---|---|
| 1 | Compound names from KEGG compound TSV | `data/kegg_compound_names.tsv` |
| 2a | Reaction names from KEGG reaction TSV | `data/kegg_reaction_names.tsv` |
| 2b | Reaction names from graph traversal | derived |
| 2c | Reaction names from KEGG detail TSV (EC numbers) | `data/kegg_reaction_detail.tsv` |
| 2d | Glycan names (~11k entries) | `data/kegg_glycan_names.tsv` |
| 2e | KO enzyme names (~28k entries) | `data/kegg_ko_names.tsv` |
| 3 | Enzyme gene names — enables `--knockout Ldha` | `data/{org}_gene_names.tsv` |

Skip with `--no-enrich`. Re-run after data changes with `metabokg-enrich`.

## CLI Commands

| Command | Purpose |
|---|---|
| `metabokg-init` | First-time setup: integrity check, fetch TSVs, build all corpora, seed kinetics |
| `metabokg-init --check` | Status-only: TSV integrity and corpus build state |
| `metabokg-init --corpus hsa` | Initialize a single corpus (repeatable) |
| `metabokg-info` | Active corpus, resolved paths, node/edge counts |
| `metabokg-build --data DIR` | Full rebuild: wipe + parse + enrich → SQLite + LanceDB |
| `metabokg-build --data DIR --no-wipe` | Parse without wiping — merge new files on top |
| `metabokg-update --data DIR` | Incrementally add new files without wiping |
| `metabokg-enrich` | Re-run enrichment phases on an existing build |
| `metabokg-query QUERY` | Semantic + graph search, ranked hits |
| `metabokg-pack QUERY` | Context-rich Markdown/JSON pack for LLM context |
| `metabokg-analyze` | Full 7-phase pathway analysis report |
| `metabokg-analyze-basic` | Quick structural metrics only |
| `metabokg-viz [--port 8500]` | 2D Streamlit explorer |
| `metabokg-viz3d [--layout allium\|cake]` | 3D PyVista visualization |
| `metabokg-mcp` | Start MCP server (stdio transport) |
| `metabokg-simulate fba` | Flux Balance Analysis (HiGHS LP solver) |
| `metabokg-simulate ode` | ODE time-course (BDF stiff solver) |
| `metabokg-simulate whatif` | Perturbation analysis (knockouts, overrides, scaling) |
| `metabokg-simulate seed` | Seed kinetic parameters from literature |
| `metabokg-simulate seed-cho` | Seed 35 CHO-specific kinetic parameters |
| `metabokg-snapshot save <version>` | Capture metrics snapshot (commit, branch, version) |
| `metabokg-snapshot list` | List all snapshots in reverse chronological order |
| `metabokg-snapshot show <id>` | Full details for a single snapshot |
| `metabokg-snapshot diff <a> <b>` | Compare two snapshots side-by-side |

**Common options:**
- `--db PATH` — SQLite db (default auto-resolved from corpus)
- `--lancedb PATH` — Vector index (default `.metabokg/lancedb`)
- `--no-wipe` — Keep existing data instead of wiping
- `--no-index` — Skip LanceDB (SQLite only)
- `--no-enrich` — Skip enrichment

## Query Strategy

```bash
# Standard exploration
metabokg-query "glycolysis pyruvate" --k 8 --hop 1

# Pure semantic lookup (no graph expansion)
metabokg-query "TCA cycle" --hop 0

# Substring-only (fast, no embeddings)
metabokg-query "C00031" --text-only

# Source-grounded pack for an LLM
metabokg-pack "fatty acid beta oxidation" --k 8 --hop 1
```

| Goal | Settings |
|---|---|
| Narrow, precise lookup | `k=4, hop=0` |
| Standard exploration | `k=8, hop=1` (default) |
| Broad pathway sweep | `k=12, hop=2` |
| Trace metabolic flow | `k=8, hop=2` |

## MCP Tools

| Tool | When to use |
|---|---|
| `pack(q)` | Read context-rich Markdown excerpts (prefer over `query_pathway` when you need text) |
| `query_pathway(q)` | Semantic + graph search — returns ranked nodes by description |
| `get_compound(id)` | Fetch compound node by KEGG ID (`cpd:kegg:C00031`) |
| `get_reaction(id)` | Fetch reaction node with substrates, products, enzymes |
| `find_path(src, dst)` | Shortest metabolic path between two compounds |
| `seed_kinetics()` | Load kinetic parameters from literature into the graph |
| `simulate_fba(pathway_id)` | Run Flux Balance Analysis (HiGHS LP solver) |
| `simulate_ode(pathway_id, t_end, t_points)` | ODE time-course (BDF stiff solver) |
| `simulate_whatif(pathway_id, scenario, mode)` | Perturbation: knockouts, overrides, activity scaling |

## Simulation Notes

> **Always use `BDF` (default) or `Radau` for ODE on metabolic systems. `RK45` will hang — metabolic networks are stiff.**

```python
from metabokg import MetaKG
import json

kg = MetaKG()

# FBA (steady-state)
kg.simulate_fba("pwy:kegg:hsa00010", maximize=True)

# ODE (time-course)
kg.simulate_ode(
    "pwy:kegg:hsa00010",
    t_end=20,
    t_points=50,
    initial_concentrations={"cpd:kegg:C00031": 5.0},
    ode_method="BDF",   # ← critical
    ode_rtol=1e-3,
    ode_atol=1e-5,
)

# What-if (perturbation)
scenario = {"enzyme_knockouts": ["enz:kegg:hsa:2539"]}
kg.simulate_whatif("pwy:kegg:hsa00010", json.dumps(scenario), mode="fba")

# Load curated kinetics from literature into the DB
kg.seed_kinetics()
```

**ODE defaults:** `ode_method="BDF"`, `ode_rtol=1e-3`, `ode_atol=1e-5`, `ode_max_step=None`.

## Multi-Corpus Convention (KGRAG)

Each organism or model builds into its own named DB and registers as a separate KGRAG corpus, enabling federated cross-organism queries.

| Corpus | DB path | Content |
|---|---|---|
| `metabokg-hsa` | `data/hsa_pathways/.metabokg/hsa.sqlite` | 369 human pathways *(bundled)* |
| `metabokg-cge` | `data/cge_pathways/.metabokg/cge.sqlite` | 366 CHO (*C. griseus*) pathways *(bundled)* |
| `metabokg-icho` | `data/icho_model/.metabokg/icho.sqlite` | iCHO2441 GEM, 6,337 reactions *(bundled)* |

```bash
# One-shot — build all three corpora
metabokg-init

# Or build individually
metabokg-build --data data/hsa_pathways
metabokg-build --data data/cge_pathways
metabokg-build --data data/icho_model
```

Phase 3 enrichment requires `data/{org}_gene_names.tsv`. Once present, `--knockout Ldha` works directly without a node-ID lookup. `metabokg-init` fetches these TSVs automatically when missing.

## Pathway Categories

Each pathway is tagged with a **category** based on KEGG ID range. Use to filter and organize networks by biological domain.

```python
from metabokg.primitives import (
    PATHWAY_CATEGORY_METABOLIC,    # 00xxx–01xxx
    PATHWAY_CATEGORY_TRANSPORT,    # 02xxx
    PATHWAY_CATEGORY_GIP,          # 03xxx (genetic info processing)
    PATHWAY_CATEGORY_SIGNALING,    # 04010–04099
    PATHWAY_CATEGORY_CELLULAR,     # 04100–04499
    PATHWAY_CATEGORY_ORGANISMAL,   # 04500–04999
    PATHWAY_CATEGORY_DISEASE,      # 05xxx
    PATHWAY_CATEGORY_DRUG,         # 07xxx
)

from metabokg import MetaKG
kg = MetaKG()
metabolic = kg.store.all_nodes(kind="pathway", category=PATHWAY_CATEGORY_METABOLIC)
```

```sql
-- SQL equivalent
SELECT COUNT(*), category FROM meta_nodes
WHERE kind='pathway'
GROUP BY category;
```

## Configure Claude Code / Kilo Code (`.mcp.json`)

```json
{
  "mcpServers": {
    "metabokg": {
      "command": "metabokg",
      "args": [
        "mcp",
        "--repo", "/absolute/path/to/repo"
      ]
    }
  }
}
```

Use **absolute paths**. Merge into existing `mcpServers` — don't overwrite other entries.

> ⚠️ Do NOT add `metabokg` to any global settings file — use per-repo `.mcp.json` only.

## Configure GitHub Copilot (`.vscode/mcp.json`)

GitHub Copilot requires `"servers"` key and `"type": "stdio"`:

```json
{
  "servers": {
    "metabokg": {
      "type": "stdio",
      "command": "metabokg",
      "args": [
        "mcp",
        "--repo", "/absolute/path/to/repo",
        "--db",   "/absolute/path/to/repo/data/hsa_pathways/.metabokg/hsa.sqlite"
      ]
    }
  }
}
```

VS Code will prompt you to **Trust** the server on first use.

## Configure Claude Desktop (`claude_desktop_config.json`)

Claude Desktop has no Poetry on PATH — use the absolute venv binary:

```bash
poetry env info --path
# → /path/to/venv (binary at /path/to/venv/bin/metabokg)
```

Config path: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

```json
{
  "mcpServers": {
    "metabokg": {
      "command": "/path/to/venv/bin/metabokg",
      "args": [
        "mcp",
        "--repo", "/abs/path",
        "--db",   "/abs/path/data/hsa_pathways/.metabokg/hsa.sqlite"
      ]
    }
  }
}
```

## Node ID Format

| Kind | Prefix | Example |
|---|---|---|
| Pathway | `pwy:kegg:<id>` | `pwy:kegg:hsa00010` |
| Compound | `cpd:kegg:<id>` | `cpd:kegg:C00031` |
| Reaction | `rxn:kegg:<id>` | `rxn:kegg:R00010` |
| Enzyme | `enz:kegg:<org>:<gene>` | `enz:kegg:hsa:2539` |
| Glycan | `gl:kegg:<id>` | `gl:kegg:G00012` |
| KO group | `ko:kegg:<id>` | `ko:kegg:K00844` |

## Visualization

```bash
# 2D Streamlit explorer (default port 8500)
metabokg-viz --port 8500

# 3D PyVista — hub-spoke layout (pathways at center, reactions radial)
metabokg-viz3d --layout allium

# 3D PyVista — concentric rings by topological distance
metabokg-viz3d --layout cake

# Override DB / dimensions
metabokg-viz3d --db data/cge_pathways/.metabokg/cge.sqlite --width 1600 --height 1000
```

In the 3D UI: select a pathway, toggle edges/labels/enzyme detail, then click **Render Graph** to apply changes. Switch layouts dynamically from the sidebar.

## Snapshots

Capture metrics over time, just like `dockg snapshot`:

```bash
metabokg-snapshot save 0.8.1
metabokg-snapshot list
metabokg-snapshot show <id>
metabokg-snapshot diff 0.8.0 0.8.1
```

Snapshot JSON files live under `**/.metabokg/snapshots/` and are tracked in git (the SQLite + LanceDB are not — see `.gitignore` below).

## .gitignore Setup

```gitignore
**/.metabokg/*.sqlite
**/.metabokg/lancedb/
# Snapshots ARE tracked — do NOT ignore:
# **/.metabokg/snapshots/
```

## Key Defaults

- Node ID format: `<kind>:kegg:<id>` (e.g. `cpd:kegg:C00031`)
- Default db: `data/hsa_pathways/.metabokg/hsa.sqlite`
- Default LanceDB: `<data-dir>/.metabokg/lancedb`
- Embedding model: ~100 MB, downloaded once on first build
- ODE method: `BDF` (stiff-optimized for metabolic systems)
- ODE tolerances: `rtol=1e-3`, `atol=1e-5`
- Transport: `stdio` (Claude Code/Desktop), `sse` (HTTP clients)

## Troubleshooting

| Error | Fix |
|---|---|
| ODE simulation hangs | Set `ode_method="BDF"` — never use RK45 on metabolic networks |
| Empty query results | Run `metabokg-init` (or `metabokg-build --data DIR` per corpus) |
| Enzyme names show as bare integers | Phase 3 enrichment needs `data/{org}_gene_names.tsv` — `metabokg-init` fetches these automatically |
| `--knockout Ldha` not found | Same as above — Phase 3 enrichment must have run |
| Glycan nodes unresolved (`gl:G#####`) | `data/kegg_glycan_names.tsv` missing — run `metabokg-init` |
| MCP server not appearing | Use absolute paths in config; reload VS Code |
| Wrong DB loaded | Multiple corpora in repo — pass explicit `--db` to point at the correct `.sqlite` |
| `mcp package not found` | `poetry install --all-extras` (must include `[mcp]` extra) |
| `detect-secrets` pre-commit failure | `detect-secrets scan --update .secrets.baseline` |

## Full Reference

See `references/installation.md` for the complete CLI flags table, MCP config templates for all agents (Claude Code, Kilo Code, GitHub Copilot, Cline, Claude Desktop), data download scripts, smoke-test commands, and the full troubleshooting table.
