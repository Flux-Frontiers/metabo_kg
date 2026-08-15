> **Analysis Report Metadata**
> - **Generated:** 2026-08-15T13:47:40Z
> - **Version:** pycode-kg 0.23.0
> - **Commit:** 6f82b51 (main)
> - **Platform:** macOS 27.0 | arm64 (arm) | turing | Python 3.12.13
> - **Graph:** 7394 nodes · 6794 edges (489 meaningful)
> - **Included directories:** scripts, src
> - **Excluded directories:** none
> - **Elapsed time:** 5s

# Metabo_kg Analysis

**Generated:** 2026-08-15 13:47:40 UTC

---

## Executive Summary

This report provides a comprehensive architectural analysis of the **Metabo_kg** repository using PyCodeKG's knowledge graph. The analysis covers complexity hotspots, module coupling, key call chains, and code quality signals to guide refactoring and architecture decisions.

| Overall Quality | Grade | Score |
| :--- | :--- | :--- |
| [B] **Good** | **B** | 84.1 / 100 |

Score components:

| Component | Points | Max | Basis |
| :--- | ---: | ---: | :--- |
| Docstring coverage | 37.8 | 40 | 85.1% documented (full marks at 90%) |
| Dead code | 11.3 | 25 | 12 candidates / 437 definitions scanned (2.7%; zero points at 5%) |
| High fan-out | 20.0 | 20 | 0 orchestrator(s); −4 pts each |
| Circular dependencies | 15.0 | 15 | 0 cycle(s); −5 pts each |

---

## Baseline Metrics

| Metric | Value |
| :--- | :--- |
| **Total Nodes** | 7394 |
| **Total Edges** | 6794 |
| **Modules** | 52 (of 52 total) |
| **Functions** | 237 |
| **Classes** | 49 |
| **Methods** | 151 |

### Edge Distribution

| Relationship Type | Count |
| :--- | ---: |
| CALLS | 2450 |
| CONTAINS | 437 |
| IMPORTS | 446 |
| ATTR_ACCESS | 2209 |
| INHERITS | 10 |

---

## Fan-In Ranking

Most-called functions and methods — potential bottlenecks or core functionality.  Classes are omitted: instantiation counts are not architectural fan-in.

| # | Kind | Function | Module | Callers |
| ---: | :--- | :--- | ---: | :--- |
| 1 | method | `node()` | src/metabokg/store.py | **25** |
| 2 | method | `close()` | src/metabokg/analyze.py | **17** |
| 3 | method | `close()` | src/metabokg/orchestrator.py | **17** |
| 4 | method | `close()` | src/metabokg/store.py | **17** |
| 5 | function | `_section()` | scripts/examples.py | **16** |
| 6 | method | `store()` | src/metabokg/orchestrator.py | **12** |
| 7 | method | `conn()` | src/metabokg/analyze.py | **9** |
| 8 | method | `edges_of()` | src/metabokg/store.py | **7** |
| 9 | function | `rewrite_repo_links()` | scripts/generate_wiki.py | **6** |
| 10 | method | `all_nodes()` | src/metabokg/store.py | **6** |
| 11 | function | `strip_image_refs()` | scripts/generate_wiki.py | **5** |
| 12 | method | `load_manifest()` | src/metabokg/snapshots.py | **5** |
| 13 | method | `load_snapshot()` | src/metabokg/snapshots.py | **5** |
| 14 | function | `_count_lines()` | src/metabokg/downloader.py | **4** |
| 15 | method | `index()` | src/metabokg/orchestrator.py | **4** |

**Insight:** Functions with high fan-in are either core APIs or bottlenecks. Review these for:

- Thread safety and performance
- Clear documentation and contracts
- Potential for breaking changes

---

## High Fan-Out Functions (Orchestrators)

Functions that call many others may indicate complex orchestration logic or poor separation of concerns.  Only repo-internal callees are counted — stdlib and third-party calls are not orchestration.

No extreme high fan-out functions detected. Well-balanced architecture.

---

## Module Architecture

Top modules by dependency coupling and cohesion (showing 10 of 52 with activity).
Cohesion = incoming / (incoming + outgoing + 1); higher = more internally focused.  Modules with no in-repo callers are externally driven (MCP router, CLI, GUI event loop) — their 0.00 cohesion is expected, not a coupling problem.

