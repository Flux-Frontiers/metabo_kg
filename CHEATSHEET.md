# MetaboKG Cheatsheet

Quick reference for all CLI commands, MCP tools, and Python API.
Full documentation: [docs/](docs/) | [EXAMPLES.md](EXAMPLES.md)

---

## Available Pathway Corpora

| Corpus | DB path | Pathways | Nodes | Edges | Status |
|--------|---------|----------|-------|-------|--------|
| Human `hsa` | `data/hsa_pathways/.metabokg/hsa.sqlite` | 369 | 17,050 | 40,166 | ✅ Bundled |
| CHO `cge` | `data/cge_pathways/.metabokg/cge.sqlite` | 366 | ~16,800 | ~39,000 | ✅ Bundled |
| iCHO2441 `icho` | `data/icho_model/.metabokg/icho.sqlite` | — | — | 6,663 rxns | 🔨 Build required |

```bash
# Build all corpora (pathway data already bundled in repo)
metabokg-build --data data/hsa_pathways   # hsa.sqlite
metabokg-build --data data/cge_pathways   # cge.sqlite
metabokg-build --data data/icho_model     # icho.sqlite
```

> Default commands use the hsa corpus. Pass `--db` / `--lancedb` to target another corpus.

---

## CLI Commands

### Build & Manage

```bash
# Full build — wipes existing data first (default)
metabokg-build --data DIR

# Keep existing data and merge new files on top
metabokg-build --data DIR --no-wipe

# Incremental — add new files without wiping
metabokg-update --data DIR

# Enrich node names only (no rebuild)
metabokg-enrich --db PATH --data DIR

# Install pre-commit snapshot hook
metabokg install-hooks
```

**`metabokg-build` options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--data PATH` | (required) | Directory containing pathway files |
| `--db PATH` | `<data>/.metabokg/<org>.sqlite` | SQLite output path |
| `--lancedb PATH` | `<data>/.metabokg/lancedb` | LanceDB output directory |
| `--model NAME` | `all-MiniLM-L6-v2` | Sentence-transformer model |
| `--no-index` | — | Skip LanceDB vector index |
| `--no-wipe` | — | Keep existing data instead of wiping |
| `--no-enrich` | — | Skip name enrichment |

---

### Search & Pack

```bash
# Semantic search (vector, all node kinds)
metabokg-query "glucose metabolism"
metabokg-query "hexokinase" --k 5 --hop 1

# Text-only fallback
metabokg-query "ATP synthase" --k 5 --text-only

# Context-rich pack for LLM use (Markdown to stdout)
metabokg-pack "TCA cycle"
metabokg-pack "fatty acid oxidation" --k 5 --hop 2 -o fa_pack.md
metabokg-pack "glycolysis" --fmt json -o glycolysis.json
```

**`metabokg-query` options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--k INT` | `10` | Number of seed results |
| `--hop INT` | `0` | Graph hops to expand from seeds |
| `--text-only` | — | Substring search instead of vector |
| `--db PATH` | env / hsa default | SQLite database |
| `--lancedb PATH` | env / hsa default | LanceDB directory |

**`metabokg-pack` options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--k INT` | `8` | Seed results from vector search |
| `--hop INT` | `1` | Graph hops to expand from seeds |
| `--output / -o PATH` | stdout | Write to file |
| `--fmt {md,json}` | `md` | Output format |
| `--max-rxn INT` | `30` | Max reactions per pathway section |
| `--db PATH` | env / hsa default | SQLite database |
| `--lancedb PATH` | env / hsa default | LanceDB directory |

---

### Simulate

```bash
# Seed kinetic parameters from curated literature (run once)
metabokg-simulate seed

# Flux Balance Analysis
metabokg-simulate fba --pathway pwy:kegg:hsa00010

# Kinetic ODE time-course
metabokg-simulate ode --pathway pwy:kegg:hsa00010 --time 100 --points 300

