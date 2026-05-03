# Changelog

All notable changes to MetaboKG are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

- **LanceDB index strategy: reactions indexed, enzymes excluded** (`src/metabokg/index.py`) — The vector index now covers **compound**, **reaction**, and **pathway** nodes. Enzyme nodes (9,427 in hsa) are dropped from indexing: they contain only gene-name lists, producing near-identical embeddings that crowd out compound and pathway results. Enzymes remain reachable via hop-1 graph expansion from reactions. Updated vector counts: hsa 7,623, cge 7,570, icho 10,512 (dim=384).
- **`embed.py` consolidated into `kgmodule-utils`** (`src/metabokg/embed.py`) — Removed local `Embedder` and `SentenceTransformerEmbedder` class definitions; the module now re-exports them from `kg_utils.embedder` (shipped in `kgmodule-utils ≥0.2.4`). MetaboKG-specific helpers (`SeedHit`, `extract_distance`, `escape_id`) remain in place.
- **`enrich.py` pipeline simplified** (`src/metabokg/enrich.py`) — Removed Phase 2c (reaction detail TSV fallback) and Phase 3 (per-organism enzyme gene symbol enrichment) from the `enrich()` pipeline. `EnrichStats` drops the `reactions_from_detail` and `enzymes_from_tsv` fields accordingly.
- **iCHO2441 stats corrected** (`README.md`, `docs/icho_workflow.md`, `docs/FEATURES.md`, `CLAUDE.md`) — The published model has 6,663 reactions; MetaboKG parses **6,337** (exchange/boundary reactions with no internal metabolites are excluded during SBML ingestion). Metabolite count corrected to **4,174**. These numbers are now consistent across all documentation surfaces.
- **`kgmodule-utils` bumped to `≥0.2.4`** (`pyproject.toml`) — Required for the shared `Embedder`/`SentenceTransformerEmbedder` re-exports in `embed.py`.
- **Transitive dependency bumps** (`poetry.lock`) — `pyvista` 0.47.3→0.48.0, `huggingface-hub` 1.12.2→1.13.0, `pycode-kg` 0.18.1→0.19.0, `cachetools` 7.0.6→7.1.0, `typer` 0.25.0→0.25.1, `cyclopts` 4.11.0→4.11.1, `jedi` 0.19.2→0.20.0, `parso` 0.8.6→0.8.7, `wcwidth` 0.6.0→0.7.0.

### Fixed

### Removed

---

## [0.8.1] - 2026-05-02

### Added

- **CI and PyPI badges in README** (`README.md`) — Live CI status badge for the new `.github/workflows/ci.yml` workflow and a PyPI version badge linking to `https://pypi.org/project/metabo-kg/` (resolves once the package is published).

### Changed

- **`/release` slash command no longer maintains `release-notes.md`** (`.claude/commands/release.md`) — GitHub Release pages are the single source of release notes; the repo no longer carries a `release-notes.md` file. The script now uses `gh release create … --generate-notes`, which auto-builds the release body from commits/PRs since the previous tag, and the artifact glob has been tightened to `dist/metabo_kg-<new_version>.*` to avoid attaching stale builds.

### Removed

- **`release-notes.md` removed** — The repo no longer keeps a tracked release-notes file. Notes for each tagged release live only on the corresponding GitHub Release page.

---

## [0.8.0] - 2026-05-02

### Added

- **`ANNOUNCEMENT.md`** (root) — GitHub-style introductory announcement post: punchy intro, why it exists, the three bundled corpora, hybrid retrieval, simulation, MCP/LLM integration, 60-second quickstart, and links to the docs map. Suitable as a Discussions post or release-page body.
- **`.github/workflows/ci.yml`** — CI workflow for `push` and `pull_request` on `main`: lint + format check (`ruff`), type check (`mypy src/`), and tests (`pytest -m "not integration and not slow"`) on Python 3.12, with cached Poetry virtualenvs.

### Changed

- **License finalized as Elastic License 2.0 across all surfaces** (`README.md`, `ANNOUNCEMENT.md`) — README badge switched from `PolyForm-NC-1.0.0` to `Elastic-2.0`; the License section was rewritten to describe the actual restrictions (no hosted-service resale, no notice circumvention) instead of the noncommercial-only framing. The `LICENSE` file and `CITATION.cff` were already on Elastic 2.0; this change reconciles the README with them.
- **README "Contributing" section softened** (`README.md`) — Renamed to "Feedback & contributions" and clarified that issues and discussions are welcome but external pull requests are paused while contribution licensing (CLA vs DCO) is finalized.
- **`pycode-kg` promoted from git source to PyPI** (`pyproject.toml`) — `pycode-kg` is now published on PyPI at `>=0.18.1`; removed the `git+https` source reference and the testpypi supplemental source entry. Both `kg` and `all` extras now resolve from PyPI.
- **`doc-kg` bumped to `>=0.12.3`** (`pyproject.toml`) — Updated minimum version in `kg` and `all` extras (was `>=0.11.0`).
- **`kgmodule-utils` bumped to `>=0.2.3`** (`pyproject.toml`) — Updated minimum version in core dependencies (was `>=0.2.0`).
- **`dev` extra merged into `kg` extra** (`pyproject.toml`) — Development tools (`detect-secrets`, `mypy`, `pre-commit`, `ruff`, `pytest`, etc.) consolidated under the `kg` extra; the separate `dev` extra is removed.
- **Code style in `embed.py`** (`src/metabokg/embed.py`) — `model.encode()` call wrapped to 88-character line limit; no functional change.
- **`/release` slash command repaired and consolidated** (`.claude/commands/release.md`) — Was a stale copy from the code_kg repo with broken paths (`src/code_kg/__init__.py`, `codekg-*` commands). Now correctly references `src/metabokg/__init__.py` and `pycodekg-*` commands, includes a clean-tree + `gh auth` preflight, and folds `poetry build` + `gh release create` into the same flow so releases are cut entirely from the laptop with a single confirmation gate. The redundant `.github/workflows/publish.yml` CI workflow was removed.

### Removed

- **`agent-kg`, `ftree-kg`, `memory-kg` removed from `kg` and `all` extras** (`pyproject.toml`) — These git-only packages are no longer listed in optional extras. Install directly from their git repositories when needed.
- **testpypi supplemental source removed** (`pyproject.toml`) — No longer needed now that `pycode-kg` is on PyPI.
- **`.github/workflows/publish.yml` removed** — Tag-triggered CI build/release workflow superseded by the repaired `/release` command, which now does `poetry build` + `gh release create` locally.

---

## [0.7.1] - 2026-04-24

### Fixed

- **`CITATION.cff`** — Consolidated `given-names` / `name-suffix` into a single `given-names` field; replaced `license` key with `license-url` pointing to the Elastic License 2.0 page (CFF 1.2 schema compliance).

---

## [0.7.0] - 2026-04-24

### Added

- **`MetaKG.stats()` — KGRAG adapter contract** (`src/metabokg/orchestrator.py`) — New method returns a flat `dict[str, Any]` with `node_count`, `total_edges`, `pathway_count`, `compound_count`, and `reaction_count`. Satisfies the adapter status contract so `kgrag probe` can render a meaningful status row for MetaboKG without calling the heavier `get_stats()` → `MetabolicRuntimeStats` path. Never raises; returns zeros on store error.

