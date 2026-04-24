> **Analysis Report Metadata**
> - **Generated:** 2026-04-24T14:37:36Z
> - **Version:** 0.7.0
> - **PyCodeKG Version:** pycode-kg 0.14.0
> - **Commit:** 0e99fbf (main)
> - **Platform:** macOS 26.4.1 | arm64 (arm) | Turing | Python 3.12.13
> - **Graph:** 5936 nodes · 5534 edges (401 meaningful)
> - **Included directories:** src
> - **Excluded directories:** none
> - **Elapsed time:** 3s

# Metabo_kg Analysis

**Generated:** 2026-04-24 14:37:36 UTC

---

## Executive Summary

This report provides a comprehensive architectural analysis of the **Metabo_kg** repository using PyCodeKG's knowledge graph. The analysis covers complexity hotspots, module coupling, key call chains, and code quality signals to guide refactoring and architecture decisions.

| Overall Quality | Grade | Score |
|----------------|-------|-------|
| [A] **Excellent** | **A** | 90 / 100 |

---

## Baseline Metrics

| Metric | Value |
|--------|-------|
| **Total Nodes** | 5936 |
| **Total Edges** | 5534 |
| **Modules** | 41 (of 41 total) |
| **Functions** | 158 |
| **Classes** | 48 |
| **Methods** | 154 |

### Edge Distribution

| Relationship Type | Count |
|-------------------|-------|
| CALLS | 1902 |
| CONTAINS | 360 |
| IMPORTS | 357 |
| ATTR_ACCESS | 1843 |
| INHERITS | 11 |

---

## Fan-In Ranking

Most-called functions are potential bottlenecks or core functionality. These functions are heavily depended upon across the codebase.

| # | Function | Module | Callers |
|---|----------|--------|---------|
| 1 | `node()` | src/metabokg/store.py | **21** |
| 2 | `close()` | src/metabokg/analyze.py | **13** |
| 3 | `close()` | src/metabokg/orchestrator.py | **13** |
| 4 | `close()` | src/metabokg/store.py | **13** |
| 5 | `store()` | src/metabokg/orchestrator.py | **12** |
| 6 | `conn()` | src/metabokg/analyze.py | **9** |
| 7 | `edges_of()` | src/metabokg/store.py | **7** |
| 8 | `index()` | src/metabokg/orchestrator.py | **6** |
| 9 | `load_manifest()` | src/metabokg/snapshots.py | **5** |
| 10 | `load_snapshot()` | src/metabokg/snapshots.py | **5** |
| 11 | `all_nodes()` | src/metabokg/store.py | **4** |
| 12 | `_get_store()` | src/metabokg/app.py | **4** |
| 13 | `SnapshotDelta()` | src/metabokg/snapshots.py | **3** |
| 14 | `simulator()` | src/metabokg/orchestrator.py | **3** |
| 15 | `_resolve_db_path()` | src/metabokg/app.py | **3** |


**Insight:** Functions with high fan-in are either core APIs or bottlenecks. Review these for:
- Thread safety and performance
- Clear documentation and contracts
- Potential for breaking changes

---

## High Fan-Out Functions (Orchestrators)

Functions that call many others may indicate complex orchestration logic or poor separation of concerns.

No extreme high fan-out functions detected. Well-balanced architecture.

---

## Module Architecture

Top modules by dependency coupling and cohesion (showing up to 10 with activity).
Cohesion = incoming / (incoming + outgoing + 1); higher = more internally focused.

| Module | Functions | Classes | Incoming | Outgoing | Cohesion |
|--------|-----------|---------|----------|----------|----------|
| `src/metabokg/store.py` | 3 | 2 | 4 | 1 | 0.17 |
| `src/metabokg/orchestrator.py` | 0 | 5 | 1 | 6 | 0.75 |
| `src/metabokg/analyze.py` | 5 | 8 | 1 | 0 | 0.00 |
| `src/metabokg/mcp_tools.py` | 28 | 0 | 0 | 0 | 0.00 |
| `src/metabokg/snapshots.py` | 1 | 5 | 1 | 0 | 0.00 |
| `src/metabokg/app.py` | 21 | 0 | 0 | 2 | 0.67 |
| `src/metabokg/simulate.py` | 5 | 6 | 2 | 0 | 0.00 |
| `src/metabokg/viz3d.py` | 15 | 1 | 0 | 0 | 0.00 |
| `src/metabokg/layout3d.py` | 3 | 5 | 0 | 0 | 0.00 |
| `src/metabokg/primitives.py` | 5 | 4 | 9 | 0 | 0.00 |

