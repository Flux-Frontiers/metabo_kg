# iCHO2441 Genome-Scale Model — Build Workflow

## Overview

iCHO2441 is the most comprehensive consensus reconstruction of Chinese Hamster
Ovary (CHO) cell metabolism (Hefzi et al. 2016, BioModels `MODEL2206100001`).
It contains 6,663 reactions, 2,441 gene products, and 4,456 metabolites across
subcellular compartments, encoded as **SBML Level 3 with the FBC v2 package**.

This document covers: downloading the model, the FBC-specific parser behaviour,
build results, enrichment state, and known gaps.

---

## 1. Download

```bash
python scripts/download_icho_model.py --output data/icho_model
python scripts/download_icho_model.py --output data/icho_model --force   # re-download
```

The script fetches `iCHO2441.xml` (~6.8 MB) from the BioModels REST API and
validates that the response is XML before writing it. It also prints the SHA
checksums from the BioModels metadata so you can verify integrity.

**Common failure mode:** The old URL pattern (`/{MODEL_ID}/download?filename=…`)
redirects to the BioModels website and returns an HTML page instead of XML.
The current script uses the correct path (`/model/download/{MODEL_ID}?filename=…`)
and will fail fast with a clear error if the response is not XML.

**Reference:**
- BioModels: <https://www.ebi.ac.uk/biomodels/MODEL2206100001>
- Hefzi et al. (2016) *Cell Systems* 3:434–443. PMID:27883890

---

## 2. Build

```bash
metabokg-build --data data/icho_model
```

The DB colocates automatically: `data/icho_model/.metabokg/icho.sqlite`.

### 2a. What the SBML parser does

The iCHO2441 model uses the **SBML Level 3 FBC (Flux Balance Constraints) v2**
package, which differs structurally from both KGML and plain SBML Level 2:

| SBML feature | iCHO2441 format | Parser action |
|---|---|---|
| Metabolites | `<listOfSpecies>` (standard) | → `compound` nodes (`cpd:syn:…`) |
| Reactions | `<listOfReactions>` (standard) | → `reaction` nodes (`rxn:syn:…`) |
| Gene–reaction links | `<fbc:listOfGeneProducts>` + `<fbc:geneProductAssociation>` | → `enzyme` nodes + `CATALYZES` edges |
| Flux bounds | FBC attributes on each reaction | (ignored — used for FBA, not graph) |

Because iCHO2441 has **no `identifiers.org` annotations** on its species or
reactions, all nodes receive synthetic hash IDs (`cpd:syn:…`, `rxn:syn:…`,
`enz:syn:…`) rather than KEGG or ChEBI IDs. The human-readable names come
directly from the SBML `name` attributes, so nodes are already labelled
without needing TSV enrichment.

### 2b. FBC gene associations

The parser extracts gene–reaction links from the `<fbc:geneProductAssociation>`
element inside each reaction. Associations may be nested `<fbc:or>` / `<fbc:and>`
trees; the parser flattens them and emits one `CATALYZES` edge per referenced
gene product (i.e., all genes in an OR/AND association are connected).

Gene product IDs use the COBRA `G_<entrez_id>` convention. The `G_` prefix is
stripped to store the raw Entrez gene ID in `xrefs`:

```json
{"gene_id": "100762926"}
```

### 2c. Build results

| Entity | Count |
|--------|------:|
| Pathways | 1 (the whole model as one pathway) |
| Reactions | 6,337 |
| Compounds | 4,174 |
| Enzymes | 2,441 |
| **Total nodes** | **12,953** |
| CONTAINS edges | 6,337 |
| SUBSTRATE\_OF edges | 12,582 |
| PRODUCT\_OF edges | 12,722 |
| CATALYZES edges | 9,796 |
| **Total edges** | **41,437** |
| Vectors indexed | 6,616 (dim=384) |
| Xref rows | 2,441 (one per enzyme) |

---

## 3. Enrichment

### What runs and why it produces 0 (and why that is correct)

