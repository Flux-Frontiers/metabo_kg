# Changelog

All notable changes to MetaKG are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

---

## [0.3.0] - 2026-03-06

### Added

- **Pathway category provenance** (`src/metakg/primitives.py`) — New `category` field on `MetaNode` and 8 `PATHWAY_CATEGORY_*` constants (`metabolic`, `transport`, `genetic_info_processing`, `signaling`, `cellular_process`, `organismal_system`, `human_disease`, `drug_development`), derived from the 5-digit KEGG numeric suffix via `_kegg_pathway_category()`. All 369 human pathways are categorized after a fresh build.

- **Category persistence in SQLite** (`src/metakg/store.py`) — `category TEXT` column added to `meta_nodes` schema. `_migrate()` runs on every open and transparently adds the column to existing databases via `ALTER TABLE`. `all_nodes()` now accepts an optional `category=` filter alongside the existing `kind=` filter.

- **Category set in KGML parser** (`src/metakg/parsers/kgml.py`) — `_kegg_pathway_category()` is called when constructing each pathway `MetaNode` so category is populated at parse time.

- **Strategy C enzyme wiring** (`src/metakg/parsers/kgml.py`) — New fallback wiring strategy reads the `reaction=` attribute on gene/ortholog `<entry>` elements to link enzymes to reactions when Strategies A and B fail. Eliminates the last class of unwired enzymes in real KEGG KGML files.

- **CONTAINS fallback for isolated nodes** (`src/metakg/parsers/kgml.py`) — Gene, ortholog, and compound entries that are not wired into any reaction are now connected to their pathway node via `CONTAINS` edges, reducing isolated node count from 12,245 → 0.

- **Agent slash commands** — New `.claude/commands/` entries (`metakg-build.md`, `metakg-simulate.md`, `metakg-viz.md`) and matching `.vscode/*.prompt.md` prompt files for all core MetaKG and CodeKG workflows.

- **`SESSION-NOTES-2026-03-06.md`** — Handoff document summarising all changes made in this session for the next agent/developer.

### Changed

- **Enrichment default-on** (`src/metakg/cli/cmd_build.py`, `src/metakg/orchestrator.py`) — `--enrich` flag renamed to `--no-enrich` (inverted logic). Enrichment now runs by default on both `metakg-build` and `metakg-update`. `MetaKG.build(enrich=False)` default changed to `True`.

- **CLAUDE.md updated** — CodeKG Commands section reverted to `codekg-*` standalone command style; Typical Workflow section updated to invoke commands directly (no `poetry run` prefix needed in activated venv).

### Fixed

- **`all_nodes()` category filter** (`src/metakg/store.py`) — Query now builds WHERE clause dynamically to support combined `kind` + `category` filtering without SQL injection risk.

---

### Changed

- **`metakg-build` default behavior** — Now wipes existing database and vector index by default (safer, more predictable). Use `--no-wipe` flag to add files incrementally instead of replacing.
  - Renamed `--wipe` flag → `--no-wipe` (inverted logic, default=True)
  - Updated docstring to clarify wipe-by-default behavior
  - Updated all documentation (CLAUDE.md, README.md, WORKFLOW.md) to reflect new defaults
- **New `metakg-update` command** (`src/metakg/cli/cmd_build.py`) — Convenience alias for `metakg-build --no-wipe`. Provides explicit intent: incrementally merge new pathway files into an existing database without wiping. Supports the same enrichment and kinetics-seeding options as `build`.
- **CLI option definition refactored** (`src/metakg/cli/options.py`) — `wipe_option` now uses Click's `flag_value=False, default=True` pattern for better clarity in inverted flags.

### Added

- **Enhanced 3D visualization CLI options** (`src/metakg/cli/cmd_viz3d.py`) — `metakg-viz3d` now supports:
  - `--layout {allium|cake}` — Select spatial layout strategy (Hub-spoke Allium vs concentric LayerCake)
  - `--width` / `--height` — Configure window dimensions (1400x900 default)
  - `--export-html PATH` / `--export-png PATH` — Batch export to file instead of interactive window
  - Improved error handling: check database existence before launching visualizer

