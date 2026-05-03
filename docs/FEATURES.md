# MetaboKG — Knowledge Graph Features

**Last updated:** 2026-04-21

Three corpora are bundled and ready to build. Each targets a different level of
metabolic resolution: curated human pathways, CHO-organism pathways, and a
genome-scale stoichiometric model.

---

## Corpus Overview

| Corpus | Organism | Source | Pathways | Reactions | Compounds | Enzymes | Nodes | Edges | Vectors |
|--------|----------|--------|:--------:|:---------:|:---------:|:-------:|------:|------:|--------:|
| `metabokg-hsa` | *Homo sapiens* | KEGG KGML | 369 | 2,139 | 5,115 | 9,427 | 17,050 | 40,166 | 7,623 |
| `metabokg-cge` | *Cricetulus griseus* (CHO) | KEGG KGML | 366 | 2,099 | 5,105 | 9,360 | 16,930 | 39,731 | 7,570 |
| `metabokg-icho` | CHO (iCHO2441 GEM) | SBML / BioModels | 1 | 6,337 | 4,174 | 2,441 | 12,953 | 41,437 | 10,512 |

---

## Human Pathways (`metabokg-hsa`)

**Source:** 369 KEGG KGML files for *Homo sapiens* (`hsa`) — curated, pathway-structured.

**Coverage:**

| Kind | Count |
|------|------:|
| Pathways | 369 |
| Reactions | 2,139 |
| Compounds | 5,115 |
| Enzymes | 9,427 |
| **Total nodes** | **17,050** |
| CATALYZES edges | 2,394 |
| CONTAINS edges | 32,689 |
| SUBSTRATE\_OF / PRODUCT\_OF | 5,083 |
| **Total edges** | **40,166** |
| Vectors (dim=384) | 7,623 |

**Enrichment:**
- Compound names: canonical KEGG names from `kegg_compound_names.tsv`
- Reaction names: from graph CATALYZES edges + `kegg_reaction_names.tsv`
- Glycan names: from `kegg_glycan_names.tsv`
- KO enzyme names: from `kegg_ko_names.tsv`

**Simulations supported:** FBA, ODE (BDF solver), what-if (enzyme knockouts by gene symbol)

**Build:**
```bash
metabokg-build --data data/hsa_pathways
```

---

## CHO Pathways (`metabokg-cge`)

**Source:** 366 KEGG KGML files for *Cricetulus griseus* (`cge`) — same pathway
structure as human but with CHO-specific enzyme gene assignments.

**Coverage:**

| Kind | Count |
|------|------:|
| Pathways | 366 |
| Reactions | 2,099 |
| Compounds | 5,105 |
| Enzymes | 9,360 |
| **Total nodes** | **16,930** |
| CATALYZES edges | 2,319 |
| CONTAINS edges | 32,413 |
| SUBSTRATE\_OF / PRODUCT\_OF | 4,999 |
| **Total edges** | **39,731** |
| Vectors (dim=384) | 7,570 |

**Enrichment:**
- Compound / reaction names: same KEGG TSVs as human
- Enzyme names: CHO gene symbols from `cge_gene_names.tsv` (e.g. `Ldha`, `Pkm`)

**Key advantage over human:** CHO-specific enzyme assignments enable `--knockout`
by CHO gene symbol directly:
```bash
metabokg-simulate whatif --pathway cge00010 --knockout Ldha
```

**Simulations supported:** FBA, ODE (BDF solver), what-if

**Build:**
```bash
metabokg-build --data data/cge_pathways
```

---

## iCHO2441 Genome-Scale Model (`metabokg-icho`)

**Source:** iCHO2441 SBML (BioModels `MODEL2206100001`, Hefzi et al. 2016),
the most comprehensive consensus CHO genome-scale metabolic model.
The published model encodes 6,663 reactions across all subcellular compartments using
**SBML Level 3 + FBC v2** (flux balance constraints package).
MetaboKG parses 6,337 reactions (exchange/boundary reactions with no internal metabolites
are excluded during SBML ingestion).

**Coverage:**

| Kind | Count |
|------|------:|
| Pathways | 1 (whole model) |
| Reactions | 6,337 |
| Compounds | 4,174 |
| Enzymes (FBC gene products) | 2,441 |
| **Total nodes** | **12,953** |
| CATALYZES edges | 9,796 |
| CONTAINS edges | 6,337 |
| SUBSTRATE\_OF / PRODUCT\_OF | 25,304 |
| **Total edges** | **41,437** |
| Vectors (dim=384) | 10,512 |
| Xref rows (gene IDs) | 2,441 |

**Enrichment:**
- Compound and reaction names come directly from SBML `name` attributes — already
  human-readable; no KEGG TSV enrichment needed or possible (no KEGG xrefs in the SBML).
- Enzyme gene symbols: 1,942 / 2,441 (80%) resolved from `cge_gene_names.tsv` by
  matching the Entrez gene ID stored in each enzyme node's `xrefs` JSON. The
  remaining 499 are CHO genes with no formal symbol in the KEGG CGE database.

**Key differences from KGML pathways:**

| Feature | KGML (hsa / cge) | iCHO2441 (SBML/FBC) |
|---|---|---|
| Pathway structure | 300–400 curated maps | Single whole-model pathway |
| Reaction count | ~2,100 | 6,337 |
| Gene–reaction links | `listOfModifiers` → CATALYZES | `fbc:geneProductAssociation` → CATALYZES |
| Stoichiometry | Partial | Complete (all reactants/products) |
| Compartments | Implicit | Explicit (cytosol, mitochondria, ER, …) |
| Node IDs | `cpd:kegg:…` / `rxn:kegg:…` | `cpd:syn:…` / `rxn:syn:…` (no KEGG xrefs) |
| Simulations | FBA + ODE + what-if | FBA (stoichiometric only; no kinetics) |

**Download and build:**
```bash
python scripts/download_icho_model.py --output data/icho_model
python scripts/download_kegg_names.py --genes cge   # for gene symbol resolution
metabokg-build --data data/icho_model
```

See [docs/icho_workflow.md](docs/icho_workflow.md) for full details.

---

## Simulation Support Matrix

| Feature | hsa | cge | icho |
|---------|:---:|:---:|:----:|
| FBA (flux balance analysis) | ✓ | ✓ | ✓ |
| ODE (kinetic time-course) | ✓ | ✓ | — |
| What-if (enzyme knockout) | ✓ | ✓ | — |
| Knockout by gene symbol | ✓ | ✓ | partial (80% resolved) |
| Semantic search (`metabokg-query`) | ✓ | ✓ | ✓ |
| MCP tools (`metabokg-mcp`) | ✓ | ✓ | ✓ |
| KGRAG federated queries | ✓ | ✓ | ✓ |

ODE and what-if require kinetic parameters. iCHO2441 is a stoichiometric model
only; seed kinetics from literature via `metabokg-simulate seed` if you need
dynamic simulation of specific reactions.

---

## Multi-Corpus Build

```bash
# Human pathways
metabokg-build --data data/hsa_pathways

# CHO pathways
metabokg-build --data data/cge_pathways

# iCHO2441 GEM
python scripts/download_icho_model.py
python scripts/download_kegg_names.py --genes cge hsa
metabokg-build --data data/icho_model
```

DBs colocate automatically with their source data:
- `data/hsa_pathways/.metabokg/hsa.sqlite`
- `data/cge_pathways/.metabokg/cge.sqlite`
- `data/icho_model/.metabokg/icho.sqlite`
