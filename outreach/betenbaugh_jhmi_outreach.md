# Outreach: Prof. Michael Betenbaugh, JHMI / JHU ChemBE

**To:** beten@jhu.edu
**Subject:** MetaboKG / KGRAG — Metabolic Knowledge Graph Module, Licensing & Collaboration Inquiry

---

Dear Professor Betenbaugh,

I am writing to introduce **MetaboKG** and to offer your lab the opportunity to
take the scientific lead on it. MetaboKG is the metabolic knowledge graph module
of **KGRAG** — a hybrid semantic + structural knowledge graph platform for
retrieval-augmented generation that we are building at Flux Frontiers. KGRAG
federates domain-specific modules (metabolic, genomic, literature, code) into a
unified query layer for AI assistants and computational workflows. MetaboKG is
the most mature module, it covers both human and CHO metabolism, and your lab
is the right scientific home for it.

## What MetaboKG Does

MetaboKG ingests metabolic pathway data from any standard format — KGML, SBML,
BioPAX, CSV — into a dual-layer local graph (SQLite for structural precision +
LanceDB for semantic vector search). KEGG is one source; genome-scale models,
BiGG, Recon, and custom flux datasets are equally valid inputs. Four query
modalities are exposed:

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

We have a complete, validated CHO build. All 366 *Cricetulus griseus* KEGG
pathways are ingested and enriched as a reference build, producing a graph
we have verified locally. The iCHO2441 genome-scale model (SBML) is also
supported as a second corpus:

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

## What Your Lab Gets Out of the Box

MetaboKG is ready to use today. A student or postdoc can install it, run FBA
on any of the 366 CHO pathways, and get kinetics-informed simulation output
in an afternoon. The analysis pipeline surfaces rate-limiting steps, allosteric
control points, and pathway coupling without any manual curation — and the
synthesis command generates a narrative summary ready to drop into a methods
section or grant proposal.

For the AMBIC consortium specifically, this means a shared, reproducible
computational substrate for CHO metabolic modeling that any member lab can
run locally, extend, and cite.

## What I Am Proposing

I would like your lab to take the **lead scientific role** on MetaboKG as a
whole, and I would like an **adjunct appointment** at JHMI or JHU ChemBE in
return. That is the core of it.

**Adjunct research scientist / adjunct faculty** — an institutional affiliation
that gives me standing to serve as co-PI on joint grant applications. There is
real money available here: NIH SBIR/STTR Phase I/II, NSF, and DARPA BRICS are
all plausible targets for a KGRAG-based metabolic modeling platform with AMBIC
behind it. Without an institutional address I cannot be on those proposals;
with one, we can go after them together.

**Research license** — JHMI / AMBIC receives a perpetual, no-cost research
license under the Elastic License 2.0. Your lab deploys and owns the
installation; no dependency on Flux Frontiers for ongoing operations.

**Working agreement** — a simple letter agreement establishing your lab as
primary scientific steward of MetaboKG within the KGRAG platform, with
co-development rights and first-authorship on the metabolic application work.

**Co-authored methods paper** targeting *Metabolic Engineering* or
*Biotechnology & Bioengineering*, establishing MetaboKG as the reference
implementation for knowledge-graph-assisted CHO metabolic modeling.

In short: you get a ready-to-use platform your consortium can adopt today,
lead authorship on a novel methods paper, and a productive co-PI for grant
work. I get an institutional home and a path to funding. It is a clean trade.

A 30-minute live demo — FBA and ODE simulations on a CHO pathway of your
choice, kinetics analysis, LLM synthesis — would show you exactly what you
would be taking on.

GitHub: https://github.com/Flux-Frontiers/metabo_kg

Thank you for your time.

Warm regards,

**Eric G. Suchanek, PhD**
Flux Frontiers
https://github.com/Flux-Frontiers

---

*Attachment: `metabokg_article.pdf` (preprint)*
