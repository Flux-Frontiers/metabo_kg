---
mode: 'agent'
description: 'Generate a comprehensive metabolic pathway analysis report from the MetaKG database.'
---

# MetaKG Thorough Pathway Analysis

Generate a comprehensive metabolic pathway analysis report from the MetaKG database.

## What This Does

Analyzes the MetaKG database and produces a polished report including:
- **Executive Summary** with key metrics
- **7-Phase Analysis**: hub metabolites, complex reactions, cross-pathway junctions, pathway coupling, topology, and enzyme coverage
- **Network Health Assessment**: identifies dead-ends, isolated nodes, sparse areas
- **Metabolic Network Strengths**: highlights well-designed patterns
- **Biological Insights & Recommendations**: actionable priorities for immediate, medium-term, and long-term research

## Usage

```bash
# Print to terminal
metakg-analyze

# Save to file (with timestamp)
metakg-analyze --output analysis_$(date +%Y%m%d_%H%M%S).md

# Show top N items per ranking
metakg-analyze --top 30

# Plain text format (no Markdown)
metakg-analyze --plain
```

## Before Running

Make sure you have:
1. ✓ Built the MetaKG database: `metakg-build --data pathways/ --wipe`
2. ✓ Database exists at `.metakg/meta.sqlite`

## Output

**Terminal format:**
- Markdown tables with emoji headers (🔥 hub metabolites, ⚡ complex reactions, etc.)
- Color-coded risk indicators: 🟢 LOW, 🟡 MED, 🔴 HIGH
- 3-tier recommendations (Immediate, Medium-term, Long-term)
- Full appendix with isolated nodes and dead-end details

**File format:**
- Full Markdown report, suitable for GitHub, Notion, Obsidian

## Examples

```bash
# Analyze default database
metakg-analyze

# Save Markdown report
metakg-analyze --db .metakg/meta.sqlite --output analysis_$(date +%Y%m%d).md

# Full details with top 50 items
metakg-analyze --top 50 --output report.md

# Plain text format for piping or scripting
metakg-analyze --plain > analysis.txt
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

- [MetaKG CLI Reference](../CLAUDE.md#metakg-commands)
- [PathwayAnalyzer Python API](../README.md#python-api)
- [Metabolic Simulations](../CLAUDE.md#simulations)
