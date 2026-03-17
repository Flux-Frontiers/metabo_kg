# MetaKG CodeKG Repository Analysis Report
**Generated:** 2026-03-03
**Tool:** CodeKG Thorough Analysis Skill
**Repository:** `/Users/egs/repos/meta_kg`

---

## Quick Stats

| Metric | Value |
|--------|-------|
| Total nodes | 5,127 |
| Classes | 54 |
| Functions | 134 |
| Methods | 198 |
| Modules | 36 |
| Symbols | 4,705 |
| Total edges | 4,902 |
| CALLS edges | 1,531 |
| ATTR_ACCESS edges | 1,513 |
| RESOLVES_TO edges | 1,160 |
| CONTAINS edges | 386 |
| IMPORTS edges | 302 |
| INHERITS edges | 10 |

**Edge density:** 4,902 / 5,127 nodes ≈ 0.96 (sparse — typical for a focused library)
**Inheritance count (10):** Minimal — confirms composition-over-inheritance design

---

## Architecture Overview

MetaKG is organized into **5 clean layers**:

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 5: Interfaces                                         │
│  cli.py (605L) · mcp_tools.py (462L) · app.py (833L+)       │
│  metakg_viz.py · metakg_viz3d.py                             │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: Orchestration                                      │
│  orchestrator.py — MetaKG (L159–677)                         │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Simulation & Kinetics                              │
│  simulate.py (909L) · kinetics_fetch.py · layout3d.py        │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Storage (dual-layer)                               │
│  store.py — MetaStore (L117–803) + GraphStore (L811–888)     │
│  index.py — MetaIndex  ·  embed.py — Embedder                │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Ingestion                                          │
│  graph.py — MetabolicGraph (dispatch + registry)             │
│  parsers/kgml.py · parsers/sbml.py · parsers/biopax.py       │
│  parsers/base.py — PathwayParser (ABC)                       │
│  primitives.py — MetaNode, MetaEdge, KineticParam            │
└─────────────────────────────────────────────────────────────┘
```

---

## Fan-In Analysis (Most Called Functions)

The following functions are the **most depended-upon** in the codebase:

| Rank | Function | Callers | Notes |
|------|----------|---------|-------|
| 1 | `MetaStore.find_shortest_path` | 4 | 3 tests + `MetaKG.find_path` |
| 2 | `kinetics_fetch.seed_kinetics` | 4 | 2 tests + `simulate_main` + `simulation_demo` |
| 3 | `MetaKG.query_pathway` | 2 | `article_examples.py` + `simulation_demo.py` |
| 4 | `MetaKG.build` | 2 | `build_main` CLI + self-call |
| 5 | `MetaStore` (class) | 3 | test fixture + `simulate_main` + `MetaKG.store` |
| 6 | `register_tools` | 1 | Only `create_server` |

**Observation:** Low absolute caller counts reflect a focused, single-public-API-surface library design.
`MetaKG` class is the **canonical entry point** — almost all production usage funnels through it.
`MetaStore` is the **backbone** — everything that touches data goes through it.

---

## Fan-Out Analysis (Most Complex Functions)

Functions calling the most other functions — **coordination hubs and potential complexity hotspots**:

| Function | Module | Scope | Type |
|----------|--------|-------|------|
| `MetaKG` class | orchestrator.py L159–677 | Coordinates 4 subsystems | Orchestrator |
| `simulate_main` | cli.py L491–597 | Calls 5 helpers + MetaStore directly | CLI hub |
| `register_tools` | mcp_tools.py L49–432 | 383-line fn, 8 nested closures | MCP router |
| `process_directory` | wire_kegg_enzymes.py L178–228 | Calls 4 helpers | Script hub |
| `MetaStore.find_shortest_path` | store.py L411–534 | Contains 3 nested closures + BFS | Algorithm |
| `MetabolicSimulator.run_ode` | simulate.py | Contains `_mm_rate` + `_dydt` closures | Solver |

---

## Architectural Patterns

### Core Modules (Most Depended-Upon)

**1. `src/metakg/store.py` — MetaStore** (lines 117–803, 686 lines)
The gravitational center of the codebase. Handles:
- Schema creation (DDL for all 7+ tables)
- Node/edge CRUD with deduplication
- xref index for cross-database ID resolution
- Bidirectional BFS shortest-path search
- Stoichiometry assembly (compound → reactions → enzymes)
- Kinetic parameter queries
- `GraphStore` visualization wrapper (lines 811–888)

**2. `src/metakg/orchestrator.py` — MetaKG** (lines 159–677)
The public API. Lazy-loads store, index, and simulator. Every CLI entry point and MCP tool delegates to it. Exposes:
- `build()`, `query_pathway()`, `get_compound()`, `get_reaction()`, `find_path()`
- `seed_kinetics()`, `simulate_fba()`, `simulate_ode()`, `simulate_whatif()`
- `get_stats()`, `close()`, context manager

**3. `src/metakg/simulate.py`** (~909 lines total)
Simulation engine + result types + render functions. Self-contained domain module.

### Integration Points (Subsystem Bridges)

| Bridge | From | To |
|--------|------|----|
| `MetaKG.store` (lazy property) | Orchestrator | SQLite persistence |
| `MetaKG.index` (lazy property) | Orchestrator | LanceDB vector search |
| `MetaKG.simulator` (lazy property) | Orchestrator | Metabolic simulation |
| `mcp_tools.register_tools` | MCP server | MetaKG public API |
| `cli.simulate_main` | CLI | MetaStore (direct, bypasses MetaKG) |
| `GraphStore` → `MetaStore` | Viz app | Structured queries |

### Design Patterns Observed

- **Template Method:** `PathwayParser` ABC defines `parse()` + `can_handle()` contract
- **Strategy:** `Embedder` ABC allows pluggable embedding backends
- **Lazy Initialization:** `MetaKG.store`, `.index`, `.simulator` are all `@property` with lazy creation
- **Context Manager:** `MetaKG.__enter__` / `__exit__` for clean resource management
- **Data Transfer Object:** Result types (`FBAResult`, `ODEResult`, `WhatIfResult`, `MetabolicQueryResult`) — clean dataclass boundaries between layers
- **Registry Pattern:** `MetabolicGraph._find_parser()` — parser registry with first-match dispatch

---

## Dependency Analysis

### Layer Dependency Flow (Correct)

```
cli.py → orchestrator.py → store.py, index.py, simulate.py
mcp_tools.py → orchestrator.py
app.py → store.py (via GraphStore)
simulate.py → store.py (MetaStore as dependency)
index.py → embed.py, store.py
graph.py → parsers/*, primitives.py
```

### Potential Layering Violation

`cli.py:simulate_main` (L491–597) **directly instantiates `MetaStore`** rather than routing through `MetaKG`:

```python
# simulate_main bypasses the orchestrator layer
store = MetaStore(args.db)  # Direct store access
simulator = MetabolicSimulator(store)
```

This creates a parallel pathway that bypasses `MetaKG`'s validation, lazy initialization, and resource management. All other CLI commands use `MetaKG` as the entry point.

### Inheritance Graph (10 INHERITS edges — minimal)

```
PathwayParser (ABC)
    ├── KGMLParser    (parsers/kgml.py)
    ├── SBMLParser    (parsers/sbml.py)
    └── BioPAXParser  (parsers/biopax.py)

Embedder (ABC)
    └── SentenceTransformerEmbedder  (embed.py)

MetaStore
    └── GraphStore  (visualization convenience wrapper)
```

---

## Code Quality Signals

### Large Files / Complex Classes

| File | Lines | Risk |
|------|-------|------|
| `src/metakg/store.py` | ~888 | MetaStore god class (686L), many responsibilities |
| `src/metakg/simulate.py` | ~909 | Simulator + 3 render functions bundled |
| `src/metakg/orchestrator.py` | 677 | Large but focused (thin delegation) |
| `src/metakg/mcp_tools.py` | 462 | `register_tools` = 383-line closure factory |
| `src/metakg/cli.py` | 605 | 8 entry points, `_simulate_args` = 158L |
| `src/metakg/app.py` | 833+ | Streamlit app (expected large for UI) |

### Orphaned / Redundant Code

| Item | Location | Issue |
|------|----------|-------|
| `wire_enzymes.py` | `scripts/wire_enzymes.py` | Appears superseded by `wire_kegg_enzymes.py` — same purpose (patch enzyme attributes) but older/simpler version |
| `GraphStore.query_semantic` | `store.py:861–888` | Docstring explicitly calls it "a simplified stub" that does name matching, not vector search. Named "semantic" but isn't. |

### `register_tools` Complexity (mcp_tools.py:49–432)

A single 383-line function that registers 8 MCP tools as nested closures, all capturing the `metakg` instance:
```python
def register_tools(mcp, metakg):
    @mcp.tool()
    async def query_pathway(name, k=8): ...  # nested closure
    @mcp.tool()
    async def get_compound(compound_id): ...  # nested closure
    # ... 6 more nested closures
```

**Impact:** Hard to unit test individual tools in isolation. Hard to read the full 383 lines end-to-end.

---

## Critical Paths

### Build Pipeline
```
scripts/download_human_kegg.py
    → scripts/wire_kegg_enzymes.py (patch enzyme links)
    → metakg-build (cli.py:build_main → MetaKG.build)
        → MetabolicGraph.extract()
            → [KGMLParser | SBMLParser | BioPAXParser].parse()
        → MetaStore.write_nodes() + write_edges()
        → MetaIndex.build() [embed → LanceDB]
```

### Query Pipeline
```
MetaKG.query_pathway(name)  → MetaIndex.search()        → LanceDB ANN
MetaKG.get_reaction(id)     → MetaStore.reaction_detail() → SQLite JOIN
MetaKG.find_path(a, b)      → MetaStore.find_shortest_path() → bidirectional BFS
MetaKG.simulate_fba(pwy)    → MetabolicSimulator.run_fba()  → SciPy linprog
MetaKG.simulate_ode(pwy)    → MetabolicSimulator.run_ode()  → SciPy BDF solver
MetaKG.simulate_whatif(pwy) → run_fba/run_ode × 2           → delta computation
```

### MCP Path
```
MCP client → create_server() → register_tools() → 8 async tool closures → MetaKG.*
```

---

## Risks

### 1. MetaStore God Class
**File:** [src/metakg/store.py](src/metakg/store.py) L117–803 (686 lines)
**Risk:** HIGH — Single class responsible for DDL, CRUD, indexing, BFS shortest-path, stoichiometry assembly, kinetic queries
**Impact:** Difficult to test specific behaviors in isolation; any schema change risks cascading effects
**Suggestion:** Consider splitting into `StoreSchema`, `NodeStore`, `PathFinder` sub-components (or just well-documented sections)

### 2. `register_tools` Mega-Function
**File:** [src/metakg/mcp_tools.py](src/metakg/mcp_tools.py) L49–432
**Risk:** MEDIUM — 383-line function with 8 closure-based tool implementations
**Impact:** All 8 MCP tools are untestable without a live MCP server + MetaKG instance
**Suggestion:** Extract each tool handler to a module-level function taking `metakg` as explicit parameter, then register the wrapper closure

### 3. `simulate_main` Layer Violation
**File:** [src/metakg/cli.py](src/metakg/cli.py) L491–597
**Risk:** MEDIUM — Bypasses MetaKG orchestrator, directly instantiates MetaStore
**Impact:** Different initialization path than all other CLI commands; MetaKG's lazy prop logic is skipped
**Suggestion:** Route through `MetaKG(db_path=args.db)` like `build_main` and `mcp_main` do

### 4. `GraphStore.query_semantic` Stub
**File:** [src/metakg/store.py](src/metakg/store.py) L861–888
**Risk:** LOW — Misleading name ("semantic") for a text-filter function
**Impact:** The Streamlit app uses this for its "Semantic Search" tab; results are name/description substring matches, not actual vector search
**Suggestion:** Either wire to `MetaIndex.search()` or rename to `query_text` / add deprecation note

### 5. Duplicate Script: `wire_enzymes.py`
**File:** [scripts/wire_enzymes.py](scripts/wire_enzymes.py)
**Risk:** LOW — Appears to be an earlier version of `wire_kegg_enzymes.py`
**Impact:** Contributor confusion about which script to use
**Suggestion:** Archive or delete if `wire_kegg_enzymes.py` is the canonical tool

---

## Opportunities

### 1. Extract Result Renderers to Separate Module
`simulate.py` contains `MetabolicSimulator` (the engine) AND `render_fba_result`, `render_ode_result`, `render_whatif_result` (formatting/display). These are separate concerns.

```
simulate.py  → keep MetabolicSimulator + result dataclasses
render.py    → move render_fba_result, render_ode_result, render_whatif_result
```

### 2. Split `register_tools` into Testable Units
```python
# Before: all 8 tools as nested closures in one 383-line function
def register_tools(mcp, metakg): ...

# After: standalone handlers, thin registration
def _query_pathway_handler(metakg, name, k=8): ...
def _get_compound_handler(metakg, compound_id): ...
# ...

def register_tools(mcp, metakg):
    mcp.tool()(_query_pathway_handler(metakg))
```

### 3. Wire `GraphStore.query_semantic` to Real LanceDB Search
The Streamlit viz app would benefit from actual vector search. `MetaIndex.search()` already exists and is fully functional — the bridge just isn't built.

### 4. Normalize `simulate_main` to Use `MetaKG`
```python
# Instead of:
store = MetaStore(args.db)
simulator = MetabolicSimulator(store)

# Use:
with MetaKG(db_path=args.db) as kg:
    result = kg.simulate_fba(pathway_id=args.pathway)
```
This uses the same path as `mcp_tools.py` and `api/` consumers.

---

## Strengths

### Well-Designed Patterns

1. **`PathwayParser` ABC** ([src/metakg/parsers/base.py](src/metakg/parsers/base.py)) — Clean contract: stateless, pure, deterministic. Adding new format support requires just one new file + class.

2. **Lazy initialization in `MetaKG`** ([src/metakg/orchestrator.py](src/metakg/orchestrator.py) L220–238) — Store, index, and simulator are only created on first use. Cheap to construct, efficient in practice.

3. **`MetaKG` as context manager** — `with MetaKG() as kg:` ensures SQLite connections are always closed. Prevents resource leaks.

4. **Deterministic node IDs in primitives** ([src/metakg/primitives.py](src/metakg/primitives.py)) — IDs like `cpd:kegg:C00022` are stable across builds. Foundation of reproducibility.

5. **BDF solver default for ODE** ([src/metakg/simulate.py](src/metakg/simulate.py)) — Correct choice for stiff metabolic systems; previous RK45 default caused hangs. Well-documented in CLAUDE.md.

6. **`SimulationConfig` dataclass** — Rich configuration with clear defaults for ODE tolerance, solver method, flux bounds, Vmax overrides. Cleanly separates "what to simulate" from "how to simulate it."

7. **`KineticParam` dataclass** ([src/metakg/primitives.py](src/metakg/primitives.py) L214–273) — Rich provenance tracking (source_database, literature_reference, organism, tissue, confidence_score). Above average for a research tool.

8. **Test suite completeness** — Tests cover parsers, store, orchestrator, simulation (FBA/ODE/whatif), and include regression guards (BDF hang prevention, max_step regression).

---

## Recommendations (Prioritized)

### Priority 1 (Safety / Correctness)
1. **Fix `simulate_main` to route through `MetaKG`** instead of directly instantiating `MetaStore`. Prevents a subtle initialization divergence that could cause hard-to-debug failures.

### Priority 2 (Maintainability)
2. **Refactor `register_tools`** into standalone handler functions. Makes individual MCP tools independently testable without a running FastMCP server.

3. **Wire `GraphStore.query_semantic`** to `MetaIndex.search()`, or rename it `query_text` and add a comment explaining it's not vector search. The current name is misleading to contributors.

### Priority 3 (Code Organization)
4. **Extract render functions from `simulate.py`** to a `render.py` module. Separates display logic from computation. No behavior change.

5. **Archive `scripts/wire_enzymes.py`** if `wire_kegg_enzymes.py` has superseded it. Add a comment to `wire_kegg_enzymes.py` noting it's the canonical version.

### Priority 4 (Long-term)
6. **Document `MetaStore` section boundaries** with clear comments or consider decomposing into `NodeStore`, `EdgeStore`, `PathFinder` sub-objects. At 686 lines with 20+ methods, the class is the single biggest comprehension challenge in the codebase.

---

## Module Inventory

| Module | Lines | Role |
|--------|-------|------|
| `src/metakg/primitives.py` | — | Domain objects: MetaNode, MetaEdge, KineticParam |
| `src/metakg/parsers/base.py` | ~59 | PathwayParser ABC |
| `src/metakg/parsers/kgml.py` | 299 | KEGG KGML parser |
| `src/metakg/parsers/sbml.py` | 288 | SBML L2/L3 parser |
| `src/metakg/parsers/biopax.py` | ~291 | BioPAX RDF/OWL parser |
| `src/metakg/graph.py` | 155 | File discovery + parser dispatch |
| `src/metakg/store.py` | ~888 | SQLite persistence + GraphStore viz wrapper |
| `src/metakg/embed.py` | 158 | Embedder ABC + SentenceTransformer impl |
| `src/metakg/index.py` | ~252 | MetaIndex LanceDB vector index |
| `src/metakg/kinetics_fetch.py` | ~693 | Curated kinetic parameters seeding |
| `src/metakg/simulate.py` | ~909 | MetabolicSimulator + result types + renderers |
| `src/metakg/orchestrator.py` | 677 | MetaKG top-level API |
| `src/metakg/mcp_tools.py` | ~462 | MCP server tools (register_tools + create_server) |
| `src/metakg/cli.py` | 605 | 8 CLI entry points |
| `src/metakg/app.py` | ~833+ | Streamlit 2D visualization |
| `src/metakg/viz3d.py` | 144 | PyVista 3D visualization |
| `src/metakg/layout3d.py` | — | 3D layout algorithms (Allium, LayerCake) |
| `src/metakg/metakg_viz.py` | 93 | Streamlit launcher |
| `src/metakg/metakg_viz3d.py` | 114 | PyVista launcher |

---

*Analysis performed with CodeKG graph traversal (5,127 nodes, 4,902 edges). Node counts reflect source code parsed at current HEAD.*