- **Flat domain keys in `MetaStore.stats()`** (`src/metabokg/store.py`) — `stats()` now includes `pathway_count`, `compound_count`, and `reaction_count` as top-level int keys alongside the existing `node_counts` / `edge_counts` dicts. These are derived from `node_counts.get(kind, 0)` with no extra queries.

- **Tests for `MetaStore.stats()` domain keys** (`tests/test_store.py`) — Two new tests in `TestMetaStoreBasic`: `test_stats_domain_keys_populated` (verifies counts against fixture data) and `test_stats_domain_keys_empty_store` (verifies zero-defaults on an empty DB).

- **`TestMetaKGStats` test class** (`tests/test_orchestrator.py`) — Eight tests covering shape, envelope keys, domain keys, correct counts, empty-DB zeros, no-raise guarantee, and consistency between `stats()` and `get_stats()`.

### Changed

- **SBML Level 3 FBC v2 gene-association parser** (`src/metabokg/parsers/sbml.py`) — `SBMLParser` now handles the Flux Balance Constraints v2 package used by iCHO2441. `_parse_fbc_genes()` reads `<fbc:listOfGeneProducts>` into `enz:syn:…` nodes (with Entrez gene IDs stored in `xrefs`). `_attach_fbc_catalyzes()` recursively flattens `<fbc:or>` / `<fbc:and>` association trees and emits one `CATALYZES` edge per referenced gene product. Result: 2,441 enzyme nodes and 9,796 CATALYZES edges parsed from iCHO2441.

- **`enrich_enzyme_names` support for `enz:syn:` (SBML FBC) nodes** (`src/metabokg/enrich.py`) — Phase 3 enrichment now handles two enzyme ID schemes. For `enz:kegg:{org}:{gene_id}` the existing org-specific TSV lookup is used. For `enz:syn:{hash}` nodes (produced by the FBC parser) the Entrez gene ID from `xrefs` is matched against all `*_gene_names.tsv` files in `data/`. Result: 1,942 / 2,441 iCHO enzymes (80%) resolved to gene symbols (e.g. `G_100762926` → `Aoc3`).

- **`enrich_from_tsv` and `enrich_reactions_from_detail` xrefs fallback** (`src/metabokg/enrich.py`) — Both functions now read the `xrefs` JSON column and extract a `kegg` cross-reference when a node's ID is not in the `cpd:kegg:…` / `rxn:kegg:…` format. This enables future SBML files that carry `identifiers.org` KEGG annotations to be enriched without code changes.

- **`docs/FEATURES.md`** — New reference document covering all three bundled corpora (hsa, cge, icho): node/edge/vector counts, enrichment details, simulation support matrix, and multi-corpus build commands.

- **`docs/icho_workflow.md`** — Detailed workflow guide for the iCHO2441 genome-scale model: download, FBC-specific parser behaviour, build results, enrichment phase-by-phase analysis, known gaps (499 unresolved genes, single-pathway structure, OR/AND flattening), and KGRAG registration.

- **`docs/EXAMPLES.md`** — Renamed from root `EXAMPLES.md` into `docs/` for consistency with the new `docs/` layout.

### Fixed

- **BioModels download URL** (`scripts/download_icho_model.py`) — The old URL pattern (`/{MODEL_ID}/download?filename=…`) returns an HTML redirect page; the script now uses the correct REST API path (`/model/download/{MODEL_ID}?filename=…`). Added an XML content check that fails fast with a clear error when the response is not SBML. Model filename changed to `iCHO2441.xml` to match the BioModels canonical name.

- **Gene symbol parsing in `_load_gene_names_tsv`** (`src/metabokg/enrich.py`) — Previous logic split only on the last `,` or `;`, producing multi-word descriptions (e.g. `"amiloride-sensitive amine oxidase [copper-containing]"`) as spurious symbols. Now splits on `;` first (drops the description portion) then takes the first `,`-separated alias, and rejects any candidate containing a space or starting with a digit.

### Changed

- **`sentence-transformers` bumped to `^5.4.1`** (`pyproject.toml`) — Updated from `^5.2.0` to track the latest stable release.

- **Author / revision / license headers** added to `scripts/download_icho_model.py`, `scripts/download_kegg_reactions.py`, `scripts/fetch_sabio_cho_kinetics.py`, and `scripts/simulation_demo.py` for consistency with the rest of the codebase (`License: Elastic 2.0`).

- **Code formatting** in `scripts/download_kegg_reactions.py`, `scripts/fetch_sabio_cho_kinetics.py`, and `scripts/simulation_demo.py` — Long lines wrapped to 88 characters (Black/ruff style).

- **`docs/cho_workflow.md`** known limitations updated — iCHO2441 download no longer requires a BioModels account; updated entry to reflect that the download script now works anonymously. Replaced the stale "SBML ingest pending" note with the actual enrichment gap (499 unresolved gene symbols in the `syn:` namespace).

- **`.claude/settings.json`** — Added allowed Bash patterns for `download_icho_model.py --force` and inline Python syntax checks used during development.

### Added

- **`_load_kg()` and `_load_full_graph()` cached resource helpers** (`src/metabokg/app.py`) — Two new `@st.cache_resource` functions hold the `MetaKG` embedding model and the full 17K-node/edge scan in memory across Streamlit reruns. Previously these were re-created on every interaction, causing noticeable latency; now they load once per session (keyed on `db_path`).

- **`_expand_hits()` — multi-hop graph expansion for search** (`src/metabokg/app.py`) — Expands a set of seed hit nodes through *n* hops of graph neighbours using `store.neighbours()` and a batched `store.nodes()` fetch, avoiding N+1 query patterns. Used by the revamped Search tab when `hops > 0`.

- **`_render_node_detail()` and `_node_detail_section()`** (`src/metabokg/app.py`) — New helpers render a rich, theme-aware detail card for any metabolic graph node (compound formula/charge, enzyme EC number, cross-references, and an edge table). A selectbox (`_node_detail_section`) lets users pick any result node without leaving the tab.

- **`_inject_css()` — theme-aware CSS injection** (`src/metabokg/app.py`) — Replaces the removed static `st.markdown(<style>…)` block at startup. Detects Streamlit's active theme via `st.get_option("theme.base")` and generates card/edge colours that work in both light and dark mode.

### Changed

- **`_tab_search()` major overhaul** (`src/metabokg/app.py`) — Search results are now persisted in `st.session_state` so they survive Streamlit reruns without re-querying. The tab gains k/hops number inputs, a graph visualisation sub-tab (PyVis) alongside the results list, a seed-vs-expanded count banner, an active kind/relation filter pass, and a `_node_detail_section` at the bottom. Added a collapsible debug panel that surfaces path resolution and model metadata when results are empty.

- **`sentence-transformers` pinned to `^5.2.0`** (`pyproject.toml`) — Tightened from `>=2.7.0` to `^5.2.0` to align with `pycode-kg`'s constraint and ensure the renamed `get_embedding_dimension()` API (introduced in 4.x) is always available; the old floor allowed silent installation of pre-rename versions.