---

## Key Call Chains

Deepest call chains in the codebase.

**Chain 1** (depth: 3)

```
__exit__ → close → close
```

**Chain 2** (depth: 3)

```
__exit__ → close → close
```

**Chain 3** (depth: 3)

```
simulator → store → MetaStore
```

---

## Public API Surface

Identified public APIs (module-level functions with high usage).

| Function | Module | Fan-In | Type |
|----------|--------|--------|------|
| `MetaKG()` | src/metabokg/orchestrator.py | 11 | class |
| `SnapshotManager()` | src/metabokg/snapshots.py | 8 | class |
| `GraphStore()` | src/metabokg/store.py | 5 | class |
| `build()` | src/metabokg/cli/cmd_build.py | 3 | function |
| `info()` | src/metabokg/cli/cmd_info.py | 3 | function |
| `SnapshotDelta()` | src/metabokg/snapshots.py | 3 | class |
| `query()` | src/metabokg/cli/cmd_query.py | 2 | function |
| `pack()` | src/metabokg/mcp_tools.py | 2 | function |
| `pack()` | src/metabokg/cli/cmd_pack.py | 2 | function |
| `SnapshotManifest()` | src/metabokg/snapshots.py | 2 | class |
---

## Docstring Coverage

Docstring coverage directly determines semantic retrieval quality. Nodes without
docstrings embed only structured identifiers (`KIND/NAME/QUALNAME/MODULE`), where
keyword search is as effective as vector embeddings. The semantic model earns its
value only when a docstring is present.

| Kind | Documented | Total | Coverage |
|------|-----------|-------|----------|
| `function` | 118 | 158 | [WARN] 74.7% |
| `method` | 131 | 154 | [OK] 85.1% |
| `class` | 48 | 48 | [OK] 100.0% |
| `module` | 41 | 41 | [OK] 100.0% |
| **total** | **338** | **401** | **[OK] 84.3%** |

---

## Structural Importance Ranking (SIR)

Weighted PageRank aggregated by module — reveals architectural spine. Cross-module edges boosted 1.5×; private symbols penalized 0.85×. Node-level detail: `pycodekg centrality --top 25`

| Rank | Score | Members | Module |
|------|-------|---------|--------|
| 1 | 0.161965 | 39 | `src/metabokg/store.py` |
| 2 | 0.112416 | 36 | `src/metabokg/orchestrator.py` |
| 3 | 0.102283 | 27 | `src/metabokg/snapshots.py` |
| 4 | 0.093696 | 29 | `src/metabokg/analyze.py` |
| 5 | 0.050093 | 15 | `src/metabokg/primitives.py` |
| 6 | 0.049542 | 21 | `src/metabokg/simulate.py` |
| 7 | 0.043345 | 29 | `src/metabokg/mcp_tools.py` |
| 8 | 0.037474 | 12 | `src/metabokg/embed.py` |
| 9 | 0.036077 | 16 | `src/metabokg/layout3d.py` |
| 10 | 0.033835 | 22 | `src/metabokg/app.py` |
| 11 | 0.029502 | 14 | `src/metabokg/enrich.py` |
| 12 | 0.026462 | 17 | `src/metabokg/viz3d.py` |
| 13 | 0.025179 | 10 | `src/metabokg/index.py` |
| 14 | 0.023605 | 5 | `src/metabokg/parsers/base.py` |
| 15 | 0.020476 | 11 | `src/metabokg/parsers/sbml.py` |



---

## Code Quality Issues

- [WARN] 1 orphaned functions found (`snapshot_diff`) -- consider archiving or documenting

---

## Architectural Strengths

- Well-structured with 15 core functions identified
- No god objects or god functions detected
- Good docstring coverage: 84.3% of functions/methods/classes/modules documented

---

## Recommendations

### Immediate Actions
1. **Remove or archive orphaned functions** — `snapshot_diff` have zero callers and add maintenance burden

### Medium-term Refactoring
1. **Harden high fan-in functions** — `node`, `close`, `close` are widely depended upon; review for thread safety, clear contracts, and stable interfaces
2. **Reduce module coupling** — consider splitting tightly coupled modules or introducing interface boundaries
3. **Add tests for key call chains** — the identified call chains represent well-traveled execution paths that benefit most from regression coverage

