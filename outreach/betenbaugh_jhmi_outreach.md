# Outreach: Prof. Michael Betenbaugh, JHMI / JHU ChemBE

**To:** beten@jhu.edu
**Subject:** MetaboKG — CHO Metabolic Knowledge Graph, Licensing & Collaboration Inquiry

---

Dear Professor Betenbaugh,

I am writing to introduce **MetaboKG**, a metabolic knowledge graph system we
have built at Flux Frontiers, and to propose a collaboration I think could
produce a strong methods paper and a meaningful licensing relationship. MetaboKG
is one piece of a broader AI-assisted bioprocess intelligence platform we are
developing; the CHO component is the most mature, and your lab is the natural
scientific home for it.

## What MetaboKG Does

MetaboKG ingests KEGG pathway data into a dual-layer local graph (SQLite for
structural precision + LanceDB for semantic vector search) and exposes four
query modalities:

1. Natural-language pathway discovery — "find CHO glutaminolysis pathways"
2. Structural neighbourhood traversal — "all products of glutamate dehydrogenase"
3. Shortest metabolic path — glucose → acetyl-CoA in < 50 ms
4. Stoichiometric detail assembly — substrates, products, enzymes, cofactors for any reaction

Beyond querying, three simulation modalities run directly against the knowledge
graph: **Flux Balance Analysis** (HiGHS LP), **kinetic ODE integration**
(Michaelis-Menten, BDF stiff solver), and **what-if perturbation analysis**
(enzyme knockouts, substrate overrides, activity scaling). A synthesis layer
then pipes the full analysis report to a local LLM to generate a narrative
summary of control points, bottlenecks, and recommended experiments.

## The CHO Build — Verified Numbers

We have a complete, validated CHO build. All 366 *Cricetulus griseus* (`cge`)
KEGG pathways are ingested and fully enriched, producing a graph we have
verified locally:

| Entity | Count |
|--------|------:|
| Pathways | 366 |
| Reactions | 2,099 |
| Compounds | 5,105 |
| Enzymes | 9,360 |
| **Total nodes** | **16,930** |
| **Total edges** | **39,731** |

The full build runs in under 5 minutes on a laptop:

```bash
metabokg-build --data ./data/cge_pathways
metabokg-simulate seed              # populate kinetic parameters
metabokg-analyze --db ...           # 8-phase analysis
metabokg-synthesize --db ...        # analysis + LLM narrative synthesis
```

## CHO-Specific Kinetics Layer

We have implemented `cho_kinetics.py`, seeding **35 reactions** across 6 core
pathways from published CHO culture literature (Ahn & Antoniewicz 2011; Zagari
et al. 2013; Templeton et al. 2013). All parameters are at **pH 7.2, 37°C**.

Selected entries illustrating CHO-specific detail:

| Reaction | Enzyme | CHO-Specific Detail |
|----------|--------|---------------------|
| R00299 | Hexokinase | Km_glucose = 0.046 mM (vs. 0.10 mM human) |
| R00703 | LDH | Vmax = 350 mM/s — overflow lactate phenotype |
| R00256 | Glutaminase (GLS1) | Km_Gln = 1.5 mM; product-inhibited by glutamate |
| R00243 | Glutamate DH (GLUD1) | TCA anaplerosis from glutamine |
| R00254 | Glutamine synthetase | GS selection marker kinetics at pH 7.2 |
| R01954 | Asparagine synthetase | Asparagine auxotroph pathway |
| R00344 | Pyruvate carboxylase | Anaplerotic TCA replenishment |
| R00756 | Phosphofructokinase | Recalibrated for CHO culture pH 7.2 |

We also queried **SABIO-RK** for all *Cricetulus griseus* kinetic entries
(91 entries, 268 measured Km and kcat values) as an additional validation layer.

The analysis pipeline now includes a dedicated kinetics phase that surfaces
rate-limiting steps (by Km), throughput bottlenecks (by Vmax), and allosteric
control points automatically — without manual curation.

## Where Your Lab's Data Would Complete the Picture

Three gaps remain that AMBIC flux data is uniquely positioned to close:

1. **CHO-specific kinetics for amino acid biosynthesis** — 20 pathways currently
   default to human literature values; CHO-measured Km/Vmax would replace them
2. **Recombinant protein coupling** — mAb / IgG synthesis as a growth-coupled
   FBA objective (product titer as the optimization target)
3. **Fed-batch culture constraints** — glucose pulse kinetics, oxygen gradients,
   lactate switch dynamics

These are exactly where your published CHO metabolomics and AMBIC flux
measurements would complete a production-grade model.

## Proposed Collaboration

I would like to propose the following structure:

**Co-authored methods paper** targeting *Metabolic Engineering* or
*Biotechnology & Bioengineering*:
- MetaboKG as the computational platform (Flux Frontiers contribution)
- AMBIC CHO flux measurements and experimental validation (Betenbaugh lab
  contribution)
- Target: a reproducible, open-source CHO metabolic modeling workflow the
  community can build on

**Institutional license** — MetaboKG is source-available under the
**Elastic License 2.0**. For JHMI / AMBIC we would structure a research
license that grants your lab and collaborators full unrestricted use, with
the data partnership as the consideration. Deployment and integration into
your existing infrastructure would be entirely on your side — the tool is
self-contained and installs with a single command.

**Adjunct appointment** — if there is appetite for a closer relationship,
an adjunct research scientist or adjunct faculty affiliation at JHMI /
JHU ChemBE would let us pursue grant funding together (NIH SBIR/STTR,
NSF, DARPA BRICS) and give the collaboration an institutional home.

A 30-minute live demo — running FBA and ODE simulations on a CHO glycolysis or
glutaminolysis pathway of your choice, including kinetics analysis and LLM
narrative synthesis — would be the fastest way to show what this can do.

GitHub: https://github.com/Flux-Frontiers/metabo_kg

Thank you for your time.

Warm regards,

**Eric G. Suchanek, PhD**
Flux Frontiers
https://github.com/Flux-Frontiers

---

*Attachment: `metabokg_article.pdf` (preprint)*