| Module | Functions | Classes | Incoming | Outgoing | Cohesion | Note |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `src/metabokg/store.py` | 3 | 2 | 4 | 1 | 0.67 |  |
| `src/metabokg/orchestrator.py` | 0 | 5 | 3 | 6 | 0.30 |  |
| `src/metabokg/analyze.py` | 5 | 8 | 2 | 0 | 0.67 |  |
| `src/metabokg/mcp_tools.py` | 28 | 0 | 0 | 0 | 0.00 | externally driven |
| `src/metabokg/snapshots.py` | 1 | 5 | 1 | 0 | 0.50 |  |
| `src/metabokg/app.py` | 21 | 0 | 0 | 2 | 0.00 | externally driven |
| `src/metabokg/simulate.py` | 5 | 6 | 2 | 0 | 0.67 |  |
| `scripts/examples.py` | 18 | 0 | 0 | 2 | 0.00 | externally driven |
| `scripts/generate_wiki.py` | 17 | 0 | 0 | 0 | 0.00 | externally driven |
| `src/metabokg/viz3d.py` | 15 | 1 | 0 | 0 | 0.00 | externally driven |

---

## Key Call Chains

Deepest call chains in the codebase.

**Chain 1** (depth: 3)

```
orchestrator.py:__exit__ → orchestrator.py:close → analyze.py:close
```

**Chain 2** (depth: 3)

```
store.py:__exit__ → store.py:close → analyze.py:close
```

---

## Public API Surface

Definitions re-exported from an `__init__.py` or otherwise reachable as public entry points, ranked by fan-in.  Top 10 of 52 shown.

| Name | Module | Fan-In | Kind |
| :--- | :--- | ---: | :--- |
| `MetaKG` | src/metabokg/orchestrator.py | 28 | class |
| `SnapshotManager` | src/metabokg/snapshots.py | 8 | class |
| `rewrite_repo_links()` | scripts/generate_wiki.py | 6 | function |
| `GraphStore` | src/metabokg/store.py | 5 | class |
| `strip_image_refs()` | scripts/generate_wiki.py | 5 | function |
| `build()` | src/metabokg/cli/cmd_build.py | 4 | function |
| `info()` | src/metabokg/cli/cmd_info.py | 3 | function |
| `SnapshotDelta` | src/metabokg/snapshots.py | 3 | class |
| `pack()` | src/metabokg/mcp_tools.py | 2 | function |
| `pack()` | src/metabokg/cli/cmd_pack.py | 2 | function |

---

## Docstring Coverage

Docstring coverage directly determines semantic retrieval quality. Nodes without docstrings embed only structured identifiers (`KIND/NAME/QUALNAME/MODULE`), where keyword search is as effective as vector embeddings. The semantic model earns its value only when a docstring is present.

| Kind | Documented | Total | Coverage |
| :--- | ---: | ---: | :--- |
| `function` | 187 | 237 | [WARN] 78.9% |
| `method` | 128 | 151 | [OK] 84.8% |
| `class` | 49 | 49 | [OK] 100.0% |
| `module` | 52 | 52 | [OK] 100.0% |
| **total** | **416** | **489** | **[OK] 85.1%** |

---

## Structural Importance Ranking (SIR)

Weighted PageRank aggregated by module — reveals architectural spine. Cross-module edges boosted 1.5×; private symbols penalized 0.85×. Node-level detail: `pycodekg centrality --top 25`

| Rank | Score | Members | Module |
| ---: | ---: | ---: | :--- |
| 1 | 0.144613 | 39 | `src/metabokg/store.py` |
| 2 | 0.109654 | 36 | `src/metabokg/orchestrator.py` |
| 3 | 0.088724 | 29 | `src/metabokg/analyze.py` |
| 4 | 0.082136 | 27 | `src/metabokg/snapshots.py` |
| 5 | 0.043983 | 21 | `src/metabokg/simulate.py` |
| 6 | 0.043661 | 15 | `src/metabokg/primitives.py` |
| 7 | 0.037615 | 29 | `src/metabokg/mcp_tools.py` |
| 8 | 0.033750 | 11 | `src/metabokg/index.py` |
| 9 | 0.031826 | 18 | `scripts/generate_wiki.py` |
| 10 | 0.028972 | 16 | `src/metabokg/layout3d.py` |
| 11 | 0.027292 | 22 | `src/metabokg/app.py` |
| 12 | 0.024999 | 15 | `src/metabokg/downloader.py` |
| 13 | 0.024409 | 14 | `src/metabokg/enrich.py` |
| 14 | 0.023049 | 19 | `scripts/examples.py` |
| 15 | 0.021250 | 17 | `src/metabokg/viz3d.py` |