### Long-term Architecture
1. **Version and stabilize the public API** — document breaking-change policies for `MetaKG`, `SnapshotManager`, `GraphStore`
2. **Enforce layer boundaries** — add linting or CI checks to prevent unexpected cross-module dependencies as the codebase grows
3. **Monitor hot paths** — instrument the high fan-in functions identified here to catch performance regressions early

---

## Inheritance Hierarchy

**11** INHERITS edges across **13** classes. Max depth: **1**.

| Class | Module | Depth | Parents | Children |
|-------|--------|-------|---------|----------|
| `SentenceTransformerEmbedder` | src/metabokg/embed.py | 1 | 1 | 0 |
| `AlliumLayout` | src/metabokg/layout3d.py | 1 | 1 | 0 |
| `LayerCakeLayout` | src/metabokg/layout3d.py | 1 | 1 | 0 |
| `BioPAXParser` | src/metabokg/parsers/biopax.py | 1 | 1 | 0 |
| `CSVParser` | src/metabokg/parsers/csv_tsv.py | 1 | 1 | 0 |
| `KGMLParser` | src/metabokg/parsers/kgml.py | 1 | 1 | 0 |
| `SBMLParser` | src/metabokg/parsers/sbml.py | 1 | 1 | 0 |
| `GraphStore` | src/metabokg/store.py | 1 | 1 | 0 |
| `Embedder` | src/metabokg/embed.py | 0 | 0 | 1 |
| `Layout3D` | src/metabokg/layout3d.py | 0 | 1 | 2 |
| `PathwayParser` | src/metabokg/parsers/base.py | 0 | 1 | 4 |
| `SnapshotManager` | src/metabokg/snapshots.py | 0 | 1 | 0 |
| `MetaStore` | src/metabokg/store.py | 0 | 0 | 1 |


---

## Snapshot History

Recent snapshots in reverse chronological order. Δ columns show change vs. the immediately preceding snapshot.

| # | Timestamp | Branch | Version | Nodes | Edges | Coverage | Δ Nodes | Δ Edges | Δ Coverage |
|---|-----------|--------|---------|-------|-------|----------|---------|---------|------------|
| 1 | 2026-04-24 14:32:44 | main | 0.14.0 | 5936 | 5534 | 84.3% | +7 | +19 | +0.1% |
| 2 | 2026-04-21 22:53:35 | main | 0.14.0 | 5929 | 5515 | 84.2% | +84 | +75 | -0.1% |
| 3 | 2026-04-20 15:17:31 | claude/analyze-streamlit-state-performance-7APrU | 0.14.0 | 5845 | 5440 | 84.3% | +166 | +197 | +0.1% |
| 4 | 2026-04-20 14:55:50 | main | 0.14.0 | 5679 | 5243 | 84.2% | +154 | +151 | +0.3% |
| 5 | 2026-04-19 19:35:36 | main | 0.14.0 | 5525 | 5092 | 83.9% | +1 | +0 | +0.0% |
| 6 | 2026-04-19 18:21:14 | main | 0.14.0 | 5524 | 5092 | 83.9% | +184 | +229 | -0.4% |
| 7 | 2026-04-19 16:29:09 | main | 0.14.0 | 5340 | 4863 | 84.3% | +34 | +20 | +0.1% |
| 8 | 2026-04-19 14:38:50 | main | 0.14.0 | 5306 | 4843 | 84.2% | +39 | +44 | +0.1% |
| 9 | 2026-04-19 02:50:33 | claude/contact-jhmi-betenbaugh-PKjNo | 0.14.0 | 5267 | 4799 | 84.1% | +123 | +124 | +0.2% |
| 10 | 2026-04-17 17:35:13 | main | 0.14.0 | 5144 | 4675 | 83.9% | — | — | — |


---

## Appendix: Orphaned Code

Functions with zero callers (potential dead code):

| Function | Module | Lines |
|----------|--------|-------|
| `snapshot_diff()` | src/metabokg/mcp_tools.py | 1 |
---

## CodeRank -- Global Structural Importance

