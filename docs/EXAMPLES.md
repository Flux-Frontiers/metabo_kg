# MetaboKG — Example Queries & Workflows

Practical examples covering CLI, Python API, simulation, and MCP tool usage.
Examples use the human (`hsa`) database by default; CHO-specific examples are
called out explicitly.

The CLI build command collocates all outputs under the data directory, so
`metabokg-build --data data/hsa_pathways` produces
`data/hsa_pathways/.metabokg/hsa.sqlite` and
`data/hsa_pathways/.metabokg/lancedb`.  Python API examples pass these paths
explicitly so they work regardless of CWD.

> **Runnable companion:** every Python block below is reproduced as a function
> in [`scripts/examples.py`](../scripts/examples.py) and is exercised end-to-end
> against the live SQLite + LanceDB databases.  Run all of them with
> `poetry run python scripts/examples.py` or a single section by name, e.g.
> `poetry run python scripts/examples.py ex_06_fba`.  If any expected output in
> this document drifts from what the script prints, this document is wrong.

---

## Table of Contents

1. [Building the Knowledge Graph](#1-building-the-knowledge-graph)
2. [Semantic Pathway Search](#2-semantic-pathway-search)
3. [Node Lookup & Graph Traversal](#3-node-lookup--graph-traversal)
4. [Finding Metabolic Paths](#4-finding-metabolic-paths)
5. [Flux Balance Analysis (FBA)](#5-flux-balance-analysis-fba)
6. [Kinetic ODE Simulation](#6-kinetic-ode-simulation)
7. [What-If Perturbation Analysis](#7-what-if-perturbation-analysis)
8. [CHO Cell Culture Workflows](#8-cho-cell-culture-workflows)
9. [MCP Tool Usage (Claude / AI assistants)](#9-mcp-tool-usage-claude--ai-assistants)
10. [Pathway Analysis Report](#10-pathway-analysis-report)

---

## 1. Building the Knowledge Graph

### Human pathways (standard build)

```bash
# Download KEGG KGML files (~19 MB, 369 pathways)
python scripts/download_human_kegg.py --output data/hsa_pathways

# Optional: download name TSVs for enrichment
python scripts/download_kegg_names.py

# Build: parse → SQLite → enrich → LanceDB → seed kinetics
# Outputs land in data/hsa_pathways/.metabokg/hsa.sqlite
metabokg-build --data ./data/hsa_pathways

# Full rebuild (wipe first)
metabokg-build --data ./data/hsa_pathways --wipe
```

### CHO pathways (separate database)

```bash
python scripts/download_cho_kegg.py --output data/cge_pathways
# Outputs land in data/cge_pathways/.metabokg/cge.sqlite
metabokg-build --data ./data/cge_pathways
```

### Python API

```python
from metabokg import MetaKG

# db_path and lancedb_dir default to CWD/.metabokg/; pass explicit paths
# when the build was run against a sub-directory data source.
HSA_DB    = "data/hsa_pathways/.metabokg/hsa.sqlite"
HSA_LANCE = "data/hsa_pathways/.metabokg/lancedb"

with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    s = kg.store.stats()
    print(f"nodes={s['total_nodes']}  edges={s['total_edges']}")
    nc = s['node_counts']
    print(f"  compounds={nc['compound']}  enzymes={nc['enzyme']}  "
          f"pathways={nc['pathway']}  reactions={nc['reaction']}")
    idx = kg.index.stats()
    print(f"indexed={idx['indexed_rows']}  dim={idx['dim']}")
```

Expected output:
```
nodes=17058  edges=41334
  compounds=5115  enzymes=9427  pathways=369  reactions=2147
indexed=7631  dim=384
```

---

## 2. Semantic Pathway Search

### CLI

```bash
# Find pathways matching a description
metabokg-viz --port 8500           # interactive browser

# Or query from the command line via MCP server (stdio)
echo '{"tool":"query_pathway","arguments":{"name":"fatty acid oxidation","k":5}}' \
  | metabokg-mcp
```

### Python API

```python
from metabokg import MetaKG

HSA_DB    = "data/hsa_pathways/.metabokg/hsa.sqlite"
HSA_LANCE = "data/hsa_pathways/.metabokg/lancedb"

with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    results = kg.query_pathway("fatty acid oxidation", k=5)
    for hit in results.hits:
        # hits carry _distance (LanceDB cosine); convert to similarity score
        score = 1.0 - hit["_distance"] / 2.0
        print(f"{hit['name']:<40}  score={score:.3f}")
```

Expected output (BAAI/bge-small-en-v1.5; `query_pathway` filters
`index.search` hits to `kind=='pathway'`, so fewer than `k` may return when
non-pathway nodes rank in the top-`k`):
```
Fatty acid degradation                    score=0.721
Biosynthesis of unsaturated fatty acids   score=0.709
Fatty acid metabolism                     score=0.706
Fatty acid biosynthesis                   score=0.703
```

### Filter by pathway category

```python
from metabokg import MetaKG
from metabokg.primitives import PATHWAY_CATEGORY_METABOLIC

HSA_DB    = "data/hsa_pathways/.metabokg/hsa.sqlite"
HSA_LANCE = "data/hsa_pathways/.metabokg/lancedb"

with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    pathways = kg.store.all_nodes(kind="pathway", category=PATHWAY_CATEGORY_METABOLIC)
    print(f"{len(pathways)} metabolic pathways")
```

Expected output:
```
99 metabolic pathways
```

---

## 3. Node Lookup & Graph Traversal

### Fetch a compound node

```python
from metabokg import MetaKG

HSA_DB    = "data/hsa_pathways/.metabokg/hsa.sqlite"
HSA_LANCE = "data/hsa_pathways/.metabokg/lancedb"

with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    pyruvate = kg.store.node("cpd:kegg:C00022")
    print(pyruvate["name"])        # Pyruvate
    print(pyruvate["formula"])     # None (formula not stored for all compounds)
```

Expected output:
```
Pyruvate
None
```

### Fetch a reaction with full stoichiometric detail

```python
with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    rxn = kg.store.reaction_detail("rxn:kegg:R00200")
    print("Substrates:", [s["name"] for s in rxn["substrates"]])
    print("Products:  ", [p["name"] for p in rxn["products"]])
    print("Enzymes:   ", [e["name"] for e in rxn["enzymes"]])
```

Expected output:
```
Substrates: ['Phosphoenolpyruvate']
Products:   ['Pyruvate']
Enzymes:    ['PKLR, PK1, PKL, PKRL, RPK']
```

### Walk neighbours of a node

```python
with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    # Reactions that consume glucose-6-phosphate
    nbrs = kg.store.neighbours(
        "cpd:kegg:C00092",
        rels=("SUBSTRATE_OF",),
    )
    for rxn_id in nbrs[:4]:
        node = kg.store.node(rxn_id)
        print(f"{rxn_id}: {node['name']}")
```

Expected output:
```
rxn:kegg:R00299: ATP:D-glucose 6-phosphotransferase
rxn:kegg:R00303: D-glucose-6-phosphate phosphohydrolase
rxn:kegg:R00771: D-glucose-6-phosphate aldose-ketose-isomerase
rxn:kegg:R07324: 1D-myo-inositol-3-phosphate lyase (isomerizing)
```

### Resolve a human-readable name to a node ID

```python
with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    node_id = kg.store.resolve_id("Glycolysis / Gluconeogenesis")
    print(node_id)   # pwy:kegg:hsa00010
```

Expected output:
```
pwy:kegg:hsa00010
```

---

## 4. Finding Metabolic Paths

### CLI

```bash
# Shortest path between glucose and acetyl-CoA
metabokg-mcp   # then send find_path tool call
```

### Python API

```python
from metabokg import MetaKG

HSA_DB    = "data/hsa_pathways/.metabokg/hsa.sqlite"
HSA_LANCE = "data/hsa_pathways/.metabokg/lancedb"

with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    result = kg.find_path(
        "cpd:kegg:C00031",   # Glucose
        "cpd:kegg:C00024",   # Acetyl-CoA
        max_hops=8,
    )
    if "error" not in result:
        names = [n["name"] for n in result["path"]]
        print(f"{result['hops']} hops: {' → '.join(names)}")
```

Expected output (the 9-hop bidirectional-BFS route currently passes through
the alpha-D-glucose-6-phosphate / NADPH cross-link before reaching
acetyl-CoA — a real shortest path under the live edge set):
```
9 hops: D-Glucose → ATP:D-glucose 6-phosphotransferase → D-Glucose 6-phosphate → D-glucose-6-phosphate aldose-ketose-isomerase → D-Fructose 6-phosphate → alpha-D-glucose-6-phosphate aldose-ketose-isomerase → alpha-D-Glucose 6-phosphate → alpha-D-glucose 6-phosphate ketol-isomerase → beta-D-Glucose 6-phosphate → beta-D-glucose-6-phosphate:NADP+ 1-oxoreductase → NADPH → glutathione:NADP+ oxidoreductase → NADP+ → isocitrate:NADP+ oxidoreductase (decarboxylating) → 2-Oxoglutarate → L-alanine:2-oxoglutarate aminotransferase → Pyruvate → pyruvate:NAD+ 2-oxidoreductase (CoA-acetylating) → Acetyl-CoA
```

### Cross-pathway hub metabolites

```python
with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    # ATP: how many pathways does it appear in?
    atp = kg.store.node("cpd:kegg:C00002")
    nbrs = kg.store.neighbours("cpd:kegg:C00002", rels=("CONTAINS",))
    print(f"ATP participates in {len(nbrs)} contexts")
```

Expected output:
```
ATP participates in 23 contexts
```

---

## 5. Flux Balance Analysis (FBA)

FBA finds the steady-state flux distribution that optimises a chosen objective
(default: maximise total flux as a biomass proxy).

### CLI

```bash
# Glycolysis — maximise flux
metabokg simulate fba --pathway "Glycolysis / Gluconeogenesis"

# TCA cycle — plain text output
metabokg simulate fba --pathway hsa00020 --plain

# Save Markdown report
metabokg simulate fba --pathway hsa00010 --output fba_glycolysis.md
```

### Python API

```python
from metabokg import MetaKG

HSA_DB    = "data/hsa_pathways/.metabokg/hsa.sqlite"
HSA_LANCE = "data/hsa_pathways/.metabokg/lancedb"

with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    result = kg.simulate_fba("pwy:kegg:hsa00010", maximize=True)
    print(f"Status:    {result['status']}")
    print(f"Objective: {result['objective_value']:.4f}")
    top = sorted(result["fluxes"].items(), key=lambda x: abs(x[1]), reverse=True)
    for rxn_id, flux in top[:5]:
        print(f"  {rxn_id}  {flux:+.4f}")
```

Expected output:
```
Status:    optimal
Objective: 151.5152
  rxn:kegg:R00710  +1000.0000
  rxn:kegg:R00711  -1000.0000
  rxn:kegg:R00746  -1000.0000
  rxn:kegg:R00754  +1000.0000
  rxn:kegg:R02569  +1000.0000
```

### Target a specific objective reaction

```python
with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    # Maximise pyruvate kinase flux specifically
    result = kg.simulate_fba(
        "pwy:kegg:hsa00010",
        objective_reaction="rxn:kegg:R00200",
        maximize=True,
    )
```

---

## 6. Kinetic ODE Simulation

ODE simulation integrates Michaelis-Menten rate equations over time.
**Always use BDF solver** — metabolic systems are stiff.

### CLI

```bash
# Seed literature kinetics first (idempotent)
metabokg simulate seed

# Glycolysis time-course: t=0..20, 50 points
metabokg simulate ode \
  --pathway "Glycolysis / Gluconeogenesis" \
  --time 20 --points 50

# Set glucose to 5 mM initially
metabokg simulate ode \
  --pathway hsa00010 \
  --time 20 --points 50 \
  --conc cpd:kegg:C00031=5.0
```

### Python API

```python
from metabokg import MetaKG

HSA_DB    = "data/hsa_pathways/.metabokg/hsa.sqlite"
HSA_LANCE = "data/hsa_pathways/.metabokg/lancedb"

with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    result = kg.simulate_ode(
        "pwy:kegg:hsa00010",
        t_end=20,
        t_points=50,
        initial_concentrations={"cpd:kegg:C00031": 5.0},   # Glucose: 5 mM
    )
    print(f"Status: {result['status']}")
    # Final concentrations, sorted by magnitude
    finals = {c: v[-1] for c, v in result["concentrations"].items() if v}
    for cpd_id, conc in sorted(finals.items(), key=lambda x: x[1], reverse=True)[:5]:
        node = kg.store.node(cpd_id)
        print(f"  {node['name']:<50}  {conc:.4f} mM")
```

Expected output:
```
Status: ok
  Acetyl-CoA                                          3.9991 mM
  D-Glyceraldehyde 3-phosphate                        3.4958 mM
  D-Fructose 1,6-bisphosphate                         3.0012 mM
  [Dihydrolipoyllysine-residue acetyltransferase] ...  2.9999 mM
  alpha-D-Glucose 6-phosphate                         2.3246 mM
```

---

## 7. What-If Perturbation Analysis

Compares a baseline simulation against a modified scenario to quantify the
effect of enzyme knockouts, activity changes, or substrate overrides.

**Note:** `simulate_whatif` signature is `(scenario_json, pathway_id, *, mode=...)`.

### CLI — enzyme knockout

```bash
# Knock out hexokinase (hsa:2539) in glycolysis
metabokg simulate whatif \
  --pathway "Glycolysis / Gluconeogenesis" \
  --mode fba \
  --knockout enz:kegg:hsa:2539 \
  --name hexokinase_ko
```

### CLI — enzyme activity reduction (50%)

```bash
metabokg simulate whatif \
  --pathway hsa00010 \
  --mode fba \
  --factor enz:kegg:hsa:2539=0.5 \
  --name hexokinase_50pct
```

### Python API

```python
import json
from metabokg import MetaKG

HSA_DB    = "data/hsa_pathways/.metabokg/hsa.sqlite"
HSA_LANCE = "data/hsa_pathways/.metabokg/lancedb"

with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    scenario = {
        "name": "hexokinase_knockout",
        "enzyme_knockouts": ["enz:kegg:hsa:2539"],
    }
    # Note: scenario_json is the first positional argument
    result = kg.simulate_whatif(
        json.dumps(scenario),
        "pwy:kegg:hsa00010",
        mode="fba",
    )
    baseline_obj = result["baseline"]["objective_value"]
    perturbed_obj = result["perturbed"]["objective_value"]
    pct_change = 100 * (perturbed_obj - baseline_obj) / baseline_obj
    print(f"Objective change: {pct_change:+.1f}%")

    # Top affected reactions
    deltas = result.get("delta_fluxes", {})
    for rxn_id, delta in sorted(deltas.items(), key=lambda x: abs(x[1]), reverse=True)[:5]:
        print(f"  {rxn_id}  Δflux={delta:+.4f}")
```

Expected output:
```
Objective change: +0.0%
  rxn:kegg:R09086  Δflux=+0.0000
  rxn:kegg:R00235  Δflux=+0.0000
  rxn:kegg:R02739  Δflux=+0.0000
  rxn:kegg:R01600  Δflux=+0.0000
  rxn:kegg:R01788  Δflux=+0.0000
```

### ODE what-if — substrate override

```python
with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
    # Double glucose, knock out LDHA (lactate dehydrogenase)
    scenario = {
        "name": "high_glucose_no_ldha",
        "enzyme_knockouts": ["enz:kegg:hsa:3939"],
        "initial_conc_overrides": {"cpd:kegg:C00031": 10.0},
    }
    result = kg.simulate_whatif(
        json.dumps(scenario),
        "pwy:kegg:hsa00010",
        mode="ode",
    )
    deltas = result.get("delta_final_conc", {})
    for cpd_id, delta in sorted(deltas.items(), key=lambda x: abs(x[1]), reverse=True)[:5]:
        node = kg.store.node(cpd_id)
        print(f"  {node['name']:<30}  Δ[final]={delta:+.4f} mM")
```

---

## 8. CHO Cell Culture Workflows

Chinese Hamster Ovary (CHO) cells are the dominant expression system for
biotherapeutics. MetaboKG includes CHO-specific kinetic parameters (37 °C,
pH 7.2) curated from published ¹³C-MFA and enzyme-kinetic studies, making it
directly applicable to bioreactor modelling and process optimisation — the
focus of our bioprocessing collaboration.

### Build the CHO knowledge graph

```bash
# Download 366 CHO (cge) KEGG pathways
python scripts/download_cho_kegg.py --output data/cge_pathways

# Build into data/cge_pathways/.metabokg/cge.sqlite
metabokg-build --data ./data/cge_pathways

# Seed CHO-specific kinetics (37°C, pH 7.2 — bioreactor conditions)
metabokg simulate seed-cho --db data/cge_pathways/.metabokg/cge.sqlite
```

### Python API — CHO database

```python
from metabokg import MetaKG

CGE_DB    = "data/cge_pathways/.metabokg/cge.sqlite"
CGE_LANCE = "data/cge_pathways/.metabokg/lancedb"

with MetaKG(db_path=CGE_DB, lancedb_dir=CGE_LANCE) as kg:
    s = kg.store.stats()
    print(f"CHO graph: {s['total_nodes']} nodes, {s['total_edges']} edges")
```

Expected output:
```
CHO graph: 16938 nodes, 40851 edges
```

### Simulate lactate metabolism — a key CHO bioprocess bottleneck

Lactate accumulation is a critical challenge in CHO fed-batch culture.
The lactate switch (aerobic glycolysis → oxidative metabolism) governs
both cell productivity and product quality.

```bash
# ODE simulation of glycolysis with elevated glucose (fed-batch conditions)
metabokg simulate ode \
  --pathway "Glycolysis / Gluconeogenesis" \
  --db data/cge_pathways/.metabokg/cge.sqlite \
  --time 20 --points 100 \
  --conc cpd:kegg:C00031=8.0 \
  --conc cpd:kegg:C00022=0.1
```

```python
from metabokg import MetaKG

CGE_DB    = "data/cge_pathways/.metabokg/cge.sqlite"
CGE_LANCE = "data/cge_pathways/.metabokg/lancedb"

# Fed-batch initial conditions: high glucose, low pyruvate
init_concs = {
    "cpd:kegg:C00031": 8.0,   # Glucose: 8 mM (fed-batch)
    "cpd:kegg:C00022": 0.1,   # Pyruvate: 0.1 mM
    "cpd:kegg:C00186": 0.5,   # L-Lactate: 0.5 mM
}

with MetaKG(db_path=CGE_DB, lancedb_dir=CGE_LANCE) as kg:
    result = kg.simulate_ode(
        "pwy:kegg:cge00010",         # CHO Glycolysis
        t_end=20,
        t_points=100,
        initial_concentrations=init_concs,
    )
    finals = {c: v[-1] for c, v in result["concentrations"].items() if v}
    lactate_final = finals.get("cpd:kegg:C00186", None)
    pyruvate_final = finals.get("cpd:kegg:C00022", None)
    print(f"Status: {result['status']}")
    print(f"Lactate [final]:  {lactate_final:.3f} mM" if lactate_final is not None else "Lactate: not tracked")
    print(f"Pyruvate [final]: {pyruvate_final:.3f} mM" if pyruvate_final is not None else "Pyruvate: not tracked")
```

Expected output:
```
Status: ok
Lactate [final]:  0.500 mM
Pyruvate [final]: 0.000 mM
```

### What-if: LDHA knockdown — reducing lactate accumulation

Lactate dehydrogenase A (LDHA) knockdown is a common strategy to reduce
lactate accumulation in CHO fed-batch culture.

```python
import json
from metabokg import MetaKG

CGE_DB    = "data/cge_pathways/.metabokg/cge.sqlite"
CGE_LANCE = "data/cge_pathways/.metabokg/lancedb"

with MetaKG(db_path=CGE_DB, lancedb_dir=CGE_LANCE) as kg:
    # 80% LDHA knockdown (siRNA-level suppression)
    scenario = {
        "name": "LDHA_80pct_knockdown",
        "enzyme_factors": {"enz:kegg:cge:3939": 0.2},
    }
    result = kg.simulate_whatif(
        json.dumps(scenario),
        "pwy:kegg:cge00010",
        mode="ode",
    )
    deltas = result.get("delta_final_conc", {})
    lactate_delta = deltas.get("cpd:kegg:C00186", 0.0)
    print(f"Lactate Δ[final]: {lactate_delta:+.3f} mM  (negative = reduction)")
```

### What-if: TCA flux under fed-batch (high glutamine)

```python
import json
from metabokg import MetaKG

CGE_DB    = "data/cge_pathways/.metabokg/cge.sqlite"
CGE_LANCE = "data/cge_pathways/.metabokg/lancedb"

# TCA cycle flux matters for energy yield driving recombinant protein synthesis
with MetaKG(db_path=CGE_DB, lancedb_dir=CGE_LANCE) as kg:
    scenario = {
        "name": "high_glutamine_tca",
        "initial_conc_overrides": {
            "cpd:kegg:C00025": 4.0,   # L-Glutamate: 4 mM
            "cpd:kegg:C00026": 1.0,   # 2-Oxoglutarate: 1 mM
        },
    }
    result = kg.simulate_whatif(
        json.dumps(scenario),
        "pwy:kegg:cge00020",          # CHO TCA cycle
        mode="fba",
    )
    print(f"Baseline objective: {result['baseline']['objective_value']:.4f}")
    print(f"Perturbed objective: {result['perturbed']['objective_value']:.4f}")
```

Expected output:
```
Baseline objective: 347.8261
Perturbed objective: 347.8261
```

### Inspect CHO-specific kinetic parameters

```python
from metabokg import MetaKG

CGE_DB    = "data/cge_pathways/.metabokg/cge.sqlite"
CGE_LANCE = "data/cge_pathways/.metabokg/lancedb"

with MetaKG(db_path=CGE_DB, lancedb_dir=CGE_LANCE) as kg:
    # store.all_kinetic_params() returns all params; filter by reaction_id
    all_params = kg.store.all_kinetic_params()
    params = [p for p in all_params if p.get("reaction_id") == "rxn:kegg:R00299"]
    for p in params:
        print(f"  Km={p.get('km')} mM  Vmax={p.get('vmax')} mM/s  "
              f"source={p.get('source_database')}  confidence={p.get('confidence')}")
```

Expected output (after `metabokg simulate seed-cho` has been run; the
hexokinase Km of 0.046 mM is the CHO-specific value at pH 7.2, 37 °C; row
count varies with the number of catalysing enzyme isoforms wired into the
graph):
```
  Km=0.046 mM  Vmax=2.2 mM/s  source=literature  confidence=None
  Km=0.046 mM  Vmax=2.2 mM/s  source=literature  confidence=None
  Km=0.046 mM  Vmax=2.2 mM/s  source=literature  confidence=None
```

---

## 9. MCP Tool Usage (Claude / AI assistants)

Start the MCP server, then use these tools from Claude or any MCP client.

```bash
metabokg-mcp --db data/hsa_pathways/.metabokg/hsa.sqlite --transport stdio
```

### `query_pathway` — semantic search

```json
{
  "tool": "query_pathway",
  "arguments": { "name": "TCA cycle energy metabolism", "k": 5 }
}
```

### `get_compound` — node detail

```json
{
  "tool": "get_compound",
  "arguments": { "compound_id": "cpd:kegg:C00022" }
}
```

### `get_reaction` — stoichiometric detail

```json
{
  "tool": "get_reaction",
  "arguments": { "reaction_id": "rxn:kegg:R00200" }
}
```

### `find_path` — shortest metabolic route

```json
{
  "tool": "find_path",
  "arguments": {
    "compound_a": "cpd:kegg:C00031",
    "compound_b": "cpd:kegg:C00024",
    "max_hops": 8
  }
}
```

### `simulate_fba` — steady-state flux

```json
{
  "tool": "simulate_fba",
  "arguments": {
    "pathway_id": "pwy:kegg:hsa00010",
    "maximize": true
  }
}
```

### `simulate_ode` — kinetic time-course

```json
{
  "tool": "simulate_ode",
  "arguments": {
    "pathway_id": "pwy:kegg:hsa00010",
    "t_end": 20,
    "t_points": 50,
    "initial_concentrations_json": "{\"cpd:kegg:C00031\": 5.0}"
  }
}
```

### `simulate_whatif` — perturbation analysis

```json
{
  "tool": "simulate_whatif",
  "arguments": {
    "pathway_id": "pwy:kegg:hsa00010",
    "scenario_json": "{\"name\": \"hk_ko\", \"enzyme_knockouts\": [\"enz:kegg:hsa:2539\"]}",
    "mode": "fba"
  }
}
```

### `get_kinetic_params` — inspect stored Km/Vmax

```json
{
  "tool": "get_kinetic_params",
  "arguments": { "reaction_id": "rxn:kegg:R00299" }
}
```

---

## 10. Pathway Analysis Report

The 7-phase analyzer characterises hub metabolites, complex reactions,
cross-pathway coupling, topology, and top enzymes.

### CLI

```bash
metabokg-analyze

# Save to file
metabokg-analyze --output analysis/hsa_analysis.md

# CHO database
metabokg-analyze --db data/cge_pathways/.metabokg/cge.sqlite --output analysis/cge_analysis.md
```

### Python API

`hub_metabolites` and `cross_pathway_hubs` are dataclass instances; access
fields as attributes, not dict keys.

```python
from metabokg.analyze import PathwayAnalyzer

with PathwayAnalyzer("data/hsa_pathways/.metabokg/hsa.sqlite") as analyzer:
    report = analyzer.run()
    print(f"Total nodes: {report.total_nodes}")
    print("Hub metabolites (top 5):")
    for m in report.hub_metabolites[:5]:
        print(f"  {m.name:<30}  pathways={m.pathway_count}  reactions={m.reaction_count}")
    print("Cross-pathway hubs (top 5):")
    for h in report.cross_pathway_hubs[:5]:
        print(f"  {h.name:<30}  pathways={h.pathway_count}  reactions={h.reaction_count}")
```

Expected output:
```
Total nodes: 17050
Hub metabolites (top 5):
  Acetyl-CoA                      pathways=37  reactions=37
  Pyruvate                        pathways=37  reactions=30
  Tetrahydrofolate                pathways=16  reactions=26
  Glycine                         pathways=27  reactions=24
  L-Glutamate                     pathways=46  reactions=23
Cross-pathway hubs (top 5):
  Calcium cation                  pathways=125  reactions=0
  D-myo-Inositol 1,4,5-trisphosphate  pathways=85  reactions=6
  Diacylglycerol                  pathways=79  reactions=0
  3',5'-Cyclic AMP                pathways=77  reactions=2
  Phosphatidylinositol-3,4,5-trisphosphate  pathways=74  reactions=4
```

---

## Key Node ID Reference

| Entity | Example ID | Description |
|--------|-----------|-------------|
| Human pathway | `pwy:kegg:hsa00010` | Glycolysis / Gluconeogenesis |
| CHO pathway | `pwy:kegg:cge00010` | CHO Glycolysis |
| Compound | `cpd:kegg:C00031` | Glucose |
| Compound | `cpd:kegg:C00022` | Pyruvate |
| Compound | `cpd:kegg:C00186` | L-Lactate |
| Compound | `cpd:kegg:C00024` | Acetyl-CoA |
| Reaction | `rxn:kegg:R00299` | Hexokinase (glucose → G6P) |
| Reaction | `rxn:kegg:R00200` | Pyruvate kinase |
| Human enzyme | `enz:kegg:hsa:2539` | HK1 — hexokinase 1 |
| Human enzyme | `enz:kegg:hsa:3939` | LDHA — lactate dehydrogenase A |
| CHO enzyme | `enz:kegg:cge:3939` | LDHA (*Cricetulus griseus*) |
