# Introducing MetaboKG — a local, queryable knowledge graph for metabolism

We're excited to release **MetaboKG v0.7.1**: an open-source Python toolkit that turns the world's metabolic pathway databases into a single, local, queryable knowledge graph — and lets you ask it questions in English, simulate flux through it, and hand it to an LLM as structured context.

**Repo:** https://github.com/flux-frontiers/metabo_kg
**License:** Elastic License 2.0 (free to use, modify, and redistribute — no hosted-service resale)
**DOI:** [10.5281/zenodo.1184537477](https://zenodo.org/badge/latestdoi/1184537477)

---

## Why we built it

Pathway data is fragmented. KEGG ships KGML, BioModels ships SBML, Reactome ships BioPAX, every wet-lab dataset ships its own CSV. If you want to ask *"what enzymes connect glucose to pyruvate in CHO cells, and what happens to the flux when I knock out LDHA?"*, you end up gluing together three parsers, four ID systems, and a simulator — every single time.

MetaboKG does that gluing once. You get a unified compound / reaction / enzyme / pathway graph, indexed for hybrid semantic + structural search, with simulation and LLM tooling already wired in. Everything runs on your laptop. No cloud APIs, no quotas, no data leaves the machine.

---

## What's in the box

**Three production-grade corpora, bundled in the repo:**

| Corpus | What it is |
|---|---|
| `metabokg-hsa` | 369 KEGG pathways for *Homo sapiens* — the complete human metabolome (17K+ nodes, 40K+ edges) |
| `metabokg-cge` | 366 KEGG pathways for *C. griseus* (CHO) — the workhorse of biopharma |
| `metabokg-icho` | iCHO2441 genome-scale model (SBML/FBC v2): 6,663 reactions, 4,456 metabolites, 2,441 gene products |

**Hybrid retrieval.** A query like *"hexokinase"* embeds against a local sentence-transformer, pulls the top-k nearest nodes from LanceDB, then expands `hop` BFS steps along typed edges (`SUBSTRATE_OF`, `PRODUCT_OF`, `CATALYZES`, `INHIBITS`, `ACTIVATES`, `XREF`). You get vector recall *and* graph context in one shot.

**Simulation.** With the `simulate` extra installed, the same graph becomes a numerical substrate:
- **FBA** — steady-state flux optimization (HiGHS backend)
- **ODE kinetics** — Michaelis-Menten time courses with literature-seeded parameters from BRENDA / SABIO-RK (BDF solver — metabolic systems are stiff)
- **What-if perturbations** — enzyme knockouts, partial inhibitions, substrate pulses, ranked by delta flux or delta concentration

**LLM-native.** `metabokg-mcp` exposes the graph as MCP tools (`pack`, `query_pathway`, `find_path`, `simulate_fba`, `simulate_ode`, `simulate_whatif`, …) for Claude, Kilo Code, and Copilot. For everything else, `metabokg-pack "TCA cycle"` writes self-contained Markdown you can pipe into any context window.

**Visualization.** 2D Streamlit explorer (`metabokg-viz`) and 3D PyVista viewer (`metabokg-viz3d`) with hub-and-spoke or concentric-ring layouts.

---

## Get started in 60 seconds

```bash
git clone https://github.com/flux-frontiers/metabo_kg.git
cd metabo_kg
python3.12 -m venv .venv && source .venv/bin/activate
poetry install --extras all

# One-shot: integrity check, fetch missing TSVs, build hsa + cge + icho, seed kinetics
metabokg-init

# Look around
metabokg-info             # what got built and where
metabokg-viz              # 2D Streamlit explorer at http://localhost:8500
```

That's it. All pathway data is bundled — there's nothing extra to download.

---

## Part of a family

MetaboKG shares a hybrid semantic-plus-structural design with two sister projects:

- **[PyCodeKG](https://github.com/flux-frontiers/pycode_kg)** — the same idea applied to Python source code
- **[DocKG](https://github.com/flux-frontiers/doc_kg)** — the same idea applied to Markdown corpora

Together they form **KGRAG**, a federated retrieval layer where one query can span code, documentation, and pathway data simultaneously.

---

## Where to go next

- **Tour the capabilities** → [docs/CAPABILITIES.md](docs/CAPABILITIES.md)
- **Browse worked examples** → [docs/EXAMPLES.md](docs/EXAMPLES.md)
- **Wire it to Claude** → [docs/MCP.md](docs/MCP.md)
- **One-page command reference** → [docs/CHEATSHEET.md](docs/CHEATSHEET.md)

---

## Get involved

- **Issues & feature requests** → [GitHub Issues](https://github.com/flux-frontiers/metabo_kg/issues)
- **Q&A and ideas** → [GitHub Discussions](https://github.com/flux-frontiers/metabo_kg/discussions)

If you use MetaboKG in research, please cite via the [Zenodo DOI](https://zenodo.org/badge/latestdoi/1184537477) or [`CITATION.cff`](CITATION.cff).

We'd love to hear what you build with it.

— *The MetaboKG team*