- **Improved Fibonacci disk layout algorithm** (`src/metakg/layout3d.py`) — Renamed `_golden_spiral_2d()` → `fibonacci_disk()` for clarity; enhanced docstrings. Tuned LayerCake parameters: layer gap 12→6 (tighter), disc radius 28→35 (wider), minimum spread 4→20 (prevent clamping on small pathways). Enzyme nodes moved to Z-level 3 (separate from compounds).

- **3D Visualization Documentation** (`CLAUDE.md`) — New section covering layout modes, in-UI controls (pathway filter, layout selector, visibility toggles), and recommended workflow.

- **Data Download Scripts Reference** (`CLAUDE.md`) — Documented all three KEGG download scripts with options and output formats. Clarified single-step vs multi-step enrichment pipelines.

- **`scripts/download_kegg_reactions.py`** — New script for bulk downloading KEGG reaction details (name, definition, equation, EC numbers). Supports scanning local KGML files for reaction IDs (faster) or querying KEGG link endpoint. Output: `data/kegg_reaction_detail.tsv`.

- **MetaKG Architecture Article** (`article/metakg_article.md`) — Comprehensive article explaining dual-layer architecture (SQLite + LanceDB), four query modalities, and comparison with existing systems (KEGG, BioCyc, Reactome, etc.).

- **Architecture Infographic Guide** (`article/metakg_architecture_infographic.md`) — Visual walkthrough of system components and data flow.

- **`metakg` unified CLI entry point** (`pyproject.toml`, `src/metakg/cli/main.py`) — New top-level `metakg` command registered as a `@click.group()` with `--version` support. All subcommands (`build`, `enrich`, `analyze`, `analyze-basic`, `simulate`, `mcp`, `viz`, `viz3d`) are accessible as `metakg <subcommand>` in addition to the existing standalone `metakg-*` aliases.

- **`docs/INSTALL.md`** — New comprehensive step-by-step installation guide covering all install variants (core, simulate, viz, viz3d, biopax, all-extras), pathway data download, graph build, name enrichment, kinetics seeding, MCP server startup, web explorer, 3D visualizer, dev install, environment variables, upgrading, and troubleshooting.

- **`docs/MCP.md`** — New guide for integrating the CodeKG MCP server with Claude Code, Claude Desktop, GitHub Copilot, and Cline; covers quick-start, per-repo `.mcp.json` / `.vscode/mcp.json` configuration, and available MCP tools.

### Changed

- **CLI refactored from monolithic `cli.py` to `cli/` package** (`src/metakg/cli/`) — The 642-line `src/metakg/cli.py` has been replaced by a proper package where each command group lives in its own module. All existing entry-point names and CLI behaviour are preserved.
  - `cli/__init__.py` — re-exports the root `cli` group and all standalone entry-point aliases
  - `cli/main.py` — root `@click.group()` with `--version`
  - `cli/options.py` — shared reusable Click option decorators (`db_option`, `lancedb_option`, `model_option`, `wipe_option`, `data_option`)
  - `cli/_utils.py` — shared helpers: `_timestamped_filename()`, `_parse_conc_args()`, `_parse_factor_args()`, `_write_output()`
  - `cli/cmd_analyze.py` — `metakg analyze` / `metakg analyze-basic`
  - `cli/cmd_build.py` — `metakg build` / `metakg enrich`
  - `cli/cmd_mcp.py` — `metakg mcp`
  - `cli/cmd_simulate.py` — `metakg simulate {fba,ode,whatif,seed}`
  - `cli/cmd_viz.py` — `metakg viz`
  - `cli/cmd_viz3d.py` — `metakg viz3d`

- **`mcp` promoted to core dependency** (`pyproject.toml`) — `mcp >= 1.0.0` moved from the optional `[mcp]` extra to the core dependency list; the MCP server is now always available without extra install flags. The `[mcp]` extra has been removed; `[viz3d]` and `[all]` extras updated accordingly. `param` optional dependency removed (no longer needed).