- **Pre-commit hooks invoke `.venv/bin/` directly** (`.pre-commit-config.yaml`) — Changed `entry` for `mypy` and `pytest` hooks from `poetry run mypy src/` / `poetry run pytest --tb=short -q` to `.venv/bin/mypy src/` / `.venv/bin/pytest --tb=short -q`. Removes the `poetry` process-spawn overhead on every commit; requires the virtualenv to be activated or the `.venv` symlink to be present.

- **`.gitignore`** — Added `.agentkg/` to exclude AgentKG runtime artefacts from version control.

### Added

- **`MetaKG.query()` — general-purpose semantic search** (`src/metabokg/orchestrator.py`) — New method searches all indexed node kinds (compound, enzyme, pathway) by semantic similarity. Unlike `query_pathway()`, it does not filter results by kind, so queries like `"glucose"` or `"ATP synthase"` now correctly return compound and enzyme nodes. Both `metabokg query` (CLI) and the Streamlit Search tab now use this method; `query_pathway()` is retained for pathway-specific callers (MCP tools, etc.).

- **`metabokg query` CLI command** (`src/metabokg/cli/cmd_query.py`) — New subcommand for semantic or substring search across the knowledge graph. Uses vector (LanceDB) search by default; falls back to text search when the index is absent or `--text-only` is set. Supports `--k`, `--hop` (graph expansion), and `--text-only` options. Also registered as a standalone `metabokg-query` entry point.

- **`MetabolicPack` result type** (`src/metabokg/orchestrator.py`) — New dataclass that bundles matched nodes with their full biological context. For pathways: reactions with substrates, products, enzymes, and stoichiometry. For reactions: full stoichiometric detail. For compounds: participating reactions. For enzymes: catalyzed reactions. Provides `to_markdown()`, `to_json()`, and `save(path, fmt)` methods. Also exported from `metabokg` top-level (`from metabokg import MetabolicPack`).

- **`MetaKG.pack(text, k=8, hop=1)` method** (`src/metabokg/orchestrator.py`) — Runs semantic search + graph expansion then enriches each hit with biological context, returning a `MetabolicPack`. Mirrors the `PyCodeKG.pack()` pattern: `kg.pack("TCA cycle", k=8, hop=1).save("context.md")`. Deduplicates results and sorts by kind (pathways first).

- **`metabokg-pack` CLI command** (`src/metabokg/cli/cmd_pack.py`) — New `metabokg pack QUERY` subcommand and `metabokg-pack` standalone entry point. Options: `--k`, `--hop`, `--output/-o`, `--fmt {md,json}`, `--max-rxn`. Default output is Markdown to stdout.

- **`pack` MCP tool** (`src/metabokg/mcp_tools.py`) — New MCP tool `pack(text, k, hop)` registered first in `register_tools`. Returns a Markdown context pack for direct LLM injection. The `create_server` instructions now surface `pack` as the primary entry point.

- **`MetaStore.expand_hops(seed_hits, hop)` method** (`src/metabokg/store.py`) — BFS graph expansion previously buried in `cli/cmd_query.py` is now a first-class method on `MetaStore`. Uses `neighbours()` internally. Called by `MetaKG.query()` and `MetaKG.query_pathway()` when `hop > 0`.

- **`hop` parameter on `MetaKG.query()` and `MetaKG.query_pathway()`** (`src/metabokg/orchestrator.py`) — Both methods now accept `hop: int = 0`. When `hop > 0`, seed hits are expanded via `store.expand_hops()`. Mirrors the `PyCodeKG.query(k, hop)` API so callers never need to handle expansion themselves.

- **Phase 2d: glycan name enrichment** (`src/metabokg/enrich.py`) — New `enrich_glycans_from_tsv()` phase resolves `gl:G#####` compound nodes using `data/kegg_glycan_names.tsv` (~11 k entries). `EnrichStats` gains a `glycans_from_tsv` field.

- **Phase 2e: KO enzyme name enrichment** (`src/metabokg/enrich.py`) — New `enrich_ko_enzymes_from_tsv()` phase resolves `enz:kegg:K#####` stubs using `data/kegg_ko_names.tsv` (~28 k entries). `EnrichStats` gains a `ko_enzymes_from_tsv` field.

- **Bundled KEGG glycan and KO name files** (`data/kegg_glycan_names.tsv`, `data/kegg_ko_names.tsv`) — Downloaded via the extended `scripts/download_kegg_names.py` and committed to the repo for offline enrichment.

### Fixed

- **Streamlit semantic search returning no results** (`src/metabokg/app.py`) — `_tab_search` was calling `kg.query_pathway()` which filtered all results to `kind == "pathway"`. Switched to `kg.query()` so compound and enzyme hits are surfaced correctly. Search mode (vector / text) is now shown in the result count banner.

- **`enrich_reactions_from_graph` ignoring `quiet` parameter** (`src/metabokg/enrich.py`) — The `quiet` argument was accepted but never used; added `if not quiet:` guards around progress output to match the behaviour of all other enrichment phases.

- **Unused `old_name` variable** (`src/metabokg/enrich.py:enrich_from_tsv`) — Loop variable renamed to `_` since only `node_id` is used in the update path.

### Changed

- **`enrich.py` module docstring** — Expanded to document all 7 enrichment sub-phases (1, 2a–2e, 3) with examples for each namespace, and updated the Public API table to include the three functions that were previously undocumented.

- **`_get_node_label` simplification** (`src/metabokg/app.py`) — Replaced per-kind branching with a single `_BARE_KEGG_ID` regex check (`^[RCG]\d{5}$`); enriched nodes of all kinds now display their human-readable names.

- **Authorship, revision date, and license headers** added to `cmd_query.py`, `cmd_build.py`, `cli/__init__.py`, `cli/options.py`, `metabokg_viz.py`, and `enrich.py` for consistency with the rest of the codebase (`License: Elastic 2.0`).

### Added

- **Per-corpus colocated storage** — `metabokg-build --data <dir>` now places its SQLite database, LanceDB index, and snapshots inside `<dir>/.metabokg/` rather than the project root. The database filename is derived from the data directory prefix (`hsa_pathways` → `hsa.sqlite`, `cge_pathways` → `cge.sqlite`), eliminating ambiguity when multiple organisms are built in the same repo. Mirrors the gutenberg_kg per-book pattern.

- **`resolve_db()` / `resolve_lancedb()` helpers** (`src/metabokg/cli/options.py`) — New module-level functions resolve the effective database/lancedb path via: explicit `--db` arg → `METABOKG_DB` / `METABOKG_LANCEDB` env vars → CWD fallback (`.metabokg/hsa.sqlite`). All CLI commands now call these instead of relying on Click option defaults.

### Changed

- **Default database name changed** from legacy `meta.sqlite` (carryover from the old `meta_kg` module name) to organism-prefixed names (`hsa.sqlite`, `cge.sqlite`). All source, documentation, and configuration references updated. The project-root `.metabokg/` directory has been removed; corpora now live under their respective data directories.

- **`.gitignore`** — Replaced blanket `.metabokg/` ignore with specific artifact ignores (`**/.metabokg/*.sqlite`, `**/.metabokg/lancedb/`) so that snapshot JSON files within `**/.metabokg/snapshots/` are tracked by git.

