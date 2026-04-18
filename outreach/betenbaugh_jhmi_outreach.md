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

- **FBA on any KEGG pathway in two lines of Python** — no model file setup
  needed; the knowledge graph *is* the stoichiometric model
- **Enzyme knockout / activity scaling** for in-silico CHO perturbations before
  wet-lab experiments
- **Semantic search** over 17 K nodes lets students and postdocs explore
  pathways without knowing exact KEGG IDs
- **MCP server** exposes all tools as a typed AI interface — Claude or any MCP
  client can query, simulate, and visualise the graph interactively

## Installation (5 minutes)

```bash
git clone https://github.com/Flux-Frontiers/metabo_kg.git
cd metabo_kg
python3.12 -m venv .venv && source .venv/bin/activate
poetry install --all-extras           # or: pip install metabokg[all]

# Download all 369 human KEGG pathways
python scripts/download_human_kegg.py --output data/hsa_pathways

# Build the knowledge graph (enrichment on by default)
metabokg-build --data ./data/hsa_pathways

# Run FBA on glycolysis
metabokg-simulate fba --pathway hsa00010 --output glycolysis_fba.md

# Launch web explorer
metabokg-viz --port 8500
```

## Potential Collaboration

We would welcome the chance to:

1. **Demonstrate** MetaboKG on a CHO-specific pathway or a current analysis
   your group is running — e.g., lactate metabolism, glutaminolysis, or
   nucleotide synthesis
2. **Co-develop** a CHO-specific kinetics layer using AMBIC data or published
   CHO flux measurements
3. **Explore co-authorship** on a methods/application note targeting
   *Metabolic Engineering*, *Bioinformatics*, or *Biotechnology & Bioengineering*

The project is PolyForm Noncommercial licensed (free for academic research),
with a GitHub repository at:
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