- **`mcp_tools.py` import guard removed** — Defensive `try/except ImportError` around `FastMCP` import eliminated now that `mcp` is a core dependency.

- **`docs/CAPABILITIES.md` dependency tables updated** — `mcp` moved to core dependencies table; `[mcp]` extra row removed; `[viz3d]` extra updated with pinned minimum versions (`pyvista >= 0.44.0`, `pyvistaqt >= 0.11.0`, `PyQt5 >= 5.15.0`); install examples updated to reflect new extras layout; link to `docs/INSTALL.md` added.

### Added

- **Name enrichment pipeline** (`src/metakg/enrich.py`) — New module that replaces bare KEGG accessions (`C00031`, `R00710`) with human-readable names stored directly in `meta_nodes.name`. Phase 1 (no network): derives reaction labels from catalysing enzyme gene symbols via `CATALYZES` edges (e.g. `R00710` → `ADH1A / ADH1B / ADH1C`). Phase 2 (requires TSV files): updates compound and reaction names from downloaded KEGG name lists. Both phases are idempotent.

- **`metakg-enrich` CLI command** (`src/metakg/cli.py`, `pyproject.toml`) — Standalone Click command for running name enrichment against an existing database: `metakg-enrich [--db PATH] [--data DIR]`. Also integrated as `--enrich` / `--enrich-data` flags on `metakg-build` for a single-step build+enrich workflow.

- **`scripts/download_kegg_names.py`** — New bulk-download script that fetches the KEGG compound list (~19 500 entries) and reaction list (~12 400 entries) from `rest.kegg.jp/list/` and saves them as `data/kegg_compound_names.tsv` / `data/kegg_reaction_names.tsv`. Supports `--data DIR`, `--force`, `--quiet`; includes 1-second courtesy pause between requests per KEGG policy.

- **`data/kegg_compound_names.tsv` / `data/kegg_reaction_names.tsv`** — Bulk KEGG name lookup tables (19 571 compounds, 12 384 reactions) committed to the repository; used by `metakg-enrich` Phase 2 and available for offline enrichment without re-downloading.

- **`MetaKG.enrich()` public method** (`src/metakg/orchestrator.py`) — Exposes enrichment via the high-level orchestrator: `kg.enrich(data_dir=None) → EnrichStats`. `build()` gains `enrich=False` and `enrich_data_dir=None` parameters.

### Changed

- **CLI fully migrated from argparse to Click** (`src/metakg/cli.py`) — All CLI commands rewritten with Click decorators (`@click.command`, `@click.group`, `@click.option`). `metakg-simulate` is now a `@click.group()` with shared `--db/--output/--plain/--top` options passed via `ctx.obj` to `fba`, `ode`, `whatif`, and `seed` subcommands. Error handling uses `raise click.ClickException(msg)` and `click.echo(..., err=True)`. Every command and subcommand now supports `--help` automatically. `click >= 8.0` added as a core dependency.

- **`docs/CAPABILITIES.md` updated to v0.2.0** — Added §5 (Name Enrichment) covering both enrichment phases, download script, CLI, and Python API. Updated ODE solver documentation from RK45 to BDF throughout with stiffness warning. Added `ode_method`, `ode_rtol`, `ode_atol`, `ode_max_step` fields to `SimulationConfig` reference. Added `click`, `matplotlib`, and `pandas` to dependency tables. Added `metakg-enrich` to CLI reference.

- **Optional viz dependencies expanded** (`pyproject.toml`) — `matplotlib >= 3.8.0` and `pandas >= 2.0.0` added as optional dependencies, included in the `[viz]` and `[all]` extras.

### Fixed

- **SQLite threading error in Streamlit** (`src/metakg/store.py`) — `sqlite3.connect()` now passes `check_same_thread=False`, resolving "SQLite objects created in a thread can only be used in that same thread" errors that occurred when the Streamlit app cached a connection via `@st.cache_resource` and served requests from worker threads.

### Changed

- **`store.query_semantic()` renamed to `query_text()`** (`src/metakg/store.py`, `src/metakg/app.py`) — Method renamed to accurately reflect that it performs a text-based substring match, not a true semantic/vector search; semantic search remains in `MetaIndex`. Docstring updated to clarify the distinction and direct users to `MetaIndex` for embedding-based queries.