- **`check-added-large-files` pre-commit exclude** — Extended pattern from `^data/kegg_.*\.tsv$` to `^data/.*\.(tsv|kgml)$`, covering organism gene name TSVs (`hsa_gene_names.tsv`, `cge_gene_names.tsv`) and all KGML pathway files which exceed the 1 MB limit.

### Added

- **CHO (*Cricetulus griseus*) pathway graph** (`data/cge_pathways/`) — 366 KGML pathway files downloaded from KEGG for the `cge` organism code (Chinese hamster, the species underlying CHO cell lines). Build yields 16,930 nodes (366 pathways, 2,099 reactions, 5,105 compounds, 9,360 enzymes) and 39,731 edges.

- **Phase 3 enzyme name enrichment** (`src/metabokg/enrich.py`) — New `enrich_enzyme_names(store, data_dir)` function resolves bare KEGG gene IDs (pure integers) and KEGG ortholog IDs (`K\d{5}`) to gene symbols at build time. Detects organisms automatically from enzyme node IDs (`enz:kegg:{org}:{id}`), loads `data/{org}_gene_names.tsv`, and updates names in-place. Also handles truncated KGML names ending in `...` and `CDS` placeholders. `EnrichStats` gains `enzymes_from_tsv` field; `enrich()` runs Phase 3 automatically after Phase 2. Enables `--knockout Ldha` and `resolve_id("Ldha")` to work without manual SQL.

- **`scripts/download_kegg_names.py --genes ORG ...`** — Extended with `download_gene_names()` function and `--genes` CLI argument. Downloads per-organism KEGG gene lists (`data/{org}_gene_names.tsv`) from `https://rest.kegg.jp/list/{org}`. Required before Phase 3 enrichment runs.

- **`metabokg-simulate seed-cho` command** (`src/metabokg/cli/cmd_simulate.py`) — New CLI subcommand that seeds 35 CHO-specific kinetic parameters across 6 pathways (glycolysis, TCA, oxidative phosphorylation, glutaminolysis, amino acid metabolism, anaplerosis/PPP) at pH 7.2, 37°C from published CHO bioreactor literature (Ahn & Antoniewicz 2011; Zagari et al. 2013; Templeton et al. 2013). Writes 46 kinetic parameter rows and 15 regulatory interactions. Supports `--force` to overwrite.

- **`scripts/fetch_sabio_cho_kinetics.py`** — New script to fetch all *Cricetulus griseus* kinetic law entries from SABIO-RK REST API. Returns SBML Level 3 XML; parser strips namespaces for version-agnostic parsing and resolves enzyme names from `listOfSpecies` via `ENZ_*` modifier references. Writes TSV with Km, kcat, Vmax, Ki values. Result: 91 entries → 268 measured parameters.

- **`docs/cho_workflow.md`** — End-to-end CHO metabolic knowledge graph build workflow documenting all 5 steps: KEGG name download, pathway KGML download, graph build, kinetics seeding, simulation. Includes multi-corpus KGRAG convention and data gaps section.

- **CHO simulation outputs** (`cho_glycolysis_fba.md`, `cho_ldh_knockout.md`) — FBA and LDH-knockout what-if results from the native `cge00010` CHO pathway graph (objective 191.043; lactate flux drops from −1000 to 0 on `Ldha` knockout).

### Changed

- **CLAUDE.md** — Added Multi-Corpus Convention section documenting separate `.sqlite` databases per organism for KGRAG federation (`metabokg-hsa`, `metabokg-cge`, `metabokg-icho`). Corrected `codekg` references to `pycodekg`.

- **`outreach/betenbaugh_jhmi_outreach.md`** — Updated with real CHO graph statistics (16,930 nodes, 39,731 edges, 366 pathways, 9,360 enzymes), 35-reaction kinetics coverage, and SABIO-RK experimental data section (91 entries, 268 parameters).

### Fixed

- **SABIO-RK organism query** (`scripts/fetch_sabio_cho_kinetics.py`) — `"Chinese hamster"` returns 0 results; fixed to `'Organism:"Cricetulus griseus"'` (91 entries).

- **SABIO-RK entry ID XML format** — API returns `<SabioEntryIDs><SabioEntryID>14351</SabioEntryID>...`; script now parses with regex instead of expecting newline-delimited plain text.

- **SBML namespace stripping** — Parser previously hardcoded SBML Level 2 namespace; rewrote with `_strip_ns()` to handle any SBML level/version.

- **Gene name TSV column** (`src/metabokg/enrich.py`) — KEGG 4-column gene list has `CDS` in column 1 and the gene symbol in the last column; parser now uses `row[-1]` instead of `row[1]`.

### Added

- **`metabokg install-hooks` command** (`src/metabokg/cli/cmd_hooks.py`) — New CLI command that installs a unified pre-commit git hook. The hook delegates to `.pre-commit-config.yaml` for quality checks (ruff, mypy, detect-secrets), rebuilds the CodeKG index, then captures snapshots for CodeKG, MetaboKG, and DocKG (the latter two only when their databases are present), staging all snapshot directories atomically. Skip with `CODEKG_SKIP_SNAPSHOT=1 git commit`.

- **Snapshot auto-version detection** (`src/metabokg/snapshots.py`) — `SnapshotManager.capture()` now detects the installed package version via `importlib.metadata` when `version=None` is passed, eliminating the fragile `pyproject.toml` grep that was previously done in the hook script. `Snapshot.version` is backward-compatible (defaults to `""` for legacy snapshots).

- **Analysis report** (`metabokg-analysis-2026-03-18-002618.md`) — Full 7-phase metabolic network analysis report: 369 pathways, 17,050 nodes, 40,166 edges; hub metabolites, complex reactions, cross-pathway junctions, coupling patterns, and network health summary.

- **Pre-commit refactor notes** (`pre-commit-refactor.md`) — Developer document describing all changes across `Metabo_kg`, `code_kg`, and `doc_kg` in this refactor.

### Changed

- **`metabokg build` `--wipe` default flipped** (`src/metabokg/cli/options.py`, `src/metabokg/cli/cmd_build.py`) — Default is now to keep existing data; use `--wipe` to wipe before building. Aligns with `codekg build` behavior. The previous `--no-wipe` opt-out flag has been removed.

- **`.pre-commit-config.yaml` portable and broader excludes** — Poetry entry paths changed from absolute (`/Users/egs/.local/bin/poetry run ...`) to relative (`poetry run ...`) so hooks work in any environment. `check-added-large-files` and `detect-secrets` excludes broadened from `.codekg/` only to `^\.[^/]+/` (all hidden directories), preventing large generated files in `.metabokg/` and `.dockg/` from triggering false positives.

- **`snapshot save` VERSION arg now optional** (`src/metabokg/cli/cmd_snapshot.py`) — Version is auto-detected from the installed package; passing it explicitly is no longer required.

### Added

- **Phase 2c reaction name enrichment** (`src/metabokg/enrich.py`) — New `enrich_reactions_from_detail(store, detail_tsv)` function resolves any reactions still carrying bare KEGG IDs (e.g. `R00123`) after Phases 1 and 2b by reading `data/kegg_reaction_detail.tsv`. `EnrichStats` gains `reactions_from_detail` field; `enrich()` runs Phase 2c automatically between Phase 2b and Phase 3. Requires `python scripts/download_kegg_reactions.py` first (~2,147 API calls).

