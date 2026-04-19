# Outreach: Prof. Michael Betenbaugh, JHMI / JHU ChemBE

**To:** beten@jhu.edu
**Subject:** MetaboKG — Open-Source Metabolic Knowledge Graph + MCP Integration (Potential Collaboration)

---

Dear Professor Betenbaugh,

I am writing to introduce **MetaboKG**, an open-source, local-first metabolic
pathway knowledge graph system we have developed at Flux Frontiers, and to
explore whether it might be useful to your lab's work in mammalian cell
metabolic engineering.

## What MetaboKG Does

MetaboKG ingests the complete *Homo sapiens* KEGG metabolome (all 369 pathways,
17,050 nodes, 40,166 edges) into a dual-layer local graph — SQLite for
structural precision and LanceDB for semantic vector search — and exposes four
complementary query modalities:

1. **Natural-language pathway discovery** — "find pathways related to CHO cell
   glutamine catabolism" (vector similarity, handles synonyms)
2. **Structural neighbourhood traversal** — "all products of pyruvate
   carboxylase" (SQL joins, sub-50 ms)
3. **Shortest metabolic path** — glucose → acetyl-CoA (BFS over the
   compound–reaction bipartite graph)
4. **Stoichiometric detail assembly** — full substrates, products, enzymes,
   cofactors, inhibitors for any reaction

Beyond querying, MetaboKG integrates three simulation modalities directly:

- **Flux Balance Analysis (FBA)** — steady-state flux optimisation via
  `scipy`/HiGHS LP solver
- **Kinetic ODE integration** — Michaelis-Menten rate laws with curated
  literature kinetics (BRENDA/SABIO-RK), BDF stiff solver
- **What-if perturbation analysis** — enzyme knockouts, substrate overrides,
  enzyme activity scaling

All 26 glycolysis/TCA/oxidative-phosphorylation reactions carry curated kinetic
parameters (Km, kcat, Vmax, Keq, ΔG°'), and regulatory interactions (PFK
allosteric inhibition by ATP/citrate, hexokinase feedback by G6P, etc.) are
wired in out of the box.

## Why It May Be Relevant to Your Lab

Your group's work on CHO cell metabolic reprogramming, bioreactor flux analysis,
and multi-omics integration sits exactly at the intersection where MetaboKG is
strongest:

- **Native CHO (`cge`) pathway support** — KEGG's *Cricetulus griseus* pathways
  ingest with the same command as human; no code changes required
- **FBA on any KEGG pathway in two lines of Python** — no model file setup
  needed; the knowledge graph *is* the stoichiometric model
- **Enzyme knockout / activity scaling** for in-silico CHO perturbations before
  wet-lab experiments
- **Semantic search** over 17 K+ nodes lets students and postdocs explore
  pathways without knowing exact KEGG IDs
- **MCP server** exposes all tools as a typed AI interface — Claude or any MCP
  client can query, simulate, and visualise the graph interactively

## Installation (5 minutes)

```bash
git clone https://github.com/Flux-Frontiers/metabo_kg.git
cd metabo_kg
python3.12 -m venv .venv && source .venv/bin/activate
poetry install --all-extras           # or: pip install metabokg[all]

# Option A — Human pathways (369 hsa pathways)
python scripts/download_human_kegg.py --output data/hsa_pathways
metabokg-build --data ./data/hsa_pathways

# Option B — CHO pathways (Cricetulus griseus / cge, same KGML format)
python scripts/download_cho_kegg.py --output data/cge_pathways
metabokg-build --data ./data/cge_pathways

# Option C — Unified human + CHO graph
metabokg-update --data ./data/cge_pathways   # merges into existing hsa graph

# Run FBA on CHO glycolysis
metabokg-simulate fba --pathway cge00010 --output cho_glycolysis_fba.md

# Launch web explorer
metabokg-viz --port 8500
```

## Licensing & Deployment

MetaboKG is released under the **Elastic License 2.0** — free to use, modify,
and deploy internally for academic and non-commercial purposes, with source
available on GitHub. Commercial redistribution requires a separate agreement.

We would welcome the chance to:

1. **License MetaboKG to JHMI / AMBIC** for internal research and teaching use
2. **Deploy it as a shared resource** for the lab or department — either as a
   local MCP server accessible to lab members' AI assistants, or as a hosted
   Streamlit instance on your infrastructure
3. **Demonstrate** the system on a live CHO pathway relevant to your current
   work — lactate metabolism, glutaminolysis, or nucleotide synthesis

GitHub repository:
https://github.com/Flux-Frontiers/metabo_kg

I would be happy to schedule a 30-minute call or Zoom to walk through a live
demo. Please feel free to reply here or reach me at the contact below.

Thank you for your time and consideration.

Warm regards,

**Eric G. Suchanek, PhD**
Flux Frontiers
https://github.com/Flux-Frontiers

---

*Attachments: `metabokg_article.pdf` (preprint)*