# Perturbation / what-if
metabokg-simulate whatif --pathway pwy:kegg:hsa00010 \
  --knockout enz:kegg:hsa:2539
```

---

### Visualize

```bash
# 2D Streamlit explorer
metabokg-viz
metabokg-viz --db data/hsa_pathways/.metabokg/hsa.sqlite --port 8500

# 3D PyVista viewer
metabokg-viz3d
metabokg-viz3d --layout cake   # allium (default) | cake
metabokg-viz3d --export-html graph.html
```

---

### Analyze

```bash
# Full 7-phase pathway analysis report
metabokg-analyze
metabokg-analyze --output report.md

# Compact structured analysis
metabokg-analyze-basic
```

---

### MCP Server

```bash
metabokg-mcp
metabokg-mcp --db data/hsa_pathways/.metabokg/hsa.sqlite \
             --lancedb data/hsa_pathways/.metabokg/lancedb \
             --transport stdio
```

---

### Snapshots

```bash
metabokg-snapshot save 0.5.0
metabokg-snapshot list
metabokg-snapshot show latest
metabokg-snapshot diff <key-a> <key-b>
metabokg-snapshot prune
```

---

## MCP Tools

Tools exposed to Claude and other MCP clients via `metabokg-mcp`.

| Tool | Signature | Description |
|------|-----------|-------------|
| `pack` | `pack(text, k=8, hop=1)` | Context-rich Markdown pack — best first call |
| `query_pathway` | `query_pathway(name, k=8)` | Semantic pathway search |
| `get_compound` | `get_compound(id)` | Compound + connected reactions |
| `get_reaction` | `get_reaction(id)` | Full stoichiometric detail |
| `find_path` | `find_path(compound_a, compound_b, max_hops=6)` | Shortest metabolic path |
| `simulate_fba` | `simulate_fba(pathway_id, objective_reaction, maximize)` | Flux Balance Analysis |
| `simulate_ode` | `simulate_ode(pathway_id, t_end, t_points, ...)` | Kinetic ODE simulation |
| `simulate_whatif` | `simulate_whatif(pathway_id, scenario_json, mode)` | Perturbation analysis |
| `get_kinetic_params` | `get_kinetic_params(reaction_id)` | Km / Vmax / kcat values |
| `seed_kinetics` | `seed_kinetics(force=False)` | Populate kinetic parameters |
| `snapshot_list` | `snapshot_list(limit=20)` | List graph snapshots |
| `snapshot_show` | `snapshot_show(key)` | Show single snapshot |
| `snapshot_diff` | `snapshot_diff(key_a, key_b)` | Compare two snapshots |

---

## Python API

### Instantiation

```python
from metabokg import MetaKG

# Default (hsa corpus)
kg = MetaKG()

# Explicit paths
kg = MetaKG(
    db_path="data/hsa_pathways/.metabokg/hsa.sqlite",
    lancedb_dir="data/hsa_pathways/.metabokg/lancedb",
)
kg.close()  # always close when done
```

### Search & Pack

```python
# Semantic search — all node kinds
result = kg.query("glucose metabolism", k=10)
result = kg.query("hexokinase", k=5, hop=1)   # + 1-hop graph expansion
for hit in result.hits:
    print(f"[{hit['kind']}] {hit['name']}")

# Pathway-only search
result = kg.query_pathway("glycolysis", k=5)
for hit in result.hits:
    print(f"{hit['name']} ({hit['member_count']} reactions)")

# Context-rich pack (pathways + reactions + enzymes + compounds)
pack = kg.pack("TCA cycle", k=8, hop=1)     # returns MetabolicPack
print(pack.to_markdown())
pack.save("context.md")
pack.save("context.json", fmt="json")
```

### Node Lookup

```python
# Single node
node = kg.store.node("cpd:kegg:C00022")           # Pyruvate
compound = kg.get_compound("cpd:kegg:C00022")      # with reactions
rxn = kg.get_reaction("rxn:kegg:R00200")           # with substrates/products/enzymes