- **`metabokg viz` CLI options** (`src/metabokg/cli/cmd_viz.py`) — `metabokg viz` now accepts `--db`, `--lancedb`, `--port`, and `--no-browser` options via Click, forwarding them to `metabokg_viz.main()`. Previously the Click wrapper had no options and rejected all flags, requiring the cumbersome `-- --db PATH` workaround.

- **`metabokg_viz.main()` keyword arguments** (`src/metabokg/metabokg_viz.py`) — Refactored from argparse-based `sys.argv` parsing to explicit keyword parameters (`db`, `lancedb`, `port`, `no_browser`). Paths are now forwarded to the Streamlit subprocess as `METABOKG_DB` / `METABOKG_LANCEDB` environment variables so `app.py` picks them up correctly at startup.

- **Smart DB path resolution in Streamlit app** (`src/metabokg/app.py`) — New `_resolve_db_path()` helper auto-discovers the `.sqlite` file when a directory is passed (checks `{dir}/.metabokg/hsa.sqlite`, then any `*.sqlite` in `.metabokg/`, then any `*.sqlite` directly). `_load_store()` now catches `sqlite3` errors gracefully and returns `None` instead of crashing. `_get_store()` updates the sidebar path to the resolved file path on first load.

- **`data/kegg_reaction_detail.tsv`** — Downloaded reaction detail file (2,147 entries: name, definition, equation, EC numbers) used by Phase 2c enrichment.

- **`EXAMPLES.md`** — New top-level examples file covering CLI, Python API, simulation, and MCP tool usage across all MetaboKG workflows.

### Changed

- **`metabokg_viz.py` → `metabokg_viz3d.py` rename** — Aligned module names with the `metabokg_` prefix convention (was `metakg_viz.py` / `metakg_viz3d.py`).

- **CLAUDE.md** — Updated `/codekg-rebuild` references to `/pycodekg-rebuild`.

- **`.claude/commands/`** — Renamed `codekg.md` → `pycodekg.md` and `codekg-rebuild.md` → `pycodekg-rebuild.md`; updated all internal references.

- **`docs/WORKFLOW.md`** — Added Phase 0 covering all three KEGG download scripts in correct order, updated Phase 2 to document the full 4-phase enrichment pipeline, added multi-corpus build section, noted `--db` on viz/viz3d commands.

- **`docs/CAPABILITIES.md`** — Bumped version to v0.5.0; rewrote enrichment section to cover all 4 phases including Phase 2c; updated CLI reference with `viz --db` options.

### Fixed

---

## [0.3.0] - 2026-03-06

### Added

- **Pathway category provenance** (`src/metabokg/primitives.py`) — New `category` field on `MetaNode` and 8 `PATHWAY_CATEGORY_*` constants (`metabolic`, `transport`, `genetic_info_processing`, `signaling`, `cellular_process`, `organismal_system`, `human_disease`, `drug_development`), derived from the 5-digit KEGG numeric suffix via `_kegg_pathway_category()`. All 369 human pathways are categorized after a fresh build.

- **Category persistence in SQLite** (`src/metabokg/store.py`) — `category TEXT` column added to `meta_nodes` schema. `_migrate()` runs on every open and transparently adds the column to existing databases via `ALTER TABLE`. `all_nodes()` now accepts an optional `category=` filter alongside the existing `kind=` filter.

- **Category set in KGML parser** (`src/metabokg/parsers/kgml.py`) — `_kegg_pathway_category()` is called when constructing each pathway `MetaNode` so category is populated at parse time.

- **Strategy C enzyme wiring** (`src/metabokg/parsers/kgml.py`) — New fallback wiring strategy reads the `reaction=` attribute on gene/ortholog `<entry>` elements to link enzymes to reactions when Strategies A and B fail. Eliminates the last class of unwired enzymes in real KEGG KGML files.

- **CONTAINS fallback for isolated nodes** (`src/metabokg/parsers/kgml.py`) — Gene, ortholog, and compound entries that are not wired into any reaction are now connected to their pathway node via `CONTAINS` edges, reducing isolated node count from 12,245 → 0.

- **Agent slash commands** — New `.claude/commands/` entries (`metabokg-build.md`, `metabokg-simulate.md`, `metabokg-viz.md`) and matching `.vscode/*.prompt.md` prompt files for all core MetaboKG and CodeKG workflows.

- **`SESSION-NOTES-2026-03-06.md`** — Handoff document summarising all changes made in this session for the next agent/developer.

### Changed

- **Enrichment default-on** (`src/metabokg/cli/cmd_build.py`, `src/metabokg/orchestrator.py`) — `--enrich` flag renamed to `--no-enrich` (inverted logic). Enrichment now runs by default on both `metabokg-build` and `metabokg-update`. `MetaKG.build(enrich=False)` default changed to `True`.

- **CLAUDE.md updated** — CodeKG Commands section reverted to `codekg-*` standalone command style; Typical Workflow section updated to invoke commands directly (no `poetry run` prefix needed in activated venv).

### Fixed

- **`all_nodes()` category filter** (`src/metabokg/store.py`) — Query now builds WHERE clause dynamically to support combined `kind` + `category` filtering without SQL injection risk.

---

### Changed

- **`metabokg-build` default behavior** — Now wipes existing database and vector index by default (safer, more predictable). Use `--no-wipe` flag to add files incrementally instead of replacing.
  - Renamed `--wipe` flag → `--no-wipe` (inverted logic, default=True)
  - Updated docstring to clarify wipe-by-default behavior
  - Updated all documentation (CLAUDE.md, README.md, WORKFLOW.md) to reflect new defaults
- **New `metabokg-update` command** (`src/metabokg/cli/cmd_build.py`) — Convenience alias for `metabokg-build --no-wipe`. Provides explicit intent: incrementally merge new pathway files into an existing database without wiping. Supports the same enrichment and kinetics-seeding options as `build`.
- **CLI option definition refactored** (`src/metabokg/cli/options.py`) — `wipe_option` now uses Click's `flag_value=False, default=True` pattern for better clarity in inverted flags.

### Added

- **Enhanced 3D visualization CLI options** (`src/metabokg/cli/cmd_viz3d.py`) — `metabokg-viz3d` now supports:
  - `--layout {allium|cake}` — Select spatial layout strategy (Hub-spoke Allium vs concentric LayerCake)
  - `--width` / `--height` — Configure window dimensions (1400x900 default)
  - `--export-html PATH` / `--export-png PATH` — Batch export to file instead of interactive window
  - Improved error handling: check database existence before launching visualizer

- **Improved Fibonacci disk layout algorithm** (`src/metabokg/layout3d.py`) — Renamed `_golden_spiral_2d()` → `fibonacci_disk()` for clarity; enhanced docstrings. Tuned LayerCake parameters: layer gap 12→6 (tighter), disc radius 28→35 (wider), minimum spread 4→20 (prevent clamping on small pathways). Enzyme nodes moved to Z-level 3 (separate from compounds).

- **3D Visualization Documentation** (`CLAUDE.md`) — New section covering layout modes, in-UI controls (pathway filter, layout selector, visibility toggles), and recommended workflow.

