# MetaboKG Pipeline

End-to-end data flow from raw pathway sources to analysis, simulation, and AI-agent access.

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 0 — Reference Data                            │
│  KEGG REST API → compound names · reaction names · reaction detail ·        │
│                  gene symbols (per organism)                                 │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ data/kegg_*.tsv
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 1 — Pathway Acquisition                       │
│  KEGG REST API → KGML files (one per pathway, per organism)                 │
│  wire_kegg_enzymes.py → injects CATALYZES edges into KGML                   │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ data/{org}_pathways/*.kgml
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 2 — Graph Construction                        │
│  KGMLParser → MetaNode / MetaEdge objects                                   │
│  MetaStore   → SQLite WAL (nodes, edges, xref index)                        │
│  MetaIndex   → LanceDB vector index (compound · enzyme · pathway nodes)     │
└──────┬────────────────────────┬────────────────────────────────────────────┘
       │ {org}.sqlite           │ lancedb/
       ▼                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 3 — Name Enrichment                           │
│  Phase 1  — reaction names from CATALYZES edges (graph-local, no network)  │
│  Phase 2a — compound names       ← kegg_compound_names.tsv                 │
│  Phase 2b — reaction names       ← kegg_reaction_names.tsv  (overrides 1)  │
│  Phase 2c — reaction names (fallback) ← kegg_reaction_detail.tsv           │
│  Phase 3  — enzyme gene symbols  ← {org}_gene_names.tsv                    │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ enriched {org}.sqlite
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 4 — Kinetic Parameterisation                  │
│  Literature curation (BRENDA · SABIO-RK · published models)                 │
│  → kinetic_parameters table  (Km, Vmax, kcat, Ki, ΔG°', Keq)               │
│  → regulatory_interactions table  (allosteric rules)                        │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ parameterised {org}.sqlite
                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                       STAGE 5 — Analysis & Simulation                        │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐   │
│  │   Structural  │  │  FBA (steady-    │  │  ODE (time-course kinetics)  │   │
│  │   Analysis    │  │  state flux)     │  │  What-If (perturbation)      │   │
│  └──────────────┘  └──────────────────┘  └──────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ Markdown / JSON reports
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 6 — Access Interfaces                         │
│  metabokg-viz / viz3d  — interactive graph explorer (Streamlit / PyVista)   │
│  metabokg-mcp          — MCP server (9 tools for Claude and AI agents)      │
│  Python API            — MetaKG class (build · query · simulate)            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Stage 0 — Reference Data Download

Fetch KEGG name reference files used during Stage 3 enrichment. Run once; re-run with `--force` to refresh.

| Script | Output | Used by |
|--------|--------|---------|
| `scripts/download_kegg_names.py` | `data/kegg_compound_names.tsv` | Phase 2a |
| `scripts/download_kegg_names.py` | `data/kegg_reaction_names.tsv` | Phase 2b |
| `scripts/download_kegg_reactions.py --kgml-dir data/hsa_pathways` | `data/kegg_reaction_detail.tsv` | Phase 2c |
| `scripts/download_kegg_names.py --genes hsa cge` | `data/{org}_gene_names.tsv` | Phase 3 |

```bash
python scripts/download_kegg_names.py
python scripts/download_kegg_reactions.py --kgml-dir data/hsa_pathways
python scripts/download_kegg_names.py --genes hsa cge
```

---

## Stage 1 — Pathway Acquisition

KGML files for human and CHO pathways are included in the repository (`data/hsa_pathways/`, `data/cge_pathways/`). Re-download only when refreshing from KEGG.

```bash
python scripts/download_human_kegg.py --output data/hsa_pathways
python scripts/download_kegg_names.py --genes hsa  # if refreshing
python scripts/wire_kegg_enzymes.py                # re-inject CATALYZES edges after refresh
```

| Organism | KEGG code | KGML files | Pathways |
|----------|-----------|-----------|----------|
| *Homo sapiens* | `hsa` | `data/hsa_pathways/` | 369 |
| *Cricetulus griseus* (CHO) | `cge` | `data/cge_pathways/` | 366 |
| iCHO2441 GEM | — | `data/icho_model/` | 6,663 reactions |

---

## Stage 2 — Graph Construction

**Input:** KGML pathway files
**Process:** `KGMLParser` extracts pathway, compound, enzyme, and reaction nodes with typed edges; `MetaStore` writes to SQLite WAL; `MetaIndex` embeds compound/enzyme/pathway nodes into LanceDB
**Output:** `{org}.sqlite` + `lancedb/` per corpus

```bash
metabokg-build --data data/hsa_pathways                          # hsa (default db)
metabokg-build --data data/cge_pathways --db .metabokg/cge.sqlite
metabokg-build --data data/icho_model   --db .metabokg/icho.sqlite
```

**Node kinds:** `pathway · reaction · compound · enzyme`
**Edge relations:** `CONTAINS · SUBSTRATE_OF · PRODUCT_OF · CATALYZES · INHIBITS · ACTIVATES · XREF`

| Corpus | Nodes | Edges | Pathways |
|--------|-------|-------|----------|
| hsa | 17,050 | 40,166 | 369 |
| cge | 16,930 | 39,731 | 366 |

---

## Stage 3 — Name Enrichment

Replaces bare KEGG accessions (`R00710`, `C00031`, `100689064`) with human-readable names. All phases are idempotent and run automatically during `metabokg-build`.

| Phase | Input | Transformation | Example |
|-------|-------|----------------|---------|
| 1 | CATALYZES edges in graph | reaction ← catalysing enzyme gene symbols | `R00710` → `ADH1A / ADH1B` |
| 2a | `kegg_compound_names.tsv` | compound ← canonical KEGG name | `C00031` → `D-Glucose` |
| 2b | `kegg_reaction_names.tsv` | reaction ← canonical KEGG name (overrides Phase 1) | `R00710` → `Acetaldehyde:NAD+ oxidoreductase` |
| 2c | `kegg_reaction_detail.tsv` | reaction ← detail name (fallback for remaining bare IDs) | `R02736` → `ATP:pyruvate 2-O-phosphotransferase` |
| 3 | `{org}_gene_names.tsv` | enzyme ← gene symbol | `2539` → `ADH1C` |

```bash
# Run standalone on an existing database
metabokg enrich --db .metabokg/hsa.sqlite

# Or skip enrichment during build
metabokg-build --data data/hsa_pathways --no-enrich
```

---

## Stage 4 — Kinetic Parameterisation

**Input:** Enriched SQLite database
**Sources:** BRENDA, SABIO-RK, Mulquiney & Kuchel (1999), published CHO bioreactor models
**Output:** `kinetic_parameters` and `regulatory_interactions` tables

| Table | Fields | Rows (hsa) |
|-------|--------|-----------|
| `kinetic_parameters` | Km, Vmax, kcat, Ki, ΔG°', Keq | 65 |
| `regulatory_interactions` | enzyme, effector, effect type, rule | 15 |

```bash
metabokg-simulate seed          # human pathways (default)
metabokg-simulate seed-cho --db .metabokg/cge.sqlite   # CHO-specific parameters
metabokg-simulate seed --force  # overwrite existing rows
```

---

## Stage 5 — Analysis & Simulation

### Structural Analysis

**Input:** SQLite graph
**Output:** Markdown report — hub metabolites, complex reactions, cross-pathway junctions, coupling patterns, network health

```bash
metabokg-analyze [--output FILE] [--db PATH]
```

### Flux Balance Analysis (FBA)

**Method:** Linear programming; maximises total forward flux (or a specified objective reaction)
**Input:** Stoichiometry matrix from SQLite
**Output:** Flux distribution per reaction

```bash
metabokg-simulate fba --pathway hsa00010 [--objective REACTION_ID] [--minimize]
```

### ODE Kinetic Simulation

**Method:** Michaelis-Menten ODEs; BDF solver (stiff-optimised)
**Input:** Kinetic parameters + initial concentrations
**Output:** Concentration time-courses per compound

```bash
metabokg-simulate ode --pathway hsa00010 [--time T] [--conc ID:mM ...]
```

> **Solver note:** Metabolic ODE systems are stiff. The default `BDF` method is required; `RK45` will hang.

### What-If Perturbation Analysis

**Method:** FBA or ODE run under modified conditions (knockouts, inhibition factors, substrate pulses)
**Output:** Delta flux (FBA) or delta final concentration (ODE), sorted by magnitude

```bash
metabokg-simulate whatif --pathway hsa00010 --mode fba --knockout ENZ_ID
metabokg-simulate whatif --pathway hsa00010 --mode ode --factor ENZ_ID:0.5
```

---

## Stage 6 — Access Interfaces

### 2D Graph Explorer

```bash
metabokg-viz [--db PATH] [--lancedb PATH] [--port PORT]
```

Interactive Streamlit browser with pathway filter, node kind and edge relation toggles, and semantic search.

### 3D Graph Visualiser

```bash
metabokg-viz3d [--db PATH] [--layout allium|cake]
```

PyVista renderer. `allium`: hub-spoke layout; `cake`: concentric rings by topological distance.

### MCP Server (AI Agent Interface)

```bash
metabokg-mcp [--transport stdio|sse] [--db PATH]
```

| Tool | Description |
|------|-------------|
| `query_pathway` | Semantic pathway search |
| `get_compound` | Compound detail + connected reactions |
| `get_reaction` | Stoichiometry + catalysing enzymes |
| `find_path` | Shortest metabolic route between two compounds |
| `seed_kinetics` | Populate kinetic parameters |
| `get_kinetic_params` | Retrieve Km/Vmax/regulatory data |
| `simulate_fba` | Flux Balance Analysis |
| `simulate_ode` | ODE kinetic time-course |
| `simulate_whatif` | Perturbation analysis |

### Python API

```python
from metabokg import MetaKG

with MetaKG(db_path=".metabokg/hsa.sqlite") as kg:
    kg.build(data_dir="data/hsa_pathways", wipe=True)
    result = kg.query_pathway("glycolysis")
    fba    = kg.simulate_fba("pwy:kegg:hsa00010")
    ode    = kg.simulate_ode("pwy:kegg:hsa00010", t_end=100)
```

---

## Quick-Start

```bash
pip install metabokg[simulate,viz]

# Stage 0 — reference data
python scripts/download_kegg_names.py
python scripts/download_kegg_reactions.py --kgml-dir data/hsa_pathways
python scripts/download_kegg_names.py --genes hsa

# Stage 2–4 — build, enrich, seed (all automatic)
metabokg-build --data data/hsa_pathways

# Stage 5 — analyse
metabokg-analyze --output analysis.md
metabokg-simulate fba --pathway hsa00010

# Stage 6 — explore
metabokg-viz --db data/hsa_pathways/.metabokg/hsa.sqlite
metabokg-mcp
```
