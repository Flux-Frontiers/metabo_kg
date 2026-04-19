# Outreach: Prof. Michael Betenbaugh, JHMI / JHU ChemBE

**To:** beten@jhu.edu
**Subject:** MetaboKG — CHO-Ready Metabolic Knowledge Graph (License Inquiry)

---

Dear Professor Betenbaugh,

I am writing to introduce **MetaboKG**, an open-source metabolic knowledge graph
system we have built at Flux Frontiers, and to ask whether your lab might be the
right institutional home for it — or simply a first user.

## What It Does

MetaboKG ingests the complete KEGG metabolome into a dual-layer local graph
(SQLite for structural precision + LanceDB for semantic vector search) and
exposes four query modalities in a single tool:

1. Natural-language pathway discovery — "find CHO glutaminolysis pathways"
2. Structural neighbourhood traversal — "all products of glutamate dehydrogenase"
3. Shortest metabolic path — glucose → acetyl-CoA in < 50 ms
4. Stoichiometric detail assembly — substrates, products, enzymes, cofactors for any reaction

Beyond querying, three simulation modalities run directly against the knowledge
graph: **Flux Balance Analysis** (HiGHS LP), **kinetic ODE integration**
(Michaelis-Menten, BDF stiff solver), and **what-if perturbation analysis**
(enzyme knockouts, substrate overrides, activity scaling).

## Why It Is Relevant to CHO Work Specifically

MetaboKG ingests KEGG's *Cricetulus griseus* (`cge`) pathways with no code
changes — the same KGML format as human. A dedicated download script and
organism-aware build are already in place:

```bash
python scripts/download_cho_kegg.py --output data/cge_pathways
metabokg-build --data ./data/cge_pathways
metabokg-simulate fba --pathway cge00010   # CHO glycolysis FBA
```

We have also implemented a CHO-specific kinetics layer (`cho_kinetics.py`)
seeding 9 reactions from published CHO culture literature (Ahn & Antoniewicz
2011; Zagari et al. 2013; Templeton et al. 2013), including the metabolic
features most relevant to bioreactor performance:

| Reaction | Enzyme | CHO-Specific Detail |
|----------|--------|---------------------|
| R00299 | Hexokinase | Km_glucose = 0.046 mM (vs. 0.10 mM human) — high glucose affinity |
| R00703 | LDH | Vmax = 350 mM/s — overflow lactate phenotype quantified |
| R00256 | Glutaminase (GLS1) | Km_Gln = 1.5 mM; product-inhibited by glutamate |
| R00243 | Glutamate DH (GLUD1) | TCA anaplerosis from glutamine |
| R00254 | Glutamine synthetase | GS selection marker kinetics at pH 7.2 |
| R01954 | Asparagine synthetase | Asparagine auxotroph pathway quantified |
| R00258 | Alanine aminotransferase | CHO alanine secretion arm of glutaminolysis |
| R00344 | Pyruvate carboxylase | Anaplerotic TCA replenishment |
| R00756 | Phosphofructokinase | Recalibrated for CHO culture pH 7.2 |

A CHO biomass composition constant (Ahn & Antoniewicz 2011; Templeton 2013) is
included as the FBA objective seed: 63% protein, 12% lipid, 6% RNA, 2% DNA,
with ATP maintenance flux and typical glucose/glutamine uptake ranges.

## What Is Still Missing

To complete a production-grade CHO metabolic platform, three gaps remain:

1. **CHO-specific kinetics for amino acid biosynthesis** — 20 pathways with
   CHO-measured Km/Vmax values; currently defaults to human literature
2. **Recombinant protein coupling** — mAb / IgG synthesis as a growth-coupled
   FBA objective (product titer as the objective function)
3. **Fed-batch culture constraints** — glucose pulse kinetics, oxygen gradients,
   lactate switch dynamics

These are precisely where AMBIC flux data and your lab's published CHO
metabolomics would complete the picture.

## The Ask

MetaboKG is licensed under the **Elastic License 2.0** — free for internal
academic and research use, source-available on GitHub. We are looking for:

1. **An institutional licensee** — JHMI / AMBIC adopting MetaboKG as a shared
   research tool for the lab and collaborators
2. **A deployment host** — running it as a shared MCP server or Streamlit
   instance accessible to lab members and AI assistants
3. **A data partnership** — AMBIC CHO flux measurements closing the kinetics
   gaps in exchange for co-authorship on a CHO-MetaboKG methods paper targeting
   *Metabolic Engineering* or *Biotechnology & Bioengineering*

A 30-minute live demo — running FBA and ODE simulations on a CHO glycolysis or
glutaminolysis pathway of your choice — would speak louder than this email.

GitHub: https://github.com/Flux-Frontiers/metabo_kg

Thank you for your time.

Warm regards,

**Eric G. Suchanek, PhD**
Flux Frontiers
https://github.com/Flux-Frontiers

---

*Attachment: `metabokg_article.pdf` (preprint)*