- **Data Download Scripts Reference** (`CLAUDE.md`) — Documented all three KEGG download scripts with options and output formats. Clarified single-step vs multi-step enrichment pipelines.

- **`scripts/download_kegg_reactions.py`** — New script for bulk downloading KEGG reaction details (name, definition, equation, EC numbers). Supports scanning local KGML files for reaction IDs (faster) or querying KEGG link endpoint. Output: `data/kegg_reaction_detail.tsv`.

- **MetaboKG Architecture Article** (`article/metabokg_article.md`) — Comprehensive article explaining dual-layer architecture (SQLite + LanceDB), four query modalities, and comparison with existing systems (KEGG, BioCyc, Reactome, etc.).

- **Architecture Infographic Guide** (`article/metabokg_architecture_infographic.md`) — Visual walkthrough of system components and data flow.

- **`metabokg` unified CLI entry point** (`pyproject.toml`, `src/metabokg/cli/main.py`) — New top-level `metabokg` command registered as a `@click.group()` with `--version` support. All subcommands (`build`, `enrich`, `analyze`, `analyze-basic`, `simulate`, `mcp`, `viz`, `viz3d`) are accessible as `metabokg <subcommand>` in addition to the existing standalone `metabokg-*` aliases.

- **`docs/INSTALL.md`** — New comprehensive step-by-step installation guide covering all install variants (core, simulate, viz, viz3d, biopax, all-extras), pathway data download, graph build, name enrichment, kinetics seeding, MCP server startup, web explorer, 3D visualizer, dev install, environment variables, upgrading, and troubleshooting.

- **`docs/MCP.md`** — New guide for integrating the CodeKG MCP server with Claude Code, Claude Desktop, GitHub Copilot, and Cline; covers quick-start, per-repo `.mcp.json` / `.vscode/mcp.json` configuration, and available MCP tools.

### Changed

- **CLI refactored from monolithic `cli.py` to `cli/` package** (`src/metabokg/cli/`) — The 642-line `src/metabokg/cli.py` has been replaced by a proper package where each command group lives in its own module. All existing entry-point names and CLI behaviour are preserved.
  - `cli/__init__.py` — re-exports the root `cli` group and all standalone entry-point aliases
  - `cli/main.py` — root `@click.group()` with `--version`
  - `cli/options.py` — shared reusable Click option decorators (`db_option`, `lancedb_option`, `model_option`, `wipe_option`, `data_option`)
  - `cli/_utils.py` — shared helpers: `_timestamped_filename()`, `_parse_conc_args()`, `_parse_factor_args()`, `_write_output()`
  - `cli/cmd_analyze.py` — `metabokg analyze` / `metabokg analyze-basic`
  - `cli/cmd_build.py` — `metabokg build` / `metabokg enrich`
  - `cli/cmd_mcp.py` — `metabokg mcp`
  - `cli/cmd_simulate.py` — `metabokg simulate {fba,ode,whatif,seed}`
  - `cli/cmd_viz.py` — `metabokg viz`
  - `cli/cmd_viz3d.py` — `metabokg viz3d`

- **`mcp` promoted to core dependency** (`pyproject.toml`) — `mcp >= 1.0.0` moved from the optional `[mcp]` extra to the core dependency list; the MCP server is now always available without extra install flags. The `[mcp]` extra has been removed; `[viz3d]` and `[all]` extras updated accordingly. `param` optional dependency removed (no longer needed).

- **`mcp_tools.py` import guard removed** — Defensive `try/except ImportError` around `FastMCP` import eliminated now that `mcp` is a core dependency.

- **`docs/CAPABILITIES.md` dependency tables updated** — `mcp` moved to core dependencies table; `[mcp]` extra row removed; `[viz3d]` extra updated with pinned minimum versions (`pyvista >= 0.44.0`, `pyvistaqt >= 0.11.0`, `PyQt5 >= 5.15.0`); install examples updated to reflect new extras layout; link to `docs/INSTALL.md` added.

### Added

- **Name enrichment pipeline** (`src/metabokg/enrich.py`) — New module that replaces bare KEGG accessions (`C00031`, `R00710`) with human-readable names stored directly in `meta_nodes.name`. Phase 1 (no network): derives reaction labels from catalysing enzyme gene symbols via `CATALYZES` edges (e.g. `R00710` → `ADH1A / ADH1B / ADH1C`). Phase 2 (requires TSV files): updates compound and reaction names from downloaded KEGG name lists. Both phases are idempotent.

- **`metabokg-enrich` CLI command** (`src/metabokg/cli.py`, `pyproject.toml`) — Standalone Click command for running name enrichment against an existing database: `metabokg-enrich [--db PATH] [--data DIR]`. Also integrated as `--enrich` / `--enrich-data` flags on `metabokg-build` for a single-step build+enrich workflow.

- **`scripts/download_kegg_names.py`** — New bulk-download script that fetches the KEGG compound list (~19 500 entries) and reaction list (~12 400 entries) from `rest.kegg.jp/list/` and saves them as `data/kegg_compound_names.tsv` / `data/kegg_reaction_names.tsv`. Supports `--data DIR`, `--force`, `--quiet`; includes 1-second courtesy pause between requests per KEGG policy.

- **`data/kegg_compound_names.tsv` / `data/kegg_reaction_names.tsv`** — Bulk KEGG name lookup tables (19 571 compounds, 12 384 reactions) committed to the repository; used by `metabokg-enrich` Phase 2 and available for offline enrichment without re-downloading.

- **`MetaKG.enrich()` public method** (`src/metabokg/orchestrator.py`) — Exposes enrichment via the high-level orchestrator: `kg.enrich(data_dir=None) → EnrichStats`. `build()` gains `enrich=False` and `enrich_data_dir=None` parameters.

### Changed

- **CLI fully migrated from argparse to Click** (`src/metabokg/cli.py`) — All CLI commands rewritten with Click decorators (`@click.command`, `@click.group`, `@click.option`). `metabokg-simulate` is now a `@click.group()` with shared `--db/--output/--plain/--top` options passed via `ctx.obj` to `fba`, `ode`, `whatif`, and `seed` subcommands. Error handling uses `raise click.ClickException(msg)` and `click.echo(..., err=True)`. Every command and subcommand now supports `--help` automatically. `click >= 8.0` added as a core dependency.

- **`docs/CAPABILITIES.md` updated to v0.2.0** — Added §5 (Name Enrichment) covering both enrichment phases, download script, CLI, and Python API. Updated ODE solver documentation from RK45 to BDF throughout with stiffness warning. Added `ode_method`, `ode_rtol`, `ode_atol`, `ode_max_step` fields to `SimulationConfig` reference. Added `click`, `matplotlib`, and `pandas` to dependency tables. Added `metabokg-enrich` to CLI reference.

- **Optional viz dependencies expanded** (`pyproject.toml`) — `matplotlib >= 3.8.0` and `pandas >= 2.0.0` added as optional dependencies, included in the `[viz]` and `[all]` extras.

### Fixed

- **SQLite threading error in Streamlit** (`src/metabokg/store.py`) — `sqlite3.connect()` now passes `check_same_thread=False`, resolving "SQLite objects created in a thread can only be used in that same thread" errors that occurred when the Streamlit app cached a connection via `@st.cache_resource` and served requests from worker threads.

### Changed