---

## Code Quality Issues

- [WARN] 12 dead-code candidates found (`biopax.py:BioPAXParser`, `store.py:upsert_kinetic_param`, `layout3d.py:LayoutNode`, `store.py:upsert_regulatory_interaction`, `layout3d.py:LayoutEdge`, `download_icho_model.py:fetch_model_info`, `store.py:regulatory_interactions_for_enzyme`, `orchestrator.py:save` and 4 more) -- no callers in code or tests; verify against downstream consumers, then remove or archive
- [INFO] 10 definitions are unused in production code but exercised by tests -- likely public API for downstream packages; not counted against the quality grade
- [WARN] `store.py` has 38 functions/methods/classes -- consider splitting into focused submodules
- [WARN] `orchestrator.py` has 35 functions/methods/classes -- consider splitting into focused submodules

---

## Architectural Strengths

- Well-structured with 15 core functions identified
- No god objects or god functions detected
- Good docstring coverage: 85.1% of functions/methods/classes/modules documented

---

## Recommendations

### Immediate Actions
1. **Triage dead-code candidates** — `BioPAXParser`, `upsert_kinetic_param`, `LayoutNode`, `upsert_regulatory_interaction`, `LayoutEdge` (and 7 more) have zero callers in code and tests; confirm no downstream package consumes them, then remove

### Medium-term Refactoring
1. **Harden high fan-in functions** — `node`, `close`, `close` are widely depended upon; review for thread safety, clear contracts, and stable interfaces
2. **Reduce module coupling** — consider splitting tightly coupled modules or introducing interface boundaries
3. **Add tests for key call chains** — the identified call chains represent well-traveled execution paths that benefit most from regression coverage

### Long-term Architecture
1. **Version and stabilize the public API** — document breaking-change policies for `MetaKG`, `SnapshotManager`, `rewrite_repo_links`
2. **Enforce layer boundaries** — add linting or CI checks to prevent unexpected cross-module dependencies as the codebase grows
3. **Monitor hot paths** — instrument the high fan-in functions identified here to catch performance regressions early

---

## Inheritance Hierarchy

**10** INHERITS edges across **11** classes. Max depth: **1**.

| Class | Module | Depth | Parents | Children |
| :--- | :--- | ---: | ---: | ---: |
| `AlliumLayout` | src/metabokg/layout3d.py | 1 | 1 | 0 |
| `LayerCakeLayout` | src/metabokg/layout3d.py | 1 | 1 | 0 |
| `BioPAXParser` | src/metabokg/parsers/biopax.py | 1 | 1 | 0 |
| `CSVParser` | src/metabokg/parsers/csv_tsv.py | 1 | 1 | 0 |
| `KGMLParser` | src/metabokg/parsers/kgml.py | 1 | 1 | 0 |
| `SBMLParser` | src/metabokg/parsers/sbml.py | 1 | 1 | 0 |
| `GraphStore` | src/metabokg/store.py | 1 | 1 | 0 |
| `Layout3D` | src/metabokg/layout3d.py | 0 | 1 | 2 |
| `PathwayParser` | src/metabokg/parsers/base.py | 0 | 1 | 4 |
| `SnapshotManager` | src/metabokg/snapshots.py | 0 | 1 | 0 |
| `MetaStore` | src/metabokg/store.py | 0 | 0 | 1 |

---

## Snapshot History

Recent snapshots in reverse chronological order. Δ columns show change vs. the immediately preceding snapshot.  6 unchanged snapshot(s) elided.

