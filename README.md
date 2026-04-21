# MetaboKG — Metabolic Pathway Knowledge Graph

A comprehensive, extendable knowledge graph system for metabolic pathways with semantic search, interactive visualization, and MCP integration.

**MetaboKG** ingests pathway data from multiple formats (KGML, SBML, BioPAX, CSV), builds a unified semantic knowledge graph, and provides powerful querying and visualization tools for exploring metabolic relationships.

**CHO support:** Full *Cricetulus griseus* (CHO cell) build — 366 KEGG pathways, CHO-specific kinetics, and iCHO2441 genome-scale model ingestion. See [docs/cho_workflow.md](docs/cho_workflow.md).

**Sister Project:** [PyCodeKG](https://github.com/flux-frontiers/pycode_kg) — A codebase knowledge graph system for Python repositories. PyCodeKG provides the semantic analysis capabilities that make it possible to explore MetaboKG's own architecture and implementation.

[![Python 3.12 | 3.13](https://img.shields.io/badge/Python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![License: Elastic-2.0](https://img.shields.io/badge/License-Elastic%202.0-blue.svg)](https://www.elastic.co/licensing/elastic-license)
[![Version](https://img.shields.io/badge/Version-0.5.0-blue.svg)](https://github.com/flux-frontiers/metabo_kg/releases)
[![Poetry](https://img.shields.io/badge/Poetry-2.0+-blue.svg)](https://python-poetry.org/)

## Features

- **Multi-format Parser** — Ingest metabolic pathway data from KGML, SBML, BioPAX, and CSV formats
- **Multi-organism** — Human (hsa), CHO/C. griseus (cge), iCHO2441 GEM, and any KEGG organism
- **Unified Knowledge Graph** — Normalize and merge pathways into a single semantic graph with compounds, reactions, enzymes, and pathways
- **Semantic Search** — Vector-based similarity search using LanceDB and sentence-transformers
- **Interactive Visualization** — Explore pathways through Streamlit web interface or 3D PyVista viewer
- **Metabolic Simulations** — Flux balance analysis (FBA), kinetic ODE integration, and what-if perturbation analysis
- **MCP Integration** — Expose the knowledge graph via Model Context Protocol for AI assistant integration
- **CHO Kinetics** — 35 CHO-specific kinetic reactions at pH 7.2, 37°C from published bioreactor literature

## Quick Start

### Installation

```bash
# Clone and navigate to the repository
git clone https://github.com/flux-frontiers/metabo_kg.git
cd metabo_kg

# Create a Python 3.12+ virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install with all public extras (viz, viz3d, simulate, biopax)
poetry install --extras all
```

### Pathway Data

**Human (`data/hsa_pathways/`) and CHO (`data/cge_pathways/`) KEGG pathways are included in the repository** — no download needed for these.

To refresh or re-download them:

```bash
poetry run python scripts/download_human_kegg.py --output data/hsa_pathways
poetry run python scripts/download_cho_kegg.py --output data/cge_pathways
```

**iCHO2441 Genome-Scale Metabolic Model (6,663 reactions, SBML)** — XML files are included in `data/icho_model/` but the knowledge graph has not been built yet. To build:

```bash
metabokg-build --data data/icho_model  # → data/icho_model/.metabokg/icho.sqlite
```

To re-download the source XML:
```bash
poetry run python scripts/download_icho_model.py --output data/icho_model
```

### Build the Metabolic Knowledge Graphs

The `--data` directory drives automatic colocation — no `--db` or `--lancedb` flags needed.

#### Human (*Homo sapiens*, `hsa`)

```bash
metabokg-build --data ./data/hsa_pathways

# Output:
# Building MetaboKG from ./data/hsa_pathways...
# data_root   : ./data/hsa_pathways
# db_path     : data/hsa_pathways/.metabokg/hsa.sqlite
# nodes       : 17050  {'compound': 5115, 'reaction': 2139, 'enzyme': 9427, 'pathway': 369}
# edges       : 40166  {'SUBSTRATE_OF': 2551, 'PRODUCT_OF': 2532, 'CATALYZES': 2394, 'CONTAINS': 32689}
# isolated    : 0
# indexed     : 14911 vectors  dim=384
```

**Complete Human Metabolome:** All 369 KEGG metabolic and regulatory pathways in a single queryable knowledge graph with 17K+ fully-connected nodes and 40K+ edges.

#### Chinese Hamster Ovary (*C. griseus*, `cge`)

```bash
metabokg-build --data ./data/cge_pathways

# Output:
# Building MetaboKG from ./data/cge_pathways...
# data_root   : ./data/cge_pathways
# db_path     : data/cge_pathways/.metabokg/cge.sqlite
# nodes       : ~16800  {'compound': ..., 'reaction': ..., 'enzyme': ..., 'pathway': 366}
# edges       : ~39000  {'SUBSTRATE_OF': ..., 'PRODUCT_OF': ..., 'CATALYZES': ..., 'CONTAINS': ...}
# isolated    : 0
```

> **Enzyme name resolution** for CHO uses `data/cge_gene_names.tsv` (bundled). To refresh: `python scripts/download_kegg_names.py --genes cge`

#### iCHO2441 Genome-Scale Metabolic Model (SBML)

```bash
metabokg-build --data ./data/icho_model

# db_path     : data/icho_model/.metabokg/icho.sqlite
```

### Launch Web Explorer

```bash
metabokg-viz --db data/hsa_pathways/.metabokg/hsa.sqlite --port 8500
```

## Multi-Organism Support

MetaboKG supports multiple organisms, each stored in its own database for federated cross-organism queries.

| Organism | Script | Output | Pathways |
|----------|--------|--------|----------|
| Human (*Homo sapiens*, `hsa`) | `download_human_kegg.py` | `data/hsa_pathways/` | 369 |
| CHO (*C. griseus*, `cge`) | `download_cho_kegg.py` | `data/cge_pathways/` | 366 |
| iCHO2441 GEM (SBML) | `download_icho_model.py` | `data/icho_model/` | 6,663 reactions |

```bash
# db and lancedb colocate automatically under each data dir
metabokg-build --data data/hsa_pathways  # → data/hsa_pathways/.metabokg/hsa.sqlite
metabokg-build --data data/cge_pathways  # → data/cge_pathways/.metabokg/cge.sqlite
metabokg-build --data data/icho_model    # → data/icho_model/.metabokg/icho.sqlite
```

## Architecture

![MetaboKG Architecture Diagram](docs/metaKG_arch.png)

```
metabokg/
├── parsers/              # Format-specific parsers
│   ├── kgml.py          # KEGG KGML parser
│   ├── sbml.py          # SBML format parser
│   ├── biopax.py        # BioPAX format parser
│   └── csv_tsv.py       # CSV/TSV table parser
│
├── graph.py             # MetabolicGraph: file discovery & dispatch
├── primitives.py        # MetaNode, MetaEdge: core data types
├── store.py             # MetaStore: SQLite persistence layer
├── index.py             # MetaIndex: LanceDB vector indexing
├── embed.py             # Embedding utilities
│
├── cli.py               # Command-line entry points
├── mcp_tools.py         # MCP server implementation
├── cho_kinetics.py      # CHO-specific kinetic parameters
│
├── visualization/
│   ├── app.py           # Streamlit web explorer
│   ├── layout3d.py      # 3D layout algorithms (Allium, LayerCake)
│   └── viz3d.py         # PyVista 3D viewer
│
└── metabokg.py          # MetaKG: orchestrator
```

### Data Model

**Nodes** (4 kinds):
- **Compound** — Small molecule metabolites (e.g., glucose, ATP)
- **Reaction** — Biochemical transformations
- **Enzyme** — Proteins that catalyze reactions
- **Pathway** — Organized sets of reactions (e.g., glycolysis)

**Edges** (7 relation types):
- `SUBSTRATE_OF` — Compound is consumed in reaction
- `PRODUCT_OF` — Compound is produced by reaction
- `CATALYZES` — Enzyme catalyzes reaction
- `INHIBITS` — Compound inhibits reaction
- `ACTIVATES` — Compound activates reaction
- `CONTAINS` — Pathway contains reaction/compound
- `XREF` — Cross-reference to external database

## Commands

Quick reference — see **[CHEATSHEET.md](CHEATSHEET.md)** for full options and examples.

Parse pathway files and build the knowledge graph. Database is automatically colocated
inside `<data-dir>/.metabokg/` — derived from the data directory name.

```bash
# Simple form (db auto-derived)
metabokg-build --data ./data/hsa_pathways
metabokg-build --data ./data/cge_pathways

# With options
metabokg-build --data ./data/hsa_pathways \
               --wipe \
               --no-index \
               --no-enrich

Options:
  --data PATH        Directory containing pathway files (required)
  --db PATH          Override SQLite path (default: <data-dir>/.metabokg/<org>.sqlite)
  --lancedb PATH     Override LanceDB dir (default: <data-dir>/.metabokg/lancedb)
  --model NAME       Sentence-transformer model (default: all-MiniLM-L6-v2)
  --no-index         Skip building LanceDB vector index
  --wipe             Wipe existing data before building (default: keep)
  --no-enrich        Skip name enrichment (enrichment runs by default)
```

### `metabokg-simulate`

Run metabolic simulations against a built graph.

```bash
# Seed kinetic parameters (human)
metabokg-simulate --db data/hsa_pathways/.metabokg/hsa.sqlite seed

# Seed CHO-specific kinetics (pH 7.2, 37°C)
metabokg-simulate --db data/cge_pathways/.metabokg/cge.sqlite seed-cho

# FBA (steady-state)
metabokg-simulate --db data/cge_pathways/.metabokg/cge.sqlite \
    fba --pathway cge00010

# ODE (kinetic time-course, BDF stiff solver)
metabokg-simulate --db data/hsa_pathways/.metabokg/hsa.sqlite \
    ode --pathway hsa00010 --time 200 --conc cpd:kegg:C00031:5.0

# What-if perturbation
metabokg-simulate --db data/cge_pathways/.metabokg/cge.sqlite \
    whatif --pathway cge00010 --mode fba --knockout Ldha --name CHO_LDH_KO
```

### `metabokg-analyze`

Run 7-phase pathway analysis and generate a report.

```bash
metabokg-analyze --db data/hsa_pathways/.metabokg/hsa.sqlite \
                 --output analysis.md --top 20
```

### `metabokg-viz`

Launch interactive Streamlit web explorer.

```bash
metabokg-viz --db data/hsa_pathways/.metabokg/hsa.sqlite --port 8500

Options:
  --db PATH     SQLite database path
  --lancedb PATH  LanceDB directory path
  --port PORT   Streamlit server port (default: 8500)
```

### `metabokg-viz3d`

Launch interactive 3D PyVista metabolic pathway visualizer.

```bash
metabokg-viz3d --db data/hsa_pathways/.metabokg/hsa.sqlite \
               --layout allium --width 1400 --height 900

Options:
  --layout {allium,cake}   3D layout strategy (default: allium)
  --width INT              Window width in pixels (default: 1400)
  --height INT             Window height in pixels (default: 900)
```

**Layout Strategies:**
- **Allium** — Hub-spoke layout with pathways at center, reactions radially distributed
- **LayerCake** — Concentric rings by topological distance

### `metabokg-mcp`

Start MCP server to expose the knowledge graph to Claude and other AI assistants.

```bash
metabokg-mcp --db data/hsa_pathways/.metabokg/hsa.sqlite \
             --transport stdio

Options:
  --db PATH                SQLite database path
  --lancedb PATH           LanceDB directory path
  --transport {stdio,sse}  MCP transport method (default: stdio)
```

## Python API

### Basic Usage

```python
from metabokg import MetaKG

# Human metabolome
kg = MetaKG(
    db_path="data/hsa_pathways/.metabokg/hsa.sqlite",
    lancedb_dir="data/hsa_pathways/.metabokg/lancedb",
)

# Query a single node
compound = kg.store.node("cpd:kegg:C00022")  # Pyruvate

# Find shortest metabolic path
path = kg.store.find_shortest_path(
    from_id="cpd:kegg:C00022",  # Pyruvate
    to_id="cpd:kegg:C00084",    # Acetyl-CoA
    max_hops=6
)

kg.close()
```

### CHO Simulations

```python
from metabokg import MetaKG

kg = MetaKG(db_path="data/cge_pathways/.metabokg/cge.sqlite")

# FBA on CHO glycolysis
result = kg.simulate_fba(
    pathway_id="pwy:kegg:cge00010",
    maximize=True,
)
print(f"Status: {result['status']}")
print(f"Objective: {result['objective_value']}")

# LDH knockout what-if
import json
scenario = {"name": "LDH_KO", "enzyme_knockouts": ["Ldha"]}
result = kg.simulate_whatif(
    pathway_id="pwy:kegg:cge00010",
    scenario_json=json.dumps(scenario),
    mode="fba",
)

kg.close()
```

### Metabolic Simulations

**Flux Balance Analysis (FBA):**
```python
from metabokg import MetaKG

kg = MetaKG(db_path="data/hsa_pathways/.metabokg/hsa.sqlite", lancedb_dir="data/hsa_pathways/.metabokg/lancedb")

# Run steady-state optimization
result = kg.simulate_fba(
    pathway_id="pwy:kegg:hsa00010",  # Glycolysis
    maximize=True,
)
```

**Kinetic ODE Simulation:**
```python
result = kg.simulate_ode(
    pathway_id="pwy:kegg:hsa00010",
    t_end=20,
    t_points=50,
    initial_concentrations={"cpd:kegg:C00031": 5.0},  # Glucose: 5 mM
    ode_method="BDF",      # Stiff ODE solver (required for metabolic systems)
)
```

**What-If Analysis (Perturbations):**
```python
import json

scenario = {
    "name": "hexokinase_knockout",
    "enzyme_knockouts": ["enz:kegg:hsa:2539"]
}
result = kg.simulate_whatif(
    pathway_id="pwy:kegg:hsa00010",
    scenario_json=json.dumps(scenario),
    mode="fba",
)
```

**ODE Solver Notes:**
- Default solver is **BDF** (stiff-optimized) for metabolic systems
- `ode_method="RK45"` will hang on metabolic pathways — do not use

## Supported Input Formats

### KGML (KEGG Markup Language)
- Native KEGG pathway format for any KEGG organism (`hsa`, `cge`, `mmu`, etc.)
- Organism-agnostic parser — works for human, CHO, mouse, and all other KEGG organisms

### SBML (Systems Biology Markup Language)
- Standard for computational models (Level 2 and Level 3)
- Ingests genome-scale models such as iCHO2441 directly

### BioPAX (Biological Pathway Exchange)
- OWL-based RDF format; supports Reactome pathways
- Requires `rdflib` extra: `poetry install --extras biopax`

### CSV/TSV
- Simple tab-separated or comma-separated tables
- Columns: `source_id`, `source_name`, `target_id`, `target_name`, `relationship`, `relationship_type`

## Installation Variants

```bash
# Core functionality only
poetry install

# Metabolic simulations (FBA, ODE)
poetry install --extras simulate

# Web visualization (Streamlit)
poetry install --extras viz

# 3D visualization (PyVista + PyQt5)
poetry install --extras viz3d

# BioPAX format support
poetry install --extras biopax

# All public extras (simulate + viz + viz3d + biopax)
poetry install --extras all
```

> **Note:** The `kg` extra (`--extras kg`) installs PyCodeKG, DocKG, AgentKG, and other
> knowledge-graph integrations from private Flux Frontiers repositories. These require
> repository access and are not publicly available. Do not use `--extras kg` unless you
> have been granted access.

## Configuration

### Storage Layout

Each `metabokg-build` run colocates its artifacts inside the data directory:

```
data/
├── hsa_pathways/
│   ├── *.kgml
│   └── .metabokg/
│       ├── hsa.sqlite     ← SQLite graph database
│       └── lancedb/       ← vector index
├── cge_pathways/
│   ├── *.kgml
│   └── .metabokg/
│       ├── cge.sqlite
│       └── lancedb/
└── icho_model/
    ├── MODEL2206100001.xml
    └── .metabokg/
        ├── icho.sqlite
        └── lancedb/
```

### Environment Variables

Override the default db path for non-build commands:

```bash
export METABOKG_DB="data/cge_pathways/.metabokg/cge.sqlite"
export METABOKG_LANCEDB="data/cge_pathways/.metabokg/lancedb"

metabokg-simulate fba --pathway cge00010   # uses env vars
metabokg-mcp                               # uses env vars
```

### Embedding Model

- Default: `all-MiniLM-L6-v2` (384-dimensional, ~80 MB, downloaded once)
- Override via `--model` flag or `METABOKG_MODEL` env var
- **SQLite** — `<data-dir>/.metabokg/<org>.sqlite` (colocated with pathway data, e.g. `data/hsa_pathways/.metabokg/hsa.sqlite`)
- **LanceDB** — `<data-dir>/.metabokg/lancedb`
- **Embedding Model** — `all-MiniLM-L6-v2` (384-dimensional vectors)

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Parse 366 KGML files (CHO) | ~60s | With enrichment |
| Parse 369 KGML files (human) | ~60s | With enrichment |
| Build vector index | ~2min | ~15K nodes at 384-dim |
| Semantic search | <100ms | LanceDB approximate nearest neighbor |
| Shortest path (6 hops) | <50ms | BFS with ~17K nodes |
| FBA (glycolysis) | <10ms | HiGHS LP solver |
| ODE simulation (t=200) | <500ms | BDF stiff solver |

## Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=metabokg --cov-report=html

# Run specific test
poetry run pytest tests/test_parsers.py::test_kgml_parser
```

## Documentation

| Document | Contents |
|----------|---------|
| [docs/CAPABILITIES.md](docs/CAPABILITIES.md) | Full API and CLI reference |
| [docs/cho_workflow.md](docs/cho_workflow.md) | CHO build, kinetics, and simulation workflow |
| [docs/INSTALL.md](docs/INSTALL.md) | Step-by-step installation guide |
| [docs/MCP.md](docs/MCP.md) | MCP server setup and Claude integration |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | General build and analysis workflow |

## License

MetaboKG is licensed under the **Elastic License 2.0**.

This means:
- ✅ Free for **academic research** and **educational** use
- ✅ Free for **personal projects** and **evaluation**
- ✅ Source-available on GitHub
- ❌ Not permitted for **commercial SaaS** or managed-service offerings without a commercial license

For commercial licensing inquiries, contact [Flux Frontiers](https://github.com/Flux-Frontiers).

## Support

- **Documentation** — [docs/CAPABILITIES.md](docs/CAPABILITIES.md) for full reference
- **Issues** — Report bugs on [GitHub Issues](https://github.com/flux-frontiers/metabo_kg/issues)
- **Discussions** — Ask questions on [GitHub Discussions](https://github.com/flux-frontiers/metabo_kg/discussions)

## Acknowledgments

- [CodeKG](https://github.com/flux-frontiers/code_kg) — Semantic analysis and knowledge graph capabilities
- Layout algorithms adapted from [repo_vis](https://github.com/Suchanek/repo_vis)
- KEGG, Reactome, and MetaCyc teams for pathway data standards
- PyVista, Streamlit, and LanceDB communities

---

**Built with ❤️ for computational biology research -egs-**

*Last updated: April 2026*