- **`store.query_semantic()` renamed to `query_text()`** (`src/metabokg/store.py`, `src/metabokg/app.py`) — Method renamed to accurately reflect that it performs a text-based substring match, not a true semantic/vector search; semantic search remains in `MetaIndex`. Docstring updated to clarify the distinction and direct users to `MetaIndex` for embedding-based queries.

- **CLI `simulate_main()` uses `MetaKG` orchestrator** (`src/metabokg/cli.py`) — `seed`, `fba`, `ode`, and `whatif` subcommands now instantiate `MetaKG` via `with MetaKG(db_path=...) as kg:` instead of directly importing `MetaStore` and `MetabolicSimulator`. Brings CLI in line with the public API surface.

- **MCP tool handlers extracted to module-level functions** (`src/metabokg/mcp_tools.py`) — All per-tool logic moved from closures inside `register_tools()` to standalone `_mcp_*()` functions at module level, making them unit-testable without a live FastMCP instance. `register_tools()` now delegates to these functions and copies docstrings for MCP schema generation.

- **WORKFLOW.md updated for `wire_kegg_enzymes.py`** — References to the old `wire_enzymes.py` replaced; description expanded to cover the scanning/patching approach and `--dry-run` flag.

### Removed

- **`pathways/` sample KGML files** (`pathways/hsa00010.xml` – `hsa00650.xml`) — 11 hand-authored KGML fixtures removed from version control; real pathway data lives in `data/hsa_pathways/` (not tracked).

- **`scripts/wire_enzymes.py`** — Hardcoded one-shot enzyme wiring script retired; superseded by the more general `scripts/wire_kegg_enzymes.py` (which auto-detects missing enzyme coverage across all KGML files).

### Fixed

- **KGML multi-gene entry grouping** (`src/metabokg/parsers/kgml.py`) — A single KGML `<entry type="gene">` often lists multiple gene IDs (e.g. pyruvate dehydrogenase complex `hsa:5160 hsa:5161 hsa:5162`). The previous parser created one enzyme node per gene but only wired the last-processed gene to its reaction via a CATALYZES edge, leaving all others as orphaned nodes with no edges. Fix: create one canonical group node per entry (keyed on the first gene ID, labelled with KEGG graphics name); all member gene IDs stored as a list in the node's `xrefs` JSON; `entry_map` points to the single node so CATALYZES wiring is correct and complete. Effect across full human KEGG dataset: ~1,797 fewer enzyme nodes, CATALYZES edge count unchanged at 4,165, ~5,255 previously orphaned enzyme nodes eliminated.

- **xref index expansion for list-valued entries** (`src/metabokg/store.py` — `MetaStore.build_xref_index`) — Updated to expand list-valued xref entries into individual `xref_index` rows. Each member gene ID in a group node gets its own row pointing to the canonical group node, so per-gene lookup works transparently. Example: group node `enz:kegg:5160` with `xrefs={"kegg": ["5160","5161","5162"]}` produces three `xref_index` rows.

### Added

- **`scripts/wire_kegg_enzymes.py`** — Analysis and patching utility that scans KGML files for reaction elements missing enzyme coverage (not handled by Strategy A or B) and patches them with `enzyme="N"` attributes. Confirmed that all 4,165 reaction elements in the full human KEGG dataset are fully covered by Strategy B; patching is only needed for hand-authored sample files.

- **`metabokg-analyze-basic` CLI entry point** — New `analyze_basic_main()` in `cli.py` exposing the original structured (non-narrative) analysis report as a separate command, preserving both report styles
- **Timestamped output filenames** — `metabokg-analyze`, `metabokg-analyze-basic`, and `metabokg-simulate` now write to auto-named files (e.g., `metabokg-analysis-2026-03-03-143022.md`) when `--output` is not specified, eliminating silent stdout dumps
- **`code-kg` core dependency** — Added `code-kg` as a production dependency in `pyproject.toml` (git source: Flux-Frontiers/code_kg); codekg CLI scripts now come from that package directly rather than being re-declared here
- **Revised article abstract** (`article/metabokg_revised.tex`) — Rewritten to lead with architectural innovation (dual-layer SQLite + LanceDB), emphasise all four query modalities plus simulation and visualisation capabilities, and highlight the complete human metabolome ingestion; format parsing demoted to supporting infrastructure

### Changed

- **`metabokg-analyze` always writes to file** — Removed stdout fallback; output path is either the `--output` argument or a timestamped default; mirrors `metabokg-simulate` behaviour
- **CLAUDE.md refactored** — Condensed from ~600 lines to ~120-line table-driven quick reference; removed redundant prose, kept command tables, simulation examples, and CodeKG query strategy
- **`pyproject.toml` scripts cleaned up** — Removed duplicate `codekg-*` script entries (now provided by the `code-kg` package); added `metabokg-analyze-basic` entry point
- **`.codekg/lancedb` untracked from git** — Removed regenerable LanceDB vector index files from version control; `.gitignore` entry already present; index can be rebuilt with `/codekg-rebuild`
- **Analysis report title** (`src/metabokg/analyze.py`) — Changed from `"MetaboKG Pathway Analysis Report"` to `"metabokg_analysis"` for cleaner file naming

### Removed

- **`codekg-*` script declarations from `pyproject.toml`** — Scripts are now provided by the `code-kg` dependency package; no functional change for users

- **Polished MetaboKG Thorough Analysis Report** — New `src/metabokg/thorough_analysis.py` module providing CodeKG-style formatted analysis output
  - Executive Summary with 5-minute KPI overview
  - Emoji-enhanced section headers (📊 📈 🔥 ⚡ 🔗 📦 🧬 🧪 ⚠️ ✅ 💡)
  - Risk level indicators (🟢 LOW 🟡 MED 🔴 HIGH) for metabolite hubs and complex reactions
  - Network Health Issues section identifying data quality signals
  - Metabolic Network Strengths section highlighting well-designed patterns
  - Structured Biological Insights & Recommendations with 3-tier action plan (Immediate, Medium-term, Long-term)
  - Full Appendix with complete isolated nodes and dead-end metabolite lists
  - Seamless CLI integration: `metabokg-analyze` now generates the polished report

- **Claude Slash Command** — New `.claude/commands/metabokg-analyze.md` for quick pathway analysis invocation with `/metabokg-analyze`

### Changed

- **`metabokg-analyze` CLI Command** — Updated `src/metabokg/cli.py:analyze_main()` to use new `render_thorough_report()` from `thorough_analysis.py`
  - Same CLI interface and flags (`--db`, `--output`, `--top`, `--plain`)
  - Richer Markdown output with polished sections and emoji headers
  - Backward compatible: plain-text mode (`--plain`) still works

- **MetaboKG Thorough Analysis Skill** — Updated `.claude/skills/metabokg-thorough-analysis/SKILL.md` Python API section to import and use `render_thorough_report()`

### Removed

### Fixed

