# MetaKG Thorough Pathway Analysis Skill

## Overview

Performs comprehensive graph analysis of a MetaKG metabolic pathway database,
analogous to the `codekg-thorough-analysis` skill but applied to biochemical networks.
Extracts metrics like:

- **Hub metabolites** (highest connectivity — cofactors, energy carriers)
- **Complex reactions** (most substrates/products — rate-limiting steps)
- **Cross-pathway junctions** (metabolites bridging multiple pathways)
- **Pathway coupling** (tightly interdependent pathway pairs)
- **Topological patterns** (dead-end metabolites, isolated nodes, metabolic cycles)
- **Top enzymes** (broadest catalytic coverage)

### Code ↔ Metabolism Analogy

| Code concept                | Metabolic equivalent                              |
|-----------------------------|---------------------------------------------------|
| Function                    | Reaction (transforms inputs → outputs)            |
| Module / Package            | Pathway (group of related reactions)              |
| Variable / data type        | Compound / metabolite                             |
| Method implementation       | Enzyme (executes the reaction)                    |
| Most-called function (fan-in) | Hub metabolite (in many reactions)              |
| Orchestrator function (fan-out) | Complex reaction (many substrates/products)  |
| Shared utility module       | Cross-pathway compound (bridges many pathways)    |
| Tightly coupled modules     | Strongly coupled pathways (shared compounds)      |
| Dead / orphaned code        | Dead-end or isolated metabolite                   |

---

## Trigger Phrases

- "analyze this pathway database thoroughly"
- "give me a complete metakg analysis"
- "pathway deep dive"
- "metabolic network architecture report"
- "find hub metabolites"
- "which pathways are tightly coupled?"

---

## Strategy

### Phase 1: Graph Statistics & Baseline

```
1. Get overall database metrics: MetaStore.stats()
   - Total nodes / edges by kind
   - Edge density by relation type (SUBSTRATE_OF, PRODUCT_OF, CATALYZES, CONTAINS, …)

2. Per-pathway profiles
   - Reaction count per pathway (size)
   - Compound count per pathway
   - Enzyme count per pathway
```

### Phase 2: Hub Metabolite Analysis (Fan-In equivalent)

```
For each compound, count:
  - Reactions it feeds INTO as substrate (SUBSTRATE_OF edges out)
  - Reactions it is PRODUCED BY as product (PRODUCT_OF edges in)

Sort by total reaction participation.

Expected top hits: ATP, ADP, NAD+, NADH, CoA, Pyruvate, Acetyl-CoA, Pi

Interpretation:
  - High reaction_count → metabolic hub (often a cofactor / energy carrier)
  - High pathway_count → cross-pathway integration point
  - Substrate-heavy → primarily consumed (energy input, electron donor)
  - Product-heavy  → primarily generated (end-product, energy output)
```

### Phase 3: Complex Reaction Analysis (Fan-Out equivalent)

```
For each reaction, count:
  - Substrates (incoming SUBSTRATE_OF edges)
  - Products (outgoing PRODUCT_OF edges)
  - Enzymes (incoming CATALYZES edges)

Sort by (substrate_count + product_count) — "stoichiometric complexity".

Interpretation:
  - complexity > 6 → multi-substrate reaction, often an allosteric control point
  - High enzyme_count → reaction catalysed by multiple enzymes (isoenzymes / redundancy)
  - High pathway_count → shared reaction appearing in many pathway definitions
```

### Phase 4: Cross-Pathway Hub Detection

```
Build compound → {pathway_ids} membership map (via CONTAINS + reaction membership).

Filter: compounds in 2+ distinct pathways.

Sort by pathway_count descending.

Interpretation:
  - pathway_count >= 5 → major junction metabolite
  - pathway_count = 2–4 → bridge between two metabolic subsystems
  - These are prime targets for studying inter-pathway regulation
```

### Phase 5: Pathway Coupling Analysis

```
For every pair of pathways (A, B):
  - Compute shared_compounds = membership[A] ∩ membership[B]
  - Sort pairs by |shared_compounds| descending

Interpretation:
  - shared_count >= 10 → tightly coupled, likely analysed together in biology
  - shared_count = 1–3 → loose coupling, one or two handoff metabolites
  - These pairs should be co-visualised in the Streamlit explorer
```

### Phase 6: Topological Pattern Detection

```
1. Dead-end metabolites
   - Compounds with exactly 1 reaction connection
   - substrate-only → pure inputs (glucose, O2, external nutrients)
   - product-only   → terminal products (CO2, H2O, biomass components)

2. Isolated nodes
   - Nodes (any kind) with zero edges
   - Likely parsing artefacts or incomplete data files

3. Metabolic cycle detection (future)
   - BFS/DFS from each compound looking for self-loops
   - Classic examples: TCA cycle, urea cycle, purine salvage
```

### Phase 7: Top Enzyme Coverage

