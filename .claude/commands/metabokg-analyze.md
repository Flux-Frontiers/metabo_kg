# MetaboKG Thorough Pathway Analysis

Generate a comprehensive metabolic pathway analysis report from the MetaboKG database.

## What This Does

Analyzes the MetaboKG database and produces a polished, CodeKG-style report including:
- **Executive Summary** with key metrics
- **7-Phase Analysis**: hub metabolites, complex reactions, cross-pathway junctions, pathway coupling, topology, and enzyme coverage
- **Network Health Assessment**: identifies dead-ends, isolated nodes, sparse areas
- **Metabolic Network Strengths**: highlights well-designed patterns
- **Biological Insights & Recommendations**: actionable priorities for immediate, medium-term, and long-term research

## Usage

```bash
# Print to terminal
/metabokg-analyze

# Save to file (with timestamp)
/metabokg-analyze --output

# Show top N items per ranking
/metabokg-analyze --top 30

# Plain text format (no Markdown)
/metabokg-analyze --plain
```

## Before Running

Make sure you have:
1. ✓ Built the MetaboKG database: `metabokg-build --data pathways/ --wipe`
2. ✓ Database exists at `.metabokg/meta.sqlite`

## Output

**Terminal format:**
- Markdown tables with emoji headers (🔥 hub metabolites, ⚡ complex reactions, etc.)
- Color-coded risk indicators: 🟢 LOW, 🟡 MED, 🔴 HIGH
- 3-tier recommendations (Immediate, Medium-term, Long-term)
- Full appendix with isolated nodes and dead-end details

**File format:**
- `Analysis_{date}.md` — Full Markdown report, suitable for GitHub, Notion, Obsidian

## Examples

```bash
# Analyze default database
metabokg-analyze

# Save Markdown report
metabokg-analyze --db .metabokg/meta.sqlite --output Analysis_$(date +%Y%m%d).md

# Full details with top 50 items
metabokg-analyze --top 50 --output report.md

# Plain text format for piping or scripting
metabokg-analyze --plain > analysis.txt
```

## Report Sections

1. **📊 Executive Summary** — 5-minute overview with key metrics
2. **📈 Baseline Metrics** — Graph statistics and pathway profiles
3. **🔥 Hub Metabolites** — Compounds in the most reactions
4. **⚡ Complex Reactions** — Multi-substrate orchestrators
5. **🔗 Cross-Pathway Junctions** — Metabolites bridging pathways
6. **📦 Pathway Coupling** — Tightly interdependent pathway pairs
7. **🧬 Topological Patterns** — Dead-ends, isolated nodes
8. **🧪 Top Enzymes** — Broadest catalytic coverage
9. **⚠️  Network Health Issues** — Data quality signals
10. **✅ Metabolic Network Strengths** — Well-designed patterns
11. **💡 Biological Insights & Recommendations** — Actionable next steps

## Learn More

- [MetaboKG CLI Reference](../../CLAUDE.md#metabokg-commands)
- [PathwayAnalyzer Python API](../../README.md#python-api)
- [Metabolic Simulations](../../CLAUDE.md#simulation-and-analysis)