| # | Timestamp | Branch | Version | Nodes | Edges | Coverage | Δ Nodes | Δ Edges | Δ Coverage |
| ---: | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2026-08-15 13:18:04 | build/fleet-dep-alignment | 0.11.0 | 7394 | 6794 | 85.1% | +0 | +0 | +0.0% |
| 2 | 2026-08-15 13:14:13 | build/fleet-dep-alignment | 0.11.0 | 7394 | 6794 | 85.1% | +2 | -25 | +0.0% |
| 6 | 2026-08-03 18:23:56 | ci/wheel-smoke-test | 0.10.0 | 7392 | 6819 | 85.1% | +2 | +12 | -0.1% |
| 8 | 2026-07-27 00:23:36 | main | 0.9.0 | 7390 | 6807 | 85.2% | +0 | +2 | +0.0% |

---

## Orphaned Code

12 definitions have no callers in code or tests (dead-code candidates).  Framework-dispatched entry points — dunder/protocol methods, properties, Click commands, MCP tools, `ast.NodeVisitor` dispatch, SDK protocol overrides, console scripts, `__main__` guards — are already excluded.

| Name | Kind | Module | Lines |
| :--- | :--- | :--- | ---: |
| `BioPAXParser` | class | src/metabokg/parsers/biopax.py | 225 |
| `upsert_kinetic_param()` | method | src/metabokg/store.py | 40 |
| `LayoutNode` | class | src/metabokg/layout3d.py | 28 |
| `upsert_regulatory_interaction()` | method | src/metabokg/store.py | 25 |
| `LayoutEdge` | class | src/metabokg/layout3d.py | 22 |
| `fetch_model_info()` | function | scripts/download_icho_model.py | 11 |
| `regulatory_interactions_for_enzyme()` | method | src/metabokg/store.py | 10 |
| `save()` | method | src/metabokg/orchestrator.py | 8 |
| `kinetic_params_for_enzyme()` | method | src/metabokg/store.py | 8 |
| `as_dict()` | method | src/metabokg/primitives.py | 4 |
| `as_dict()` | method | src/metabokg/primitives.py | 4 |
| `_is_bare_compound()` | function | src/metabokg/enrich.py | 1 |

10 further definitions are unused in production code but exercised by tests — likely public API consumed by downstream packages.  Not counted against the quality grade; review for intentional export.

| Name | Kind | Module | Lines |
| :--- | :--- | :--- | ---: |
| `KGMLParser` | class | src/metabokg/parsers/kgml.py | 339 |
| `SBMLParser` | class | src/metabokg/parsers/sbml.py | 292 |
| `CSVParser` | class | src/metabokg/parsers/csv_tsv.py | 213 |
| `write()` | method | src/metabokg/store.py | 53 |
| `get_stats()` | method | src/metabokg/orchestrator.py | 27 |
| `CorpusSpec` | class | src/metabokg/downloader.py | 14 |
| `TsvSpec` | class | src/metabokg/downloader.py | 14 |
| `stoichiometry_dict()` | method | src/metabokg/primitives.py | 12 |
| `evidence_dict()` | method | src/metabokg/primitives.py | 11 |
| `xrefs_dict()` | method | src/metabokg/primitives.py | 11 |

---

## CodeRank — Global Structural Importance

Weighted PageRank over CALLS + IMPORTS + INHERITS edges (test paths excluded). Scores are normalized to sum to 1.0. This ranking seeds fan-in discovery and the concern queries below.  Top 20 of 25 shown.

