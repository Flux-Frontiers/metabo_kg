# MetaboKG: Metabolic Pathway Knowledge Graph

> **Generated:** 2026-09-06T15:53:29.082883+00:00 | **Version:** 0.23.1 | **Commit:** ddb98ea43b

This codebase is organized into 2 architectural layers: Scripts Layer, Src Layer. The architecture supports semantic code search via knowledge graph indexing and querying.

## Architectural Layers

### Scripts Layer
Handles scripts concerns.

**Responsibilities:**
- Component responsibility

**Modules:**
- `scripts/collect_pathway_data.py`
- `scripts/download_cho_kegg.py`
- `scripts/download_human_kegg.py`
- `scripts/download_icho_model.py`
- `scripts/examples.py`
- `scripts/fetch_sabio_cho_kinetics.py`
- `scripts/generate_wiki.py`
- `scripts/simulation_demo.py`
- `scripts/wire_kegg_enzymes.py`

### Src Layer
Handles src concerns.

**Responsibilities:**
- Component responsibility

**Modules:**
- `src/metabokg/__init__.py`
- `src/metabokg/analyze.py`
- `src/metabokg/app.py`
- `src/metabokg/cho_kinetics.py`
- `src/metabokg/cli/__init__.py`
- `src/metabokg/cli/_utils.py`
- `src/metabokg/cli/cmd_analyze.py`
- `src/metabokg/cli/cmd_build.py`
- `src/metabokg/cli/cmd_hooks.py`
- `src/metabokg/cli/cmd_info.py`
- `src/metabokg/cli/cmd_init.py`
- `src/metabokg/cli/cmd_mcp.py`
- `src/metabokg/cli/cmd_pack.py`
- `src/metabokg/cli/cmd_query.py`
- `src/metabokg/cli/cmd_simulate.py`
- `src/metabokg/cli/cmd_snapshot.py`
- `src/metabokg/cli/cmd_viz.py`
- `src/metabokg/cli/cmd_viz3d.py`
- `src/metabokg/cli/main.py`
- `src/metabokg/cli/options.py`
- `src/metabokg/downloader.py`
- `src/metabokg/embed.py`
- `src/metabokg/enrich.py`
- `src/metabokg/graph.py`
- `src/metabokg/index.py`
- `src/metabokg/kinetics_fetch.py`
- `src/metabokg/layout3d.py`
- `src/metabokg/mcp_tools.py`
- `src/metabokg/metabokg_viz.py`
- `src/metabokg/metabokg_viz3d.py`
- `src/metabokg/orchestrator.py`
- `src/metabokg/parsers/__init__.py`
- `src/metabokg/parsers/base.py`
- `src/metabokg/parsers/biopax.py`
- `src/metabokg/parsers/csv_tsv.py`
- `src/metabokg/parsers/kgml.py`
- `src/metabokg/parsers/sbml.py`
- `src/metabokg/primitives.py`
- `src/metabokg/simulate.py`
- `src/metabokg/snapshots.py`
- `src/metabokg/store.py`
- `src/metabokg/thorough_analysis.py`
- `src/metabokg/viz3d.py`

## Key Components

### HubMetabolite
**Type:** `class` | **File:** `src/metabokg/analyze.py:61`

A compound that participates in many reactions (high connectivity).

### ComplexReaction
**Type:** `class` | **File:** `src/metabokg/analyze.py:75`

A reaction with many substrates, products, and/or enzyme regulators.

### CrossPathwayHub
**Type:** `class` | **File:** `src/metabokg/analyze.py:88`

A compound that appears in two or more distinct pathways.

### PathwayCoupling
**Type:** `class` | **File:** `src/metabokg/analyze.py:100`

Two pathways that share a significant number of compounds.

### DeadEndMetabolite
**Type:** `class` | **File:** `src/metabokg/analyze.py:112`

A compound with only one reaction connection (potential sink or source).

## Critical Paths

### Path 1: Graph Query Pipeline
Semantic search → graph expansion → snippet packing

- Semantic search finds seed nodes via sqlite-vec
- Graph expansion traverses CALLS, CONTAINS, IMPORTS edges
- Snippet pack materializes source code with context

### Path 2: AST Extraction & Graph Building
Repository scanning → code analysis → graph storage

- CodeGraph walks repo and extracts Python files
- PyCodeKGVisitor traverses AST, collects nodes and edges
- GraphStore persists in SQLite with symbol resolution

## Dependency & Coupling Analysis