- **CLI `simulate_main()` uses `MetaKG` orchestrator** (`src/metakg/cli.py`) — `seed`, `fba`, `ode`, and `whatif` subcommands now instantiate `MetaKG` via `with MetaKG(db_path=...) as kg:` instead of directly importing `MetaStore` and `MetabolicSimulator`. Brings CLI in line with the public API surface.

- **MCP tool handlers extracted to module-level functions** (`src/metakg/mcp_tools.py`) — All per-tool logic moved from closures inside `register_tools()` to standalone `_mcp_*()` functions at module level, making them unit-testable without a live FastMCP instance. `register_tools()` now delegates to these functions and copies docstrings for MCP schema generation.

- **WORKFLOW.md updated for `wire_kegg_enzymes.py`** — References to the old `wire_enzymes.py` replaced; description expanded to cover the scanning/patching approach and `--dry-run` flag.

### Removed

- **`pathways/` sample KGML files** (`pathways/hsa00010.xml` – `hsa00650.xml`) — 11 hand-authored KGML fixtures removed from version control; real pathway data lives in `data/hsa_pathways/` (not tracked).

- **`scripts/wire_enzymes.py`** — Hardcoded one-shot enzyme wiring script retired; superseded by the more general `scripts/wire_kegg_enzymes.py` (which auto-detects missing enzyme coverage across all KGML files).

### Fixed

- **KGML multi-gene entry grouping** (`src/metakg/parsers/kgml.py`) — A single KGML `<entry type="gene">` often lists multiple gene IDs (e.g. pyruvate dehydrogenase complex `hsa:5160 hsa:5161 hsa:5162`). The previous parser created one enzyme node per gene but only wired the last-processed gene to its reaction via a CATALYZES edge, leaving all others as orphaned nodes with no edges. Fix: create one canonical group node per entry (keyed on the first gene ID, labelled with KEGG graphics name); all member gene IDs stored as a list in the node's `xrefs` JSON; `entry_map` points to the single node so CATALYZES wiring is correct and complete. Effect across full human KEGG dataset: ~1,797 fewer enzyme nodes, CATALYZES edge count unchanged at 4,165, ~5,255 previously orphaned enzyme nodes eliminated.

- **xref index expansion for list-valued entries** (`src/metakg/store.py` — `MetaStore.build_xref_index`) — Updated to expand list-valued xref entries into individual `xref_index` rows. Each member gene ID in a group node gets its own row pointing to the canonical group node, so per-gene lookup works transparently. Example: group node `enz:kegg:5160` with `xrefs={"kegg": ["5160","5161","5162"]}` produces three `xref_index` rows.

### Added

- **`scripts/wire_kegg_enzymes.py`** — Analysis and patching utility that scans KGML files for reaction elements missing enzyme coverage (not handled by Strategy A or B) and patches them with `enzyme="N"` attributes. Confirmed that all 4,165 reaction elements in the full human KEGG dataset are fully covered by Strategy B; patching is only needed for hand-authored sample files.

- **`metakg-analyze-basic` CLI entry point** — New `analyze_basic_main()` in `cli.py` exposing the original structured (non-narrative) analysis report as a separate command, preserving both report styles
- **Timestamped output filenames** — `metakg-analyze`, `metakg-analyze-basic`, and `metakg-simulate` now write to auto-named files (e.g., `metakg-analysis-2026-03-03-143022.md`) when `--output` is not specified, eliminating silent stdout dumps
- **`code-kg` core dependency** — Added `code-kg` as a production dependency in `pyproject.toml` (git source: Flux-Frontiers/code_kg); codekg CLI scripts now come from that package directly rather than being re-declared here
- **Revised article abstract** (`article/metakg_revised.tex`) — Rewritten to lead with architectural innovation (dual-layer SQLite + LanceDB), emphasise all four query modalities plus simulation and visualisation capabilities, and highlight the complete human metabolome ingestion; format parsing demoted to supporting infrastructure

