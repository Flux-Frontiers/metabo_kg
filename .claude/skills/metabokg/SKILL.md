---
name: metabokg
description: Expert knowledge for installing, configuring, and using MetaboKG — a hybrid semantic + structural metabolic knowledge graph. Use this skill when the user asks about: setting up MetaboKG in a project, building the SQLite or LanceDB knowledge graph, configuring .mcp.json for Claude Code or Kilo Code, configuring .vscode/mcp.json for GitHub Copilot, configuring Cline MCP settings, using the metabokg CLI (metabokg-build, metabokg-analyze, metabokg-viz, metabokg-viz3d, metabokg-mcp, metabokg-simulate, metabokg-query), using the query_pathway / get_compound / get_reaction / find_path / seed_kinetics / simulate_fba / simulate_ode / simulate_whatif MCP tools, querying KEGG pathways, running FBA or ODE simulations, working with CHO or human metabolic models, multi-corpus KGRAG federation, or troubleshooting MetaboKG errors.
---

# MetaboKG Skill

> **MetaboKG understands metabolism the way PyCodeKG understands code.**
>
> It ingests KEGG pathway graphs (KGML) into a dual-layer local store — SQLite for structural precision, LanceDB for semantic vector search — and exposes query, path-finding, and simulation capabilities as MCP tools for AI agents.

## Quick Setup

```bash
poetry install --all-extras   # installs viz, viz3d, mcp extras
```

## Build the Knowledge Graph

```bash
# Human pathways (bundled in repo — no download needed)
metabokg-build --data ./data/hsa_pathways

# CHO pathways
metabokg-build --data ./data/cge_pathways

# Force full rebuild
metabokg-build --data ./data/hsa_pathways --wipe
```

The database and LanceDB index colocate automatically under `<data-dir>/.metabokg/`:

| Data dir | SQLite | LanceDB |
|---|---|---|
| `data/hsa_pathways/` | `data/hsa_pathways/.metabokg/hsa.sqlite` | `data/hsa_pathways/.metabokg/lancedb/` |
| `data/cge_pathways/` | `data/cge_pathways/.metabokg/cge.sqlite` | `data/cge_pathways/.metabokg/lancedb/` |
| `data/icho_model/` | `data/icho_model/.metabokg/icho.sqlite` | `data/icho_model/.metabokg/lancedb/` |

Enrichment runs by default (canonical compound/reaction/enzyme names). Skip with `--no-enrich`.

## Enrichment Phases

| Phase | What it does |
|---|---|
| 1 | Compound names from KEGG compound TSV |
| 2a | Reaction names from KEGG reaction TSV |
| 2b | Reaction names from graph traversal |
| 2c | Reaction names from KEGG detail TSV (EC numbers) |
| 2d | Glycan names from `data/kegg_glycan_names.tsv` (~11k entries) |
| 2e | KO enzyme names from `data/kegg_ko_names.tsv` (~28k entries) |
| 3 | Enzyme gene names from `data/{org}_gene_names.tsv` — enables `--knockout Ldha` |

## CLI Commands

| Command | Purpose |
|---|---|
| `metabokg-build --data DIR` | Parse pathways → SQLite + LanceDB (enriches by default) |
| `metabokg-build --data DIR --wipe` | Full rebuild: wipe then parse |
| `metabokg-update --data DIR` | Incrementally add new files without wiping |
| `metabokg-analyze [--output FILE]` | 7-phase pathway analysis report |
| `metabokg-viz [--port 8500]` | 2D Streamlit explorer |
| `metabokg-viz3d [--layout allium\|cake]` | 3D PyVista visualization |
| `metabokg-mcp` | MCP server for Claude |
| `metabokg-query QUERY` | Semantic or substring search across the graph |
| `metabokg-simulate fba --pathway PWY` | Flux Balance Analysis |
| `metabokg-simulate ode --pathway PWY` | ODE time-course simulation |
| `metabokg-simulate whatif --pathway PWY` | Perturbation analysis |
| `metabokg-simulate seed` | Seed kinetic parameters from literature |
| `metabokg-simulate seed-cho` | Seed 35 CHO-specific kinetic parameters |

**Common options:**
- `--db PATH` — SQLite db (default: `.metabokg/hsa.sqlite`)
- `--lancedb PATH` — Vector index (default: `.metabokg/lancedb`)
- `--wipe` — Wipe existing data before building
- `--no-index` — Skip LanceDB (SQLite only)
- `--no-enrich` — Skip enrichment

## MCP Tools

