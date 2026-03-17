# MetaKG Workflow

End-to-end guide from raw pathway data to running simulations and serving an MCP agent.

---

## Overview

```
KEGG REST API
     │
     ▼
collect_pathway_data.py        ← optional; data/hsa_pathways/ already available
     │  downloads hsa*.kgml
     ▼
data/hsa_pathways/*.kgml  (KGML)
     │
     ▼
wire_enzymes.py                ← one-time; already applied to data/hsa_pathways files
     │  injects enzyme="N" into <reaction> elements
     ▼
data/hsa_pathways/*.kgml  (patched)
     │
     ▼
metakg-build --data data/hsa_pathways/  ← wipes and rebuilds by default
     │  KGMLParser → MetaNode/MetaEdge
     ├──► .metakg/meta.sqlite   (SQLite knowledge graph)
     └──► .metakg/lancedb/      (vector index for semantic search)
     │
     ▼
metakg-simulate seed           ← run once after build
     │  kinetics_fetch.py → kinetic_parameters + regulatory_interactions
     ▼
.metakg/meta.sqlite  (complete)
     │
     ├── metakg-analyze         → Markdown pathway analysis report
     ├── metakg-simulate fba    → flux distribution
     ├── metakg-simulate ode    → concentration time-courses
     ├── metakg-simulate whatif → perturbation analysis
     ├── metakg-mcp             → MCP server (for Claude)
     └── metakg-viz / viz3d     → interactive visualisers
```

---

## Phase 1 — Get Pathway Data

The 369 KGML files in `data/hsa_pathways/` are **already available** in the repo.
Skip this phase unless you want to expand the dataset or refresh from KEGG.

```bash
# See all 30 curated pathways without downloading
python scripts/collect_pathway_data.py --list

# Download all 30 pathways (1 s polite delay between KEGG API calls)
python scripts/collect_pathway_data.py --out data/hsa_pathways/

# Download only one metabolic category
python scripts/collect_pathway_data.py --category energy
python scripts/collect_pathway_data.py --category lipid
python scripts/collect_pathway_data.py --category amino_acid

# Force re-download even if files already exist
python scripts/collect_pathway_data.py --force
```

**Available categories:** `energy`, `lipid`, `amino_acid`, `nucleotide`, `cofactor`, `carbohydrate`

After downloading fresh KGML files, re-run the enzyme wiring step:

```bash
# Inject enzyme="N" attributes so the parser can emit CATALYZES edges
python scripts/wire_kegg_enzymes.py

# Dry-run to preview changes without writing
python scripts/wire_kegg_enzymes.py --data data/hsa_pathways --dry-run
```

`wire_kegg_enzymes.py` is a one-time data-preparation tool.  It scans all
KGML files and patches `<reaction>` elements that have no enzyme coverage by
adding an `enzyme="N"` attribute pointing to the correct gene/ortholog entry
ID, which lets the parser emit CATALYZES edges.  The patch has already been
applied to all files currently in `data/hsa_pathways/` — only re-run it when
ingesting newly downloaded or refreshed KGML files.

---

## Phase 2 — Build Both Databases & Seed Kinetics

```bash
# Full rebuild — wipes existing data first (default behaviour)
metakg-build --data data/hsa_pathways/

# Incremental update — merge new files without wiping
metakg-update --data data/hsa_pathways/

# Keep existing data (equivalent to metakg-update; explicit flag)
metakg-build --data data/hsa_pathways/ --no-wipe

# Build without the LanceDB vector index (faster, no semantic search)
metakg-build --data data/hsa_pathways/ --no-index

# Skip kinetic seeding (rarely needed)
metakg-build --data data/hsa_pathways/ --no-seed-kinetics

# Custom paths or embedding model
metakg-build --data data/hsa_pathways/ \
             --db .metakg/meta.sqlite \
             --lancedb .metakg/lancedb \
             --model all-MiniLM-L6-v2
```

By default, `metakg-build` automatically:
1. Parses pathway KGML files → SQLite graph
2. Builds xref index
3. Builds LanceDB vector index (if `--no-index` not set)
4. **Seeds kinetic parameters from literature** (if `--no-seed-kinetics` not set)

The build prints a stat block on completion:

```
nodes: 342 (compound: 198, reaction: 87, enzyme: 41, pathway: 16)
edges: 891 (SUBSTRATE_OF: 234, PRODUCT_OF: 234, CATALYZES: 87, CONTAINS: 336)
xref_index: 621 rows
lancedb: 255 rows indexed (dim=384)
parse_errors: 0
kinetic_parameters: 26 rows
regulatory_interactions: 13 rows
```

