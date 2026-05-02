# MetaboKG Pipeline

End-to-end data flow from raw pathway sources to analysis, simulation, and AI-agent access.

**Bundled corpora:**

| Corpus | Organism | Pathways | Reactions | Compounds | Enzymes | Nodes | Edges |
|--------|----------|---------:|----------:|----------:|--------:|------:|------:|
| `hsa`  | *Homo sapiens* (Human Metabolome)         | 369   | 2,139 | 5,115 | 9,427 | 17,050 | 40,166 |
| `cge`  | *Cricetulus griseus* (CHO Metabolome)     | 366   | 2,099 | 5,105 | 9,360 | 16,930 | 39,731 |
| `icho` | iCHO2441 GEM (genome-scale CHO model)     | 1     | 6,337 | 4,174 | 2,441 | 12,953 | 41,437 |

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
│  Phase 2d — glycan names         ← kegg_glycan_names.tsv                   │
│  Phase 2e — KO enzyme names      ← kegg_ko_names.tsv                       │
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

## Stage 0 — Reference Data

KEGG name reference files used during Stage 3 enrichment. **All TSVs are bundled in the repo**; `metabokg-init` checks integrity on first run and auto-fetches anything missing from KEGG REST.

| File | Source endpoint | Used by |
|------|-----------------|---------|
| `data/kegg_compound_names.tsv` | `/list/compound` | Phase 2a |
| `data/kegg_reaction_names.tsv` | `/list/reaction` | Phase 2b |
| `data/kegg_reaction_detail.tsv` | `/get/rn:R#####` (per-reaction) | Phase 2c |
| `data/kegg_glycan_names.tsv` | `/list/glycan` | Phase 2d |
| `data/kegg_ko_names.tsv` | `/list/ko` | Phase 2e |
| `data/{org}_gene_names.tsv` | `/list/{org}` | Phase 3 |
| `data/sabio_cho_kinetics.tsv` | SABIO-RK (credentials-gated, manual) | Stage 4 (CHO) |

```bash
metabokg-init --check          # status only — show TSV integrity + corpus build state
metabokg-init                  # fetch missing TSVs, build all corpora, seed kinetics
metabokg-init --no-fetch       # fail instead of downloading
```

The integrity check classifies each TSV as `ok` / `thin` / `empty` / `missing`; auto-download is triggered only for the missing/empty cases. `sabio_cho_kinetics.tsv` is excluded from auto-fetch and must be obtained via `scripts/fetch_sabio_cho_kinetics.py`.

---

## Stage 1 — Pathway Acquisition

KGML files for human and CHO pathways and the iCHO2441 SBML are included in the repository (`data/hsa_pathways/`, `data/cge_pathways/`, `data/icho_model/`). Re-download only when refreshing from KEGG.

```bash
python scripts/download_human_kegg.py --output data/hsa_pathways
python scripts/download_cho_kegg.py    --output data/cge_pathways
python scripts/download_icho_model.py  --output data/icho_model
python scripts/wire_kegg_enzymes.py    # re-inject CATALYZES edges after refresh
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

`metabokg-init` builds all three corpora in one shot. Use `metabokg-build` to (re)build a single corpus:

```bash
metabokg-build --data data/hsa_pathways   # → data/hsa_pathways/.metabokg/hsa.sqlite
metabokg-build --data data/cge_pathways   # → data/cge_pathways/.metabokg/cge.sqlite
metabokg-build --data data/icho_model     # → data/icho_model/.metabokg/icho.sqlite
```

**Node kinds:** `pathway · reaction · compound · enzyme`
**Edge relations:** `CONTAINS · SUBSTRATE_OF · PRODUCT_OF · CATALYZES · INHIBITS · ACTIVATES · XREF`

| Corpus | Nodes | Edges | Pathways |
|--------|------:|------:|---------:|
| hsa  | 17,050 | 40,166 | 369 |
| cge  | 16,930 | 39,731 | 366 |
| icho | 12,953 | 41,437 |   1 |

---

## Stage 3 — Name Enrichment

Replaces bare KEGG accessions with human-readable names across all node kinds. All phases are idempotent and run automatically during `metabokg-build`.

| Phase | Node kind | Input TSV | Transformation | Example |
|-------|-----------|-----------|----------------|---------|
| 1 | reaction | *(graph-local, no file needed)* | reaction ← gene symbols of catalysing enzymes (CATALYZES edges) | `R00710` → `ADH1A / ADH1B` |
| 2a | compound | `kegg_compound_names.tsv` | compound ← canonical KEGG name | `C00031` → `D-Glucose` |
| 2b | reaction | `kegg_reaction_names.tsv` | reaction ← canonical KEGG name (overrides Phase 1) | `R00710` → `Acetaldehyde:NAD+ oxidoreductase` |
| 2c | reaction | `kegg_reaction_detail.tsv` | reaction ← detail name (fallback for remaining bare IDs) | `R02736` → `ATP:pyruvate 2-O-phosphotransferase` |
| 2d | glycan | `kegg_glycan_names.tsv` | glycan compound ← canonical KEGG glycan name | `G13086` → `Lactosylceramide` |
| 2e | enzyme (KO) | `kegg_ko_names.tsv` | KO enzyme ← KEGG Orthology description | `K00001` → `alcohol dehydrogenase` |
| 3 | enzyme | `{org}_gene_names.tsv` | organism enzyme ← gene symbol | `2539` → `ADH1C` |

**Namespace coverage after full enrichment:**

| KEGG namespace | Pattern | Enrichment phase |
|----------------|---------|-----------------|
| Compounds | `C#####` | Phase 2a (~18 k entries) |
| Reactions | `R#####` | Phase 2b + 2c (~12 k entries) |
| Glycans | `G#####` | Phase 2d (~11 k entries) |
| KO orthologues | `K#####` | Phase 2e (~28 k entries) |
| Organism genes | `{org}:{id}` | Phase 3 (per-organism TSV) |

```bash
# Skip enrichment during build (rare — enrichment is on by default)
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

with MetaKG(db_path="data/hsa_pathways/.metabokg/hsa.sqlite") as kg:
    kg.build(data_dir="data/hsa_pathways", wipe=True)
    result = kg.query_pathway("glycolysis")
    fba    = kg.simulate_fba("pwy:kegg:hsa00010")
    ode    = kg.simulate_ode("pwy:kegg:hsa00010", t_end=100)
```

---

## Quick-Start

```bash
pip install metabokg[simulate,viz]

# Stages 0–4 — integrity check, fetch missing TSVs, build all corpora, seed kinetics
metabokg-init

# Stage 5 — analyse
metabokg-analyze --output analysis.md
metabokg-simulate fba --pathway hsa00010

# Stage 6 — explore
metabokg-viz   # default: data/hsa_pathways/.metabokg/hsa.sqlite
metabokg-mcp
```

`metabokg-init --check` reports TSV integrity and per-corpus build state without modifying anything. Use `metabokg-init --corpus hsa` to scope to a single corpus, or `--force` to rebuild existing databases.