### Changed

- **`metakg-analyze` always writes to file** — Removed stdout fallback; output path is either the `--output` argument or a timestamped default; mirrors `metakg-simulate` behaviour
- **CLAUDE.md refactored** — Condensed from ~600 lines to ~120-line table-driven quick reference; removed redundant prose, kept command tables, simulation examples, and CodeKG query strategy
- **`pyproject.toml` scripts cleaned up** — Removed duplicate `codekg-*` script entries (now provided by the `code-kg` package); added `metakg-analyze-basic` entry point
- **`.codekg/lancedb` untracked from git** — Removed regenerable LanceDB vector index files from version control; `.gitignore` entry already present; index can be rebuilt with `/codekg-rebuild`
- **Analysis report title** (`src/metakg/analyze.py`) — Changed from `"MetaKG Pathway Analysis Report"` to `"metaKG_analysis"` for cleaner file naming

### Removed

- **`codekg-*` script declarations from `pyproject.toml`** — Scripts are now provided by the `code-kg` dependency package; no functional change for users

- **Polished MetaKG Thorough Analysis Report** — New `src/metakg/thorough_analysis.py` module providing CodeKG-style formatted analysis output
  - Executive Summary with 5-minute KPI overview
  - Emoji-enhanced section headers (📊 📈 🔥 ⚡ 🔗 📦 🧬 🧪 ⚠️ ✅ 💡)
  - Risk level indicators (🟢 LOW 🟡 MED 🔴 HIGH) for metabolite hubs and complex reactions
  - Network Health Issues section identifying data quality signals
  - Metabolic Network Strengths section highlighting well-designed patterns
  - Structured Biological Insights & Recommendations with 3-tier action plan (Immediate, Medium-term, Long-term)
  - Full Appendix with complete isolated nodes and dead-end metabolite lists
  - Seamless CLI integration: `metakg-analyze` now generates the polished report

- **Claude Slash Command** — New `.claude/commands/metakg-analyze.md` for quick pathway analysis invocation with `/metakg-analyze`

### Changed

- **`metakg-analyze` CLI Command** — Updated `src/metakg/cli.py:analyze_main()` to use new `render_thorough_report()` from `thorough_analysis.py`
  - Same CLI interface and flags (`--db`, `--output`, `--top`, `--plain`)
  - Richer Markdown output with polished sections and emoji headers
  - Backward compatible: plain-text mode (`--plain`) still works

- **MetaKG Thorough Analysis Skill** — Updated `.claude/skills/metakg-thorough-analysis/SKILL.md` Python API section to import and use `render_thorough_report()`

### Removed

### Fixed

- **Name enrichment Phase 2 now loads canonical KEGG reaction names** (`src/metakg/enrich.py`) — The enrichment pipeline had an architectural flaw: Phase 1 would rename reactions from bare accessions (e.g., `R00710`) to gene symbols (e.g., `ADH1A / ADH1B / ADH1C`), then Phase 2 would skip them because it only recognized bare accessions, preventing 1,771 canonical KEGG reaction function names from ever being loaded. Fixed by extracting the KEGG accession directly from the immutable node ID (format: `rxn:kegg:R00710`) instead of relying on the volatile `name` field. This implements the intended **dual-layer design**: Phase 2 now always overrides Phase 1, ensuring canonical structural names take priority over enriched gene labels. Phase 1 names are preserved only when no canonical KEGG name exists. Result: 1,771 additional reaction names now loaded (was 0 before). Example: `R00710` now displays as `"acetaldehyde:NAD+ oxidoreductase"` instead of gene symbols.

- **3D visualization now displays KEGG reaction function names in enzyme sidebar** (`src/metakg/viz3d.py`) — When picking an enzyme node, the sidebar now shows the reactions it catalyzes with their canonical KEGG function names (e.g., `"alcohol dehydrogenase (NAD+)"`, `"3-ketosteroid 1-dehydrogenase"`). This is now possible thanks to the enrichment fix above. Changes: (1) Load KEGG reaction names TSV at startup (lines 154–173), (2) Update enzyme display to show catalyzed reactions with KEGG function names (lines 252–280), (3) Gracefully fallback to bare accession if no KEGG name available, (4) Clarify labels: `"Enzyme"` → `"Gene symbol"` for clarity. This fixes the user request: instead of bare gene symbols like `ADH1A`, the sidebar now describes what each enzyme does.

