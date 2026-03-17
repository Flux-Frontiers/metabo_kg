
# MetaKG — Complete Capabilities Reference

**v0.2.0** · Metabolic pathway knowledge graph with simulation, semantic search, and MCP tooling.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Data Model](#2-data-model)
3. [File Format Parsers](#3-file-format-parsers)
4. [Building the Knowledge Graph](#4-building-the-knowledge-graph-metakg-build)
5. [Name Enrichment](#5-name-enrichment-metakg-enrich)
6. [Semantic Search & Vector Index](#6-semantic-search--vector-index)
7. [Simulation Engine](#7-simulation-engine)
   - [FBA — Flux Balance Analysis](#71-fba--flux-balance-analysis)
   - [ODE — Kinetic Simulation](#72-ode--kinetic-simulation)
   - [WhatIf — Perturbation Analysis](#73-whatif--perturbation-analysis)
8. [Kinetic & Regulatory Parameters](#8-kinetic--regulatory-parameters)
9. [Pathway Analysis](#9-pathway-analysis-metakg-analyze)
10. [MCP Server & Tools](#10-mcp-server--tools-metakg-mcp)
11. [CLI Reference](#11-cli-reference)
12. [Python API Reference](#12-python-api-reference)
13. [Database Schema](#13-database-schema)
14. [Dependencies & Extras](#14-dependencies--extras)

---

## 1. Architecture Overview

```
  Pathway Files (KGML / SBML / BioPAX / CSV)
           │
           ▼  parsers/
  ┌────────────────┐
  │  MetabolicGraph │  discovers + parses all files in a data directory
  └────────┬───────┘
           │  (nodes + edges)
           ▼
  ┌────────────────┐        ┌──────────────────┐
  │   MetaStore    │◄──────►│    LanceDB        │
  │  (SQLite WAL)  │        │  (vector index)   │
  └───────┬────────┘        └──────────────────┘
          │
          ▼  enrich.py (optional post-build pass)
  ┌────────────────┐
  │  Name Enricher  │  Phase 1: enzyme labels from CATALYZES edges
  │                 │  Phase 2: KEGG TSV → human-readable names
  └───────┬────────┘
          │
    ┌─────┴────────────────────────────────┐
    │              MetaKG                  │  high-level orchestrator
    │  build · enrich · query · find_path  │
    └────┬─────────┬──────────┬────────────┘
         │         │          │
         ▼         ▼          ▼
   CLI tools   MCP server   Python API
  (9 commands) (9 tools)
         │
   ┌─────┴─────────────────────────────────────┐
   │          MetabolicSimulator               │
   │   run_fba  ·  run_ode  ·  run_whatif      │
   └───────────────────────────────────────────┘
```

MetaKG keeps all graph data in a local **SQLite** file (`.metakg/meta.sqlite`) and an optional **LanceDB** directory (`.metakg/lancedb`) for vector-similarity search.  An optional enrichment pass replaces bare KEGG accessions with human-readable names stored directly in the database.  All components interact through a single stable API; the MCP server and CLI are thin wrappers.

---

## 2. Data Model

### 2.1 Node Kinds

| Kind | ID Prefix Example | Holds |
|------|-------------------|-------|
| `compound` | `cpd:kegg:C00022` | Small molecules, metabolites |
| `reaction` | `rxn:kegg:R00196` | Biochemical transformations |
| `enzyme` | `enz:kegg:hsa:2538` | Gene products, EC classes |
| `pathway` | `pwy:kegg:hsa00010` | Named metabolic pathways |

**ID scheme:**

```
node_id(kind, db, ext_id) → "<prefix>:<db>:<ext_id>"
```

When no external database ID is available a deterministic synthetic ID is used:

```
synthetic_id(kind, name) → "<prefix>:syn:<sha1[:8]>"
```

### 2.2 Edge Relations

| Relation | Direction | Meaning |
|----------|-----------|---------|
| `SUBSTRATE_OF` | compound → reaction | Compound consumed by reaction |
| `PRODUCT_OF` | reaction → compound | Compound produced by reaction |
| `CATALYZES` | enzyme → reaction | Enzyme catalyses reaction |
| `INHIBITS` | compound → reaction | Compound inhibits reaction |
| `ACTIVATES` | compound → reaction | Compound activates reaction |
| `CONTAINS` | pathway → reaction/compound | Pathway membership |
| `XREF` | any → any | Cross-database identity link |

Edges carry an optional **`evidence`** JSON blob (`{"stoich": 2.0, "compartment": "cytosol", ...}`).

### 2.3 Node Fields

```
MetaNode:
  id              — stable URI-style identifier
  kind            — compound | reaction | enzyme | pathway
  name            — primary display name (enriched to human-readable after metakg-enrich)
  description     — free-text for embedding/search
  formula         — molecular formula (compounds)
  charge          — formal charge (compounds)
  ec_number       — EC number (enzymes)
  stoichiometry   — JSON: {substrates, products, direction}
  xrefs           — JSON: {db_name: ext_id, ...}
  source_format   — kgml | sbml | biopax | csv
  source_file     — absolute path of origin file
```

---

## 3. File Format Parsers

Four parsers are registered and tried in order for every file in the data directory.

### 3.1 KGML — KEGG Markup Language

| Property | Detail |
|----------|--------|
| **Extensions** | `.xml`, `.kgml` |
| **Detection** | Root element is `<pathway>` |
| **Dependencies** | None (stdlib `xml.etree`) |
| **Source** | Download from KEGG REST API or KEGG Mapper |

**What is extracted:**

- Pathway node from `<pathway>` attributes (`number`, `title`, `org`)
- Compound nodes from `<entry type="compound">` (KEGG `cpd:C*` IDs)
- Enzyme / gene nodes from `<entry type="gene">` and `<entry type="ortholog">`
- Reactions from `<reaction>` elements
  - `name` attribute → KEGG reaction ID (e.g. `rn:R00299`)
  - `type` attribute → `reversible` or `irreversible`
  - `<substrate>` / `<product>` children → stoichiometry (coefficient = 1 unless annotated)
- `SUBSTRATE_OF` / `PRODUCT_OF` edges from substrate/product lists
- `CATALYZES` edges wired from gene entries referenced by reactions
- `CONTAINS` edges: pathway → all reactions

> **Note:** KGML files store compound and reaction names as bare KEGG accessions (e.g. `C00031`, `R00299`).
> Run `metakg-enrich` after building to replace these with human-readable names.
>
> **Scope:** Only metabolic KGML files (those containing `<reaction>` elements, typically `hsa000xx` series) are parsed. Signalling, disease, and cellular-process pathways that use only `<relation>` elements are silently skipped.

### 3.2 SBML — Systems Biology Markup Language

| Property | Detail |
|----------|--------|
| **Extensions** | `.xml`, `.sbml` |
| **Detection** | Root element is `<sbml>` |
| **Dependencies** | None (stdlib `xml.etree`) |
| **Levels** | SBML Level 2 and Level 3 |

**What is extracted:**

- `<species>` → compound nodes; identifiers.org annotations → `kegg`, `chebi` xrefs
- `<reaction>` → reaction nodes; `reversible` attribute respected
- `<listOfReactants>` / `<listOfProducts>` → stoichiometry with `stoichiometry` attribute
- `<listOfModifiers>` → modifier species checked against SBO terms:
  - SBO:0000460 or SBO:0000013 → `INHIBITS`
  - SBO:0000459 or SBO:0000461 → `ACTIVATES`
  - Otherwise → `CATALYZES`
- Compartments recorded in edge `evidence` JSON

### 3.3 BioPAX — Biological Pathway Exchange (Level 3)

| Property | Detail |
|----------|--------|
| **Extensions** | `.owl`, `.rdf` |
| **Detection** | Root namespace contains `biopax` |
| **Dependencies** | `rdflib` (optional extra `[biopax]`) |
| **Standard** | BioPAX Level 3 OWL ontology |

**What is extracted:**

- `bpx:SmallMolecule` / `bpx:Dna` / `bpx:Rna` → compound nodes
- `bpx:Protein` / `bpx:Complex` → enzyme nodes
- `bpx:BiochemicalReaction` → reaction nodes (left/right → SUBSTRATE_OF/PRODUCT_OF)
- `bpx:Catalysis` → `CATALYZES` edge (with direction)
- `bpx:Inhibition` → `INHIBITS` edge
- `bpx:Activation` → `ACTIVATES` edge
- `bpx:Pathway` → pathway node + `CONTAINS` edges to member reactions
- `bpx:UnificationXref` → database cross-references

### 3.4 CSV / TSV Tables

| Property | Detail |
|----------|--------|
| **Extensions** | `.csv`, `.tsv`, `.txt` |
| **Detection** | Sniffs delimiter; must have recognisable column header |
| **Dependencies** | None (stdlib `csv`) |
| **Configurability** | `CSVParserConfig` for custom column names |

**Recognised column names** (case-insensitive, aliases accepted):

| Field | Accepted Headers |
|-------|-----------------|
| Reaction ID | `reaction_id`, `rxn_id`, `reaction` |
| Reaction name | `reaction_name`, `name` |
| Substrate | `substrate`, `reactant`, `substrate_id` |
| Product | `product`, `product_id` |
| Enzyme | `enzyme`, `gene`, `catalyst`, `ec` |
| Stoichiometry | `stoichiometry`, `stoich` |
| Pathway | `pathway`, `pathway_name`, `pathway_id` |
| EC number | `ec_number`, `ec` |
| Reversible | `reversible`, `direction`, `type` |

Multiple substrates/products in one cell can be separated by `;` or `|`.  Rows sharing the same `reaction_id` are merged.

---

## 4. Building the Knowledge Graph — `metakg-build`

```bash
metakg-build \
  --data     <DIR>                    # required: directory of pathway files
  --db       .metakg/meta.sqlite      # SQLite output path
  --lancedb  .metakg/lancedb         # LanceDB vector index directory
  --model    all-MiniLM-L6-v2        # SentenceTransformer model
  --no-index                         # skip LanceDB index build
  --no-wipe                          # keep existing data (default: wipe before build)
  --enrich                           # run name enrichment after build
  --enrich-data  DIR                 # KEGG TSV directory (default: data/)
```

To incrementally add files without wiping, use `metakg-update` (same options, always merges):

```bash
metakg-update --data <DIR>
```

**What happens:**

1. `MetabolicGraph` walks `--data` recursively; skips `.md`, `.json`, `.py`, `.yaml`, `.log`
2. Each file is passed to parsers in priority order (KGML → SBML → BioPAX → CSV); first match wins
3. All `MetaNode` and `MetaEdge` objects are bulk-written to SQLite
4. The `xref_index` table is populated by expanding `xrefs` JSON blobs
5. Unless `--no-index`, compound + enzyme + pathway nodes are embedded and loaded into LanceDB
6. If `--enrich` is set, name enrichment runs immediately after indexing (see §5)

**Build stats printed to stderr:**

```
nodes: 342 (compound: 198, reaction: 87, enzyme: 41, pathway: 16)
edges: 891 (SUBSTRATE_OF: 234, PRODUCT_OF: 234, CATALYZES: 87, CONTAINS: 336)
xref_index: 621 rows
lancedb: 255 rows indexed (dim=384)
parse_errors: 0
Enrichment: 87 reaction names from graph, 198 compound names from TSV, 54 reaction names from TSV
```

---

## 5. Name Enrichment — `metakg-enrich`

KGML-sourced graphs initially carry bare KEGG accessions as node names (e.g. `C00031`,
`R00710`).  The enrichment pipeline replaces these with human-readable names and stores
them directly in `meta_nodes.name`, making them available everywhere — CLI, MCP, Streamlit.

### 5.1 Two-phase enrichment

**Phase 1 — no network, always runs:**

For every reaction node still carrying a bare accession name, look up all `CATALYZES`
edges pointing to it and join the catalysing enzyme gene symbols with ` / `:

```
R00710  →  "ADH1A / ADH1B / ADH1C"
```

**Phase 2 — requires downloaded KEGG name TSV files:**

Download the KEGG bulk name lists (~19 500 compounds, ~12 400 reactions) using the
provided script, then re-run enrichment:

```bash
# Download KEGG name lists (~30s, 1-second courtesy pause between requests)
python scripts/download_kegg_names.py

# Apply to the database
metakg-enrich --db .metakg/meta.sqlite
```

Phase 2 updates:
- **Compound names** from `data/kegg_compound_names.tsv` (e.g. `C00031` → `D-Glucose`)
- **Reaction names** from `data/kegg_reaction_names.tsv` (overrides Phase-1 enzyme labels
  with canonical KEGG reaction names where available)

Both phases are **idempotent** — safe to run multiple times.

### 5.2 Download script options

```bash
python scripts/download_kegg_names.py \
  [--data DIR]   # output directory (default: data/)
  [--force]      # re-download even if files already exist
  [--quiet]      # suppress progress output
```

TSV format produced:

```
C00031    D-Glucose
C00022    Pyruvate
R00710    Acetaldehyde:NAD+ oxidoreductase
...
```

### 5.3 Enrichment CLI options

```bash
metakg-enrich \
  [--db   .metakg/meta.sqlite]  # database to update
  [--data DIR]                  # directory containing TSV files (default: data/)
```

### 5.4 Integrating with build

Pass `--enrich` (and optionally `--enrich-data`) to `metakg-build` to run enrichment
automatically in one step:

```bash
metakg-build --data ./pathways --enrich
# equivalent to:
metakg-build --data ./pathways && metakg-enrich
```

### 5.5 Python API

```python
from metakg import MetaKG
from metakg.enrich import enrich, EnrichStats

with MetaKG(db_path=".metakg/meta.sqlite") as kg:
    # Integrated call via orchestrator
    stats: EnrichStats = kg.enrich(data_dir="data/")
    print(stats)
    # Enrichment: 87 reaction names from graph, 198 compound names from TSV, 54 reaction names from TSV

# Or lower-level
from metakg.store import MetaStore
from metakg.enrich import enrich_reactions_from_graph, enrich_from_tsv
store = MetaStore(".metakg/meta.sqlite")
n = enrich_reactions_from_graph(store)
n = enrich_from_tsv(store, Path("data/kegg_compound_names.tsv"), "compound")
```

---

## 6. Semantic Search & Vector Index

### 6.1 What is indexed

**Compounds, enzymes, and pathways** are indexed.  Reactions are excluded (no natural-language description to embed).

Each node is converted to a text document before embedding:

```
KIND: compound
NAME: Pyruvate
XREF kegg: C00022
XREF chebi: 15361
FORMULA: C3H4O3
DESCRIPTION:
The simplest alpha-keto acid; end product of glycolysis;
substrate of the TCA cycle via pyruvate dehydrogenase.
```

### 6.2 Default model

`sentence-transformers/all-MiniLM-L6-v2` — 384-dim, MIT licence, ~80 MB.  Any Sentence Transformers model can be substituted via `--model`.

### 6.3 Python usage

```python
from metakg import MetaKG

kg = MetaKG(db_path=".metakg/meta.sqlite", lancedb_dir=".metakg/lancedb")

# Semantic pathway search — returns top-k pathway nodes
result = kg.query_pathway("glucose catabolism", k=5)
for hit in result.hits:
    print(hit["name"], hit["distance"])

# Fetch a specific compound by any resolvable ID
cpd = kg.get_compound("cpd:kegg:C00022")   # full ID
cpd = kg.get_compound("kegg:C00022")       # shorthand
cpd = kg.get_compound("Pyruvate")          # name lookup (works after enrichment)

# Fetch a reaction with full stoichiometry
rxn = kg.get_reaction("rxn:kegg:R00196")

# Shortest metabolic path between two compounds
path = kg.find_path("cpd:kegg:C00031", "cpd:kegg:C00022", max_hops=8)
# → {"path": [...], "hops": 10, "edges": [...]}
```

### 6.4 ID resolution

`store.resolve_id(user_id)` resolves in this order:

1. Exact match in `meta_nodes.id`
2. Shorthand `db:ext_id` via `xref_index`
3. Case-insensitive name match in `meta_nodes.name`

---

## 7. Simulation Engine

The simulation engine lives in `metakg.simulate`.  It requires `scipy` (`pip install metakg[simulate]`).

```python
from metakg.store import MetaStore
from metakg.simulate import MetabolicSimulator, SimulationConfig, WhatIfScenario

store = MetaStore(".metakg/meta.sqlite")
sim   = MetabolicSimulator(store)
```

### `SimulationConfig` — shared configuration

```python
@dataclass
class SimulationConfig:
    pathway_id: str | None = None        # scope to one pathway
    reaction_ids: list[str] | None = None # or an explicit reaction list

    # ODE settings
    t_end: float = 100.0                 # end time (arbitrary units)
    t_points: int = 500                  # output sample count
    initial_concentrations: dict[str, float] = {}  # compound_id → mM
    default_concentration: float = 1.0   # fallback initial conc (mM)

    # ODE solver settings (metabolic systems are stiff — use BDF or Radau)
    ode_method: str = "BDF"              # BDF (default), Radau, RK45 (non-stiff only)
    ode_rtol: float = 1e-3              # relative tolerance
    ode_atol: float = 1e-5             # absolute tolerance
    ode_max_step: float | None = None   # None = adaptive (recommended)

    # FBA settings
    objective_reaction: str | None = None  # None → maximise total flux
    maximize: bool = True
    flux_bounds: dict[str, tuple[float, float]] = {}  # per-reaction overrides

    # ODE overrides (applied on top of DB values)
    vmax_overrides: dict[str, float] = {}  # reaction_id → fixed Vmax
    vmax_factors: dict[str, float] = {}    # reaction_id → multiplier
```

> **Important:** Metabolic systems are biochemically stiff (fast enzyme kinetics coexist with
> slow substrate depletion).  The default solver **BDF** handles this efficiently.  **Do not use
> RK45** for metabolic pathways — it will either hang or fail with "repeated convergence
> failures" as it must take millions of tiny internal steps.

---

### 7.1 FBA — Flux Balance Analysis

Finds the steady-state flux distribution that optimises a chosen reaction rate.

**Mathematical formulation:**

```
minimise   c · v
subject to S · v = 0         (metabolic steady-state)
           lb ≤ v ≤ ub        (reaction capacity bounds)

where:
  S    = stoichiometric matrix  (n_compounds × n_reactions)
  v    = flux vector            (n_reactions,)
  lb_j = 0    for irreversible reactions
       = −1000 for reversible reactions
  ub_j = 1000 for all reactions
  c_j  = −1 on objective reaction (maximise) or +1 (minimise)
         = −1/n on all irreversible reactions (biomass proxy)
```

Shadow prices (dual variables of the steady-state constraint) are returned: a positive shadow price for a compound means relaxing that compound's balance constraint would improve the objective.

**Solver:** `scipy.optimize.linprog` with the HiGHS backend.

**Result:**

```python
@dataclass
class FBAResult:
    status: str           # "optimal" | "infeasible" | "unbounded" | "error"
    objective_value: float | None
    fluxes: dict[str, float]        # reaction_id → flux value
    shadow_prices: dict[str, float] # compound_id → dual value
    message: str
```

**Python example:**

```python
config = SimulationConfig(
    pathway_id="pwy:kegg:hsa00010",       # glycolysis
    objective_reaction="rxn:kegg:R00196", # pyruvate kinase
    maximize=True,
)
result = sim.run_fba(config)
# result.status          → "optimal"
# result.objective_value → 1000.0  (upper bound, unconstrained)
# result.fluxes          → {"rxn:kegg:R00299": 1000.0, ...}
# result.shadow_prices   → {"cpd:kegg:C00022": -1.0, ...}
```

**CLI:**

```bash
metakg-simulate fba --db .metakg/meta.sqlite \
    --pathway hsa00010 \
    --objective rxn:kegg:R00196 \
    --output fba_glycolysis.md
```

---

### 7.2 ODE — Kinetic Simulation

Integrates the metabolic system forward in time using Michaelis-Menten rate equations.

**Rate equation (forward direction):**

```
v_j = Vmax_j · ∏_k  [S_k] / (Km_k + [S_k])
```

**Reversible extension (Haldane relationship):**

```
v_j = v_fwd − v_rev
    = Vmax_f · ∏_k [S_k]/(Km_k + [S_k])
    − (Vmax_f / Keq) · ∏_p [P_p]/(Km_p·Keq + [P_p])
```

**Mass balance ODE:**

```
d[C_i]/dt = Σ_j  s_ij · v_j(y, t)

where s_ij < 0 for substrates, s_ij > 0 for products.
```

**Solver:** `scipy.integrate.solve_ivp` with **BDF** (implicit, stiff-optimized).
Default tolerances: `rtol=1e-3`, `atol=1e-5`.  Max step: adaptive (no upper limit).

**Default kinetic parameters** (used when no database entry exists):
- Vmax = 1.0 mM/s
- Km = 0.5 mM
- Keq = 1.0

**Result:**

```python
@dataclass
class ODEResult:
    status: str   # "ok" | "failed" | "error"
    t: list[float]                           # time points
    concentrations: dict[str, list[float]]   # compound_id → [mM, ...]
    message: str
```

**Python example:**

```python
config = SimulationConfig(
    pathway_id="pwy:kegg:hsa00010",
    t_end=200.0,
    t_points=1000,
    initial_concentrations={
        "cpd:kegg:C00031": 5.0,  # glucose 5 mM
        "cpd:kegg:C00002": 3.0,  # ATP 3 mM
    },
    default_concentration=0.5,
    ode_method="BDF",   # default; explicit for documentation
)
result = sim.run_ode(config)
# result.t                           → [0.0, 0.2, 0.4, ...]
# result.concentrations["cpd:..."]   → [5.0, 4.97, 4.93, ...]
```

**CLI:**

```bash
metakg-simulate ode --db .metakg/meta.sqlite \
    --pathway hsa00010 \
    --time 200 --points 1000 \
    --conc cpd:kegg:C00031:5.0 \
    --conc cpd:kegg:C00002:3.0 \
    --default-conc 0.5
```

---

### 7.3 WhatIf — Perturbation Analysis

Runs a baseline simulation and a perturbed simulation side-by-side, then reports the differences.

**Perturbation types:**

| Type | FBA effect | ODE effect |
|------|-----------|-----------|
| **Enzyme knockout** | Reaction bounds → (0, 0) | Vmax → 0 for catalysed reactions |
| **Enzyme factor** | Upper flux bound scaled | Vmax multiplied by factor |
| **Substrate override** | (not applied) | Initial concentration replaced |

**Result:**

```python
@dataclass
class WhatIfResult:
    scenario_name: str
    baseline: FBAResult | ODEResult
    perturbed: FBAResult | ODEResult
    delta_fluxes: dict[str, float]       # FBA: Δflux per reaction
    delta_final_conc: dict[str, float]   # ODE: Δ[final mM] per compound
    mode: str  # "fba" | "ode"
```

**Python example:**

```python
scenario = WhatIfScenario(
    name="PFK_50pct_inhibition",
    enzyme_knockouts=["enz:kegg:hsa:5211"],    # PFKL silenced
    enzyme_factors={"enz:kegg:hsa:5213": 0.5}, # PFKM at half activity
    initial_conc_overrides={"cpd:kegg:C00158": 2.0}, # citrate 2 mM (ODE only)
)
result = sim.run_whatif(
    SimulationConfig(pathway_id="pwy:kegg:hsa00010"),
    scenario,
    mode="fba",
)
# result.delta_fluxes → {"rxn:kegg:R00756": -350.0, ...}
```

**CLI:**

```bash
metakg-simulate whatif --db .metakg/meta.sqlite \
    --pathway hsa00010 \
    --mode fba \
    --knockout enz:kegg:hsa:5211 \
    --factor enz:kegg:hsa:5213:0.5 \
    --name "PFK_perturbation" \
    --output whatif_pfk.md
```

---

## 8. Kinetic & Regulatory Parameters

### 8.1 KineticParam — fields

```python
@dataclass
class KineticParam:
    id: str                            # deterministic hash (kp_<sha1[:12]>)
    enzyme_id: str | None              # FK → meta_nodes
    reaction_id: str | None = None     # FK → meta_nodes
    substrate_id: str | None = None    # FK → meta_nodes (substrate-specific Km)

    # Enzyme kinetics
    km:               float | None  # Michaelis constant (mM)
    kcat:             float | None  # Catalytic rate (s⁻¹)
    vmax:             float | None  # Maximum velocity (mM/s @ 1 mg/mL enzyme)
    ki:               float | None  # Competitive inhibition constant (mM)
    hill_coefficient: float | None  # Hill n (cooperativity)

    # Thermodynamics
    delta_g_prime:        float | None  # ΔG°' (kJ/mol) at pH 7, 25°C, I=0.1 M
    equilibrium_constant: float | None  # Keq (dimensionless)

    # Measurement conditions
    ph:                   float | None  # pH
    temperature_celsius:  float | None  # °C
    ionic_strength:       float | None  # M

    # Provenance
    source_database:      str | None    # "brenda" | "sabio" | "literature" | "default"
    literature_reference: str | None    # PubMed ID or DOI
    organism:             str | None
    tissue:               str | None
    confidence_score:     float | None  # 0–1
    measurement_error:    float | None
```

### 8.2 RegulatoryInteraction — fields

```python
@dataclass
class RegulatoryInteraction:
    id: str               # deterministic hash (ri_<sha1[:12]>)
    enzyme_id: str        # regulated enzyme FK → meta_nodes
    compound_id: str      # effector compound FK → meta_nodes
    interaction_type: str # "allosteric_inhibitor" | "allosteric_activator"
                          # "feedback_inhibitor"   | "competitive_inhibitor"
    ki_allosteric: float | None  # half-saturation of effector (mM)
    hill_coefficient: float | None
    site: str | None      # "active" | "regulatory"
    organism: str | None
    source_database: str | None
```

### 8.3 Built-in curated parameter library

Seeded via `metakg-simulate seed` or `seed_kinetics(store)`.  All values are for *Homo sapiens*, pH 7.0, 37°C.

#### Kinetic parameters (26 reactions)

| Pathway | Reactions covered |
|---------|-----------------|
| **Glycolysis** (hsa00010) | Hexokinase (R00299), G6P isomerase (R02740), PFK (R00756), Aldolase (R01068), TPI (R01015), GAPDH (R01061), PGK (R01512), PGAM (R01518), Enolase (R00430), Pyruvate kinase (R00196), LDH (R00703) |
| **Pyruvate metabolism** (hsa00620) | Pyruvate dehydrogenase complex (R00351) |
| **TCA cycle** (hsa00020) | Citrate synthase (R00352), Aconitase (R01324), IDH (R00709), α-KG DH (R00621), Succinyl-CoA synthetase (R00432), Succinate DH (R02164), Fumarase (R01082), Malate DH (R00342) |
| **Pentose phosphate** (hsa00030) | G6P dehydrogenase (R00835), Transketolase (R01641) |
| **Oxidative phosphorylation** (hsa00190) | Complex I (R02163), Complex IV (R00081), ATP synthase (R00086) |
| **Fatty acid degradation** (hsa00071) | Acyl-CoA DH (R01278), Enoyl-CoA hydratase (R01279), 3-Hydroxyacyl-CoA DH (R01280), Thiolase (R00238) |
| **Glutathione** (hsa00480) | Glutathione reductase (R00115), Glutathione peroxidase (R00116) |
| **Purine** (hsa00230) | Adenylate kinase (R00127) |

Each entry includes: Km (mM), kcat (s⁻¹), Vmax (mM/s), Keq, ΔG°' (kJ/mol), and source reference.

#### Regulatory interactions (10 rules, ~20 rows after enzyme expansion)

| Regulated enzyme | Effector | Type | Ki_allosteric (mM) |
|-----------------|----------|------|--------------------|
| PFK | ATP | allosteric_inhibitor | 1.0 |
| PFK | Citrate | allosteric_inhibitor | 0.8 |
| PFK | AMP | allosteric_activator | 0.05 |
| PFK | ADP | allosteric_activator | 0.1 |
| Pyruvate kinase | F-1,6-BP | allosteric_activator | 0.03 |
| Pyruvate kinase | ATP | allosteric_inhibitor | 10.0 |
| Hexokinase | G6P | feedback_inhibitor | 0.3 |
| Citrate synthase | NADH | allosteric_inhibitor | 0.05 |
| Citrate synthase | ATP | allosteric_inhibitor | 0.9 |
| Isocitrate DH | ADP | allosteric_activator | 0.1 |
| Isocitrate DH | NADH | allosteric_inhibitor | 0.02 |
| Isocitrate DH | ATP | allosteric_inhibitor | 0.5 |
| G6P DH | NADPH | feedback_inhibitor | 0.15 |

### 8.4 Python API for kinetics

```python
# Seed all built-in values
from metakg.kinetics_fetch import seed_kinetics
n_kp, n_ri = seed_kinetics(store)           # skip existing
n_kp, n_ri = seed_kinetics(store, force=True)  # overwrite

# Retrieve parameters
params = store.kinetic_params_for_reaction("rxn:kegg:R00299")
params = store.kinetic_params_for_enzyme("enz:kegg:hsa:2538")
all_kp = store.all_kinetic_params()

# Retrieve regulatory interactions
regs = store.regulatory_interactions_for_enzyme("enz:kegg:hsa:5211")
regs = store.regulatory_interactions_for_reaction("rxn:kegg:R00756")

# Insert custom parameters
from metakg.primitives import KineticParam, _kp_id
kp = KineticParam(
    id=_kp_id("enz:kegg:hsa:2538", "rxn:kegg:R00299", None, "brenda"),
    enzyme_id="enz:kegg:hsa:2538",
    reaction_id="rxn:kegg:R00299",
    km=0.08, kcat=115.0, vmax=3.1,
    source_database="brenda",
    organism="Homo sapiens",
    confidence_score=0.9,
)
store.upsert_kinetic_param(kp)
```

---

## 9. Pathway Analysis — `metakg-analyze`

```bash
metakg-analyze --db .metakg/meta.sqlite \
               --output analysis.md \
               --top 20 \
               [--plain]
```

Runs seven analysis phases and emits a Markdown (or plain-text) report.

### 9.1 Analysis phases

| Phase | What it computes |
|-------|-----------------|
| **Graph statistics** | Node counts by kind; edge counts by relation |
| **Hub metabolites** | Compounds ranked by total reaction participation (substrate + product appearances); also shows per-pathway spread |
| **Complex reactions** | Reactions ranked by a complexity score = substrate_count + product_count + enzyme_count; highlights rate-limiting or allosteric candidates |
| **Cross-pathway hubs** | Compounds appearing in 2+ pathways; key shared utilities (ATP, NADH, CoA, etc.) |
| **Pathway coupling** | All pathway pairs ranked by number of shared metabolites; reveals biochemical interdependence |
| **Dead-end metabolites** | Compounds with only one reaction or appearing only as substrate / only as product — hints at pathway boundaries or parsing gaps |
| **Top enzymes** | Enzymes ranked by reaction coverage |

### 9.2 Biological insights section

The report closes with a narrative paragraph covering:

- Energy cofactor dominance (ATP, NADH as expected hubs)
- Strongest metabolic junction (highest hub)
- Most tightly coupled pathway pair
- Dead-end categorisation (boundary metabolites vs. parsing artefacts)
- Complexity outlier (most multi-substrate reaction)

### 9.3 Python API

```python
from metakg.analyze import PathwayAnalyzer, render_report

with PathwayAnalyzer(".metakg/meta.sqlite", top_n=20) as analyzer:
    report = analyzer.run()

md = render_report(report, markdown=True)
print(md)
```

---

## 10. MCP Server & Tools — `metakg-mcp`

```bash
metakg-mcp --db .metakg/meta.sqlite \
           --lancedb .metakg/lancedb \
           --model all-MiniLM-L6-v2 \
           --transport stdio   # or sse
```

Transport `stdio` (default) connects to Claude Desktop / Claude Code via stdin/stdout.  Transport `sse` starts an HTTP server.

### 10.1 All exposed tools

#### `query_pathway(name, k=8)`

Semantic search for pathways by name or description.

```json
[
  {"id": "pwy:kegg:hsa00010", "name": "Glycolysis / Gluconeogenesis",
   "member_count": 32, "distance": 0.12},
  ...
]
```

---

#### `get_compound(id)`

Look up a compound and all its connected reactions.

**Accepts:** `cpd:kegg:C00022`, `kegg:C00022`, `"Pyruvate"`, or `"C00022"`

```json
{
  "id": "cpd:kegg:C00022",
  "name": "Pyruvate",
  "formula": "C3H4O3",
  "xrefs": {"kegg": "C00022", "chebi": "15361"},
  "as_substrate_of": [{"id": "rxn:kegg:R00351", "name": "PDH complex"}, ...],
  "as_product_of":   [{"id": "rxn:kegg:R00196", "name": "Pyruvate kinase"}, ...]
}
```

---

#### `get_reaction(id)`

Full reaction detail with stoichiometry and enzymes.

```json
{
  "id": "rxn:kegg:R00196",
  "name": "Pyruvate kinase",
  "reversible": false,
  "substrates": [{"id": "cpd:kegg:C00074", "name": "Phosphoenolpyruvate", "stoich": 1.0}, ...],
  "products":   [{"id": "cpd:kegg:C00022", "name": "Pyruvate", "stoich": 1.0}, ...],
  "enzymes":    [{"id": "enz:kegg:hsa:5315", "name": "PKM", "ec": "2.7.1.40"}]
}
```

---

#### `find_path(compound_a, compound_b, max_hops=6)`

Bidirectional BFS through the reaction graph.

```json
{
  "path": ["cpd:kegg:C00031", "rxn:kegg:R00299", "cpd:kegg:C00668", ...],
  "hops": 10,
  "edges": [
    {"src": "cpd:kegg:C00031", "rel": "SUBSTRATE_OF", "dst": "rxn:kegg:R00299"},
    ...
  ]
}
```

---

#### `simulate_fba(pathway_id, objective_reaction="", maximize=True)`

Run FBA; returns fluxes enriched with reaction names.

```json
{
  "status": "optimal",
  "objective_value": 1000.0,
  "fluxes": {
    "rxn:kegg:R00299": {"name": "Hexokinase", "flux": 1000.0},
    "rxn:kegg:R00756": {"name": "Phosphofructokinase", "flux": 1000.0}
  },
  "shadow_prices": {"cpd:kegg:C00022": -1.0}
}
```

---

#### `simulate_ode(pathway_id, t_end=100, t_points=200, initial_concentrations_json="{}", default_concentration=1.0)`

Run kinetic ODE simulation (BDF solver).

```json
{
  "status": "ok",
  "message": "Integration OK. t=[0, 100], 200 time points, 45 compounds, 22 reactions.",
  "t": [0.0, 0.5, 1.0, ...],
  "concentrations": {"cpd:kegg:C00022": [0.0, 0.012, 0.031, ...]},
  "summary": [
    {"id": "cpd:kegg:C00002", "name": "ATP", "initial_mM": 3.0, "final_mM": 2.87}
  ]
}
```

---

#### `simulate_whatif(pathway_id, scenario_json, mode="fba")`

Baseline vs. perturbed simulation.

**`scenario_json` schema:**

```json
{
  "name": "string",
  "enzyme_knockouts": ["enz:kegg:hsa:2538"],
  "enzyme_factors":   {"enz:kegg:hsa:5211": 0.5},
  "initial_conc_overrides": {"cpd:kegg:C00158": 2.0}
}
```

**Response:**

```json
{
  "scenario_name": "HK_knockout",
  "mode": "fba",
  "baseline_objective": 1000.0,
  "perturbed_objective": 0.0,
  "top_changes": [
    {"id": "rxn:kegg:R00299", "name": "Hexokinase",
     "baseline_flux": 1000.0, "perturbed_flux": 0.0, "delta": -1000.0}
  ]
}
```

---

#### `get_kinetic_params(reaction_id)`

Retrieve stored kinetic and regulatory parameters for a reaction.

---

#### `seed_kinetics(force=False)`

Populate the database with curated literature kinetic parameters.

```json
{
  "kinetic_params_written": 34,
  "regulatory_interactions_written": 18,
  "message": "Seeded 34 kinetic parameter row(s) and 18 regulatory interaction row(s)."
}
```

---

### 10.2 Python: registering tools

```python
from metakg import MetaKG
from metakg.mcp_tools import create_server, register_tools

kg     = MetaKG(db_path=".metakg/meta.sqlite")
server = create_server(kg, name="my-metakg-server")
server.run(transport="stdio")

# Or mount onto an existing FastMCP instance:
from mcp import FastMCP
mcp = FastMCP("my-app")
register_tools(mcp, kg)
```

---

## 11. CLI Reference

All commands use [Click](https://click.palletsprojects.com/) and support `--help` at every level.

### `metakg-build`

```
metakg-build --data <DIR>
             [--db   .metakg/meta.sqlite]
             [--lancedb .metakg/lancedb]
             [--model all-MiniLM-L6-v2]
             [--no-index]          skip LanceDB index
             [--no-wipe]           keep existing data (default: wipe before build)
             [--enrich]            run name enrichment after building
             [--enrich-data DIR]   KEGG TSV directory (default: data/)
```

### `metakg-update`

Incrementally merge new pathway files into an existing database without wiping.

```
metakg-update --data <DIR>
              [--db   .metakg/meta.sqlite]
              [--lancedb .metakg/lancedb]
              [--model all-MiniLM-L6-v2]
              [--no-index]
              [--enrich]
              [--enrich-data DIR]
```

### `metakg-enrich`

```
metakg-enrich [--db   .metakg/meta.sqlite]
              [--data DIR]          directory with kegg_*_names.tsv files
```

Phase 1 always runs (enzyme labels from CATALYZES edges).
Phase 2 runs if `kegg_compound_names.tsv` / `kegg_reaction_names.tsv` exist in `--data`.

Download KEGG name files first with:

```bash
python scripts/download_kegg_names.py [--data DIR] [--force] [--quiet]
```

### `metakg-mcp`

```
metakg-mcp [--db   .metakg/meta.sqlite]
           [--lancedb .metakg/lancedb]
           [--model all-MiniLM-L6-v2]
           [--transport stdio|sse]
```

### `metakg-analyze`

```
metakg-analyze [--db .metakg/meta.sqlite]
               [--output FILE.md]
               [--top 20]
               [--plain]
```

### `metakg-analyze-basic`

```
metakg-analyze-basic [--db .metakg/meta.sqlite]
                     [--output FILE.md]
                     [--top 20]
                     [--plain]
```

### `metakg-simulate`

```
# Shared options (apply to all subcommands):
metakg-simulate [--db .metakg/meta.sqlite]
                [--output FILE.md] [--top 25] [--plain]
                <subcommand>

# Seed kinetic parameters (run once after build):
metakg-simulate seed [--force]

# FBA:
metakg-simulate fba [--pathway ID|NAME]
                    [--objective RXN_ID]
                    [--minimize]

# ODE kinetic simulation:
metakg-simulate ode [--pathway ID|NAME]
                    [--time 100.0]
                    [--points 500]
                    [--conc CPD_ID:MM ...]      # repeatable
                    [--default-conc 1.0]

# What-if perturbation:
metakg-simulate whatif [--pathway ID|NAME]
                        [--mode fba|ode]
                        [--knockout ENZ_ID ...]      # repeatable
                        [--factor ENZ_ID:FACTOR ...]  # repeatable
                        [--conc CPD_ID:MM ...]        # repeatable (ODE)
                        [--name LABEL]
                        [--time 100.0]
```

### `metakg-viz`

Launches a **Streamlit** web application for interactive pathway exploration (requires `pip install metakg[viz]`).

### `metakg-viz3d`

Launches a **PyVista** 3D graph viewer (requires `pip install metakg[viz3d]`).

---

## 12. Python API Reference

### `MetaKG` — high-level orchestrator

```python
from metakg import MetaKG

kg = MetaKG(
    db_path     = ".metakg/meta.sqlite",
    lancedb_dir = ".metakg/lancedb",
    model       = "all-MiniLM-L6-v2",
    table       = "metakg_nodes",
)

kg.build(data_dir, wipe=False, build_index=True,
         enrich=False, enrich_data_dir=None)  → MetabolicBuildStats
kg.enrich(data_dir=None)                      → EnrichStats
kg.query_pathway(name: str, k: int = 8)       → MetabolicQueryResult
kg.get_compound(id: str)                       → dict | None
kg.get_reaction(id: str)                       → dict | None
kg.find_path(a: str, b: str, max_hops: int = 6) → dict
kg.seed_kinetics(force=False)                  → dict
kg.simulate_fba(pathway_id=None, ...)          → dict
kg.simulate_ode(pathway_id=None, ...)          → dict
kg.simulate_whatif(pathway_id=None, ...)       → dict
kg.stats()                                     → dict
kg.close()
```

### `MetaStore` — SQLite persistence

```python
from metakg.store import MetaStore

store = MetaStore(".metakg/meta.sqlite")
# or:
with MetaStore(".metakg/meta.sqlite") as store: ...

# Write
store.write(nodes, edges, wipe=False)
store.build_xref_index()                         → int
store.upsert_kinetic_param(KineticParam)
store.upsert_kinetic_params(list[KineticParam])  → int
store.upsert_regulatory_interaction(RegulatoryInteraction)
store.upsert_regulatory_interactions(list)       → int

# Read — nodes
store.node(node_id)                              → dict | None
store.node_by_xref(db_name, ext_id)             → dict | None
store.resolve_id(user_id)                        → str | None
store.all_nodes(kind=None)                       → list[dict]

# Read — edges
store.edges_of(node_id)                          → list[dict]
store.neighbours(node_id, rels=DEFAULT_RELS)     → list[str]
store.edges_within(node_ids: set)                → list[dict]

# Read — complex queries
store.reaction_detail(rxn_id)                    → dict | None
store.find_shortest_path(from_id, to_id, max_hops=6) → dict

# Read — kinetics
store.kinetic_params_for_reaction(rxn_id)        → list[dict]
store.kinetic_params_for_enzyme(enz_id)          → list[dict]
store.all_kinetic_params()                       → list[dict]
store.regulatory_interactions_for_enzyme(enz_id) → list[dict]
store.regulatory_interactions_for_reaction(rxn_id) → list[dict]

# Stats
store.stats()                                    → dict
store.close()
```

### `MetabolicSimulator`

```python
from metakg.simulate import (
    MetabolicSimulator, SimulationConfig, WhatIfScenario,
    FBAResult, ODEResult, WhatIfResult,
    render_fba_result, render_ode_result, render_whatif_result,
)

sim = MetabolicSimulator(store)
sim.run_fba(config: SimulationConfig)                          → FBAResult
sim.run_ode(config: SimulationConfig)                          → ODEResult
sim.run_whatif(config, scenario, mode="fba"|"ode")             → WhatIfResult

render_fba_result(result, store=None, top_n=20, markdown=True) → str
render_ode_result(result, store=None, top_n=20, markdown=True) → str
render_whatif_result(result, store=None, top_n=20, markdown=True) → str
```

### `EnrichStats` — enrichment result

```python
from metakg.enrich import EnrichStats

@dataclass
class EnrichStats:
    reactions_from_graph: int  # reaction names set from enzyme CATALYZES labels
    compounds_from_tsv:   int  # compound names updated from KEGG TSV
    reactions_from_tsv:   int  # reaction names updated from KEGG TSV
```

---

## 13. Database Schema

```sql
-- Nodes
CREATE TABLE meta_nodes (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,    -- compound|reaction|enzyme|pathway
    name          TEXT NOT NULL,    -- human-readable after metakg-enrich
    description   TEXT,
    formula       TEXT,
    charge        INTEGER,
    ec_number     TEXT,
    stoichiometry TEXT,             -- JSON
    xrefs         TEXT,             -- JSON
    source_format TEXT,
    source_file   TEXT
);

-- Edges
CREATE TABLE meta_edges (
    src      TEXT NOT NULL,
    rel      TEXT NOT NULL,
    dst      TEXT NOT NULL,
    evidence TEXT,                  -- JSON
    PRIMARY KEY (src, rel, dst)
);

-- Fast xref lookup
CREATE TABLE xref_index (
    node_id  TEXT NOT NULL,
    db_name  TEXT NOT NULL,
    ext_id   TEXT NOT NULL,
    PRIMARY KEY (db_name, ext_id)
);

-- Kinetic parameters
CREATE TABLE kinetic_parameters (
    id                   TEXT PRIMARY KEY,   -- kp_<sha1[:12]>
    enzyme_id            TEXT,
    reaction_id          TEXT,
    substrate_id         TEXT,
    km                   REAL,
    kcat                 REAL,
    vmax                 REAL,
    ki                   REAL,
    hill_coefficient     REAL,
    delta_g_prime        REAL,
    equilibrium_constant REAL,
    ph                   REAL,
    temperature_celsius  REAL,
    ionic_strength       REAL,
    source_database      TEXT,
    literature_reference TEXT,
    organism             TEXT,
    tissue               TEXT,
    confidence_score     REAL,
    measurement_error    REAL
);

-- Allosteric & regulatory interactions
CREATE TABLE regulatory_interactions (
    id               TEXT PRIMARY KEY,   -- ri_<sha1[:12]>
    enzyme_id        TEXT NOT NULL,
    compound_id      TEXT NOT NULL,
    interaction_type TEXT NOT NULL,
    ki_allosteric    REAL,
    hill_coefficient REAL,
    site             TEXT,
    organism         TEXT,
    source_database  TEXT
);

-- Indexes: kind, name, ec_number, edge src/dst/rel, xref node,
--          kp_enzyme, kp_reaction, ri_enzyme, ri_compound
```

SQLite is opened with `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; check_same_thread=False`
for concurrent read performance (required for multi-threaded Streamlit deployments).

---

## 14. Dependencies & Extras

### Core (always required)

```toml
python                = "^3.12, <3.13"
lancedb               = ">=0.29.0"
numpy                 = ">=1.24.0"
sentence-transformers = ">=2.7.0"
click                 = ">=8.0"
mcp                   = ">=1.0.0"
```

> **Note:** `mcp` is a core dependency — the MCP server is always available without any extra flags.

### Optional extras

| Extra | Package(s) | Purpose |
|-------|-----------|---------|
| `[simulate]` | `scipy >= 1.11.0` | FBA (linprog/HiGHS) + ODE (solve_ivp BDF) |
| `[biopax]` | `rdflib >= 6.0.0` | BioPAX Level 3 RDF/OWL parsing |
| `[viz]` | `streamlit >= 1.35.0`, `pyvis >= 0.3.2`, `matplotlib >= 3.8.0`, `pandas >= 2.0.0` | Interactive web UI + plots |
| `[viz3d]` | `pyvista >= 0.44.0`, `pyvistaqt >= 0.11.0`, `PyQt5 >= 5.15.0` | 3D graph viewer (Qt-embedded PyVista window) |
| `[all]` | All of the above | Everything |

```bash
# With Poetry (recommended)
poetry install                        # core + mcp
poetry install --extras simulate      # + FBA / ODE
poetry install --extras viz           # + Streamlit web UI
poetry install --extras viz3d         # + PyVista 3D viewer
poetry install --extras biopax        # + BioPAX parsing
poetry install --all-extras           # everything

# With pip (after package release)
pip install metakg[simulate]
pip install metakg[simulate,viz]
pip install metakg[all]
```

See [`docs/INSTALL.md`](INSTALL.md) for a full step-by-step installation guide.

---

## Quick-start Workflow

```bash
# 1. Install
pip install metakg[simulate,mcp]

# 2. Build the graph from a directory of KGML / SBML / BioPAX / CSV files
metakg-build --data ./pathways --db .metakg/meta.sqlite

# 3. Download KEGG name lists and enrich the graph with human-readable names
python scripts/download_kegg_names.py
metakg-enrich --db .metakg/meta.sqlite
# (or combine steps 2–3: metakg-build --data ./pathways --enrich)

# 4. Seed kinetic parameters from curated literature values
metakg-simulate seed --db .metakg/meta.sqlite

# 5. Run steady-state FBA on glycolysis
metakg-simulate fba --db .metakg/meta.sqlite --pathway hsa00010 -o fba.md

# 6. Run ODE kinetic simulation for 200 time units (BDF solver, ~0.2s)
metakg-simulate ode --db .metakg/meta.sqlite --pathway hsa00010 \
    --time 200 --conc cpd:kegg:C00031:5.0 -o ode.md

# 7. Knock out hexokinase and see the cascade
metakg-simulate whatif --db .metakg/meta.sqlite --pathway hsa00010 \
    --mode fba --knockout enz:kegg:hsa:2538 --name HK_KO -o hk_ko.md

# 8. Run thorough pathway analysis report
metakg-analyze --db .metakg/meta.sqlite -o analysis.md

# 9. Start MCP server for Claude integration
metakg-mcp --db .metakg/meta.sqlite --transport stdio
```
