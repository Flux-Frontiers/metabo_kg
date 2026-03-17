# Release Notes — v0.3.0

> Released: 2026-03-06

## Added

- **Pathway category provenance** (`src/metakg/primitives.py`) — New `category` field on `MetaNode` and 8 `PATHWAY_CATEGORY_*` constants (`metabolic`, `transport`, `genetic_info_processing`, `signaling`, `cellular_process`, `organismal_system`, `human_disease`, `drug_development`), derived from the 5-digit KEGG numeric suffix via `_kegg_pathway_category()`. All 369 human pathways are categorized after a fresh build.

- **Category persistence in SQLite** (`src/metakg/store.py`) — `category TEXT` column added to `meta_nodes` schema. `_migrate()` runs on every open and transparently adds the column to existing databases via `ALTER TABLE`. `all_nodes()` now accepts an optional `category=` filter alongside the existing `kind=` filter.

- **Category set in KGML parser** (`src/metakg/parsers/kgml.py`) — `_kegg_pathway_category()` is called when constructing each pathway `MetaNode` so category is populated at parse time.

- **Strategy C enzyme wiring** (`src/metakg/parsers/kgml.py`) — New fallback wiring strategy reads the `reaction=` attribute on gene/ortholog `<entry>` elements to link enzymes to reactions when Strategies A and B fail. Eliminates the last class of unwired enzymes in real KEGG KGML files.

- **CONTAINS fallback for isolated nodes** (`src/metakg/parsers/kgml.py`) — Gene, ortholog, and compound entries that are not wired into any reaction are now connected to their pathway node via `CONTAINS` edges, reducing isolated node count from 12,245 → 0.

- **Agent slash commands** — New `.claude/commands/` entries (`metakg-build.md`, `metakg-simulate.md`, `metakg-viz.md`) and matching `.vscode/*.prompt.md` prompt files for all core MetaKG and CodeKG workflows.

- **`SESSION-NOTES-2026-03-06.md`** — Handoff document summarising all changes made in this session for the next agent/developer.

- **Enhanced 3D visualization CLI options** (`src/metakg/cli/cmd_viz3d.py`) — `metakg-viz3d` now supports layout selection, window sizing, and batch export modes.

- **Improved Fibonacci disk layout algorithm** (`src/metakg/layout3d.py`) — Renamed `_golden_spiral_2d()` → `fibonacci_disk()` for clarity; enhanced docstrings and tuned LayerCake parameters for better visualization.

- **3D Visualization Documentation** (`CLAUDE.md`) — New section covering layout modes, in-UI controls, and recommended workflow.

- **Data Download Scripts Reference** (`CLAUDE.md`) — Documented all three KEGG download scripts with options and output formats.

- **`scripts/download_kegg_reactions.py`** — New script for bulk downloading KEGG reaction details (name, definition, equation, EC numbers).

- **MetaKG Architecture Article** (`article/metakg_article.md`) — Comprehensive article explaining dual-layer architecture (SQLite + LanceDB), four query modalities, and comparison with existing systems.

- **Architecture Infographic Guide** (`article/metakg_architecture_infographic.md`) — Visual walkthrough of system components and data flow.

- **`metakg` unified CLI entry point** (`pyproject.toml`, `src/metakg/cli/main.py`) — New top-level `metakg` command with `--version` support and all subcommands accessible as `metakg <subcommand>`.

- **`docs/INSTALL.md`** — New comprehensive step-by-step installation guide covering all install variants and workflows.

- **`docs/MCP.md`** — New guide for integrating the CodeKG MCP server with Claude Code, Claude Desktop, GitHub Copilot, and Cline.

- **Name enrichment pipeline** (`src/metakg/enrich.py`) — New module replacing bare KEGG accessions with human-readable names. Phase 1: derives labels from enzyme symbols. Phase 2: updates from KEGG name lists.

- **`metakg-enrich` CLI command** — Standalone command for running name enrichment against existing databases.

- **`scripts/download_kegg_names.py`** — Bulk-download script for KEGG compound and reaction name lists (19,571 compounds, 12,384 reactions).

- **`data/kegg_compound_names.tsv` / `data/kegg_reaction_names.tsv`** — Bulk KEGG name lookup tables committed to repository for offline enrichment.

- **`MetaKG.enrich()` public method** (`src/metakg/orchestrator.py`) — Exposes enrichment via the high-level orchestrator.

- **`scripts/wire_kegg_enzymes.py`** — Analysis and patching utility for enzyme coverage across KGML files.

- **`metakg-analyze-basic` CLI entry point** — New command exposing original structured analysis report style.

- **Timestamped output filenames** — `metakg-analyze`, `metakg-analyze-basic`, and `metakg-simulate` now write to auto-named files when `--output` is not specified.

- **`code-kg` core dependency** — Added as production dependency for codebase analysis capabilities.

- **Polished MetaKG Thorough Analysis Report** (`src/metakg/thorough_analysis.py`) — New module providing formatted analysis output with executive summary, risk indicators, and structured recommendations.

## Changed

- **Enrichment default-on** — `--enrich` flag renamed to `--no-enrich` (inverted logic). Enrichment now runs by default.

- **CLAUDE.md updated** — CodeKG Commands section reverted to standalone command style.

- **`metakg-build` default behavior** — Now wipes existing database by default. Use `--no-wipe` for incremental updates.

- **New `metakg-update` command** — Convenience alias for `metakg-build --no-wipe`.

- **CLI option definition refactored** (`src/metakg/cli/options.py`) — Better clarity in inverted flags.

- **CLI refactored from monolithic `cli.py` to `cli/` package** — 642-line monolithic CLI split into modular per-command files while preserving all entry-point names and behavior.

- **`mcp` promoted to core dependency** — `mcp >= 1.0.0` moved to core; MCP server always available without extra install flags.

- **`docs/CAPABILITIES.md` dependency tables updated** — Reflects core/optional dependency changes.

- **CLI fully migrated from argparse to Click** — All commands rewritten with Click decorators; full `--help` support across all commands.

- **`store.query_semantic()` renamed to `query_text()`** — Accurately reflects text-based substring matching behavior.

- **CLI `simulate_main()` uses `MetaKG` orchestrator** — Brings CLI in line with public API surface.

- **MCP tool handlers extracted to module-level functions** — Improves unit testability.

- **WORKFLOW.md updated** — References to enzyme wiring utilities updated.

- **`metakg-analyze` always writes to file** — Removed stdout fallback for consistency.

- **CLAUDE.md refactored** — Condensed to table-driven quick reference.

- **`pyproject.toml` scripts cleaned up** — Removed duplicate `codekg-*` entries now provided by `code-kg` package.

## Fixed

- **`all_nodes()` category filter** — Query builds WHERE clause dynamically for safe combined filtering.

- **SQLite threading error in Streamlit** — Added `check_same_thread=False` to resolve threading issues in web visualizer.

- **KGML multi-gene entry grouping** — Multi-gene entries now create canonical group nodes with all members referenced, eliminating ~5,255 orphaned nodes.

- **xref index expansion for list-valued entries** — Each member gene ID now gets individual `xref_index` row for transparent per-gene lookup.

- **Name enrichment Phase 2 now loads canonical KEGG reaction names** — Phase 2 now extracts KEGG accession from immutable node ID, allowing 1,771 canonical reaction names to load.

- **3D visualization now displays KEGG reaction function names in enzyme sidebar** — Sidebar shows reactions with canonical KEGG function names.

- **Pylint configuration and test fixture naming** — Created `.pylintrc` with proper configuration; fixed fixture naming for pylint compatibility.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