- **Pylint configuration and test fixture naming** (`.pylintrc`, `tests/test_simulation.py`) — Created `.pylintrc` with proper configuration for the codebase; fixed unrecognized `max-lines` option (changed to `max-module-lines`). Renamed fixture `kg_with_minimal_pathway` to `kkg_with_minimal_pathway` to eliminate false pylint `redefined-outer-name` warnings in pytest test functions.

## [0.2.0] - 2026-02-28

### Added

- **Comprehensive Metabolic Simulation Documentation** — Expanded CLI reference, API guide, and scientific article with complete examples for all three simulation modalities
  - CLAUDE.md: New "Simulation and Analysis" section with detailed examples for FBA, kinetic ODE integration, and what-if perturbation analysis
  - README.md: New "Metabolic Simulations" section with runnable code examples and ODE solver configuration guide
  - article/metakg.tex: New "Metabolic Simulations" subsection explaining solver architecture and parameter seeding
  - Comprehensive explanation of why BDF solver is optimal for metabolic systems (inherent stiffness from fast enzyme kinetics + slow substrate dynamics)
  - All ODE parameters documented: ode_method, ode_rtol, ode_atol, ode_max_step with defaults and rationale

- **Comprehensive Unit Tests for Metabolic Simulations** — 21 new tests covering all simulation modalities with timeout guards
  - FBA tests: Basic FBA, minimize mode, nonexistent pathway handling
  - ODE tests: BDF (default), RK45 (non-stiff), Radau, custom tolerances, max_step behavior, edge cases, stiffness handling
  - What-if tests: FBA mode (baseline/knockout/inhibition), ODE mode with perturbations
  - Kinetics tests: seed_kinetics, force overwrite, repeated seeding
  - Regression tests: BDF completes <2s on integration (prevents hanging), ode_max_step=None doesn't cause hanging
  - Timeout guards: @pytest.mark.timeout(3-10s) on all ODE/what-if tests prevents test runner lock-up

- **Updated Orchestrator Docstrings** — Clarified ODE parameters in simulate_ode() and simulate_whatif() method documentation
  - Corrected default ode_method from "LSODA" to "BDF" with stiffness explanation
  - Updated ode_rtol, ode_atol with relaxed defaults (1e-3, 1e-5) optimized for convergence on stiff systems
  - Documented ode_max_step=None as recommended to let solver adapt adaptively

- **Public Statistics API** — New `MetabolicRuntimeStats` dataclass and `MetaKG.get_stats()` method for clean, type-safe access to knowledge graph statistics
  - Encapsulates total nodes/edges, node counts by kind, edge counts by relation
  - Includes optional vector index statistics (indexed rows and embedding dimension)
  - Provides `__str__()` for nicely formatted output and `to_dict()` for serialization
  - Eliminates internal `.store` exposure in public API
  - Exported in `metakg` module for public use

- **Comprehensive Unit Tests for Orchestrator** — 14 new tests for `MetabolicRuntimeStats` and `MetaKG.get_stats()`
  - Tests basic construction, serialization, and string representation
  - Tests stats accuracy with real data (node/edge counts)
  - Tests edge cases (empty database, multiple calls consistency)
  - Tests API cleanliness (no internal implementation exposure)

- **Simulation Demo Script** — `scripts/simulation_demo.py` demonstrating metabolic pathway simulations
  - Example 1: Seeding kinetic parameters from literature (BRENDA/SABIO-RK)
  - Example 2: Flux Balance Analysis (FBA) for steady-state flux prediction
  - Example 3: FBA with custom objective reaction
  - Example 4: Kinetic ODE simulation for time-course dynamics
  - Example 5: Enzyme knockout perturbation analysis
  - Example 6: Enzyme partial inhibition (50%) perturbation analysis

