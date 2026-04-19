# CHO Metabolic Knowledge Graph — Build Workflow

## Overview

Complete workflow for building, parameterizing, and simulating a *Cricetulus
griseus* (CHO) metabolic knowledge graph in MetaboKG. All commands use default
paths (`.metabokg/meta.sqlite`, `.metabokg/lancedb`).

---

## 0. One-time: Download KEGG Name Lists

```bash
python scripts/download_kegg_names.py --genes cge hsa
```

Downloads compound, reaction, and per-organism gene name TSVs to `data/`.
Required for enzyme name enrichment (Phase 3) during build.

| File | Rows | Purpose |
|------|-----:|---------|
| `data/kegg_compound_names.tsv` | ~19,500 | Compound name enrichment |
| `data/kegg_reaction_names.tsv` | ~12,400 | Reaction name enrichment |
| `data/cge_gene_names.tsv` | 23,574 | CHO enzyme gene symbol enrichment |
| `data/hsa_gene_names.tsv` | 24,252 | Human enzyme gene symbol enrichment |

---

## 1. Download CHO KEGG Pathways

```bash
python scripts/download_cho_kegg.py --output data/cge_pathways
```

Downloads all 366 `cge` KGML pathway files from KEGG. The `cge` organism code
is Chinese hamster (*Cricetulus griseus*), the species underlying CHO cell lines.

**Output:** `data/cge_pathways/*.kgml` (366 files)

---

## 2. Build the Knowledge Graph

```bash
metabokg-build --data data/cge_pathways
```

Runs the full build pipeline automatically:

1. Parse 366 KGML files → SQLite
2. Enrich reaction names from CATALYZES edges
3. Enrich compound names from `kegg_compound_names.tsv`
4. Enrich reaction names from `kegg_reaction_names.tsv`
5. **Enrich enzyme names from `cge_gene_names.tsv`** (Phase 3 — new)
6. Build LanceDB vector index

After Phase 3, enzymes are addressable by gene symbol:
```bash
metabokg-simulate whatif --pathway cge00010 --knockout Ldha   # works directly
```

**Result:**

| Entity | Count |
|--------|------:|
| Pathways | 366 |
| Reactions | 2,099 |
| Compounds | 5,105 |
| Enzymes | 9,360 (5,329 with gene symbols) |
| **Total nodes** | **16,930** |
| **Total edges** | **39,731** |

---

## 3. Seed CHO-Specific Kinetics (curated literature)

```bash
metabokg-simulate seed-cho
```

Seeds 35 reactions across 6 core pathways from published CHO culture literature
at **pH 7.2, 37°C** (standard bioreactor conditions):

| Pathway | Reactions |
|---------|----------:|
| Glycolysis (cge00010) | 12 |
| TCA cycle (cge00020) | 8 |
| Oxidative phosphorylation (cge00190) | 3 |
| Glutaminolysis | 4 |
| Amino acid metabolism | 4 |
| Anaplerosis / PPP | 4 |

Sources: Ahn & Antoniewicz 2011; Zagari et al. 2013; Templeton et al. 2013.

**Result:** 46 kinetic parameter rows, 15 regulatory interactions written.

Use `--force` to overwrite existing rows.

---

## 4. Fetch SABIO-RK Experimental Kinetics

```bash
python scripts/fetch_sabio_cho_kinetics.py --output data/sabio_cho_kinetics.tsv
```

Queries SABIO-RK for all *Cricetulus griseus* kinetic law entries and writes
measured Km, kcat, Vmax, and Ki values to TSV.

**Key notes:**
- Organism query: `Organism:"Cricetulus griseus"` (not "Chinese hamster" — returns 0)
- API returns SBML Level 3 XML; parser strips namespaces for version-agnostic parsing
- Enzyme names resolved from `listOfSpecies` via `ENZ_*` modifier references

**Result:** 91 kinetic law entries → 268 measured parameters (Km, kcat, Vmax, Ki)

---

## 5. Run Simulations

```bash
# Flux Balance Analysis — CHO glycolysis
metabokg-simulate fba --pathway cge00010

# ODE kinetic time-course
metabokg-simulate ode --pathway cge00010 --time 20

# LDH knockout what-if (gene symbol works directly after Phase 3 enrichment)
metabokg-simulate whatif --pathway cge00010 --knockout Ldha --name CHO_LDH_KO
```

---

## Multi-Corpus Convention (KGRAG)

Each organism or model builds into its own named db so it can be registered
as a separate KGRAG corpus — enabling federated queries across organisms:

```bash
metabokg-build --data data/hsa_pathways          # → .metabokg/meta.sqlite   (human)
metabokg-build --data data/cge_pathways  --db .metabokg/cge.sqlite   (CHO)
metabokg-build --data data/icho_model    --db .metabokg/icho.sqlite  (iCHO2441)
```

| Corpus | DB | Coverage |
|--------|-----|---------|
| `metabokg-hsa` | `.metabokg/meta.sqlite` | 369 human pathways |
| `metabokg-cge` | `.metabokg/cge.sqlite` | 366 CHO pathways |
| `metabokg-icho` | `.metabokg/icho.sqlite` | iCHO2441, 6,663 reactions |

With all three registered, a single KGRAG query spans them simultaneously:
"find glutaminolysis flux differences between human and CHO."

---

## Data Gaps (open)

1. **SABIO-RK coverage** — 91 entries, mostly tRNA ligases; central carbon
   enzymes (HK, PFK, LDH, CS, etc.) not yet in SABIO-RK for CHO
2. **iCHO2441 SBML** — the 6,663-reaction consensus GEM (Hefzi et al. 2016,
   BioModels `MODEL2206100001`) requires a free BioModels account to download;
   once obtained, ingest with `metabokg-build --data data/icho_model`
3. **Amino acid biosynthesis kinetics** — 20 pathways still use human defaults
4. **Fed-batch constraints** — glucose pulse, oxygen gradient, lactate switch

---

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `scripts/download_kegg_names.py --genes cge hsa` | Download gene name TSVs (one-time) |
| `scripts/download_cho_kegg.py` | Download 366 cge KGML pathways |
| `scripts/fetch_sabio_cho_kinetics.py` | Fetch *C. griseus* kinetics from SABIO-RK |
| `scripts/download_icho_model.py` | Download iCHO2441 SBML (requires BioModels login) |
