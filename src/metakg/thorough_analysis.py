"""
thorough_analysis.py — Polished MetaKG Metabolic Pathway Analysis Report Renderer

Generates a CodeKG-style comprehensive report with executive summary, emoji headers,
risk indicators, network health assessment, architectural strengths, and structured
biological recommendations.

Usage::

    from metakg.analyze import PathwayAnalyzer
    from metakg.thorough_analysis import render_thorough_report

    with PathwayAnalyzer(".metakg/meta.sqlite", top_n=20) as analyzer:
        report = analyzer.run()

    print(render_thorough_report(report))

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28 21:15:00

"""

from __future__ import annotations

from metakg import __version__
from metakg.analyze import PathwayAnalysisReport


def _risk(n: int) -> str:
    """
    Return a risk emoji indicator based on numeric value.

    :param n: Numeric value (e.g., reaction count).
    :return: Risk emoji string (🟢 LOW, 🟡 MED, 🔴 HIGH).
    """
    for lo, hi, label in [
        (0, 5, "🟢 LOW"),
        (5, 15, "🟡 MED"),
        (15, float("inf"), "🔴 HIGH"),
    ]:
        if lo <= n < hi:
            return label
    return "🔴 HIGH"


def render_thorough_report(report: PathwayAnalysisReport, *, markdown: bool = True) -> str:
    """
    Render a comprehensive metabolic pathway analysis report in CodeKG-style format.

    Features:
    - Executive Summary with KPI table
    - Emoji-enhanced section headers
    - Risk level indicators
    - Network Health Issues assessment
    - Metabolic Network Strengths
    - Structured Biological Insights & Recommendations (3-tier)
    - Appendix with full network details

    :param report: PathwayAnalysisReport from PathwayAnalyzer.run().
    :param markdown: If ``True``, use Markdown formatting; otherwise plain text.
    :return: Formatted report string.
    """
    lines: list[str] = []

    def h(level: int, text: str) -> None:
        """Add header at specified level."""
        if markdown:
            lines.append(f"\n{'#' * level} {text}\n")
        else:
            lines.append(f"\n{'=' * level} {text} {'=' * level}\n")

    def row(*cols: str | int) -> str:
        """Format a markdown table row."""
        return "| " + " | ".join(str(c) for c in cols) + " |"

    def th(*cols: str | int) -> list[str]:
        """Format markdown table header and separator."""
        header = row(*cols)
        sep = "| " + " | ".join("---" for _ in cols) + " |"
        return [header, sep]

    # ---- Metadata badge ----
    lines.append("> **Analysis Report Metadata**")
    lines.append(f"> - **Generated:** {report.generated_at}")
    lines.append(f"> - **Version:** MetaKG {__version__}")
    lines.append(f"> - **Database:** `{report.db_path}`\n")

    # ---- Title ----
    h(1, "MetaKG Metabolic Pathway Analysis Report")

    # ---- Executive Summary ----
    h(2, "📊 Executive Summary")
    lines.append(
        "This report provides a comprehensive metabolic network analysis using MetaKG's "
        "knowledge graph. The analysis identifies hub metabolites, complex reactions, "
        "cross-pathway junctions, coupling patterns, and network topology.\n"
    )

    nc = report.node_counts
    ec = report.edge_counts
    sub_only = sum(1 for d in report.dead_end_metabolites if d.role == "substrate-only")
    prod_only = sum(1 for d in report.dead_end_metabolites if d.role == "product-only")

    lines.append("**Key Findings:**")
    lines.append(
        f"- **Total entities:** {nc.get('pathway', 0)} pathways, "
        f"{nc.get('reaction', 0)} reactions, {nc.get('compound', 0)} compounds, "
        f"{nc.get('enzyme', 0)} enzymes"
    )
    lines.append(
        f"- **Hub metabolites:** {len(report.hub_metabolites)} high-connectivity compounds"
    )
    lines.append(
        f"- **Cross-pathway hubs:** {len(report.cross_pathway_hubs)} compounds bridging pathways"
    )
    lines.append(
        f"- **Network health:** {100 - len(report.isolated_nodes) // max(1, report.total_nodes) * 100:.0f}% connected, "
        f"{len(report.dead_end_metabolites)} dead-ends\n"
    )

    # ---- Baseline Metrics ----
    h(2, "📈 Baseline Metrics")

    lines.extend(th("Metric", "Value"))
    lines.append(row("**Total Nodes**", f"{report.total_nodes:,}"))
    lines.append(row("**Total Edges**", f"{report.total_edges:,}"))
    lines.append(row("**Pathways**", nc.get("pathway", 0)))
    lines.append(row("**Reactions**", nc.get("reaction", 0)))
    lines.append(row("**Compounds**", nc.get("compound", 0)))
    lines.append(row("**Enzymes**", nc.get("enzyme", 0)))

    # Edge distribution
    lines.append("\n### Edge Distribution\n")
    lines.extend(th("Relationship Type", "Count"))
    for rel, cnt in sorted(ec.items(), key=lambda x: -x[1]):
        lines.append(row(rel, f"{cnt:,}"))

    # Pathway profiles
    if report.pathway_profiles:
        lines.append("\n### Pathway Profiles\n")
        lines.extend(th("Pathway", "Reactions", "Compounds", "Enzymes"))
        for p in report.pathway_profiles:
            lines.append(row(p.name, p.reaction_count, p.compound_count, p.enzyme_count))

    # ---- Hub Metabolites ----
    h(2, "🔥 Hub Metabolites (Highest Connectivity)")
    lines.append(
        "_Compounds in the most reactions — analogous to the most-called functions in code. "
        "These are metabolic hubs, often cofactors or energy carriers._\n"
    )
    if report.hub_metabolites:
        lines.extend(
            th(
                "Rank",
                "Compound",
                "Formula",
                "Reactions",
                "Substrate",
                "Product",
                "Pathways",
                "Load",
            )
        )
        for i, h_met in enumerate(report.hub_metabolites, 1):
            lines.append(
                row(
                    i,
                    h_met.name,
                    h_met.formula or "—",
                    h_met.reaction_count,
                    h_met.as_substrate,
                    h_met.as_product,
                    h_met.pathway_count,
                    _risk(h_met.reaction_count),
                )
            )
    else:
        lines.append("_No compound–reaction edges found. Build the knowledge graph first._")

    # ---- Complex Reactions ----
    h(2, "⚡ Complex Reactions (Highest Stoichiometric Complexity)")
    lines.append(
        "_Reactions with the most substrates and products — orchestrators in metabolism. "
        "Often rate-limiting steps or allosteric control points._\n"
    )
    if report.complex_reactions:
        lines.extend(
            th("Rank", "Reaction", "Substrates", "Products", "Enzymes", "Pathways", "Complexity")
        )
        for i, rxn in enumerate(report.complex_reactions, 1):
            lines.append(
                row(
                    i,
                    rxn.name,
                    rxn.substrate_count,
                    rxn.product_count,
                    rxn.enzyme_count,
                    rxn.pathway_count,
                    _risk(rxn.complexity),
                )
            )
    else:
        lines.append("_No reactions found._")

    # ---- Cross-pathway hubs ----
    h(2, "🔗 Cross-Pathway Metabolic Junctions")
    lines.append(
        "_Compounds bridging multiple distinct pathways — integration points where "
        "metabolic modules communicate. These are prime regulatory targets._\n"
    )
    if report.cross_pathway_hubs:
        lines.extend(th("Rank", "Compound", "Formula", "Pathways", "Reactions", "Examples"))
        for i, hub in enumerate(report.cross_pathway_hubs, 1):
            example_pwys = "; ".join(hub.pathway_names[:3])
            if len(hub.pathway_names) > 3:
                example_pwys += f" (+{len(hub.pathway_names) - 3} more)"
            lines.append(
                row(
                    i,
                    hub.name,
                    hub.formula or "—",
                    hub.pathway_count,
                    hub.reaction_count,
                    example_pwys,
                )
            )
    else:
        lines.append("_No cross-pathway metabolites detected._")

    # ---- Pathway coupling ----
    h(2, "📦 Pathway Coupling")
    lines.append(
        "_Pathway pairs sharing the most metabolites — tightly coupled metabolic modules. "
        "High overlap indicates co-regulation and interdependence._\n"
    )
    if report.pathway_couplings:
        lines.extend(th("Pathway A", "Pathway B", "Shared Compounds", "Examples"))
        for coupling in report.pathway_couplings:
            examples = ", ".join(coupling.shared_names[:3])
            if coupling.shared_count > 3:
                examples += f" (+{coupling.shared_count - 3} more)"
            lines.append(
                row(
                    coupling.pathway_a_name,
                    coupling.pathway_b_name,
                    coupling.shared_count,
                    examples,
                )
            )
    else:
        lines.append("_No pathway coupling detected._")

    # ---- Topological patterns ----
    h(2, "🧬 Topological Patterns")

    h(3, "Dead-End Metabolites")
    lines.append(
        "_Compounds with only one reaction connection — potential pathway endpoints, "
        "sinks, or data gaps._\n"
    )
    if report.dead_end_metabolites:
        lines.append(f"Found **{len(report.dead_end_metabolites)}** dead-end metabolites.\n")

        substrate_only = [d for d in report.dead_end_metabolites if d.role == "substrate-only"]
        product_only = [d for d in report.dead_end_metabolites if d.role == "product-only"]

        if substrate_only:
            lines.append(
                f"**Substrate-only** ({len(substrate_only)} — pure inputs, never produced):\n"
            )
            lines.extend(th("Compound", "Formula"))
            for d in substrate_only[:10]:
                lines.append(row(d.name, d.formula or "—"))

        if product_only:
            lines.append(
                f"\n**Product-only** ({len(product_only)} — terminal outputs, never consumed):\n"
            )
            lines.extend(th("Compound", "Formula"))
            for d in product_only[:10]:
                lines.append(row(d.name, d.formula or "—"))
    else:
        lines.append("_No dead-end metabolites found._")

    h(3, "Isolated Nodes")
    if report.isolated_nodes:
        lines.append(f"Found **{len(report.isolated_nodes)}** nodes with zero edges:\n")
        lines.extend(th("ID", "Name", "Kind"))
        for n in report.isolated_nodes[:15]:
            lines.append(row(n.get("id", ""), n.get("name", ""), n.get("kind", "")))
    else:
        lines.append("_No isolated nodes — all entities are connected._")

    # ---- Top enzymes ----
    h(2, "🧪 Top Enzymes by Reaction Coverage")
    lines.append(
        "_Enzymes catalysing the most reactions — the busiest workers of metabolism. "
        "High coverage indicates multifunctionality or enzyme families._\n"
    )
    if report.top_enzymes:
        lines.extend(th("Rank", "Enzyme", "EC Number", "Reactions Catalysed"))
        for i, enz in enumerate(report.top_enzymes, 1):
            lines.append(
                row(i, enz.get("name", ""), enz.get("ec_number") or "—", enz.get("rxn_cnt", 0))
            )
    else:
        lines.append("_No enzyme–reaction relationships found._")

    # ---- Network Health Issues ----
    h(2, "⚠️  Network Health Issues")
    health_issues: list[str] = []

    if len(report.dead_end_metabolites) > 0:
        health_issues.append(
            f"- **{len(report.dead_end_metabolites)} dead-end metabolites** "
            f"({sub_only} substrate-only, {prod_only} product-only) — may indicate "
            "incomplete pathway data or genuine metabolic boundaries"
        )

    if report.isolated_nodes:
        health_issues.append(
            f"- **{len(report.isolated_nodes)} isolated nodes** — likely parsing artefacts "
            "or incomplete pathway definitions"
        )

    if not report.hub_metabolites:
        health_issues.append("- **No hub metabolites detected** — sparse or incomplete network")

    if health_issues:
        for issue in health_issues:
            lines.append(issue)
    else:
        lines.append("✓ No significant health issues detected.")

    # ---- Metabolic Network Strengths ----
    h(2, "✅ Metabolic Network Strengths")
    strengths: list[str] = []

    if report.pathway_profiles:
        avg_reactions = sum(p.reaction_count for p in report.pathway_profiles) // len(
            report.pathway_profiles
        )
        strengths.append(
            f"✓ **Well-connected pathways** — {len(report.pathway_profiles)} pathways, "
            f"avg {avg_reactions} reactions each"
        )

    if len(report.cross_pathway_hubs) > 0:
        strengths.append(
            f"✓ **Strong metabolic integration** — {len(report.cross_pathway_hubs)} cross-pathway junctions "
            "indicating interdependent metabolic modules"
        )

    if not report.isolated_nodes:
        strengths.append("✓ **All entities connected** — no orphaned nodes in the network")

    if len(report.pathway_couplings) > 0:
        strengths.append(
            f"✓ **Coupled pathway architecture** — {len(report.pathway_couplings)} pathway pairs "
            "show metabolic interdependence"
        )

    if strengths:
        for strength in strengths:
            lines.append(strength)
    else:
        lines.append("⚠️  Network structure unclear — insufficient data to assess strengths.")

    # ---- Biological Insights & Recommendations ----
    h(2, "💡 Biological Insights & Recommendations")

    h(3, "Key Findings")

    insights: list[str] = []

    # Cofactor hubs
    cofactor_keywords = {
        "atp",
        "adp",
        "amp",
        "nad",
        "nadh",
        "nadph",
        "nadp",
        "coa",
        "coenzyme a",
        "fad",
        "fadh",
        "gtp",
        "gdp",
        "ump",
        "ctp",
    }
    cofactors_found = [
        h_met
        for h_met in report.hub_metabolites[:10]
        if any(kw in h_met.name.lower() for kw in cofactor_keywords)
    ]
    if cofactors_found:
        names = ", ".join(h_met.name for h_met in cofactors_found[:4])
        insights.append(
            f"**Energy cofactor dominance**: {names} are among the top hub metabolites. "
            "This is expected — cofactors mediate energy transfer across all pathways. "
            "Consider filtering them when studying pathway-specific connectivity."
        )

    # Cross-pathway hubs
    if report.cross_pathway_hubs:
        top_hub = report.cross_pathway_hubs[0]
        insights.append(
            f"**Top metabolic junction**: {top_hub.name} appears in {top_hub.pathway_count} "
            f"pathways and {top_hub.reaction_count} reactions, making it a critical metabolic "
            "integration point. Perturbations here may have wide-ranging systemic effects."
        )

    # Pathway coupling
    if report.pathway_couplings:
        top_couple = report.pathway_couplings[0]
        insights.append(
            f"**Tightest pathway coupling**: {top_couple.pathway_a_name} ↔ "
            f"{top_couple.pathway_b_name} share {top_couple.shared_count} compounds. "
            "These pathways are metabolically interdependent and should be analysed together."
        )

    # Dead ends
    if sub_only > 0 or prod_only > 0:
        insights.append(
            f"**Dead-end metabolites**: {sub_only} substrate-only and {prod_only} product-only "
            "compounds detected. These may represent: (a) genuine pathway boundaries, "
            "(b) metabolites requiring additional pathway data, or (c) parsing gaps."
        )

    # Isolated
    if report.isolated_nodes:
        insights.append(
            f"**{len(report.isolated_nodes)} isolated nodes** have no edges. "
            "These are likely parsing artefacts or pathway stubs. Investigate source files."
        )

    # Complex reactions
    if report.complex_reactions:
        top_rxn = report.complex_reactions[0]
        insights.append(
            f"**Most complex reaction**: {top_rxn.name} has {top_rxn.substrate_count} "
            f"substrates and {top_rxn.product_count} products (complexity {_risk(top_rxn.complexity)}). "
            "Multi-substrate reactions are often rate-limiting steps and prime drug targets."
        )

    for insight in insights:
        lines.append(f"\n- {insight}")

    # Immediate research priorities
    h(3, "Immediate Research Priorities")
    lines.append(
        "1. **Review bottleneck reactions** — Complex reactions (Phase 3) are often rate-limiting "
        "steps; prioritize experimental validation\n"
    )
    lines.append(
        "2. **Investigate hub metabolites** — Understand regulation of high-connectivity compounds; "
        "they are often drug targets\n"
    )
    lines.append(
        "3. **Resolve dead-end metabolites** — Determine if they represent genuine pathway boundaries "
        "or incomplete data; validate source files\n"
    )

    # Medium-term analysis
    h(3, "Medium-term Analysis")
    lines.append(
        "1. **Pathway enrichment analysis** — Correlate pathway coupling patterns with known "
        "biological co-regulation\n"
    )
    lines.append(
        "2. **Enzyme target prioritization** — Score enzymes by connectivity, pathway count, "
        "and known inhibitors\n"
    )
    lines.append(
        "3. **Cross-pathway regulation study** — Map regulatory interactions between coupled pathways "
        "using Phase 5 data\n"
    )

    # Long-term modeling
    h(3, "Long-term Metabolic Modeling")
    lines.append("Use MetaKG's simulation tools to build predictive models:\n")
    lines.append(
        "- **Steady-state analysis**: `metakg-simulate fba --pathway <id>` — "
        "Predict metabolic fluxes at equilibrium\n"
    )
    lines.append(
        "- **Kinetic dynamics**: `metakg-simulate ode --pathway <id>` — "
        "Model time-course concentration changes with enzyme kinetics\n"
    )
    lines.append(
        "- **Perturbation analysis**: `metakg-simulate whatif --pathway <id>` — "
        "Predict effects of enzyme knockouts, inhibitions, or metabolite overrides\n"
    )

    # ---- Appendix ----
    h(2, "📋 Appendix: Network Details")

    h(3, "All Isolated Nodes")
    if report.isolated_nodes:
        lines.extend(th("ID", "Name", "Kind"))
        for n in report.isolated_nodes:
            lines.append(row(n.get("id", ""), n.get("name", ""), n.get("kind", "")))
    else:
        lines.append("_(No isolated nodes.)_")

    h(3, "All Dead-End Metabolites")
    if report.dead_end_metabolites:
        lines.extend(th("Compound", "Formula", "Role", "Reaction Count"))
        for d in report.dead_end_metabolites:
            lines.append(row(d.name, d.formula or "—", d.role, d.reaction_count))
    else:
        lines.append("_(No dead-end metabolites.)_")

    # ---- Footer ----
    lines.append(
        f"\n\n---\n*Generated by MetaKG thorough pathway analyzer · {report.generated_at}*\n"
    )

    return "\n".join(lines)