### Changed

- **Codebase Formatting & Maintainability Improvements** — Comprehensive code cleanup across all modules for consistency and maintainability
  - Added author attribution and revision timestamps to all module docstrings (20 files)
  - Standardized import ordering (alphabetical) across all modules
  - Improved code readability with consistent line-breaking and comment alignment
  - Reformatted SQL queries for better readability (multi-line formatting)
  - Applied consistent __all__ list formatting and inline comment alignment
  - Enhanced docstring formatting in data classes and analysis functions
  - All changes pass Ruff formatting, type checking, and linting standards

- **Article Examples API Cleanup** — Updated `scripts/article_examples.py` to use public `kg.get_stats()` instead of internal `kg.store.stats()`
  - Uses typed `MetabolicRuntimeStats` object with attribute access instead of dict access
  - Gracefully handles optional index statistics with `.get()` calls
  - Demonstrates proper API usage patterns for users

- **License Migration to Elastic License 2.0** — Updated from PolyForm Noncommercial to Elastic License 2.0 to align with sister project CodeKG
  - Updated `pyproject.toml` license field to `Elastic-2.0`
  - Added `LICENSE` file with complete Elastic License 2.0 terms
  - Updated README license badge with link to official license page

### Fixed

- **Pylance Type Checking Issues** — Added `MetaIndex.stats()` method to resolve type errors in `MetaKG.get_stats()`
  - Returns indexed row count and embedding dimension from LanceDB index
  - Gracefully handles missing or unavailable index

- **Code Quality & Linting**
  - Fixed import ordering in `scripts/simulation_demo.py`, `src/metakg/orchestrator.py`, and `tests/test_orchestrator.py` to comply with Ruff I001
  - Removed f-string prefixes from non-placeholder strings in `scripts/simulation_demo.py` (Ruff F541)
  - Removed unused imports (`tempfile`, `pathlib.Path`) from `tests/test_orchestrator.py`
  - All changes pass Ruff linting and mypy type checking

- **Critical Namespace Shadowing Bug** — `src/metakg/metakg.py` was shadowing the metakg package namespace, preventing imports of submodules like `graph.py` and breaking all CLI commands. Resolved by renaming to `orchestrator.py` and updating all import statements.

### Added

- **Consistent Project Badges** — Enhanced README with project status badges matching CodeKG style
  - Python version badge showing supported versions (3.10, 3.11, 3.12)
  - Version badge (0.1.0) with link to releases
  - Poetry dependency manager badge
  - Updated license badge for Elastic License 2.0

- **CodeKG Sister Project Reference** — Added prominent reference to CodeKG in README
  - Sister Project section highlighting CodeKG's role in enabling semantic analysis of MetaKG's own codebase
  - Added CodeKG to Acknowledgments section as primary enabling technology

- **Architecture Diagram in README** — Integrated visual architecture diagram (`docs/metaKG_arch.png`) into the Architecture section
  - Provides quick visual overview of system components and organization
  - Complements detailed file structure documentation

- **CodeKG Integration for Codebase Analysis** — MetaKG can now be analyzed using CodeKG's knowledge graph tools
  - Built static analysis graph (SQLite): 3,136 nodes, 2,920 edges across 27 modules
  - Built semantic vector index (LanceDB): 290 vectors with 384-dimensional embeddings
  - Configured MCP servers for Claude Code, GitHub Copilot, Kilo Code, and Cline
  - Enables tools like `query_codebase`, `pack_snippets`, `callers` for code exploration

- **Comprehensive CLI Documentation** — Added `CLAUDE.md` with complete reference for both MetaKG and CodeKG commands
  - MetaKG commands: `metakg-build`, `metakg-analyze`, `metakg-viz`, `metakg-viz3d`, `metakg-mcp`
  - CodeKG commands: `codekg-build-sqlite`, `codekg-build-lancedb`, `codekg-query`, `codekg-mcp`
  - MCP tool documentation with usage examples and query strategies
  - Typical workflows and combined MetaKG + CodeKG usage patterns
  - All examples include `poetry run` activation for virtual environment