### Module Dependencies
**src/metabokg/store.py**
- imports: __future__.annotations
- imports: json
- imports: sqlite3
- imports: collections.deque
- imports: collections.abc.Iterable
- imports: pathlib.Path
- imports: typing.cast
- imports: metabokg.primitives.DEFAULT_RELS
- imports: metabokg.primitives.REL_PRODUCT_OF
- imports: metabokg.primitives.REL_SUBSTRATE_OF
- imports: metabokg.primitives.KineticParam
- imports: metabokg.primitives.MetaEdge
- imports: metabokg.primitives.MetaNode
- imports: metabokg.primitives.RegulatoryInteraction

**src/metabokg/snapshots.py**
- imports: __future__.annotations
- imports: importlib.metadata
- imports: json
- imports: sqlite3
- imports: dataclasses.asdict
- imports: dataclasses.dataclass
- imports: dataclasses.field
- imports: datetime.UTC
- imports: datetime.datetime
- imports: pathlib.Path
- imports: typing.Any
- imports: kg_utils.snapshots.PruneResult
- imports: kg_utils.snapshots.SnapshotManager

**src/metabokg/embed.py**
- imports: __future__.annotations
- imports: dataclasses.dataclass
- imports: kg_utils.embed.DEFAULT_MODEL
- imports: kg_utils.embedder.Embedder
- imports: kg_utils.embedder.SentenceTransformerEmbedder

**src/metabokg/downloader.py**
- imports: __future__.annotations
- imports: csv
- imports: re
- imports: sys
- imports: time
- imports: urllib.error
- imports: urllib.request
- imports: dataclasses.dataclass
- imports: pathlib.Path
- imports: xml.etree.ElementTree

**src/metabokg/index.py**
- imports: __future__.annotations
- imports: json
- imports: pathlib.Path
- imports: kg_utils.vector_backend.SqliteVecBackend
- imports: metabokg.embed.DEFAULT_MODEL
- imports: metabokg.embed.Embedder
- imports: metabokg.embed.SeedHit
- imports: metabokg.embed.SentenceTransformerEmbedder
- imports: metabokg.embed.extract_distance
- imports: metabokg.primitives.KIND_COMPOUND
- imports: metabokg.primitives.KIND_PATHWAY
- imports: metabokg.primitives.KIND_REACTION
- imports: metabokg.store.MetaStore

**src/metabokg/enrich.py**
- imports: __future__.annotations
- imports: csv
- imports: json
- imports: re
- imports: dataclasses.dataclass
- imports: pathlib.Path

**src/metabokg/primitives.py**
- imports: __future__.annotations
- imports: hashlib
- imports: json
- imports: re
- imports: dataclasses.dataclass

**src/metabokg/metabokg_viz3d.py**
- imports: __future__.annotations
- imports: pathlib.Path

**src/metabokg/graph.py**
- imports: __future__.annotations
- imports: logging
- imports: pathlib.Path
- imports: metabokg.parsers.base.PathwayParser
- imports: metabokg.parsers.biopax.BioPAXParser
- imports: metabokg.parsers.csv_tsv.CSVParser
- imports: metabokg.parsers.kgml.KGMLParser
- imports: metabokg.parsers.sbml.SBMLParser
- imports: metabokg.primitives.MetaEdge
- imports: metabokg.primitives.MetaNode

**src/metabokg/simulate.py**
- imports: __future__.annotations
- imports: copy
- imports: json
- imports: dataclasses.dataclass
- imports: dataclasses.field
- imports: typing.TYPE_CHECKING
- imports: numpy
- imports: scipy.integrate.solve_ivp
- imports: scipy.optimize.linprog

**src/metabokg/__init__.py**
- imports: importlib.metadata.PackageNotFoundError
- imports: importlib.metadata.version
- imports: metabokg.orchestrator.MetabolicBuildStats
- imports: metabokg.orchestrator.MetabolicPack
- imports: metabokg.orchestrator.MetabolicQueryResult
- imports: metabokg.orchestrator.MetabolicRuntimeStats
- imports: metabokg.orchestrator.MetaKG

**src/metabokg/thorough_analysis.py**
- imports: __future__.annotations
- imports: metabokg.__version__
- imports: metabokg.analyze.PathwayAnalysisReport

**src/metabokg/cho_kinetics.py**
- imports: __future__.annotations
- imports: json
- imports: pathlib.Path

## Health & Quality Signals

- **Circular Dependencies:** 0
- **Coupling Health:** Acyclic
- **Orphaned Functions:** 0
- **Dead Code Status:** Clean