# Resolve by name or shorthand
nid = kg.store.resolve_id("D-Glucose")             # → "cpd:kegg:C00031"
nid = kg.store.resolve_id("kegg:C00031")

# Neighbours
neighbours = kg.store.neighbours("cpd:kegg:C00022")
expanded = kg.store.expand_hops([node], hop=2)     # BFS expansion
```

### Graph Traversal

```python
# Shortest path between compounds
path = kg.find_path("cpd:kegg:C00031", "cpd:kegg:C00022")
path = kg.find_path("D-Glucose", "Pyruvate", max_hops=6)
# → {"path": [...], "hops": 2, "edges": [...]}

# Reaction detail
detail = kg.store.reaction_detail("rxn:kegg:R00200")
# → {"substrates": [...], "products": [...], "enzymes": [...]}
```

### Simulations

```python
# Seed kinetics once per build
kg.seed_kinetics()

# FBA — steady-state flux
result = kg.simulate_fba("pwy:kegg:hsa00010", maximize=True)
# → {"status": "optimal", "objective_value": ..., "fluxes": {...}}

# ODE — time-course (always use BDF for stiff metabolic systems)
result = kg.simulate_ode(
    "pwy:kegg:hsa00010",
    t_end=100, t_points=300,
    initial_concentrations={"cpd:kegg:C00031": 5.0},
    ode_method="BDF",
)

# What-if perturbation
import json
result = kg.simulate_whatif(
    "pwy:kegg:hsa00010",
    json.dumps({"enzyme_knockouts": ["enz:kegg:hsa:2539"]}),
    mode="fba",
)
```

---

## Node ID Formats

| Kind | Format | Example |
|------|--------|---------|
| Compound | `cpd:kegg:<CXXXXX>` | `cpd:kegg:C00031` |
| Reaction | `rxn:kegg:<RXXXXX>` | `rxn:kegg:R00200` |
| Enzyme | `enz:kegg:<org>:<gene>` | `enz:kegg:hsa:2538` |
| Pathway | `pwy:kegg:<org><XXXXX>` | `pwy:kegg:hsa00010` |

**Shorthand accepted by most API calls:**
- `kegg:C00031` → resolves to `cpd:kegg:C00031`
- `"D-Glucose"` (name) → resolves via name index
- `"Glycolysis"` (pathway name) → resolves via name index

**Common metabolite IDs:**
| Metabolite | ID |
|-----------|-----|
| D-Glucose | `cpd:kegg:C00031` |
| Pyruvate | `cpd:kegg:C00022` |
| ATP | `cpd:kegg:C00002` |
| ADP | `cpd:kegg:C00008` |
| NAD⁺ | `cpd:kegg:C00003` |
| NADH | `cpd:kegg:C00004` |
| Acetyl-CoA | `cpd:kegg:C00024` |
| Oxaloacetate | `cpd:kegg:C00036` |
| Citrate | `cpd:kegg:C00158` |

**Common pathway IDs:**
| Pathway | ID |
|---------|-----|
| Glycolysis / Gluconeogenesis | `pwy:kegg:hsa00010` |
| TCA cycle | `pwy:kegg:hsa00020` |
| Fatty acid degradation | `pwy:kegg:hsa00071` |
| Oxidative phosphorylation | `pwy:kegg:hsa00190` |
| Pentose phosphate pathway | `pwy:kegg:hsa00030` |
| Amino sugar metabolism | `pwy:kegg:hsa00520` |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `METABOKG_DB` | `data/hsa_pathways/.metabokg/hsa.sqlite` | Default SQLite path |
| `METABOKG_LANCEDB` | `data/hsa_pathways/.metabokg/lancedb` | Default LanceDB path |
| `METABOKG_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model |