- **Name enrichment Phase 2 now loads canonical KEGG reaction names** (`src/metabokg/enrich.py`) — The enrichment pipeline had an architectural flaw: Phase 1 would rename reactions from bare accessions (e.g., `R00710`) to gene symbols (e.g., `ADH1A / ADH1B / ADH1C`), then Phase 2 would skip them because it only recognized bare accessions, preventing 1,771 canonical KEGG reaction function names from ever being loaded. Fixed by extracting the KEGG accession directly from the immutable node ID (format: `rxn:kegg:R00710`) instead of relying on the volatile `name` field. This implements the intended **dual-layer design**: Phase 2 now always overrides Phase 1, ensuring canonical structural names take priority over enriched gene labels. Phase 1 names are preserved only when no canonical KEGG name exists. Result: 1,771 additional reaction names now loaded (was 0 before). Example: `R00710` now displays as `"acetaldehyde:NAD+ oxidoreductase"` instead of gene symbols.

- **3D visualization now displays KEGG reaction function names in enzyme sidebar** (`src/metabokg/viz3d.py`) — When picking an enzyme node, the sidebar now shows the reactions it catalyzes with their canonical KEGG function names (e.g., `"alcohol dehydrogenase (NAD+)"`, `"3-ketosteroid 1-dehydrogenase"`). This is now possible thanks to the enrichment fix above. Changes: (1) Load KEGG reaction names TSV at startup (lines 154–173), (2) Update enzyme display to show catalyzed reactions with KEGG function names (lines 252–280), (3) Gracefully fallback to bare accession if no KEGG name available, (4) Clarify labels: `"Enzyme"` → `"Gene symbol"` for clarity. This fixes the user request: instead of bare gene symbols like `ADH1A`, the sidebar now describes what each enzyme does.

- **Pylint configuration and test fixture naming** (`.pylintrc`, `tests/test_simulation.py`) — Created `.pylintrc` with proper configuration for the codebase; fixed unrecognized `max-lines` option (changed to `max-module-lines`). Renamed fixture `kg_with_minimal_pathway` to `kkg_with_minimal_pathway` to eliminate false pylint `redefined-outer-name` warnings in pytest test functions.

## [0.2.0] - 2026-02-28

### Added

- **Comprehensive Metabolic Simulation Documentation** — Expanded CLI reference, API guide, and scientific article with complete examples for all three simulation modalities
  - CLAUDE.md: New "Simulation and Analysis" section with detailed examples for FBA, kinetic ODE integration, and what-if perturbation analysis
  - README.md: New "Metabolic Simulations" section with runnable code examples and ODE solver configuration guide
  - article/metabokg.tex: New "Metabolic Simulations" subsection explaining solver architecture and parameter seeding
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
  - Exported in `metabokg` module for public use

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
  - Fixed import ordering in `scripts/simulation_demo.py`, `src/metabokg/orchestrator.py`, and `tests/test_orchestrator.py` to comply with Ruff I001
  - Removed f-string prefixes from non-placeholder strings in `scripts/simulation_demo.py` (Ruff F541)
  - Removed unused imports (`tempfile`, `pathlib.Path`) from `tests/test_orchestrator.py`
  - All changes pass Ruff linting and mypy type checking

- **Critical Namespace Shadowing Bug** — `src/metabokg/metabokg.py` was shadowing the metabokg package namespace, preventing imports of submodules like `graph.py` and breaking all CLI commands. Resolved by renaming to `orchestrator.py` and updating all import statements.

### Added

- **Consistent Project Badges** — Enhanced README with project status badges matching CodeKG style
  - Python version badge showing supported versions (3.10, 3.11, 3.12)
  - Version badge (0.1.0) with link to releases
  - Poetry dependency manager badge
  - Updated license badge for Elastic License 2.0

- **CodeKG Sister Project Reference** — Added prominent reference to CodeKG in README
  - Sister Project section highlighting CodeKG's role in enabling semantic analysis of MetaboKG's own codebase
  - Added CodeKG to Acknowledgments section as primary enabling technology

- **Architecture Diagram in README** — Integrated visual architecture diagram (`docs/metaKG_arch.png`) into the Architecture section
  - Provides quick visual overview of system components and organization
  - Complements detailed file structure documentation

- **CodeKG Integration for Codebase Analysis** — MetaboKG can now be analyzed using CodeKG's knowledge graph tools
  - Built static analysis graph (SQLite): 3,136 nodes, 2,920 edges across 27 modules
  - Built semantic vector index (LanceDB): 290 vectors with 384-dimensional embeddings
  - Configured MCP servers for Claude Code, GitHub Copilot, Kilo Code, and Cline
  - Enables tools like `query_codebase`, `pack_snippets`, `callers` for code exploration

- **Comprehensive CLI Documentation** — Added `CLAUDE.md` with complete reference for both MetaboKG and CodeKG commands
  - MetaboKG commands: `metabokg-build`, `metabokg-analyze`, `metabokg-viz`, `metabokg-viz3d`, `metabokg-mcp`
  - CodeKG commands: `codekg-build-sqlite`, `codekg-build-lancedb`, `codekg-query`, `codekg-mcp`
  - MCP tool documentation with usage examples and query strategies
  - Typical workflows and combined MetaboKG + CodeKG usage patterns
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

- **Layout Algorithms** (`src/metabokg/layout3d.py`)
  - Fibonacci spatial utilities for uniform point distribution on spheres and annuli
  - AlliumLayout class for plant-inspired botanical visualization
  - LayerCakeLayout class for stratified hierarchical visualization
  - Extensible Layout3D abstract base class for custom layout implementations

- **CLI Commands**
  - `metabokg-viz` — Launch Streamlit web explorer with database and port configuration
  - `metabokg-viz3d` — Launch 3D PyVista visualizer with layout and export options

- **GraphStore Wrapper** (`src/metabokg/store.py`)
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

- **Orchestrator Class** — Renamed `MetaKG` source file from `metabokg.py` to `orchestrator.py` for clarity and to eliminate namespace shadowing
- **Import Paths** — Updated all references from `metabokg.metabokg` to `metabokg.orchestrator` in `__init__.py`, `mcp_tools.py`, and `app.py`
- **pyproject.toml** — Added optional visualization dependencies and `viz` + `viz3d` extras, plus CodeKG CLI entry points
- **src/metabokg/cli.py** — Added `viz_main()` and `viz3d_main()` entry points for new CLI commands
- **src/metabokg/store.py** — Extended with GraphStore compatibility wrapper class

### Technical Details

- **Visualization Scope** — Adapted from flux-frontiers/code_kg with metabolic pathway domain-specific customizations
- **Node Types** — Supports compound, reaction, enzyme, and pathway nodes
- **Edge Relations** — SUBSTRATE_OF, PRODUCT_OF, CATALYZES, INHIBITS, ACTIVATES, CONTAINS, XREF
- **Embedding Model** — Integrates with sentence-transformers via LanceDB for semantic search
- **Database** — SQLite persistence with indexed queries for graph operations

## [0.1.0] — 2024-02-27

### Added

- Initial standalone MetaboKG package release
- Metabolic pathway parser supporting KGML, SBML, BioPAX, and CSV formats
- Semantic knowledge graph with LanceDB vector indexing
- MCP (Model Context Protocol) server integration
- Core CLI: `metabokg-build` and `metabokg-mcp` commands
- SQLite-based graph persistence layer
- Cross-reference resolution and pathway unification

---

[Unreleased]: https://github.com/flux-frontiers/metabo_kg/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/flux-frontiers/metabo_kg/releases/tag/v0.1.0
