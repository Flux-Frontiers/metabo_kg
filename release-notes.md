# Release Notes — v0.7.0

> Released: 2026-04-24

## Highlights

This release rounds out MetaboKG's multi-corpus story, completes the enrichment pipeline, and makes the system meaningfully more useful as an LLM context source.

### iCHO2441 genome-scale model support
The SBML parser now handles the Flux Balance Constraints v2 (FBC) package used by iCHO2441. It extracts 2,441 enzyme nodes and 9,796 CATALYZES edges from `<fbc:listOfGeneProducts>` and recursively flattens OR/AND gene-association trees. Phase 3 enrichment resolves 80% of those enzymes (1,942 / 2,441) to gene symbols via Entrez IDs stored in `xrefs`.

### KGRAG adapter contract
`MetaKG.stats()` returns a flat `dict` (`node_count`, `total_edges`, `pathway_count`, `compound_count`, `reaction_count`) that satisfies the KGRAG probe status contract. `kgrag probe` can now render a meaningful status row for MetaboKG without invoking the heavier `get_stats()` path. Never raises; returns zeros on store error.

### `MetabolicPack` and `MetaKG.pack()`
A new `pack(text, k=8, hop=1)` method mirrors PyCodeKG's pack API: it runs semantic search + graph expansion and wraps results in a `MetabolicPack` object with full biological context (stoichiometry, enzymes, cross-references). Output via `to_markdown()`, `to_json()`, or `save()`. The `metabokg-pack` CLI command and `pack` MCP tool expose this to the command line and Claude.

### General-purpose `MetaKG.query()`
The previous `query_pathway()` filtered results to pathway nodes only, silently dropping compounds and enzymes. The new `query()` method searches all indexed node kinds. Both the `metabokg query` CLI and the Streamlit Search tab now use it; `query_pathway()` is retained for callers that need pathway-only results.

### Enrichment pipeline completed
The enrichment pipeline now covers seven sub-phases:
- **2c** — reaction names from `kegg_reaction_detail.tsv` (2,147 entries)
- **2d** — glycan names from `kegg_glycan_names.tsv` (~11k entries)
- **2e** — KO enzyme names from `kegg_ko_names.tsv` (~28k entries)

An `xrefs` fallback in Phases 2a/2c enables future SBML files carrying `identifiers.org` KEGG annotations to be enriched without code changes.

### Streamlit app performance
Two `@st.cache_resource` functions now hold the `MetaKG` embedding model and full graph scan in memory across reruns (previously recreated on every interaction). Search results are persisted in `st.session_state`. The Search tab gains k/hops inputs, a PyVis sub-tab, an active-filter count banner, and a node detail panel.

### Pre-commit hooks and snapshots
`metabokg install-hooks` installs a unified pre-commit hook that runs quality checks, rebuilds CodeKG, and captures MetaboKG/DocKG snapshots atomically. `SnapshotManager.capture()` now auto-detects the installed package version via `importlib.metadata` — no more fragile `pyproject.toml` grep.

## Bug fixes

- **BioModels download URL** — fixed from HTML-redirect path to correct REST API path (`/model/download/{ID}`); added XML content check.
- **Gene symbol parsing** — `_load_gene_names_tsv` previously produced multi-word descriptions as spurious symbols; now splits on `;` first and rejects candidates containing spaces or starting with digits.
- **Enrichment Phase 2 ordering** — Phase 2 previously skipped reactions already renamed by Phase 1; now derives the KEGG accession from the immutable node ID, ensuring canonical KEGG names always win. Result: 1,771 additional reaction names now loaded.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
