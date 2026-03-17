"""
analyze.py — MetaKG Thorough Pathway Analysis

Performs comprehensive graph analysis of a MetaKG SQLite database,
analogous to the code_kg thorough repository analysis but applied to
metabolic pathway networks.

Metabolic ↔ Code analogy
─────────────────────────
  Compounds     ↔  Variables / data types
  Reactions     ↔  Functions  (transform inputs → outputs)
  Enzymes       ↔  Method implementations
  Pathways      ↔  Modules / packages
  Hub metabolite (high fan-in)  ↔  Most-called function
  Complex reaction (high fan-out) ↔  Most-calling function (orchestrator)
  Cross-pathway compound  ↔  Shared utility imported by many modules
  Dead-end metabolite     ↔  Orphaned / dead code

Analysis Phases
───────────────
  1. Graph Statistics & Baseline
  2. Hub Metabolite Analysis      — compounds in the most reactions
  3. Complex Reaction Analysis    — reactions with the most participants
  4. Cross-Pathway Hub Detection  — metabolites bridging multiple pathways
  5. Pathway Coupling             — pairs of pathways sharing many compounds
  6. Topological Patterns         — dead-ends, isolated nodes, metabolic cycles
  7. Top Enzymes                  — enzymes catalysing the most reactions
  8. Actionable Biological Insights

Usage::

    from metakg.analyze import PathwayAnalyzer, render_report

    analyzer = PathwayAnalyzer(".metakg/meta.sqlite")
    report   = analyzer.run()
    print(render_report(report))

Or via CLI::

    metakg-analyze --db .metakg/meta.sqlite
    metakg-analyze --db .metakg/meta.sqlite --output report.md

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28 20:55:28

"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------


@dataclass
class HubMetabolite:
    """A compound that participates in many reactions (high connectivity)."""

    node_id: str
    name: str
    formula: str | None
    reaction_count: int
    as_substrate: int
    as_product: int
    pathway_count: int
    xrefs: str | None


@dataclass
class ComplexReaction:
    """A reaction with many substrates, products, and/or enzyme regulators."""

    node_id: str
    name: str
    substrate_count: int
    product_count: int
    enzyme_count: int
    complexity: int  # substrate_count + product_count
    pathway_count: int


@dataclass
class CrossPathwayHub:
    """A compound that appears in two or more distinct pathways."""

    node_id: str
    name: str
    formula: str | None
    pathway_count: int
    pathway_names: list[str]
    reaction_count: int


@dataclass
class PathwayCoupling:
    """Two pathways that share a significant number of compounds."""

    pathway_a_id: str
    pathway_a_name: str
    pathway_b_id: str
    pathway_b_name: str
    shared_count: int
    shared_names: list[str]


@dataclass
class DeadEndMetabolite:
    """A compound with only one reaction connection (potential sink or source)."""

    node_id: str
    name: str
    formula: str | None
    reaction_count: int
    role: str  # "substrate-only", "product-only", or "single-reaction"


@dataclass
class PathwayProfile:
    """Statistics for a single pathway."""

    node_id: str
    name: str
    reaction_count: int
    compound_count: int
    enzyme_count: int


@dataclass
class PathwayAnalysisReport:
    """Full output of :class:`PathwayAnalyzer.run`."""

    db_path: str
    generated_at: str

    # Phase 1
    total_nodes: int
    total_edges: int
    node_counts: dict[str, int]
    edge_counts: dict[str, int]

    # Phase 2
    hub_metabolites: list[HubMetabolite] = field(default_factory=list)

    # Phase 3
    complex_reactions: list[ComplexReaction] = field(default_factory=list)

    # Phase 4
    cross_pathway_hubs: list[CrossPathwayHub] = field(default_factory=list)

    # Phase 5
    pathway_couplings: list[PathwayCoupling] = field(default_factory=list)

    # Phase 6
    dead_end_metabolites: list[DeadEndMetabolite] = field(default_factory=list)
    isolated_nodes: list[dict] = field(default_factory=list)

    # Phase 7
    top_enzymes: list[dict] = field(default_factory=list)

    # Pathway profiles
    pathway_profiles: list[PathwayProfile] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class PathwayAnalyzer:
    """
    Runs the full 7-phase metabolic pathway analysis against a MetaKG database.

    :param db_path: Path to the MetaKG SQLite database.
    :param top_n: How many items to return in ranked lists.
    """

    def __init__(self, db_path: str | Path, *, top_n: int = 20) -> None:
        self.db_path = Path(db_path)
        self.top_n = top_n
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create the database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> PathwayAnalyzer:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Phase 1: baseline stats
    # ------------------------------------------------------------------

    def _phase1_stats(self) -> tuple[int, int, dict[str, int], dict[str, int]]:
        cur = self.conn.cursor()

        cur.execute("SELECT kind, COUNT(*) FROM meta_nodes GROUP BY kind")
        node_counts = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("SELECT rel, COUNT(*) FROM meta_edges GROUP BY rel")
        edge_counts = {r[0]: r[1] for r in cur.fetchall()}

        return (
            sum(node_counts.values()),
            sum(edge_counts.values()),
            node_counts,
            edge_counts,
        )

    # ------------------------------------------------------------------
    # Utility: compound-pathway membership
    # ------------------------------------------------------------------

    def _compound_pathway_membership(self) -> dict[str, set[str]]:
        """
        Build compound_id → {pathway_id, ...} mapping.

        Membership is inferred three ways:
          1. Direct pathway CONTAINS compound edge.
          2. pathway CONTAINS reaction, compound SUBSTRATE_OF reaction.
          3. pathway CONTAINS reaction, reaction PRODUCT_OF compound.
        """
        membership: dict[str, set[str]] = defaultdict(set)

        # 1. Direct
        cur = self.conn.execute(
            """
            SELECT pc.src AS pwy, pc.dst AS cpd
            FROM   meta_edges pc
            JOIN   meta_nodes p ON p.id = pc.src AND p.kind = 'pathway'
            JOIN   meta_nodes c ON c.id = pc.dst AND c.kind = 'compound'
            WHERE  pc.rel = 'CONTAINS'
        """
        )
        for row in cur:
            membership[row[0]].add(row[1])

        # 2. Via substrates
        cur = self.conn.execute(
            """
            SELECT pc.src AS pwy, cs.src AS cpd
            FROM   meta_edges pc
            JOIN   meta_nodes r ON r.id = pc.dst AND r.kind = 'reaction'
            JOIN   meta_edges cs ON cs.dst = r.id AND cs.rel = 'SUBSTRATE_OF'
            WHERE  pc.rel = 'CONTAINS'
        """
        )
        for row in cur:
            membership[row[0]].add(row[1])

        # 3. Via products
        cur = self.conn.execute(
            """
            SELECT pc.src AS pwy, rp.dst AS cpd
            FROM   meta_edges pc
            JOIN   meta_nodes r ON r.id = pc.dst AND r.kind = 'reaction'
            JOIN   meta_edges rp ON rp.src = r.id AND rp.rel = 'PRODUCT_OF'
            WHERE  pc.rel = 'CONTAINS'
        """
        )
        for row in cur:
            membership[row[0]].add(row[1])

        return dict(membership)

    # ------------------------------------------------------------------
    # Phase 2: hub metabolites
    # ------------------------------------------------------------------

    def _phase2_hub_metabolites(self, membership: dict[str, set[str]]) -> list[HubMetabolite]:
        """
        Find compounds that participate in the most reactions.
        Analogous to 'most-called functions' (fan-in) in code analysis.
        """
        # Substrate count per compound
        cur = self.conn.execute(
            """
            SELECT src AS cpd_id, COUNT(*) AS cnt
            FROM   meta_edges
            WHERE  rel = 'SUBSTRATE_OF'
            GROUP  BY src
        """
        )
        substrate_of: dict[str, int] = {r[0]: r[1] for r in cur.fetchall()}

        # Product count per compound
        cur = self.conn.execute(
            """
            SELECT dst AS cpd_id, COUNT(*) AS cnt
            FROM   meta_edges
            WHERE  rel = 'PRODUCT_OF'
            GROUP  BY dst
        """
        )
        product_of: dict[str, int] = {r[0]: r[1] for r in cur.fetchall()}

        # Combine
        all_cpd_ids = set(substrate_of) | set(product_of)
        ranked: list[tuple[int, str]] = []
        for cid in all_cpd_ids:
            sub = substrate_of.get(cid, 0)
            prod = product_of.get(cid, 0)
            ranked.append((sub + prod, cid))

        ranked.sort(reverse=True)

        # Invert membership map: compound → set of pathways
        cpd_to_pathways: dict[str, set[str]] = defaultdict(set)
        for pwy_id, cpd_set in membership.items():
            for cid in cpd_set:
                cpd_to_pathways[cid].add(pwy_id)

        results: list[HubMetabolite] = []
        for _, cid in ranked[: self.top_n]:
            cur2 = self.conn.execute(
                "SELECT name, formula, xrefs FROM meta_nodes WHERE id=?", (cid,)
            )
            row = cur2.fetchone()
            if not row:
                continue
            results.append(
                HubMetabolite(
                    node_id=cid,
                    name=row["name"],
                    formula=row["formula"],
                    reaction_count=substrate_of.get(cid, 0) + product_of.get(cid, 0),
                    as_substrate=substrate_of.get(cid, 0),
                    as_product=product_of.get(cid, 0),
                    pathway_count=len(cpd_to_pathways.get(cid, set())),
                    xrefs=row["xrefs"],
                )
            )

        return results

    # ------------------------------------------------------------------
    # Phase 3: complex reactions
    # ------------------------------------------------------------------

    def _phase3_complex_reactions(self) -> list[ComplexReaction]:
        """
        Find reactions with the most substrates/products/enzymes.
        Analogous to 'most-calling functions' (fan-out) in code analysis.
        """
        cur = self.conn.execute(
            """
            SELECT r.id, r.name,
                   SUM(CASE WHEN e.rel='SUBSTRATE_OF' AND e.dst=r.id THEN 1 ELSE 0 END) AS sub_cnt,
                   SUM(CASE WHEN e.rel='PRODUCT_OF'   AND e.src=r.id THEN 1 ELSE 0 END) AS prd_cnt,
                   SUM(CASE WHEN e.rel='CATALYZES'    AND e.dst=r.id THEN 1 ELSE 0 END) AS enz_cnt
            FROM   meta_nodes r
            LEFT JOIN meta_edges e
                   ON (e.dst = r.id AND e.rel IN ('SUBSTRATE_OF','CATALYZES'))
                   OR (e.src = r.id AND e.rel = 'PRODUCT_OF')
            WHERE  r.kind = 'reaction'
            GROUP  BY r.id
            ORDER  BY (sub_cnt + prd_cnt) DESC
            LIMIT  ?
        """,
            (self.top_n,),
        )

        rows = cur.fetchall()

        # Count pathways per reaction
        cur2 = self.conn.execute(
            """
            SELECT dst AS rxn_id, COUNT(*) AS pwy_cnt
            FROM   meta_edges
            WHERE  rel = 'CONTAINS'
            GROUP  BY dst
        """
        )
        rxn_to_pwy: dict[str, int] = {r[0]: r[1] for r in cur2.fetchall()}

        return [
            ComplexReaction(
                node_id=r["id"],
                name=r["name"],
                substrate_count=r["sub_cnt"] or 0,
                product_count=r["prd_cnt"] or 0,
                enzyme_count=r["enz_cnt"] or 0,
                complexity=(r["sub_cnt"] or 0) + (r["prd_cnt"] or 0),
                pathway_count=rxn_to_pwy.get(r["id"], 0),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Phase 4: cross-pathway hubs
    # ------------------------------------------------------------------

    def _phase4_cross_pathway_hubs(self, membership: dict[str, set[str]]) -> list[CrossPathwayHub]:
        """
        Identify metabolites that appear in two or more distinct pathways.
        These are the 'shared utility' metabolites bridging multiple biological processes.
        """
        # Invert: compound → {pathway_ids}
        cpd_to_pathways: dict[str, set[str]] = defaultdict(set)
        for pwy_id, cpd_set in membership.items():
            for cid in cpd_set:
                cpd_to_pathways[cid].add(pwy_id)

        # Only keep compounds in 2+ pathways
        multi_pwy = {cid: pwys for cid, pwys in cpd_to_pathways.items() if len(pwys) >= 2}

        # Reaction count per compound
        cur = self.conn.execute(
            """
            SELECT src AS cpd, COUNT(*) AS cnt FROM meta_edges WHERE rel='SUBSTRATE_OF' GROUP BY src
            UNION ALL
            SELECT dst AS cpd, COUNT(*) AS cnt FROM meta_edges WHERE rel='PRODUCT_OF'   GROUP BY dst
        """
        )
        rxn_cnt: dict[str, int] = defaultdict(int)
        for row in cur:
            rxn_cnt[row[0]] += row[1]

        # Pathway name lookup
        cur2 = self.conn.execute("SELECT id, name FROM meta_nodes WHERE kind='pathway'")
        pwy_names: dict[str, str] = {r[0]: r[1] for r in cur2.fetchall()}

        results: list[CrossPathwayHub] = []
        for cid, pwy_ids in sorted(multi_pwy.items(), key=lambda x: -len(x[1])):
            cur3 = self.conn.execute("SELECT name, formula FROM meta_nodes WHERE id=?", (cid,))
            row = cur3.fetchone()
            if not row:
                continue
            results.append(
                CrossPathwayHub(
                    node_id=cid,
                    name=row["name"],
                    formula=row["formula"],
                    pathway_count=len(pwy_ids),
                    pathway_names=sorted(pwy_names.get(p, p) for p in pwy_ids),
                    reaction_count=rxn_cnt.get(cid, 0),
                )
            )

        return results[: self.top_n]

    # ------------------------------------------------------------------
    # Phase 5: pathway coupling
    # ------------------------------------------------------------------

    def _phase5_pathway_coupling(self, membership: dict[str, set[str]]) -> list[PathwayCoupling]:
        """
        Find pairs of pathways that share the most compounds.
        Analogous to module-level dependency coupling in code analysis.
        """
        pwy_names_cur = self.conn.execute("SELECT id, name FROM meta_nodes WHERE kind='pathway'")
        pwy_names: dict[str, str] = {r[0]: r[1] for r in pwy_names_cur.fetchall()}

        pwy_ids = list(membership.keys())
        pairs: list[tuple[int, str, str, list[str]]] = []

        for i, a in enumerate(pwy_ids):
            for j in range(i + 1, len(pwy_ids)):
                b = pwy_ids[j]
                shared_cpd_ids = membership[a] & membership[b]
                if not shared_cpd_ids:
                    continue

                # Resolve compound names (limit to top 5 for the report)
                shared_names: list[str] = []
                for cid in list(shared_cpd_ids)[:5]:
                    cur = self.conn.execute("SELECT name FROM meta_nodes WHERE id=?", (cid,))
                    row = cur.fetchone()
                    if row:
                        shared_names.append(row[0])

                pairs.append((len(shared_cpd_ids), a, b, shared_names))

        pairs.sort(reverse=True)

        return [
            PathwayCoupling(
                pathway_a_id=a,
                pathway_a_name=pwy_names.get(a, a),
                pathway_b_id=b,
                pathway_b_name=pwy_names.get(b, b),
                shared_count=cnt,
                shared_names=names,
            )
            for cnt, a, b, names in pairs[: self.top_n]
        ]

    # ------------------------------------------------------------------
    # Phase 6: topological patterns
    # ------------------------------------------------------------------

    def _phase6_topology(self) -> tuple[list[DeadEndMetabolite], list[dict]]:
        """
        Identify dead-end metabolites and isolated nodes.

        Dead-ends: compounds with only 1 reaction connection.
        Isolated:  nodes (any kind) with zero edges at all.
        """
        # Count substrate-of edges per compound
        cur = self.conn.execute(
            """
            SELECT src, COUNT(*) FROM meta_edges WHERE rel='SUBSTRATE_OF' GROUP BY src
        """
        )
        as_sub: dict[str, int] = {r[0]: r[1] for r in cur.fetchall()}

        # Count product-of edges per compound
        cur = self.conn.execute(
            """
            SELECT dst, COUNT(*) FROM meta_edges WHERE rel='PRODUCT_OF' GROUP BY dst
        """
        )
        as_prod: dict[str, int] = {r[0]: r[1] for r in cur.fetchall()}

        cur = self.conn.execute("SELECT id, name, formula FROM meta_nodes WHERE kind='compound'")
        compound_rows = cur.fetchall()

        dead_ends: list[DeadEndMetabolite] = []
        for row in compound_rows:
            cid = row["id"]
            sub = as_sub.get(cid, 0)
            prod = as_prod.get(cid, 0)
            total = sub + prod
            if total == 0:
                continue  # truly isolated — handled separately
            if total == 1:
                if sub > 0:
                    role = "substrate-only"
                elif prod > 0:
                    role = "product-only"
                else:
                    role = "single-reaction"
                dead_ends.append(
                    DeadEndMetabolite(
                        node_id=cid,
                        name=row["name"],
                        formula=row["formula"],
                        reaction_count=total,
                        role=role,
                    )
                )

        # Isolated nodes (no edges at all)
        cur = self.conn.execute(
            """
            SELECT n.id, n.name, n.kind
            FROM   meta_nodes n
            WHERE  n.id NOT IN (SELECT src FROM meta_edges)
              AND  n.id NOT IN (SELECT dst FROM meta_edges)
        """
        )
        isolated: list[dict] = [dict(r) for r in cur.fetchall()]

        return dead_ends, isolated

    # ------------------------------------------------------------------
    # Phase 7: top enzymes
    # ------------------------------------------------------------------

    def _phase7_top_enzymes(self) -> list[dict]:
        """
        Rank enzymes by the number of reactions they catalyse.
        Analogous to 'most-implementing classes' in code analysis.
        """
        cur = self.conn.execute(
            """
            SELECT e.id, e.name, e.ec_number, COUNT(*) AS rxn_cnt
            FROM   meta_nodes e
            JOIN   meta_edges ed ON ed.src = e.id AND ed.rel = 'CATALYZES'
            WHERE  e.kind = 'enzyme'
            GROUP  BY e.id
            ORDER  BY rxn_cnt DESC
            LIMIT  ?
        """,
            (self.top_n,),
        )
        return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Pathway profiles
    # ------------------------------------------------------------------

    def _pathway_profiles(self) -> list[PathwayProfile]:
        """Return per-pathway summary statistics."""
        cur = self.conn.execute("SELECT id, name FROM meta_nodes WHERE kind='pathway'")
        pathways = cur.fetchall()

        profiles: list[PathwayProfile] = []
        for pwy in pathways:
            pid = pwy["id"]

            rxn_cur = self.conn.execute(
                """
                SELECT COUNT(*) FROM meta_edges e
                JOIN meta_nodes r ON r.id = e.dst AND r.kind = 'reaction'
                WHERE e.src = ? AND e.rel = 'CONTAINS'
            """,
                (pid,),
            )
            rxn_cnt = rxn_cur.fetchone()[0]

            # Count distinct compounds reachable via reactions in this pathway
            # (KGML only creates CONTAINS→reaction edges, not CONTAINS→compound)
            cpd_cur = self.conn.execute(
                """
                SELECT COUNT(DISTINCT cpd_id) FROM (
                    SELECT cs.src AS cpd_id
                    FROM   meta_edges pc
                    JOIN   meta_edges cs ON cs.dst = pc.dst AND cs.rel = 'SUBSTRATE_OF'
                    WHERE  pc.src = ? AND pc.rel = 'CONTAINS'
                    UNION
                    SELECT rp.dst AS cpd_id
                    FROM   meta_edges pc
                    JOIN   meta_edges rp ON rp.src = pc.dst AND rp.rel = 'PRODUCT_OF'
                    WHERE  pc.src = ? AND pc.rel = 'CONTAINS'
                )
            """,
                (pid, pid),
            )
            cpd_cnt = cpd_cur.fetchone()[0]

            enz_cur = self.conn.execute(
                """
                SELECT COUNT(DISTINCT enz.id)
                FROM   meta_edges pc
                JOIN   meta_nodes r ON r.id = pc.dst AND r.kind = 'reaction'
                JOIN   meta_edges ec ON ec.dst = r.id AND ec.rel = 'CATALYZES'
                JOIN   meta_nodes enz ON enz.id = ec.src AND enz.kind = 'enzyme'
                WHERE  pc.src = ? AND pc.rel = 'CONTAINS'
            """,
                (pid,),
            )
            enz_cnt = enz_cur.fetchone()[0]

            profiles.append(
                PathwayProfile(
                    node_id=pid,
                    name=pwy["name"],
                    reaction_count=rxn_cnt,
                    compound_count=cpd_cnt,
                    enzyme_count=enz_cnt,
                )
            )

        profiles.sort(key=lambda p: p.reaction_count, reverse=True)
        return profiles

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> PathwayAnalysisReport:
        """
        Execute all analysis phases and return a :class:`PathwayAnalysisReport`.
        """
        # Phase 1
        total_nodes, total_edges, node_counts, edge_counts = self._phase1_stats()

        # Shared computation used by phases 2, 4, 5
        membership = self._compound_pathway_membership()

        # Phase 2
        hub_metabolites = self._phase2_hub_metabolites(membership)

        # Phase 3
        complex_reactions = self._phase3_complex_reactions()

        # Phase 4
        cross_pathway_hubs = self._phase4_cross_pathway_hubs(membership)

        # Phase 5
        pathway_couplings = self._phase5_pathway_coupling(membership)

        # Phase 6
        dead_ends, isolated = self._phase6_topology()

        # Phase 7
        top_enzymes = self._phase7_top_enzymes()

        # Profiles
        profiles = self._pathway_profiles()

        return PathwayAnalysisReport(
            db_path=str(self.db_path),
            generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            total_nodes=total_nodes,
            total_edges=total_edges,
            node_counts=node_counts,
            edge_counts=edge_counts,
            hub_metabolites=hub_metabolites,
            complex_reactions=complex_reactions,
            cross_pathway_hubs=cross_pathway_hubs,
            pathway_couplings=pathway_couplings,
            dead_end_metabolites=dead_ends,
            isolated_nodes=isolated,
            top_enzymes=top_enzymes,
            pathway_profiles=profiles,
        )


# ---------------------------------------------------------------------------
# Report renderer
# ---------------------------------------------------------------------------

_RISK_LABEL = {
    (0, 3): "🟢 LOW",
    (3, 10): "🟡 MED",
    (10, 999): "🔴 HIGH",
}


def _risk(n: int) -> str:
    for (lo, hi), label in _RISK_LABEL.items():
        if lo <= n < hi:
            return label
    return "🔴 HIGH"


def render_report(report: PathwayAnalysisReport, *, markdown: bool = True) -> str:
    """
    Render a :class:`PathwayAnalysisReport` as a Markdown or plain-text string.

    :param report: Report to render.
    :param markdown: If ``True``, use Markdown formatting; otherwise plain text.
    :return: Formatted report string.
    """
    lines: list[str] = []

    def h(level: int, text: str) -> None:
        if markdown:
            lines.append(f"\n{'#' * level} {text}\n")
        else:
            lines.append(f"\n{'=' * level} {text} {'=' * level}\n")

    def row(*cols: str | int) -> str:
        return "| " + " | ".join(str(c) for c in cols) + " |"

    def th(*cols: str | int) -> list[str]:
        header = row(*cols)
        sep = "| " + " | ".join("---" for _ in cols) + " |"
        return [header, sep]

    # ---- Title ----
    h(1, "metaKG_analysis")
    lines.append(f"**Database:** `{report.db_path}`  \n**Generated:** {report.generated_at}\n")

    # ---- Phase 1: Baseline stats ----
    h(2, "Phase 1 — Graph Statistics")

    nc = report.node_counts
    ec = report.edge_counts
    lines.append(f"- **Total nodes:** {report.total_nodes:,}")
    lines.append(f"  - Pathways: {nc.get('pathway', 0):,}")
    lines.append(f"  - Reactions: {nc.get('reaction', 0):,}")
    lines.append(f"  - Compounds: {nc.get('compound', 0):,}")
    lines.append(f"  - Enzymes: {nc.get('enzyme', 0):,}")
    lines.append(f"- **Total edges:** {report.total_edges:,}")
    for rel, cnt in sorted(ec.items(), key=lambda x: -x[1]):
        lines.append(f"  - {rel}: {cnt:,}")

    if report.pathway_profiles:
        h(3, "Pathway Profiles")
        lines.extend(th("Pathway", "Reactions", "Compounds", "Enzymes"))
        for p in report.pathway_profiles:
            lines.append(row(p.name, p.reaction_count, p.compound_count, p.enzyme_count))

    # ---- Phase 2: Hub metabolites ----
    h(2, "Phase 2 — Hub Metabolites (Highest Connectivity)")
    lines.append(
        "_These compounds appear in the most reactions — analogous to the most-called "
        "functions in code. Classic examples: ATP, NAD⁺, CoA._\n"
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

    # ---- Phase 3: Complex reactions ----
    h(2, "Phase 3 — Complex Reactions (Highest Stoichiometric Complexity)")
    lines.append(
        "_Reactions with the most substrates and products — analogous to orchestrator "
        "functions with high fan-out. May indicate multi-step transformations._\n"
    )
    if report.complex_reactions:
        lines.extend(
            th(
                "Rank",
                "Reaction",
                "Substrates",
                "Products",
                "Enzymes",
                "Pathways",
                "Complexity",
            )
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

    # ---- Phase 4: Cross-pathway hubs ----
    h(2, "Phase 4 — Cross-Pathway Hub Metabolites")
    lines.append(
        "_Compounds that bridge multiple distinct pathways — the 'shared utilities' "
        "of metabolism. These are integration points between biological modules._\n"
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

    # ---- Phase 5: Pathway coupling ----
    h(2, "Phase 5 — Pathway Coupling")
    lines.append(
        "_Pairs of pathways sharing the most metabolites — analogous to tightly coupled "
        "modules. High overlap suggests metabolic interdependence._\n"
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

    # ---- Phase 6: Topology ----
    h(2, "Phase 6 — Topological Patterns")

    h(3, "Dead-End Metabolites")
    lines.append(
        "_Compounds involved in only one reaction — analogous to dead code or "
        "terminal data types. May represent pathway endpoints, sinks, or "
        "incompletely parsed data._\n"
    )
    if report.dead_end_metabolites:
        lines.append(f"Found **{len(report.dead_end_metabolites)}** dead-end metabolites.")

        substrate_only = [d for d in report.dead_end_metabolites if d.role == "substrate-only"]
        product_only = [d for d in report.dead_end_metabolites if d.role == "product-only"]

        if substrate_only:
            lines.append(
                f"\n**Substrate-only** ({len(substrate_only)} — pure inputs, never produced):\n"
            )
            lines.extend(th("Compound", "Formula"))
            for d in substrate_only[:10]:
                lines.append(row(d.name, d.formula or "—"))

        if product_only:
            lines.append(
                f"\n**Product-only** ({len(product_only)} — terminal products, never consumed):\n"
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

    # ---- Phase 7: Top enzymes ----
    h(2, "Phase 7 — Top Enzymes by Reaction Coverage")
    lines.append(
        "_Enzymes catalysing the most reactions — the 'busiest workers' of metabolism. "
        "High coverage enzymes are often multi-functional or represent enzyme families._\n"
    )
    if report.top_enzymes:
        lines.extend(th("Rank", "Enzyme", "EC Number", "Reactions Catalysed"))
        for i, enz in enumerate(report.top_enzymes, 1):
            lines.append(
                row(
                    i,
                    enz.get("name", ""),
                    enz.get("ec_number") or "—",
                    enz.get("rxn_cnt", 0),
                )
            )
    else:
        lines.append("_No enzyme–reaction relationships found._")

    # ---- Insights ----
    h(2, "Biological Insights & Recommendations")

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
            "This is expected — cofactors mediate energy transfer across virtually all pathways. "
            "Consider filtering them out when analysing pathway-specific connectivity."
        )

    # Cross-pathway hubs
    if report.cross_pathway_hubs:
        top_hub = report.cross_pathway_hubs[0]
        insights.append(
            f"**Top metabolic junction**: {top_hub.name} appears in {top_hub.pathway_count} "
            f"pathways and {top_hub.reaction_count} reactions, making it a key metabolic "
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
    substrate_only_count = sum(1 for d in report.dead_end_metabolites if d.role == "substrate-only")
    product_only_count = sum(1 for d in report.dead_end_metabolites if d.role == "product-only")
    if substrate_only_count or product_only_count:
        insights.append(
            f"**Dead-end metabolites**: {substrate_only_count} substrate-only and "
            f"{product_only_count} product-only compounds detected. These may represent: "
            "(a) genuine pathway boundaries, (b) metabolites that require additional "
            "pathway data to fully connect, or (c) parsing gaps."
        )

    # Isolated nodes
    if report.isolated_nodes:
        insights.append(
            f"**{len(report.isolated_nodes)} isolated nodes** have no edges. "
            "These are likely parsing artefacts or pathway stubs. "
            "Investigate source files for completeness."
        )

    if report.complex_reactions:
        top_rxn = report.complex_reactions[0]
        insights.append(
            f"**Most complex reaction**: {top_rxn.name} has {top_rxn.substrate_count} "
            f"substrates and {top_rxn.product_count} products (complexity score "
            f"{top_rxn.complexity}). Multi-substrate reactions are often rate-limiting "
            "steps and prime drug targets."
        )

    for insight in insights:
        lines.append(f"\n- {insight}")

    # ---- Footer ----
    lines.append(f"\n\n---\n*Generated by MetaKG pathway analyzer · {report.generated_at}*\n")

    return "\n".join(lines)
