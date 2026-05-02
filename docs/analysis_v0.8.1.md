> **Analysis Report Metadata**
> - **Generated:** 2026-05-02T23:44:51Z
> - **Version:** pycode-kg 0.18.1
> - **Commit:** 15fd336 (main)
> - **Platform:** macOS 26.4.1 | arm64 (arm) | turing | Python 3.12.13
> - **Graph:** 7207 nodes · 6661 edges (479 meaningful)
> - **Included directories:** scripts, src
> - **Excluded directories:** none
> - **Elapsed time:** 3s

# Metabo_kg Analysis

**Generated:** 2026-05-02 23:44:51 UTC

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
| **Total Nodes** | 7207 |
| **Total Edges** | 6661 |
| **Modules** | 52 (of 52 total) |
| **Functions** | 220 |
| **Classes** | 51 |
| **Methods** | 156 |

### Edge Distribution

| Relationship Type | Count |
|-------------------|-------|
| CALLS | 2366 |
| CONTAINS | 427 |
| IMPORTS | 436 |
| ATTR_ACCESS | 2194 |
| INHERITS | 11 |

---

## Fan-In Ranking

Most-called functions are potential bottlenecks or core functionality. These functions are heavily depended upon across the codebase.

| # | Function | Module | Callers |
|---|----------|--------|---------|
| 1 | `node()` | src/metabokg/store.py | **21** |
| 2 | `close()` | src/metabokg/analyze.py | **20** |
| 3 | `close()` | src/metabokg/orchestrator.py | **20** |
| 4 | `close()` | src/metabokg/store.py | **20** |
| 5 | `store()` | src/metabokg/orchestrator.py | **12** |
| 6 | `conn()` | src/metabokg/analyze.py | **9** |
| 7 | `edges_of()` | src/metabokg/store.py | **7** |
| 8 | `index()` | src/metabokg/orchestrator.py | **6** |
| 9 | `all_nodes()` | src/metabokg/store.py | **5** |
| 10 | `load_manifest()` | src/metabokg/snapshots.py | **5** |
| 11 | `load_snapshot()` | src/metabokg/snapshots.py | **5** |
| 12 | `_count_lines()` | src/metabokg/downloader.py | **4** |
| 13 | `_get_store()` | src/metabokg/app.py | **4** |
| 14 | `seed_kinetics()` | src/metabokg/orchestrator.py | **4** |
| 15 | `SnapshotDelta()` | src/metabokg/snapshots.py | **3** |


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
| `src/metabokg/orchestrator.py` | 0 | 5 | 3 | 6 | 0.60 |
| `src/metabokg/analyze.py` | 5 | 8 | 1 | 0 | 0.00 |
| `src/metabokg/mcp_tools.py` | 28 | 0 | 0 | 0 | 0.00 |
| `src/metabokg/snapshots.py` | 1 | 5 | 1 | 0 | 0.00 |
| `src/metabokg/app.py` | 21 | 0 | 0 | 2 | 0.67 |
| `src/metabokg/simulate.py` | 5 | 6 | 2 | 0 | 0.00 |
| `src/metabokg/viz3d.py` | 15 | 1 | 0 | 0 | 0.00 |
| `src/metabokg/layout3d.py` | 3 | 5 | 0 | 0 | 0.00 |
| `scripts/generate_wiki.py` | 14 | 0 | 0 | 0 | 0.00 |

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
| `MetaKG()` | src/metabokg/orchestrator.py | 17 | class |
| `SnapshotManager()` | src/metabokg/snapshots.py | 8 | class |
| `GraphStore()` | src/metabokg/store.py | 5 | class |
| `build()` | src/metabokg/cli/cmd_build.py | 4 | function |
| `info()` | src/metabokg/cli/cmd_info.py | 3 | function |
| `SnapshotDelta()` | src/metabokg/snapshots.py | 3 | class |
| `pack()` | src/metabokg/mcp_tools.py | 2 | function |
| `pack()` | src/metabokg/cli/cmd_pack.py | 2 | function |
| `SnapshotManifest()` | src/metabokg/snapshots.py | 2 | class |
| `Snapshot()` | src/metabokg/snapshots.py | 2 | class |
---

## Docstring Coverage

Docstring coverage directly determines semantic retrieval quality. Nodes without
docstrings embed only structured identifiers (`KIND/NAME/QUALNAME/MODULE`), where
keyword search is as effective as vector embeddings. The semantic model earns its
value only when a docstring is present.

