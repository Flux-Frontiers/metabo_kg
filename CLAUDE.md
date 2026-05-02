# MetaboKG CLI Commands Reference

**Repository:** https://github.com/Flux-Frontiers/metabo_kg | **Sister:** https://github.com/Flux-Frontiers/pycode_kg

## PyCodeKG Tools (Available in Claude Code)

| Tool | Purpose |
|------|---------|
| `query_codebase(q, k=8, hop=1)` | Semantic code search |
| `pack_snippets(q, k=8, hop=1)` | Source-grounded code snippets |
| `get_node(node_id)` | Fetch node by ID (fmt: `fn:module:qualname`) |
| `callers(node_id)` | Find all callers of a function |
| `graph_stats()` | Codebase metrics |
| `/pycodekg-rebuild` | Rebuild after code changes |

**Workflow:** Query → read snippets → inspect node → find callers

---

## Quick Setup

```bash
poetry install --all-extras  # Full install with viz, viz3d, mcp
```

---

## MetaboKG Commands

| Command | Purpose |
|---------|---------|
| `metabokg-init` | **First-time setup**: integrity check, fetch missing TSVs, build all corpora, seed kinetics |
| `metabokg-init --check` | Status-only: show TSV integrity and corpus build state without modifying anything |
| `metabokg-init --corpus hsa` | Initialize a single corpus (repeatable: `--corpus hsa --corpus cge`) |
| `metabokg-info` | Show active corpus, resolved db/lancedb paths, node/edge counts |
| `metabokg-build --data DIR` | Full rebuild: wipe + parse pathways → SQLite + LanceDB (enriches by default) |
| `metabokg-build --data DIR --no-wipe` | Parse without wiping — merge new files on top |
| `metabokg-update --data DIR` | Incrementally add new files without wiping |
| `metabokg-analyze [--output FILE]` | 7-phase pathway analysis |
| `metabokg-viz [--port 8500]` | 2D Streamlit explorer |
| `metabokg-viz3d [--layout allium\|cake]` | 3D PyVista visualization |
| `metabokg-mcp` | MCP server for Claude |
| `metabokg-query QUERY [--k 10] [--hop 0]` | Semantic + graph search, ranked hits |
| `metabokg-pack QUERY [--k 8] [--hop 1]` | Context-rich Markdown/JSON pack for LLM use |

**Common options:**
- `--db PATH`: SQLite db (default: `.metabokg/hsa.sqlite`)
- `--lancedb PATH`: Vector index (default: `.metabokg/lancedb`)
- `--no-wipe`: Keep existing data instead of wiping (build wipes by default)
- `--no-index`: Skip LanceDB (SQLite only)
- `--no-enrich`: Skip enrichment (on by default)

**MCP tools:** `pack`, `query_pathway`, `get_compound`, `get_reaction`, `find_path`, `seed_kinetics`, `simulate_fba`, `simulate_ode`, `simulate_whatif`

### 3D Visualization (`metabokg-viz3d`)

```bash
metabokg-viz3d [--layout allium|cake] [--db PATH] [--width W] [--height H]
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

**Constants available in `metabokg.primitives`:**
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
from metabokg import MetaKG
from metabokg.primitives import PATHWAY_CATEGORY_METABOLIC

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
from metabokg import MetaKG
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

## Multi-Corpus Convention (KGRAG)

Each organism or model builds into its own named db and registers as a separate
KGRAG corpus, enabling federated cross-organism queries.

| Corpus | DB path (colocated) | Content |
|--------|---------------------|---------|
| `metabokg-hsa` | `data/hsa_pathways/.metabokg/hsa.sqlite` | 369 human pathways *(bundled in repo)* |
| `metabokg-cge` | `data/cge_pathways/.metabokg/cge.sqlite` | 366 CHO (*C. griseus*) pathways *(bundled in repo)* |
| `metabokg-icho` | `data/icho_model/.metabokg/icho.sqlite` | iCHO2441 GEM, 6,663 reactions |

```bash
# One-shot: builds all three corpora
metabokg-init

