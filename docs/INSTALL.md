# MetaKG — Installation Guide

**v0.2.0** · Metabolic pathway knowledge graph with simulation, semantic search, and MCP tooling.

*Author: Eric G. Suchanek, PhD*

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Getting the Code](#2-getting-the-code)
3. [Installation Options](#3-installation-options)
   - [Core install](#31-core-install-recommended-starting-point)
   - [With simulation](#32-with-simulation-scipy)
   - [With web visualization](#33-with-web-visualization-streamlit)
   - [With 3D visualization](#34-with-3d-visualization-pyvista)
   - [With BioPAX support](#35-with-biopax-support)
   - [Everything](#36-everything)
4. [Verifying the Install](#4-verifying-the-install)
5. [Downloading Pathway Data](#5-downloading-pathway-data)
6. [Building the Knowledge Graph](#6-building-the-knowledge-graph)
7. [Name Enrichment](#7-name-enrichment)
7a. [Pathway Categories](#7a-pathway-categories)
8. [Seeding Kinetic Parameters](#8-seeding-kinetic-parameters)
9. [Running the MCP Server](#9-running-the-mcp-server)
10. [Running the Web Explorer](#10-running-the-web-explorer)
11. [Running the 3D Visualizer](#11-running-the-3d-visualizer)
12. [Development Install](#12-development-install)
13. [Environment Variables](#13-environment-variables)
14. [Upgrading](#14-upgrading)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Python** | 3.12.x | Exactly 3.12 — the package pins `^3.12, <3.13` |
| **Poetry** | ≥ 2.0 | Package and dependency manager |
| **Git** | any | For cloning the repo and the `code-kg` dependency |
| **Disk space** | ~2 GB | Sentence-transformer model (~80 MB) + KEGG data (~19 MB) + LanceDB vectors |
| **RAM** | ≥ 4 GB | Recommended for building the full human metabolome (22K+ nodes) |

### Check your Python version

```bash
python3 --version
# Must be: Python 3.12.x
```

If you have multiple Python versions, use `pyenv` or `conda` to select 3.12:

```bash
# With pyenv
pyenv install 3.12.8
pyenv local 3.12.8

# With conda
conda create -n metakg python=3.12
conda activate metakg
```

### Install Poetry (if not already installed)

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Verify:

```bash
poetry --version
# Poetry (version 2.x.x)
```

---

## 2. Getting the Code

```bash
git clone https://github.com/Flux-Frontiers/meta_kg.git
cd meta_kg
```

The repository includes sample KEGG pathway data in `data/hsa_pathways/` (a subset of human pathways). The full human metabolome can be downloaded separately — see [Section 5](#5-downloading-pathway-data).

---

## 3. Installation Options

MetaKG uses **Poetry extras** to keep the core install lightweight. Choose the combination that matches your use case.

### 3.1 Core install (recommended starting point)

Installs the graph engine, semantic search, CLI tools, and MCP server support.

```bash
poetry install
```

**What you get:**
- `metakg-build` — parse pathway files and build the knowledge graph
- `metakg-enrich` — enrich node names with human-readable labels
- `metakg-analyze` / `metakg-analyze-basic` — pathway analysis reports
- `metakg-mcp` — MCP server for Claude and other AI assistants
- Full Python API (`MetaKG`, `MetaStore`, `MetaIndex`)

**Included packages:** `lancedb`, `numpy`, `sentence-transformers`, `click`, `mcp`, `code-kg`

> **Note:** `mcp` is a core dependency — the MCP server is always available without any extra flags.

---

### 3.2 With simulation (scipy)

Adds Flux Balance Analysis (FBA) and kinetic ODE simulation.

```bash
poetry install --extras simulate
```

**What you get (in addition to core):**
- `metakg-simulate` — FBA, ODE, and what-if perturbation analysis from the CLI
- `MetabolicSimulator` Python class
- `scipy.optimize.linprog` (HiGHS backend) for FBA
- `scipy.integrate.solve_ivp` (BDF solver) for stiff ODE integration

> **Solver note:** Metabolic systems are biochemically stiff. The default solver is **BDF** (implicit, stiff-optimized). Do **not** use `RK45` for metabolic pathways — it will hang or fail with convergence errors.

---

### 3.3 With web visualization (Streamlit)

Adds the interactive browser-based pathway explorer.

```bash
poetry install --extras viz
```

**What you get (in addition to core):**
- `metakg-viz` — launches a Streamlit web app at `http://localhost:8500`
- Interactive graph browser with semantic search
- Node detail panels with cross-references
- Network visualization via PyVis

**Included packages:** `streamlit`, `matplotlib`, `pandas`, `pyvis`

---

### 3.4 With 3D visualization (PyVista)

Adds the interactive 3D graph viewer.

```bash
poetry install --extras viz3d
```

**What you get (in addition to core):**
- `metakg-viz3d` — launches a PyVista 3D viewer
- Two layout strategies: **Allium** (pathway-as-flower) and **LayerCake** (vertical stratification)
- Export to HTML or PNG

**Included packages:** `pyvista`, `pyvistaqt`, `PyQt5`

> **macOS note:** PyQt5 requires XCode command-line tools. If you see build errors:
> ```bash
> xcode-select --install
> ```

---

### 3.5 With BioPAX support

Adds parsing of BioPAX Level 3 `.owl` / `.rdf` files (e.g., from Reactome).

```bash
poetry install --extras biopax
```

**Included packages:** `rdflib`

---

### 3.6 Everything

Install all optional extras at once.

```bash
poetry install --all-extras
```

Or equivalently:

```bash
poetry install --extras all
```

This is the recommended approach for development or if you want to explore all features without thinking about which extras you need.

---

### Combining extras

You can combine any extras:

```bash
# Simulation + MCP (common for server deployments)
poetry install --extras simulate

# Simulation + web visualization
poetry install --extras "simulate viz"

# Everything except 3D (lighter install for headless servers)
poetry install --extras "simulate viz biopax"
```

---

## 4. Verifying the Install

After installation, confirm the CLI entry points are available:

```bash
# Check core commands
poetry run metakg --help
poetry run metakg-build --help
poetry run metakg-mcp --help

# Check simulation (if installed with --extras simulate)
poetry run metakg-simulate --help

# Check visualization (if installed with --extras viz)
poetry run metakg-viz --help

# Check 3D visualization (if installed with --extras viz3d)
poetry run metakg-viz3d --help
```

Verify the Python package imports correctly:

```bash
poetry run python -c "
import metakg
from metakg import MetaKG
from metakg.store import MetaStore
print('metakg OK')

# Check MCP (always available)
from mcp.server.fastmcp import FastMCP
print('mcp OK')

# Check simulation (only if --extras simulate was used)
try:
    from scipy.integrate import solve_ivp
    from scipy.optimize import linprog
    print('scipy OK')
except ImportError:
    print('scipy not installed (run: poetry install --extras simulate)')
"
```

---

## 5. Downloading Pathway Data

MetaKG ships with a subset of human KEGG pathways in `data/hsa_pathways/`. For the full human metabolome (369 pathways, ~19 MB), use the provided download script:

```bash
# Download all 369 human KEGG pathways
poetry run python scripts/download_human_kegg.py --output data/hsa_pathways

# Preview what would be downloaded (no network requests)
poetry run python scripts/download_human_kegg.py --output data/hsa_pathways --dry-run
```

The script makes one KEGG REST API request per pathway with a 1-second courtesy pause between requests (~6 minutes total). KEGG's terms of service permit non-commercial use.

**Download script options:**

```
--output DIR     Output directory (default: data/hsa_pathways)
--dry-run        List pathways without downloading
--force          Re-download files that already exist
--quiet          Suppress progress output
```

After downloading, the directory will contain 369 `.kgml` files:

```
data/hsa_pathways/
├── hsa00010.kgml   # Glycolysis / Gluconeogenesis
├── hsa00020.kgml   # Citrate cycle (TCA cycle)
├── hsa00030.kgml   # Pentose phosphate pathway
...
```

---

## 6. Building the Knowledge Graph

The build step parses all pathway files and writes the graph to SQLite + LanceDB.

### Basic build

```bash
metakg-build --data ./data/hsa_pathways
```

This wipes any existing database and rebuilds from scratch using default paths:
`.metakg/meta.sqlite` for SQLite and `.metakg/lancedb` for the vector index. Enrichment (human-readable names) is enabled by default.

### Full build with all options

```bash
metakg-build \
  --data     ./data/hsa_pathways \
  --db       .metakg/meta.sqlite \
  --lancedb  .metakg/lancedb \
  --model    all-MiniLM-L6-v2
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--data PATH` | *(required)* | Directory containing pathway files |
| `--db PATH` | `.metakg/meta.sqlite` | SQLite output path |
| `--lancedb PATH` | `.metakg/lancedb` | LanceDB vector index directory |
| `--model NAME` | `all-MiniLM-L6-v2` | Sentence-transformer model for embeddings |
| `--no-index` | off | Skip building the LanceDB vector index |
| `--no-wipe` | off | Keep existing data instead of wiping before build |
| `--no-enrich` | off | Skip name enrichment (on by default) |
| `--enrich-data DIR` | `data/` | Directory containing KEGG name TSV files |

### Expected output (full human metabolome)

```
Building MetaKG from ./data/hsa_pathways...
data_root   : ./data/hsa_pathways
db_path     : .metakg/meta.sqlite
nodes       : 17050  {'compound': 5115, 'reaction': 2139, 'enzyme': 9427, 'pathway': 369}
edges       : 40166  {'SUBSTRATE_OF': 2551, 'PRODUCT_OF': 2532, 'CATALYZES': 2394, 'CONTAINS': 32689}
isolated    : 0
indexed     : 14911 vectors  dim=384
```

> **First build note:** The sentence-transformer model (`all-MiniLM-L6-v2`, ~80 MB) is downloaded automatically on first use and cached in `~/.cache/huggingface/`. Subsequent builds are much faster.

### Rebuilding

The build wipes and rebuilds by default. To **add** new pathway files to an
existing database without wiping, use `metakg-update` or pass `--no-wipe`:

```bash
# Merge new files into the existing graph
metakg-update --data ./new_pathways

# Equivalent explicit flag on build
metakg-build --data ./new_pathways --no-wipe
```

---

## 7. Name Enrichment

KGML files store compound and reaction names as bare KEGG accessions (e.g., `C00031`, `R00710`). The enrichment step replaces these with human-readable names and runs **by default** during `metakg-build`.

### Default behavior

```bash
metakg-build --data ./data/hsa_pathways
```

The build automatically runs enrichment in two phases:

- **Phase 1** (always runs, no network needed): Reaction nodes with bare accession names get labels derived from their catalysing enzymes (e.g., `R00710 → "ADH1A / ADH1B / ADH1C"`)
- **Phase 2** (runs if KEGG name TSV files are present): Compound and reaction names are replaced with canonical KEGG names (e.g., `C00031 → "D-Glucose"`, `R00710 → "Acetaldehyde:NAD+ oxidoreductase"`)

### Skipping enrichment

To build without enrichment:

```bash
metakg-build --data ./data/hsa_pathways --no-enrich
```

### Manual enrichment (optional)

If you want to enrich an existing database separately (e.g., after downloading new KEGG name files):

```bash
metakg-enrich --db .metakg/meta.sqlite --data data/
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--db PATH` | `.metakg/meta.sqlite` | Database to update |
| `--data DIR` | `data/` | Directory containing KEGG TSV files |

### Download KEGG name lists (optional)

For Phase 2 enrichment to use canonical KEGG names, download the name lists:

```bash
poetry run python scripts/download_kegg_names.py
```

This downloads two TSV files to `data/`:
- `data/kegg_compound_names.tsv` — ~19,500 compound names
- `data/kegg_reaction_names.tsv` — ~12,400 reaction names

Both phases are idempotent — safe to run multiple times.

---

## 7a. Pathway Categories

Each pathway node is automatically tagged with a **category** based on its KEGG ID range. This enables type-based queries and rendering in visualizers.

### Category mapping

| KEGG ID range | Category | Value string |
|---|---|---|
| 00xxx – 01xxx | Metabolic | `"metabolic"` |
| 02xxx | Transport | `"transport"` |
| 03xxx | Genetic information processing | `"genetic_info_processing"` |
| 04010 – 04099 | Cell signaling | `"signaling"` |
| 04100 – 04499 | Cellular processes | `"cellular_process"` |
| 04500 – 04999 | Organismal systems | `"organismal_system"` |
| 05xxx | Human diseases | `"human_disease"` |
| 07xxx | Drug development | `"drug_development"` |

### Using categories

**Python API:**

```python
from metakg import MetaKG
from metakg.primitives import PATHWAY_CATEGORY_METABOLIC

kg = MetaKG()

# All metabolic pathways
metabolic_pathways = kg.store.all_nodes(kind="pathway", category="metabolic")

# All human disease pathways
disease_pathways = kg.store.all_nodes(kind="pathway", category="human_disease")
```

**SQL:**

```sql
-- Pathway count by category
SELECT category, COUNT(*) FROM meta_nodes
WHERE kind='pathway'
GROUP BY category;

-- All signaling pathways
SELECT name FROM meta_nodes
WHERE kind='pathway' AND category='signaling'
ORDER BY name;
```

**Distribution (369 human pathways):**

```
metabolic                99
organismal_system        98
human_disease            84
cellular_process         39
genetic_info_processing  29
signaling                19
transport                 1
```

---

## 8. Seeding Kinetic Parameters

The simulation engine uses Michaelis-Menten kinetics. A curated library of literature-sourced kinetic parameters (Km, kcat, Vmax, Keq, ΔG°') is included for 26 key reactions across glycolysis, TCA cycle, pentose phosphate pathway, oxidative phosphorylation, and more.

Seed the database once after building:

```bash
metakg-simulate seed --db .metakg/meta.sqlite
```

Or with `--force` to overwrite existing values:

```bash
metakg-simulate seed --db .metakg/meta.sqlite --force
```

> **Requires:** `poetry install --extras simulate`

This writes ~34 kinetic parameter rows and ~18 regulatory interaction rows (allosteric inhibitors/activators for PFK, pyruvate kinase, hexokinase, etc.).

---

## 9. Running the MCP Server

The MCP server exposes the knowledge graph to Claude and other AI assistants via the Model Context Protocol.

```bash
metakg-mcp --db .metakg/meta.sqlite --transport stdio
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--db PATH` | `.metakg/meta.sqlite` | SQLite database path |
| `--lancedb PATH` | `.metakg/lancedb` | LanceDB vector index directory |
| `--model NAME` | `all-MiniLM-L6-v2` | Embedding model |
| `--transport` | `stdio` | `stdio` (Claude Desktop/Code) or `sse` (HTTP) |

### Connecting to Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "metakg": {
      "command": "/path/to/venv/bin/metakg-mcp",
      "args": [
        "--db", "/absolute/path/to/meta_kg/.metakg/meta.sqlite",
        "--lancedb", "/absolute/path/to/meta_kg/.metakg/lancedb"
      ]
    }
  }
}
```

Find your venv path with:

```bash
poetry env info --path
# → /Users/you/Library/Caches/pypoetry/virtualenvs/metakg-abc123-py3.12
```

The `metakg-mcp` binary is at `<venv_path>/bin/metakg-mcp`.

### Connecting to Claude Code / Kilo Code

Create `.mcp.json` in the project root:

```json
{
  "mcpServers": {
    "metakg": {
      "command": "metakg-mcp",
      "args": [
        "--db", "/absolute/path/to/meta_kg/.metakg/meta.sqlite",
        "--lancedb", "/absolute/path/to/meta_kg/.metakg/lancedb"
      ]
    }
  }
}
```

Restart Claude Code to activate. The server exposes 9 tools: `query_pathway`, `get_compound`, `get_reaction`, `find_path`, `simulate_fba`, `simulate_ode`, `simulate_whatif`, `get_kinetic_params`, `seed_kinetics`.

---

## 10. Running the Web Explorer

The Streamlit web explorer provides an interactive browser-based interface for exploring the knowledge graph.

> **Requires:** `poetry install --extras viz`

```bash
metakg-viz --db .metakg/meta.sqlite --port 8500
```

Opens automatically at `http://localhost:8500`.

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--db PATH` | `.metakg/meta.sqlite` | SQLite database path |
| `--lancedb PATH` | `.metakg/lancedb` | LanceDB vector index directory |
| `--port INT` | `8500` | Streamlit server port |
| `--no-browser` | off | Don't open browser automatically |

**Features:**
- **Graph Browser** — Visualize the full or filtered metabolic network
- **Semantic Search** — Query by description or keywords
- **Node Details** — View compound formulas, reaction stoichiometry, enzyme EC numbers, cross-references

---

## 11. Running the 3D Visualizer

The PyVista 3D viewer renders the knowledge graph as an interactive 3D scene.

> **Requires:** `poetry install --extras viz3d`

```bash
metakg-viz3d --db .metakg/meta.sqlite --layout allium
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--db PATH` | `.metakg/meta.sqlite` | SQLite database path |
| `--layout` | `allium` | Layout strategy: `allium` or `cake` |
| `--width INT` | `1400` | Window width in pixels |
| `--height INT` | `900` | Window height in pixels |
| `--export-html PATH` | — | Export to HTML file instead of opening GUI |
| `--export-png PATH` | — | Export to PNG file instead of opening GUI |

**Layout strategies:**

- **Allium** — Each pathway rendered as a "giant allium flower": reactions and compounds form a Fibonacci sphere around the pathway node, with enzyme sub-spheres orbiting each reaction. Pathways are arranged in an annular ring.
- **LayerCake** — Vertical stratification by node kind: pathways at the base, reactions in the middle, compounds and enzymes at the top.

---

## 12. Development Install

For contributing to MetaKG or running the test suite, install with the `dev` dependency group. In Poetry, dependency groups are separate from optional extras and are activated with `--with dev`.

```bash
# Core + dev tools only (no optional extras)
poetry install --with dev

# All extras + dev tools — recommended for contributors
poetry install --all-extras --with dev
```

**What the `dev` group includes:**

| Package | Purpose |
|---|---|
| `pytest >= 8.0.0` | Test runner |
| `pytest-cov >= 5.0.0` | Coverage reporting |
| `pytest-timeout >= 2.4.0` | Per-test timeout enforcement |
| `ruff >= 0.4.0` | Fast linter and formatter |
| `mypy >= 1.10.0` | Static type checker |
| `pre-commit >= 4.0.0` | Git hook manager |
| `detect-secrets >= 1.5.0` | Prevent accidental secret commits |
| `pylint >= 4.0.5` | Additional static analysis |

```bash
# Run the test suite
poetry run pytest

# Run with coverage
poetry run pytest --cov=metakg --cov-report=html

# Lint
poetry run ruff check src/

# Type check
poetry run mypy src/metakg/

# Format
poetry run ruff format src/
```

### Pre-commit hooks

```bash
poetry run pre-commit install
```

This installs hooks for `ruff`, `mypy`, and `detect-secrets` that run automatically on `git commit`.

### Project structure

```
meta_kg/
├── src/metakg/          # Main package
│   ├── cli/             # Click CLI commands
│   ├── parsers/         # KGML, SBML, BioPAX, CSV parsers
│   ├── primitives.py    # MetaNode, MetaEdge data types
│   ├── store.py         # SQLite persistence (MetaStore)
│   ├── index.py         # LanceDB vector indexing (MetaIndex)
│   ├── embed.py         # Sentence-transformer embeddings
│   ├── graph.py         # File discovery and parser dispatch
│   ├── orchestrator.py  # High-level MetaKG API
│   ├── simulate.py      # FBA + ODE simulation engine
│   ├── mcp_tools.py     # MCP tool registrations
│   ├── app.py           # Streamlit web explorer
│   ├── viz3d.py         # PyVista 3D viewer
│   └── layout3d.py      # 3D layout algorithms
├── tests/               # pytest test suite
├── data/                # Sample pathway data + KEGG name TSVs
├── scripts/             # Utility scripts
└── docs/                # Documentation
```

---

## 13. Environment Variables

All CLI defaults can be overridden with environment variables:

| Variable | Default | Description |
|---|---|---|
| `METAKG_DB` | `.metakg/meta.sqlite` | SQLite database path |
| `METAKG_LANCEDB` | `.metakg/lancedb` | LanceDB vector index directory |
| `METAKG_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model name |

Example for a Docker deployment:

```bash
export METAKG_DB="/data/meta.sqlite"
export METAKG_LANCEDB="/data/lancedb"
metakg-mcp --transport sse
```

---

## 14. Upgrading

```bash
# Pull latest code
git pull

# Update dependencies (regenerates poetry.lock)
poetry update

# Rebuild the knowledge graph after significant updates
metakg-build --data ./data/hsa_pathways
```

If the database schema has changed (check `CHANGELOG.md`), always use `metakg-build`
(which wipes by default) rather than `metakg-update` to avoid merging into an old schema.

---

## 15. Troubleshooting

### `python3.12` not found

```bash
# Check available Python versions
python3 --version
which python3.12

# Install via pyenv
pyenv install 3.12.8
pyenv local 3.12.8
```

### `poetry: command not found`

```bash
# Add Poetry to PATH (add to ~/.zshrc or ~/.bashrc)
export PATH="$HOME/.local/bin:$PATH"
source ~/.zshrc
```

### `code-kg` dependency fails to install

The `code-kg` package is installed directly from GitHub. Ensure you have Git and network access:

```bash
git ls-remote https://github.com/Flux-Frontiers/code_kg.git HEAD
```

If behind a corporate proxy, configure Git:

```bash
git config --global http.proxy http://proxy.example.com:8080
```

### `sentence-transformers` model download fails

The model is downloaded from Hugging Face on first use. If you're offline or behind a firewall, pre-download it:

```bash
poetry run python -c "
from sentence_transformers import SentenceTransformer
SentenceTransformer('all-MiniLM-L6-v2')
print('Model cached.')
"
```

### `metakg-simulate` not found

The `simulate` extra is required:

```bash
poetry install --extras simulate
```

### `metakg-viz` not found or `ModuleNotFoundError: streamlit`

The `viz` extra is required:

```bash
poetry install --extras viz
```

### `metakg-viz3d` not found or `ModuleNotFoundError: pyvista`

The `viz3d` extra is required:

```bash
poetry install --extras viz3d
```

On macOS, if PyQt5 fails to build:

```bash
xcode-select --install
poetry install --extras viz3d
```

### Build produces 0 nodes

Check that the `--data` directory contains `.kgml`, `.xml`, `.sbml`, `.owl`, `.rdf`, `.csv`, or `.tsv` files:

```bash
ls data/hsa_pathways/*.kgml | wc -l
# Should be > 0
```

### LanceDB index missing — semantic search returns no results

The vector index must be built during `metakg-build`. If you used `--no-index`, rebuild:

```bash
metakg-build --data ./data/hsa_pathways
```

### ODE simulation hangs or fails with "repeated convergence failures"

You are likely using `RK45` (explicit, non-stiff solver) on a stiff metabolic system. Always use the default `BDF` solver:

```python
# Wrong — will hang on metabolic pathways
kg.simulate_ode(pathway_id="...", ode_method="RK45")

# Correct — BDF is the default
kg.simulate_ode(pathway_id="...")
# or explicitly:
kg.simulate_ode(pathway_id="...", ode_method="BDF")
```

### MCP server not appearing in Claude Desktop

1. Verify the binary path is absolute (not relative):
   ```bash
   poetry env info --path
   # Use: <venv_path>/bin/metakg-mcp
   ```
2. Verify the database exists:
   ```bash
   ls -la .metakg/meta.sqlite
   ```
3. Restart Claude Desktop after editing `claude_desktop_config.json`.

### `WARNING: SQLite database not found`

Run `metakg-build` first:

```bash
metakg-build --data ./data/hsa_pathways
```

---

## Complete Quickstart (copy-paste)

```bash
# 1. Clone and enter the repo
git clone https://github.com/Flux-Frontiers/meta_kg.git
cd meta_kg

# 2. Install with simulation + web visualization
poetry install --extras "simulate viz"

# 3. Download the full human KEGG metabolome
poetry run python scripts/download_human_kegg.py --output data/hsa_pathways

# 4. Download KEGG name lists for enrichment
poetry run python scripts/download_kegg_names.py

# 5. Build the knowledge graph with enrichment in one step
metakg-build --data ./data/hsa_pathways --enrich

# 6. Seed kinetic parameters from curated literature
metakg-simulate seed

# 7. Run a quick analysis
metakg-analyze --output analysis.md

# 8. Launch the web explorer
metakg-viz

# 9. (Optional) Start the MCP server for Claude
metakg-mcp --transport stdio
```

---

## Install Summary

| Goal | Command |
|---|---|
| Core only (graph + search + MCP) | `poetry install` |
| + Simulation (FBA / ODE) | `poetry install --extras simulate` |
| + Web UI | `poetry install --extras viz` |
| + 3D viewer | `poetry install --extras viz3d` |
| + BioPAX parsing | `poetry install --extras biopax` |
| Everything (no dev tools) | `poetry install --all-extras` |
| Dev tools only (pytest, ruff, mypy…) | `poetry install --with dev` |
| Everything + dev tools | `poetry install --all-extras --with dev` |