| Kind | Documented | Total | Coverage |
|------|-----------|-------|----------|
| `function` | 173 | 220 | [WARN] 78.6% |
| `method` | 132 | 156 | [OK] 84.6% |
| `class` | 51 | 51 | [OK] 100.0% |
| `module` | 52 | 52 | [OK] 100.0% |
| **total** | **408** | **479** | **[OK] 85.2%** |

---

## Structural Importance Ranking (SIR)

Weighted PageRank aggregated by module — reveals architectural spine. Cross-module edges boosted 1.5×; private symbols penalized 0.85×. Node-level detail: `pycodekg centrality --top 25`

| Rank | Score | Members | Module |
|------|-------|---------|--------|
| 1 | 0.146363 | 39 | `src/metabokg/store.py` |
| 2 | 0.107996 | 36 | `src/metabokg/orchestrator.py` |
| 3 | 0.091350 | 29 | `src/metabokg/analyze.py` |
| 4 | 0.084094 | 27 | `src/metabokg/snapshots.py` |
| 5 | 0.043474 | 15 | `src/metabokg/primitives.py` |
| 6 | 0.041260 | 21 | `src/metabokg/simulate.py` |
| 7 | 0.036770 | 29 | `src/metabokg/mcp_tools.py` |
| 8 | 0.034676 | 12 | `src/metabokg/embed.py` |
| 9 | 0.029663 | 16 | `src/metabokg/layout3d.py` |
| 10 | 0.027820 | 22 | `src/metabokg/app.py` |
| 11 | 0.025954 | 10 | `src/metabokg/index.py` |
| 12 | 0.025595 | 15 | `src/metabokg/downloader.py` |
| 13 | 0.024370 | 14 | `src/metabokg/enrich.py` |
| 14 | 0.022609 | 15 | `scripts/generate_wiki.py` |
| 15 | 0.021757 | 17 | `src/metabokg/viz3d.py` |



---

## Code Quality Issues

- [WARN] 2 orphaned functions found (`snapshot_diff`, `main`) -- consider archiving or documenting
- [WARN] `store.py` has 38 functions/methods/classes -- consider splitting into focused submodules
- [WARN] `orchestrator.py` has 35 functions/methods/classes -- consider splitting into focused submodules

---

## Architectural Strengths

- Well-structured with 15 core functions identified
- No god objects or god functions detected
- Good docstring coverage: 85.2% of functions/methods/classes/modules documented

---

## Recommendations

### Immediate Actions
1. **Remove or archive orphaned functions** — `snapshot_diff`, `main` have zero callers and add maintenance burden

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
| 1 | 2026-05-02 23:43:52 | main | 0.18.1 | 7207 | 6661 | 85.2% | +0 | +0 | +0.0% |
| 2 | 2026-05-02 22:47:35 | main | 0.18.1 | 7207 | 6661 | 85.2% | +0 | +0 | +0.0% |
| 3 | 2026-05-02 22:46:39 | main | 0.18.1 | 7207 | 6661 | 85.2% | +0 | +0 | +0.0% |
| 4 | 2026-05-02 19:20:40 | main | 0.18.1 | 7207 | 6661 | 85.2% | +0 | +0 | +0.0% |
| 5 | 2026-05-02 16:16:27 | main | 0.18.1 | 7207 | 6661 | 85.2% | +0 | +0 | +0.0% |
| 6 | 2026-05-02 16:14:28 | main | 0.18.1 | 7207 | 6661 | 85.2% | +0 | +0 | +0.0% |
| 7 | 2026-05-02 16:13:51 | main | 0.18.1 | 7207 | 6661 | 85.2% | +0 | +0 | +0.0% |
| 8 | 2026-05-02 16:12:37 | main | 0.18.1 | 7207 | 6661 | 85.2% | +1259 | +1118 | +0.9% |
| 9 | 2026-04-30 00:27:23 | main | 0.18.1 | 5948 | 5543 | 84.3% | +0 | +0 | +0.0% |
| 10 | 2026-04-30 00:15:20 | main | 0.18.1 | 5948 | 5543 | 84.3% | +0 | +0 | +0.0% |


---

## Appendix: Orphaned Code

Functions with zero callers (potential dead code):

| Function | Module | Lines |
|----------|--------|-------|
| `main()` | scripts/simulation_demo.py | 197 |
| `snapshot_diff()` | src/metabokg/mcp_tools.py | 1 |
---

## CodeRank -- Global Structural Importance

