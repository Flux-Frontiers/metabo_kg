# MetaKG CLI Commands Reference

**Repository:** https://github.com/Flux-Frontiers/meta_kg | **Sister:** https://github.com/Flux-Frontiers/code_kg

## CodeKG Tools (Available in Claude Code)

| Tool | Purpose |
|------|---------|
| `query_codebase(q, k=8, hop=1)` | Semantic code search |
| `pack_snippets(q, k=8, hop=1)` | Source-grounded code snippets |
| `get_node(node_id)` | Fetch node by ID (fmt: `fn:module:qualname`) |
| `callers(node_id)` | Find all callers of a function |
| `graph_stats()` | Codebase metrics |
| `/codekg-rebuild` | Rebuild after code changes |

**Workflow:** Query → read snippets → inspect node → find callers

---

## Quick Setup

```bash
poetry install --all-extras  # Full install with viz, viz3d, mcp
```

---

## MetaKG Commands

| Command | Purpose |
|---------|---------|
| `metakg-build --data DIR` | Parse pathways → SQLite + LanceDB (wipes & enriches by default) |
| `metakg-update --data DIR` | Incrementally add new files without wiping |
| `metakg-analyze [--output FILE]` | 7-phase pathway analysis |
| `metakg-viz [--port 8500]` | 2D Streamlit explorer |
| `metakg-viz3d [--layout allium\|cake]` | 3D PyVista visualization |
| `metakg-mcp` | MCP server for Claude |

**Common options:**
- `--db PATH`: SQLite db (default: `.metakg/meta.sqlite`)
- `--lancedb PATH`: Vector index (default: `.metakg/lancedb`)
- `--no-wipe`: Keep existing data (default: wipe before build)
- `--no-index`: Skip LanceDB (SQLite only)
- `--no-enrich`: Skip enrichment (on by default)

**MCP tools:** `query_pathway`, `get_compound`, `get_reaction`, `find_path`, `seed_kinetics`, `simulate_fba`, `simulate_ode`, `simulate_whatif`

### 3D Visualization (`metakg-viz3d`)

```bash
metakg-viz3d [--layout allium|cake] [--db PATH] [--width W] [--height H]
```

**Layout modes:**
- `allium` (default): Hub-spoke layout with pathways at center, reactions radially distributed
- `cake`: Concentric rings by topological distance (layer-based)

**In the UI:**
- **Pathway Filter**: Select single pathway or "(All Pathways)" — category filtering coming soon
- **Layout Selector**: Switch between Allium and LayerCake (recomputes positions)
- **Visibility Toggles**: Show/hide edges, labels, enzyme detail
- **Render Graph**: Apply staged changes (filters + toggles) to the visualization

**Workflow:**
1. Start with `--layout cake` for metabolic flow visualization
2. Select a pathway (e.g., Glycolysis)
3. Adjust visibility toggles
4. Click "Render Graph" to render
5. Switch layouts dynamically from the sidebar

---

## Pathway Categories

Each pathway is tagged with a **category** based on KEGG ID ranges (metabolic, signaling, disease, etc.). Use categories to filter and organize networks by biological domain.

**Constants available in `metakg.primitives`:**
```python
PATHWAY_CATEGORY_METABOLIC          # 00xxx–01xxx
PATHWAY_CATEGORY_TRANSPORT          # 02xxx
PATHWAY_CATEGORY_GIP                # 03xxx (genetic info processing)
PATHWAY_CATEGORY_SIGNALING          # 04010–04099
PATHWAY_CATEGORY_CELLULAR           # 04100–04499
PATHWAY_CATEGORY_ORGANISMAL         # 04500–04999
PATHWAY_CATEGORY_DISEASE            # 05xxx (human disease)
PATHWAY_CATEGORY_DRUG               # 07xxx (drug development)
```

**Query by category:**
```python
from metakg import MetaKG
from metakg.primitives import PATHWAY_CATEGORY_METABOLIC

kg = MetaKG()
pathways = kg.store.all_nodes(kind="pathway", category=PATHWAY_CATEGORY_METABOLIC)
```

**SQL:**
```sql
SELECT COUNT(*), category FROM meta_nodes
WHERE kind='pathway'
GROUP BY category;
```

---

## Simulations

**ODE Default:** `ode_method="BDF"` (implicit, stiff-optimized for metabolic systems)
- Use BDF/Radau for stiff systems
- **RK45 will hang on metabolic pathways** (avoid!)