| Tool | When to use |
|---|---|
| `query_pathway(q)` | Semantic search — returns pathways by description |
| `get_compound(id)` | Fetch compound node by KEGG ID |
| `get_reaction(id)` | Fetch reaction node with substrates, products, enzymes |
| `find_path(src, dst)` | Shortest metabolic path between two compounds |
| `seed_kinetics()` | Load kinetic parameters from literature into the graph |
| `simulate_fba(pathway_id)` | Run Flux Balance Analysis (HiGHS LP solver) |
| `simulate_ode(pathway_id, t_end, t_points)` | ODE time-course (BDF stiff solver) |
| `simulate_whatif(pathway_id, scenario, mode)` | Perturbation: knockouts, overrides, activity scaling |

## Simulation Notes

**ODE solver:** Always use `BDF` (default) or `Radau` for metabolic systems. **RK45 will hang** — metabolic networks are stiff.

```python
from metabokg import MetaKG
kg = MetaKG()

# FBA (steady-state)
kg.simulate_fba("pwy:kegg:hsa00010", maximize=True)

# ODE (time-course)
kg.simulate_ode("pwy:kegg:hsa00010", t_end=20, t_points=50,
                initial_concentrations={"cpd:kegg:C00031": 5.0})

# What-if (perturbation)
import json
scenario = {"enzyme_knockouts": ["enz:kegg:hsa:2539"]}
kg.simulate_whatif("pwy:kegg:hsa00010", json.dumps(scenario), mode="fba")
```

## Multi-Corpus Convention (KGRAG)

Each organism builds into its own named database and registers as a separate KGRAG corpus for federated cross-organism queries:

| Corpus | DB path | Content |
|---|---|---|
| `metabokg-hsa` | `data/hsa_pathways/.metabokg/hsa.sqlite` | 369 human pathways |
| `metabokg-cge` | `data/cge_pathways/.metabokg/cge.sqlite` | 366 CHO pathways |
| `metabokg-icho` | `data/icho_model/.metabokg/icho.sqlite` | iCHO2441 GEM, 6,663 reactions |

## Pathway Categories

```python
from metabokg.primitives import (
    PATHWAY_CATEGORY_METABOLIC,   # 00xxx–01xxx
    PATHWAY_CATEGORY_TRANSPORT,   # 02xxx
    PATHWAY_CATEGORY_GIP,         # 03xxx (genetic info processing)
    PATHWAY_CATEGORY_SIGNALING,   # 04010–04099
    PATHWAY_CATEGORY_CELLULAR,    # 04100–04499
    PATHWAY_CATEGORY_ORGANISMAL,  # 04500–04999
    PATHWAY_CATEGORY_DISEASE,     # 05xxx
    PATHWAY_CATEGORY_DRUG,        # 07xxx
)
```

## Configure Claude Code / Kilo Code (.mcp.json)

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

Use absolute paths. Merge into existing `mcpServers` — don't overwrite other entries.

## Configure GitHub Copilot (.vscode/mcp.json)

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

## Automated Setup

```bash
bash scripts/install-skill.sh --providers claude,copilot
```

Or via curl from any target repo:
```bash
curl -fsSL https://raw.githubusercontent.com/Flux-Frontiers/metabo_kg/main/scripts/install-skill.sh | bash
```

## .gitignore Setup

```gitignore
**/.metabokg/*.sqlite
**/.metabokg/lancedb/
```

Snapshot JSON files under `**/.metabokg/snapshots/` are tracked by git.

## Key Defaults

- Node ID format: `<kind>:kegg:<id>` (e.g. `cpd:kegg:C00031`, `rxn:kegg:R00010`, `pwy:kegg:hsa00010`)
- Default db: `data/hsa_pathways/.metabokg/hsa.sqlite`
- ODE method: `BDF` (stiff-optimized)
- ODE tolerances: `rtol=1e-3`, `atol=1e-5`

## Troubleshooting

| Error | Fix |
|---|---|
| ODE simulation hangs | Switch to `ode_method="BDF"` — never use RK45 on metabolic networks |
| Empty query results | Run `metabokg-build --data DIR` to populate LanceDB |
| Enzyme names show as bare IDs | Download gene names: `python scripts/download_kegg_names.py --genes hsa cge` then rebuild |
| `--knockout Ldha` not found | Phase 3 enrichment requires `data/{org}_gene_names.tsv` — see above |
| MCP server not appearing | Use absolute paths in config; reload VS Code |

## Full Reference

See `references/installation.md` for complete CLI flags, MCP config templates, data download scripts, and the full troubleshooting table.