| Rank | Score | Kind | Name | Module |
| ---: | ---: | :--- | :--- | :--- |
| 1 | 0.000719 | method | `MetaKG.store()` | src/metabokg/orchestrator.py |
| 2 | 0.000637 | function | `_section()` | scripts/examples.py |
| 3 | 0.000382 | method | `MetaStore.node()` | src/metabokg/store.py |
| 4 | 0.000363 | method | `PathwayAnalyzer.conn()` | src/metabokg/analyze.py |
| 5 | 0.000337 | function | `rewrite_repo_links()` | scripts/generate_wiki.py |
| 6 | 0.000308 | class | `SnapshotDelta` | src/metabokg/snapshots.py |
| 7 | 0.000308 | method | `MetaIndex._new_backend()` | src/metabokg/index.py |
| 8 | 0.000298 | class | `SnapshotManifest` | src/metabokg/snapshots.py |
| 9 | 0.000291 | function | `strip_image_refs()` | scripts/generate_wiki.py |
| 10 | 0.000270 | method | `MetaStore.all_nodes()` | src/metabokg/store.py |
| 11 | 0.000267 | method | `SnapshotManager.load_manifest()` | src/metabokg/snapshots.py |
| 12 | 0.000252 | method | `MetaKG.simulator()` | src/metabokg/orchestrator.py |
| 13 | 0.000248 | function | `_resolve_db_path()` | src/metabokg/app.py |
| 14 | 0.000239 | method | `MetaStore.close()` | src/metabokg/store.py |
| 15 | 0.000239 | method | `MetaKG.close()` | src/metabokg/orchestrator.py |
| 16 | 0.000239 | method | `PathwayAnalyzer.close()` | src/metabokg/analyze.py |
| 17 | 0.000239 | class | `CSVParserConfig` | src/metabokg/parsers/csv_tsv.py |
| 18 | 0.000239 | function | `_parse_conc_args()` | src/metabokg/cli/_utils.py |
| 19 | 0.000227 | method | `SnapshotManager.load_snapshot()` | src/metabokg/snapshots.py |
| 20 | 0.000217 | function | `_fbc()` | src/metabokg/parsers/sbml.py |

---

## Concern-Based Hybrid Ranking

Top structurally-dominant nodes per architectural concern (0.60 × semantic + 0.25 × CodeRank + 0.15 × graph proximity).

### Configuration Loading Initialization Setup

| Rank | Score | Kind | Name | Module |
| ---: | ---: | :--- | :--- | :--- |
| 1 | 0.7525 | function | `_init_state()` | src/metabokg/app.py |
| 2 | 0.7473 | function | `init()` | src/metabokg/cli/cmd_init.py |
| 3 | 0.7407 | method | `MetaKG.__init__()` | src/metabokg/orchestrator.py |
| 4 | 0.7379 | method | `CSVParser.__init__()` | src/metabokg/parsers/csv_tsv.py |
| 5 | 0.7322 | function | `_load_kg()` | src/metabokg/app.py |

### Data Persistence Storage Database

| Rank | Score | Kind | Name | Module |
| ---: | ---: | :--- | :--- | :--- |
| 1 | 0.8621 | method | `MetaKG.store()` | src/metabokg/orchestrator.py |
| 2 | 0.7516 | function | `_load_store()` | src/metabokg/app.py |
| 3 | 0.7426 | method | `MetaStore._migrate()` | src/metabokg/store.py |
| 4 | 0.7281 | method | `MetaStore.node_by_xref()` | src/metabokg/store.py |
| 5 | 0.7281 | function | `_get_store()` | src/metabokg/app.py |

### Query Search Retrieval Semantic

| Rank | Score | Kind | Name | Module |
| ---: | ---: | :--- | :--- | :--- |
| 1 | 0.75 | method | `GraphStore.query_text()` | src/metabokg/store.py |
| 2 | 0.7467 | function | `query()` | src/metabokg/cli/cmd_query.py |
| 3 | 0.7388 | function | `_tab_search()` | src/metabokg/app.py |
| 4 | 0.7349 | method | `MetaKG.query()` | src/metabokg/orchestrator.py |
| 5 | 0.7272 | method | `MetaIndex.search()` | src/metabokg/index.py |

### Graph Traversal Node Edge

| Rank | Score | Kind | Name | Module |
| ---: | ---: | :--- | :--- | :--- |
| 1 | 0.7509 | function | `_expand_hits()` | src/metabokg/app.py |
| 2 | 0.7337 | method | `MetaStore.expand_hops()` | src/metabokg/store.py |
| 3 | 0.7195 | method | `AlliumLayout.compute()` | src/metabokg/layout3d.py |
| 4 | 0.7189 | method | `LayerCakeLayout.compute()` | src/metabokg/layout3d.py |
| 5 | 0.7163 | method | `Layout3D.compute()` | src/metabokg/layout3d.py |

---

*Report generated by PyCodeKG Thorough Analysis Tool — analysis completed in 5.0s*