```
For each enzyme, count CATALYZES edges (reactions it can catalyse).

Sort descending.

Interpretation:
  - High coverage → multi-functional enzyme (e.g. alcohol dehydrogenase family)
  - EC number 1.x.x.x → oxidoreductase (ubiquitous, expect high counts)
  - Enzymes with many reactions but few pathways → pathway-specific specialists
```

### Phase 8: Actionable Biological Insights

```
Compile findings into:
1. Energy cofactor dominance — flag ATP/NAD+/CoA as expected hubs
2. Top metabolic junction — the single highest cross-pathway compound
3. Tightest pathway coupling — the pathway pair with most shared metabolites
4. Dead-end inventory — substrate-only vs product-only breakdown
5. Data completeness warnings — isolated nodes, parsing gaps
6. Drug target candidates — high-complexity reactions with known enzyme coverage
```

---

## Implementation

### Running the Analysis

```bash
# Build the knowledge graph first
metakg-build --data pathways/ --db .metakg/meta.sqlite --wipe

# Run thorough analysis (print to terminal)
metakg-analyze --db .metakg/meta.sqlite

# Save Markdown report
metakg-analyze --db .metakg/meta.sqlite --output Analysis_$(date +%Y%m%d).md

# Top 30 items in each list
metakg-analyze --db .metakg/meta.sqlite --top 30

# Plain text (no Markdown)
metakg-analyze --db .metakg/meta.sqlite --plain
```

### Python API

```python
from metakg.analyze import PathwayAnalyzer
from metakg.thorough_analysis import render_thorough_report

with PathwayAnalyzer(".metakg/meta.sqlite", top_n=20) as analyzer:
    report = analyzer.run()

# Print polished Markdown report
print(render_thorough_report(report))

# Access structured data
for hub in report.hub_metabolites[:5]:
    print(f"{hub.name}: {hub.reaction_count} reactions across {hub.pathway_count} pathways")

for coupling in report.pathway_couplings[:3]:
    print(f"{coupling.pathway_a_name} ↔ {coupling.pathway_b_name}: "
          f"{coupling.shared_count} shared compounds")
```

### Data Collection

```bash
# Download 30 curated KEGG KGML pathway files
python scripts/collect_pathway_data.py

# List available pathways (no download)
python scripts/collect_pathway_data.py --list

# Download only energy metabolism pathways
python scripts/collect_pathway_data.py --category energy

# Force re-download
python scripts/collect_pathway_data.py --force

# Custom delay (be polite to KEGG)
python scripts/collect_pathway_data.py --delay 1.5
```

---

## Output Format

**Terminal output:**
- Markdown tables rendered inline (works with `rich` or standard terminal)
- Phase headers with numbered sections
- Emoji risk indicators: 🟢 LOW / 🟡 MED / 🔴 HIGH

**File output (`--output`):**
- `Analysis_{date}.md` — full Markdown report
- Suitable for GitHub wiki, Obsidian, Notion

**Report sections:**

```markdown
# MetaKG Pathway Analysis Report

## Phase 1 — Graph Statistics
  - Node/edge counts by kind
  - Per-pathway profiles (reactions, compounds, enzymes)

## Phase 2 — Hub Metabolites (Highest Connectivity)
| Rank | Compound | Formula | Reactions | Substrate | Product | Pathways | Load |
| 1    | ATP      | C10H16N5O13P3 | 47 | 23 | 24 | 12 | 🔴 HIGH |

## Phase 3 — Complex Reactions
| Rank | Reaction | Substrates | Products | Enzymes | Pathways | Complexity |

## Phase 4 — Cross-Pathway Hub Metabolites
| Rank | Compound | Formula | Pathways | Reactions | Examples |

## Phase 5 — Pathway Coupling
| Pathway A | Pathway B | Shared Compounds | Examples |

## Phase 6 — Topological Patterns
### Dead-End Metabolites
  substrate-only: pure inputs (glucose, O2, ...)
  product-only:   terminal outputs (CO2, H2O, ...)

### Isolated Nodes
  Zero-edge nodes (parsing artefacts)

## Phase 7 — Top Enzymes
| Rank | Enzyme | EC Number | Reactions Catalysed |

## Biological Insights & Recommendations
  - Energy cofactor dominance ...
  - Top metabolic junction ...
  - Tightest pathway coupling ...
```

---

## Example Invocations

```bash
# Analyze current database
metakg-analyze

# Full analysis with output saved
metakg-analyze --db .metakg/meta.sqlite --output reports/pathway_analysis.md --top 25

# Quick check (top 5 only)
metakg-analyze --top 5

# JSON-friendly plain text
metakg-analyze --plain > analysis.txt
```

---

## Skill Output Example

For a database built from ~30 KEGG human metabolic pathways:

```
# MetaKG Pathway Analysis Report

**Database:** `.metakg/meta.sqlite`
**Generated:** 2026-02-27 14:30 UTC

## Phase 1 — Graph Statistics

- Total nodes: 1,847
  - Pathways: 30
  - Reactions: 612
  - Compounds: 984
  - Enzymes: 221
- Total edges: 4,103
  - SUBSTRATE_OF: 1,402
  - PRODUCT_OF: 1,289
  - CONTAINS: 892
  - CATALYZES: 487
  - INHIBITS: 33

### Pathway Profiles
| Pathway                              | Reactions | Compounds | Enzymes |
| Purine metabolism                    | 77        | 0         | 0       |
| Pyrimidine metabolism                | 54        | 0         | 0       |
| Glycolysis / Gluconeogenesis         | 26        | 0         | 0       |
| Citrate cycle (TCA cycle)            | 20        | 0         | 0       |

## Phase 2 — Hub Metabolites

| Rank | Compound     | Formula          | Reactions | Substrate | Product | Pathways | Load     |
|  1   | ATP          | C10H16N5O13P3    | 47        | 23        | 24      | 12       | 🔴 HIGH  |
|  2   | ADP          | C10H15N5O10P2    | 41        | 18        | 23      | 11       | 🔴 HIGH  |
|  3   | NAD+         | C21H27N7O14P2    | 38        | 21        | 17      | 9        | 🔴 HIGH  |
|  4   | Orthophosphate | HO4P           | 35        | 8         | 27      | 10       | 🔴 HIGH  |
|  5   | CoA          | C21H36N7O16P3S   | 28        | 14        | 14      | 8        | 🔴 HIGH  |

## Phase 3 — Complex Reactions

| Rank | Reaction                      | Substrates | Products | Enzymes | Pathways | Complexity |
|  1   | ATP synthesis (Complex V)     | 4          | 3        | 2       | 1        | 🔴 HIGH    |
|  2   | Phosphoglycerate kinase       | 3          | 2        | 1       | 2        | 🟡 MED     |

## Phase 4 — Cross-Pathway Hubs

| Rank | Compound   | Pathways | Reactions | Example pathways                             |
|  1   | Pyruvate   | 8        | 14        | Glycolysis; TCA; Pyruvate metabolism (+5 more)|
|  2   | Acetyl-CoA | 7        | 11        | TCA; Fatty acid biosynthesis; CoA (+4 more)  |

## Phase 5 — Pathway Coupling

| Pathway A                    | Pathway B             | Shared | Examples              |
| Glycolysis / Gluconeogenesis | Pyruvate metabolism   | 6      | Pyruvate, PEP, ATP... |
| TCA cycle                    | Glyoxylate metabolism | 4      | Oxaloacetate, CoA...  |

## Phase 6 — Topological Patterns

Found 142 dead-end metabolites.
  substrate-only (43): glucose-6-phosphate, fructose, D-xylose, ...
  product-only (99):   lactate, acetate, CO2, H2O, ...

No isolated nodes — all entities connected.

## Phase 7 — Top Enzymes

| Rank | Enzyme                          | EC       | Reactions |
|  1   | Alcohol dehydrogenase           | 1.1.1.1  | 12        |
|  2   | Pyruvate dehydrogenase complex  | 1.2.4.1  | 8         |

## Biological Insights

- **Energy cofactor dominance**: ATP, ADP, NAD+, CoA are top hub metabolites.
  Filter these when studying pathway-specific connectivity.
- **Top metabolic junction**: Pyruvate appears in 8 pathways and 14 reactions.
- **Tightest pathway coupling**: Glycolysis ↔ Pyruvate metabolism (6 shared compounds).
- **142 dead-end metabolites**: 43 substrate-only (external inputs), 99 product-only (outputs).
- **Most complex reaction**: ATP synthesis (Complex V) with complexity score 🔴 HIGH.
```

---

## Key Features

✅ **Comprehensive** — All 7 analysis phases, covering topology and biology
✅ **Actionable** — Identifies specific compounds/reactions/enzymes to investigate
✅ **Biologically grounded** — Insight labels aware of cofactor biology
✅ **Fast** — Pure SQLite aggregate queries, no in-memory graph construction
✅ **Reusable** — Works on any MetaKG database regardless of input format
✅ **Extensible** — Add custom phases via `PathwayAnalyzer` subclass

## Edge Cases

- **Cofactor inflation** — ATP/NAD appear in nearly every pathway; expected high scores
- **Sparse data** — Single-pathway databases will show no cross-pathway hubs
- **KGML compound nodes** — KEGG maps often include "undefined" compounds; expected in dead-ends
- **Multi-format data** — Mix KGML + SBML + BioPAX for richer compound coverage

## Future Enhancements

1. **Metabolic cycle detection** — BFS-based cycle finding (TCA, urea cycle, purine salvage)
2. **Flux balance proxies** — Estimate metabolic load from stoichiometry
3. **Drug target scoring** — Rank reactions by target tractability × pathway essentiality
4. **Temporal analysis** — Compare two MetaKG snapshots (before/after data update)
5. **MCP tool integration** — Expose analysis results via `metakg-mcp` tools
6. **Interactive report** — Streamlit dashboard for the analysis output