# Or build individually:
metabokg-build --data data/hsa_pathways  # → data/hsa_pathways/.metabokg/hsa.sqlite
metabokg-build --data data/cge_pathways  # → data/cge_pathways/.metabokg/cge.sqlite
metabokg-build --data data/icho_model    # → data/icho_model/.metabokg/icho.sqlite
```

- **Enzyme name resolution** requires `data/{org}_gene_names.tsv` — `metabokg-init` fetches these automatically if missing
- After Phase 3 enrichment, `--knockout Ldha` works directly (no node ID lookup needed)

---

## PyCodeKG Commands

| Command | Purpose |
|---------|---------|
| `pycodekg-build [--repo DIR] [--wipe]` | Full pipeline: AST → SQLite → LanceDB |
| `pycodekg-build-sqlite [--repo DIR] [--wipe]` | Structural analysis → SQLite only |
| `pycodekg-build-lancedb [--repo DIR] [--wipe]` | Embeddings → LanceDB (requires SQLite already built) |
| `pycodekg-query QUERY [--k 8] [--hop 1]` | Semantic + graph search, ranked summary |
| `pycodekg-pack QUERY [--k 8] [--hop 1]` | Source-grounded snippet packs |
| `pycodekg-mcp [--repo DIR]` | MCP server |
| `pycodekg-analyze [--repo DIR]` | Architectural analysis report |
| `pycodekg-viz` / `pycodekg-viz3d` | Streamlit / PyVista visualizer |

**Query strategy:**
- `k=8, hop=1`: standard exploration
- `k=12, hop=2`: broad context
- `k=8, hop=2, rels=CALLS,IMPORTS`: deep dependencies

**When to rebuild:** Function/class rename/delete → `--wipe`. Minor edits → incremental.

---

## Data Download Scripts

**All source data is bundled in the repo** (`data/hsa_pathways/`, `data/cge_pathways/`, `data/icho_model/*.xml`, all `data/*.tsv`).

TSV annotation files (compound/reaction/gene names) are fetched automatically by `metabokg-init` if missing — no separate script needed.

Scripts below are for **refreshing pathway files** only (e.g. after a KEGG update):

| Script | Purpose | Output |
|--------|---------|--------|
| `scripts/download_human_kegg.py` | Re-download hsa KGML pathway files | `data/hsa_pathways/*.kgml` |
| `scripts/download_cho_kegg.py` | Re-download cge KGML pathway files | `data/cge_pathways/*.kgml` |
| `scripts/download_icho_model.py` | Re-download iCHO2441 SBML XML | `data/icho_model/*.xml` |
| `scripts/fetch_sabio_cho_kinetics.py` | Fetch CHO kinetics from SABIO-RK (credentials needed) | `data/sabio_cho_kinetics.tsv` |

---

## Typical Workflow

```bash
# 1. All data is bundled — just install and init
poetry install --all-extras

# 2. One-shot initialization: checks TSVs, builds all corpora, seeds kinetics
metabokg-init

# 3. Check what was built (read-only)
metabokg-init --check

# 4. Run analysis report
metabokg-analyze

# Explore (choose your view)
metabokg-viz                      # 2D Streamlit explorer
metabokg-viz3d --layout allium    # 3D visualization (allium or cake)
metabokg-mcp                      # MCP server for Claude

# Rebuild a single corpus (e.g. after refreshing pathway files)
metabokg-build --data ./data/hsa_pathways

# Optional: analyze codebase
pycodekg-build --repo . --wipe
pycodekg-query "orchestrator pipeline"
pycodekg-pack "pathway category provenance"
```

---

## Key Notes

- **Paths:** Relative to CWD
- **Embedding model:** ~100MB, downloaded once
- **ODE solvers:** Metabolic systems are stiff → use BDF (not RK45)
- **PyCodeKG node ID:** `fn:src/path/file.py:Class.method`
- **Rebuild:** Use `--wipe` after major refactors to avoid stale data
- **Graph quality:** No isolated nodes (all 17K+ nodes are wired), all pathways categorized
- **Enrichment:** Now default-on during build; use `--no-enrich` to skip