| Phase | Action | iCHO result | Why |
|---|---|---|---|
| Phase 1 | Label bare reactions from CATALYZES enzyme names | 1 updated | Most reactions already have descriptive names from SBML; only truly bare names are relabelled |
| Phase 2a | Compound names from `kegg_compound_names.tsv` | 0 | No `cpd:kegg:…` IDs; iCHO compounds use `cpd:syn:…` and already have names |
| Phase 2b | Reaction names from `kegg_reaction_names.tsv` | 0 | Same — `rxn:syn:…` namespace, names already present |
| Phase 2c | Reaction names from `kegg_reaction_detail.tsv` | 0 | Same |
| Phase 2d | Glycan names | 0 | No glycan nodes in iCHO |
| Phase 2e | KO enzyme names | 0 | No `enz:kegg:K…` nodes |
| Phase 3 | Gene symbol resolution from `{org}_gene_names.tsv` | 0 | Enzyme IDs are `enz:syn:…`; Phase 3 auto-detection requires `enz:kegg:{org}:…` format |

The `syn:` namespace fallback in `enrich_from_tsv` and `enrich_reactions_from_detail`
will resolve names for any future SBML file whose annotations include a
`kegg` cross-reference (stored in the node's `xrefs` JSON). iCHO has none, so it
is a no-op here but does not need special-casing.

### Resolving enzyme gene symbols

Phase 3 enrichment resolves FBC gene product Entrez IDs to gene symbols by
scanning all `*_gene_names.tsv` files in `data/` and matching against the
`gene_id` stored in each enzyme node's `xrefs` JSON. Download the gene name
TSVs once:

```bash
python scripts/download_kegg_names.py --genes cge hsa
```

**Result:** 1,942 / 2,441 enzymes (80%) are resolved to gene symbols (e.g.,
`G_100762926` → `Aoc3`). The remaining 499 are CHO genes that the KEGG CGE
database lists only with a protein description and no formal gene symbol — a
data limit, not a code issue.

---

## 4. Known Gaps

| Gap | Impact | Fix |
|---|---|---|
| 499 enzymes without gene symbols | ~20% of FBC gene products have no formal symbol in KEGG CGE — they display as `G_<entrez_id>` | Upstream data limit; no fix available without a curated symbol mapping |
| Single-pathway model | The whole GEM appears as one pathway node; no sub-pathway structure | Parse SBML `groups` package (L3 optional) or add a pathway-assignment TSV |
| No KEGG cross-references | Cannot enrich compound/reaction names via KEGG TSVs | iCHO names are already readable; add BiGG/MetaNetX annotation parsing if canonical IDs needed |
| OR/AND gene associations flattened | All genes in an AND association are treated as independent catalysts | Preserve Boolean logic in edge `evidence` JSON for downstream FBA-aware queries |

---

## 5. Multi-Corpus Registration (KGRAG)

After building, register iCHO as its own KGRAG corpus so federated queries can
span it alongside the human and CHO pathway graphs:

```bash
# Build all three corpora
metabokg-build --data data/hsa_pathways          # → data/hsa_pathways/.metabokg/hsa.sqlite
metabokg-build --data data/cge_pathways          # → data/cge_pathways/.metabokg/cge.sqlite
metabokg-build --data data/icho_model            # → data/icho_model/.metabokg/icho.sqlite
```

| Corpus | DB | Coverage |
|---|---|---|
| `metabokg-hsa` | `data/hsa_pathways/.metabokg/hsa.sqlite` | 369 human pathways |
| `metabokg-cge` | `data/cge_pathways/.metabokg/cge.sqlite` | 366 CHO pathways |
| `metabokg-icho` | `data/icho_model/.metabokg/icho.sqlite` | iCHO2441 GEM, 6,337 reactions |

---

## 6. Simulation

iCHO2441 is a stoichiometric (FBA) model — ODE simulation requires kinetic
parameters not present in the SBML file.

```bash
# Flux Balance Analysis across the whole model
metabokg-simulate fba --pathway pwy:syn:<model_id>

# Inspect a reaction
metabokg-query "lactate dehydrogenase icho"
```

Use `metabokg-build --data data/cge_pathways` for the CHO KGML pathways if you
need kinetically parameterised ODE or what-if simulations — those have
CATALYZES edges with resolved gene symbols enabling `--knockout Ldha`.