---

## Phase 3 — Manual Kinetic Parameter Updates (Optional)

If you need to re-seed or force-overwrite kinetic parameters:

```bash
# Overwrite existing rows (use after updating kinetics_fetch.py)
metakg-simulate seed --force
```

Kinetics are automatically populated with 26 key reactions and 13 allosteric regulatory rules from curated literature sources (Mulquiney & Kuchel, BRENDA, eQuilibrator).

| Table | Content |
|-------|---------|
| `kinetic_parameters` | Km, kcat, Vmax, Ki, ΔG°', Keq |
| `regulatory_interactions` | Allosteric rules (PFK, PK, HK, CS, IDH, G6PD) |

---

## Phase 4 — Analyse and Simulate

### Structural pathway analysis

```bash
# Print Markdown report to stdout
metakg-analyze

# Write to file
metakg-analyze --output analysis.md

# Plain text, top 30 items per section
metakg-analyze --output analysis.txt --plain --top 30
```

Covers: graph statistics, hub metabolites, complex reactions,
cross-pathway hubs, pathway coupling, dead-end metabolites, top enzymes.

---

### Flux Balance Analysis (FBA)

```bash
# Maximise total forward flux across a pathway
metakg-simulate fba --pathway hsa00010

# Optimise a specific reaction (e.g. pyruvate kinase)
metakg-simulate fba --pathway hsa00010 \
    --objective rxn:kegg:R00196 \
    --output fba_glycolysis.md

# Minimise instead of maximise
metakg-simulate fba --pathway hsa00020 --minimize

# All pathways in the graph (no --pathway filter)
metakg-simulate fba --output fba_all.md
```

---

### ODE Kinetic Simulation

```bash
# Default: 100 time units, 500 points, 1 mM initial concentration for all compounds
metakg-simulate ode --pathway hsa00010

# Custom time range and initial conditions
metakg-simulate ode --pathway hsa00010 \
    --time 200 --points 1000 \
    --conc cpd:kegg:C00031:5.0 \
    --conc cpd:kegg:C00002:3.0 \
    --default-conc 0.5 \
    --output ode_glycolysis.md
```

Uses Michaelis-Menten kinetics (seeded Km/Vmax values, or defaults of
Km = 0.5 mM / Vmax = 1.0 mM/s when parameters are absent).

---

### What-If Perturbation Analysis

```bash
# Enzyme knockout via FBA
metakg-simulate whatif --pathway hsa00010 \
    --mode fba \
    --knockout enz:kegg:hsa:2538 \
    --name HK_knockout \
    --output whatif_hk.md

# Partial inhibition (50%) of two enzymes via ODE
metakg-simulate whatif --pathway hsa00010 \
    --mode ode \
    --factor enz:kegg:hsa:5211:0.5 \
    --factor enz:kegg:hsa:5213:0.5 \
    --name PFK_inhibition \
    --output whatif_pfk.md

# Substrate pulse with FBA
metakg-simulate whatif --pathway hsa00010 \
    --mode ode \
    --conc cpd:kegg:C00031:10.0 \
    --name glucose_pulse \
    --output whatif_glucose.md
```

Reports the delta flux (FBA) or delta final concentration (ODE)
for every affected reaction or compound, sorted by magnitude.

---

## Phase 5 — Serve via MCP (for Claude)

```bash
# stdio transport (Claude Desktop / Claude Code)
metakg-mcp

# SSE transport (HTTP, for custom integrations)
metakg-mcp --transport sse
```

Exposes 9 tools to the connected agent:

| Tool | Purpose |
|------|---------|
| `query_pathway` | Semantic search for pathways |
| `get_compound` | Compound detail + connected reactions |
| `get_reaction` | Full stoichiometry + enzymes |
| `find_path` | Shortest metabolic route between two compounds |
| `seed_kinetics` | Populate kinetic parameters from literature |
| `get_kinetic_params` | Retrieve Km/Vmax/regulatory data for a reaction |
| `simulate_fba` | Flux Balance Analysis |
| `simulate_ode` | ODE kinetic time-course |
| `simulate_whatif` | Perturbation analysis |

---

## Quick-Start (from scratch)

```bash
pip install metakg[simulate,mcp]

# data/hsa_pathways/ already in repo — skip collect/wire if using available files
metakg-build --data data/hsa_pathways/
# ✓ Kinetic parameters are now seeded automatically during build
metakg-analyze --output analysis.md
metakg-simulate fba --pathway hsa00010 --output fba.md
metakg-mcp
```