Weighted PageRank over CALLS + IMPORTS + INHERITS edges (test paths excluded). Scores are normalized to sum to 1.0. This ranking seeds Phase 2 fan-in discovery and Phase 15 concern queries.

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.000739 | method | `MetaKG.store` | src/metabokg/orchestrator.py |
| 2 | 0.000392 | method | `MetaStore.node` | src/metabokg/store.py |
| 3 | 0.000372 | method | `PathwayAnalyzer.conn` | src/metabokg/analyze.py |
| 4 | 0.000316 | class | `SnapshotDelta` | src/metabokg/snapshots.py |
| 5 | 0.000306 | class | `SnapshotManifest` | src/metabokg/snapshots.py |
| 6 | 0.000277 | method | `MetaStore.all_nodes` | src/metabokg/store.py |
| 7 | 0.000274 | method | `SnapshotManager.load_manifest` | src/metabokg/snapshots.py |
| 8 | 0.000261 | function | `extract_section` | scripts/generate_wiki.py |
| 9 | 0.000259 | method | `MetaKG.simulator` | src/metabokg/orchestrator.py |
| 10 | 0.000255 | function | `_resolve_db_path` | src/metabokg/app.py |
| 11 | 0.000245 | method | `MetaStore.close` | src/metabokg/store.py |
| 12 | 0.000245 | method | `SentenceTransformerEmbedder.embed_texts` | src/metabokg/embed.py |
| 13 | 0.000245 | method | `MetaKG.close` | src/metabokg/orchestrator.py |
| 14 | 0.000245 | method | `PathwayAnalyzer.close` | src/metabokg/analyze.py |
| 15 | 0.000245 | class | `CSVParserConfig` | src/metabokg/parsers/csv_tsv.py |
| 16 | 0.000245 | function | `_parse_conc_args` | src/metabokg/cli/_utils.py |
| 17 | 0.000233 | method | `SnapshotManager.load_snapshot` | src/metabokg/snapshots.py |
| 18 | 0.000228 | method | `MetaIndex._get_table` | src/metabokg/index.py |
| 19 | 0.000222 | function | `_fbc` | src/metabokg/parsers/sbml.py |
| 20 | 0.000222 | function | `_count_lines` | src/metabokg/downloader.py |

---

## Concern-Based Hybrid Ranking

Top structurally-dominant nodes per architectural concern (0.60 × semantic + 0.25 × CodeRank + 0.15 × graph proximity).

### Configuration Loading Initialization Setup

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7525 | function | `_init_state` | src/metabokg/app.py |
| 2 | 0.7461 | function | `init` | src/metabokg/cli/cmd_init.py |
| 3 | 0.7308 | method | `CSVParser.__init__` | src/metabokg/parsers/csv_tsv.py |
| 4 | 0.7266 | method | `MetaKG.__init__` | src/metabokg/orchestrator.py |
| 5 | 0.7212 | function | `_load_kg` | src/metabokg/app.py |

### Data Persistence Storage Database

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.861 | method | `MetaKG.store` | src/metabokg/orchestrator.py |
| 2 | 0.7471 | function | `_load_store` | src/metabokg/app.py |
| 3 | 0.7304 | method | `MetaStore._migrate` | src/metabokg/store.py |
| 4 | 0.7126 | method | `MetaStore.node_by_xref` | src/metabokg/store.py |
| 5 | 0.711 | function | `_get_store` | src/metabokg/app.py |

### Query Search Retrieval Semantic

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.75 | method | `GraphStore.query_text` | src/metabokg/store.py |
| 2 | 0.7337 | function | `query` | src/metabokg/cli/cmd_query.py |
| 3 | 0.7304 | function | `_tab_search` | src/metabokg/app.py |
| 4 | 0.7256 | method | `MetaKG.query` | src/metabokg/orchestrator.py |
| 5 | 0.7251 | function | `example_4_semantic_search` | scripts/article_examples.py |

### Graph Traversal Node Edge

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.75 | method | `LayerCakeLayout.compute` | src/metabokg/layout3d.py |
| 2 | 0.7474 | method | `AlliumLayout.compute` | src/metabokg/layout3d.py |
| 3 | 0.7381 | method | `Layout3D.compute` | src/metabokg/layout3d.py |
| 4 | 0.7077 | method | `MetaStore.edges_within` | src/metabokg/store.py |
| 5 | 0.7021 | method | `MetaStore.edges_of` | src/metabokg/store.py |



---

*Report generated by PyCodeKG Thorough Analysis Tool — analysis completed in 3.8s*