Weighted PageRank over CALLS + IMPORTS + INHERITS edges (test paths excluded). Scores are normalized to sum to 1.0. This ranking seeds Phase 2 fan-in discovery and Phase 15 concern queries.

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.000898 | method | `MetaKG.store` | src/metabokg/orchestrator.py |
| 2 | 0.000476 | method | `MetaStore.node` | src/metabokg/store.py |
| 3 | 0.000452 | method | `PathwayAnalyzer.conn` | src/metabokg/analyze.py |
| 4 | 0.000384 | class | `SnapshotDelta` | src/metabokg/snapshots.py |
| 5 | 0.000371 | class | `SnapshotManifest` | src/metabokg/snapshots.py |
| 6 | 0.000337 | method | `MetaStore.all_nodes` | src/metabokg/store.py |
| 7 | 0.000333 | method | `SnapshotManager.load_manifest` | src/metabokg/snapshots.py |
| 8 | 0.000314 | method | `MetaKG.simulator` | src/metabokg/orchestrator.py |
| 9 | 0.000310 | function | `_resolve_db_path` | src/metabokg/app.py |
| 10 | 0.000298 | method | `MetaStore.close` | src/metabokg/store.py |
| 11 | 0.000298 | method | `SentenceTransformerEmbedder.embed_texts` | src/metabokg/embed.py |
| 12 | 0.000298 | method | `MetaKG.close` | src/metabokg/orchestrator.py |
| 13 | 0.000298 | method | `PathwayAnalyzer.close` | src/metabokg/analyze.py |
| 14 | 0.000298 | class | `CSVParserConfig` | src/metabokg/parsers/csv_tsv.py |
| 15 | 0.000298 | function | `_parse_conc_args` | src/metabokg/cli/_utils.py |
| 16 | 0.000284 | method | `SnapshotManager.load_snapshot` | src/metabokg/snapshots.py |
| 17 | 0.000277 | method | `MetaIndex._get_table` | src/metabokg/index.py |
| 18 | 0.000270 | function | `_fbc` | src/metabokg/parsers/sbml.py |
| 19 | 0.000258 | method | `MetaKG.index` | src/metabokg/orchestrator.py |
| 20 | 0.000258 | function | `_strip_ns` | src/metabokg/parsers/sbml.py |

---

## Concern-Based Hybrid Ranking

Top structurally-dominant nodes per architectural concern (0.60 × semantic + 0.25 × CodeRank + 0.15 × graph proximity).

### Configuration Loading Initialization Setup

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7532 | function | `_init_state` | src/metabokg/app.py |
| 2 | 0.7308 | method | `CSVParser.__init__` | src/metabokg/parsers/csv_tsv.py |
| 3 | 0.7266 | method | `MetaKG.__init__` | src/metabokg/orchestrator.py |
| 4 | 0.7215 | function | `_load_kg` | src/metabokg/app.py |
| 5 | 0.7152 | function | `_load_full_graph` | src/metabokg/app.py |

### Data Persistence Storage Database

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.8921 | method | `MetaKG.store` | src/metabokg/orchestrator.py |
| 2 | 0.7496 | function | `_load_store` | src/metabokg/app.py |
| 3 | 0.7341 | method | `MetaStore._migrate` | src/metabokg/store.py |
| 4 | 0.714 | method | `MetaStore.node_by_xref` | src/metabokg/store.py |
| 5 | 0.7127 | function | `_get_store` | src/metabokg/app.py |

### Query Search Retrieval Semantic

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.75 | method | `GraphStore.query_text` | src/metabokg/store.py |
| 2 | 0.7337 | function | `query` | src/metabokg/cli/cmd_query.py |
| 3 | 0.731 | function | `_tab_search` | src/metabokg/app.py |
| 4 | 0.7262 | method | `MetaKG.query` | src/metabokg/orchestrator.py |
| 5 | 0.7133 | method | `MetaIndex.search` | src/metabokg/index.py |

### Graph Traversal Node Edge

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.75 | method | `LayerCakeLayout.compute` | src/metabokg/layout3d.py |
| 2 | 0.7474 | method | `AlliumLayout.compute` | src/metabokg/layout3d.py |
| 3 | 0.7381 | method | `Layout3D.compute` | src/metabokg/layout3d.py |
| 4 | 0.7085 | method | `MetaStore.edges_within` | src/metabokg/store.py |
| 5 | 0.7034 | method | `MetaStore.edges_of` | src/metabokg/store.py |



---

*Report generated by PyCodeKG Thorough Analysis Tool — analysis completed in 3.6s*