**ODE params:** `ode_rtol=1e-3`, `ode_atol=1e-5`, `ode_max_step=None`

```python
from metakg import MetaKG
kg = MetaKG()

# FBA (steady-state)
kg.simulate_fba("pwy:kegg:hsa00010", maximize=True)

# ODE (time-course)
kg.simulate_ode("pwy:kegg:hsa00010", t_end=20, t_points=50,
                initial_concentrations={"cpd:kegg:C00031": 5.0})

# What-if (perturbation)
scenario = {"enzyme_knockouts": ["enz:kegg:hsa:2539"]}
kg.simulate_whatif("pwy:kegg:hsa00010", json.dumps(scenario), mode="fba")

# Load kinetics from literature
kg.seed_kinetics()
```

---

## CodeKG Commands

| Command | Purpose |
|---------|---------|
| `codekg-build [--repo DIR] [--wipe]` | Full pipeline: AST → SQLite → LanceDB |
| `codekg-build-sqlite [--repo DIR] [--wipe]` | Structural analysis → SQLite only |
| `codekg-build-lancedb [--repo DIR] [--wipe]` | Embeddings → LanceDB (requires SQLite already built) |
| `codekg-query QUERY [--k 8] [--hop 1]` | Semantic + graph search, ranked summary |
| `codekg-pack QUERY [--k 8] [--hop 1]` | Source-grounded snippet packs |
| `codekg-mcp [--repo DIR]` | MCP server |
| `codekg-analyze [--repo DIR]` | Architectural analysis report |
| `codekg-viz` / `codekg-viz3d` | Streamlit / PyVista visualizer |

**Query strategy:**
- `k=8, hop=1`: standard exploration
- `k=12, hop=2`: broad context
- `k=8, hop=2, rels=CALLS,IMPORTS`: deep dependencies

**When to rebuild:** Function/class rename/delete → `--wipe`. Minor edits → incremental.

---

## Data Download Scripts

| Script | Purpose | Output |
|--------|---------|--------|
| `scripts/download_human_kegg.py` | Download all hsa KGML pathway files | `data/hsa_pathways/*.kgml` |
| `scripts/download_kegg_names.py` | Bulk-download compound + reaction name lists | `data/kegg_compound_names.tsv`, `data/kegg_reaction_names.tsv` |
| `scripts/download_kegg_reactions.py` | Per-reaction detail: name, definition, equation, EC numbers | `data/kegg_reaction_detail.tsv` |

**Reaction detail download (EC numbers):**
```bash
# From local KGML files (faster, no extra network call for ID list):
python scripts/download_kegg_reactions.py --kgml-dir data/hsa_pathways

# From KEGG link endpoint (~2000 reactions across all hsa pathways):
python scripts/download_kegg_reactions.py

# Options: --force (re-download), --dry-run (list IDs only), --delay SECS
```

Output format (`data/kegg_reaction_detail.tsv`):
```
reaction_id  name                              definition        equation           ec_numbers
R00710       acetaldehyde:NAD+ oxidoreductase  Acetaldehyde ...  C00084 + C00003 …  1.2.1.3; 1.2.1.4
```

---

## Typical Workflow

```bash
# 1. Download pathway KGML files
python scripts/download_human_kegg.py --output data/hsa_pathways

# 2. (Optional) Download KEGG name lists for canonical names in enrichment
python scripts/download_kegg_names.py

# 3. Build & analyze pathways (enrichment runs by default)
metakg-build --data ./data/hsa_pathways

# 4. Seed kinetic parameters from literature
metakg-simulate seed

# 5. Run analysis report
metakg-analyze

# Explore (choose your view)
metakg-viz           # 2D Streamlit explorer
metakg-viz3d --layout allium    # 3D visualization (allium or cake)
metakg-mcp           # MCP server for Claude

# Optional: analyze codebase
codekg-build --repo . --wipe
codekg-query "orchestrator pipeline"
codekg-pack "pathway category provenance"
```

---

## Key Notes

- **Paths:** Relative to CWD
- **Embedding model:** ~100MB, downloaded once
- **ODE solvers:** Metabolic systems are stiff → use BDF (not RK45)
- **CodeKG node ID:** `fn:src/path/file.py:Class.method`
- **Rebuild:** Use `--wipe` after major refactors to avoid stale data
- **Graph quality:** No isolated nodes (all 17K+ nodes are wired), all pathways categorized
- **Enrichment:** Now default-on during build; use `--no-enrich` to skip