- **MCP Server Configuration** — Added MCP server definitions for multiple clients
  - `.mcp.json` for Claude Code and Kilo Code
  - `.vscode/mcp.json` for GitHub Copilot integration

- **Interactive Web Visualization** — Streamlit-based metabolic knowledge graph explorer
  - Graph Browser tab for visualizing pathways, reactions, compounds, and enzymes
  - Semantic Search tab for querying nodes by description and keywords
  - Node Details tab for exploring comprehensive node information
  - Pyvis-based interactive graph rendering with filtering and legend controls

- **3D Metabolic Pathway Visualization** — PyVista-powered 3D interactive visualizer
  - Allium layout strategy: each pathway rendered as a "Giant Allium plant" with reactions/compounds as the spherical head
  - LayerCake layout strategy: vertical stratification by node kind with golden-angle spiral distribution
  - Interactive 3D rendering with color coding by metabolic entity type
  - Export to HTML and PNG formats

- **Layout Algorithms** (`src/metakg/layout3d.py`)
  - Fibonacci spatial utilities for uniform point distribution on spheres and annuli
  - AlliumLayout class for plant-inspired botanical visualization
  - LayerCakeLayout class for stratified hierarchical visualization
  - Extensible Layout3D abstract base class for custom layout implementations

- **CLI Commands**
  - `metakg-viz` — Launch Streamlit web explorer with database and port configuration
  - `metakg-viz3d` — Launch 3D PyVista visualizer with layout and export options

- **GraphStore Wrapper** (`src/metakg/store.py`)
  - Convenience compatibility layer wrapping MetaStore with visualization-friendly methods
  - `query_nodes()` — Query nodes with optional kind filtering
  - `query_edges()` — Query edges with optional source/destination filtering
  - `query_semantic()` — Text-based semantic search (extensible for embeddings)
  - `get_node()` — Fetch individual nodes by ID

- **Dependencies**
  - Optional visualization extras: `viz` (Streamlit + pyvis), `viz3d` (PyVista + PyQt5)
  - Updated pyproject.toml with streamlit, pyvis, pyvista, pyvistaqt, PyQt5, and param dependencies

- **Documentation**
  - Comprehensive README.md with quick start, architecture, commands, and API examples
  - Detailed feature descriptions and usage patterns
  - Performance characteristics and installation variants

### Changed

- **Orchestrator Class** — Renamed `MetaKG` source file from `metakg.py` to `orchestrator.py` for clarity and to eliminate namespace shadowing
- **Import Paths** — Updated all references from `metakg.metakg` to `metakg.orchestrator` in `__init__.py`, `mcp_tools.py`, and `app.py`
- **pyproject.toml** — Added optional visualization dependencies and `viz` + `viz3d` extras, plus CodeKG CLI entry points
- **src/metakg/cli.py** — Added `viz_main()` and `viz3d_main()` entry points for new CLI commands
- **src/metakg/store.py** — Extended with GraphStore compatibility wrapper class

### Technical Details

- **Visualization Scope** — Adapted from flux-frontiers/code_kg with metabolic pathway domain-specific customizations
- **Node Types** — Supports compound, reaction, enzyme, and pathway nodes
- **Edge Relations** — SUBSTRATE_OF, PRODUCT_OF, CATALYZES, INHIBITS, ACTIVATES, CONTAINS, XREF
- **Embedding Model** — Integrates with sentence-transformers via LanceDB for semantic search
- **Database** — SQLite persistence with indexed queries for graph operations

## [0.1.0] — 2024-02-27

### Added

- Initial standalone MetaKG package release
- Metabolic pathway parser supporting KGML, SBML, BioPAX, and CSV formats
- Semantic knowledge graph with LanceDB vector indexing
- MCP (Model Context Protocol) server integration
- Core CLI: `metakg-build` and `metakg-mcp` commands
- SQLite-based graph persistence layer
- Cross-reference resolution and pathway unification

---

[Unreleased]: https://github.com/flux-frontiers/meta_kg/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/flux-frontiers/meta_kg/releases/tag/v0.1.0
