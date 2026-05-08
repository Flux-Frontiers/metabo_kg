#!/usr/bin/env python3
"""Runnable companion to docs/EXAMPLES.md and article/metabokg_article.tex.

Each ``ex_*`` function reproduces one block from the docs and prints the
actual output it produces, so the documentation can be kept in lock-step
with the live system. Run a specific example by name::

    poetry run python scripts/examples.py ex_06_fba

Run everything (default)::

    poetry run python scripts/examples.py

Assumes ``metabokg-init`` (or per-corpus ``metabokg-build``) has populated
``data/{hsa,cge,icho}_pathways/.metabokg/*.sqlite``.

Author: Eric G. Suchanek, PhD
Last Revision: 2026-05-07 19:50:27
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from metabokg import MetaKG  # noqa: E402
from metabokg.analyze import PathwayAnalyzer  # noqa: E402
from metabokg.primitives import PATHWAY_CATEGORY_METABOLIC  # noqa: E402

HSA_DB = str(REPO_ROOT / "data/hsa_pathways/.metabokg/hsa.sqlite")
HSA_LANCE = str(REPO_ROOT / "data/hsa_pathways/.metabokg/lancedb")
CGE_DB = str(REPO_ROOT / "data/cge_pathways/.metabokg/cge.sqlite")
CGE_LANCE = str(REPO_ROOT / "data/cge_pathways/.metabokg/lancedb")


def _section(title: str) -> None:
    bar = "=" * 78
    print(f"\n{bar}\n{title}\n{bar}")


def ex_01_build_stats() -> None:
    """EXAMPLES.md §1 / article §8.1 — build stats."""
    _section("ex_01_build_stats — graph stats (hsa)")
    with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
        s = kg.store.stats()
        nc = s["node_counts"]
        ec = s["edge_counts"]
        print(f"nodes={s['total_nodes']}  edges={s['total_edges']}")
        print(
            f"  compounds={nc.get('compound', 0)}  enzymes={nc.get('enzyme', 0)}  "
            f"pathways={nc.get('pathway', 0)}  reactions={nc.get('reaction', 0)}"
        )
        if kg.index is not None:
            idx = kg.index.stats()
            print(f"indexed={idx['indexed_rows']}  dim={idx['dim']}")
        print("\nedge breakdown:")
        for rel in sorted(ec):
            print(f"  {rel:<14} {ec[rel]}")


def ex_02_query_pathway() -> None:
    """EXAMPLES.md §2 — semantic pathway search."""
    _section('ex_02_query_pathway — query_pathway("fatty acid oxidation", k=5)')
    with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
        results = kg.query_pathway("fatty acid oxidation", k=5)
        for hit in results.hits:
            score = 1.0 - hit["_distance"] / 2.0
            print(f"{hit['name']:<40}  score={score:.3f}")


def ex_02b_query_pathway_article() -> None:
    """article §8.4 — semantic search, beta-oxidation phrasing, raw distance."""
    _section('ex_02b_query_pathway_article — "fatty acid beta-oxidation"')
    with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
        result = kg.query_pathway("fatty acid beta-oxidation", k=5)
        for hit in result.hits:
            print(f"{hit['name']:40s}  dist={hit['_distance']:.3f}")


def ex_03_pathway_category_filter() -> None:
    """EXAMPLES.md §2 — filter pathways by category."""
    _section("ex_03_pathway_category_filter — metabolic pathways")
    with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
        pathways = kg.store.all_nodes(
            kind="pathway",
            category=PATHWAY_CATEGORY_METABOLIC,
        )
        print(f"{len(pathways)} metabolic pathways")


def ex_04_node_lookup() -> None:
    """EXAMPLES.md §3 — node lookup, reaction detail, neighbours, resolve_id."""
    _section("ex_04_node_lookup — store.node / reaction_detail / neighbours")
    with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
        pyruvate = kg.store.node("cpd:kegg:C00022")
        print(f"compound name:    {pyruvate['name']}")
        print(f"compound formula: {pyruvate.get('formula')}")

        rxn = kg.store.reaction_detail("rxn:kegg:R00200")
        print(f"\nR00200 substrates: {[s['name'] for s in rxn['substrates']]}")
        print(f"R00200 products:   {[p['name'] for p in rxn['products']]}")
        print(f"R00200 enzymes:    {[e['name'] for e in rxn['enzymes']]}")

        nbrs = kg.store.neighbours("cpd:kegg:C00092", rels=("SUBSTRATE_OF",))
        print("\nFirst 4 reactions consuming G6P (cpd:kegg:C00092):")
        for rxn_id in nbrs[:4]:
            node = kg.store.node(rxn_id)
            print(f"  {rxn_id}: {node['name']}")

        node_id = kg.store.resolve_id("Glycolysis / Gluconeogenesis")
        print(f"\nresolve_id('Glycolysis / Gluconeogenesis') -> {node_id}")


def ex_05_find_path() -> None:
    """EXAMPLES.md §4 + article §8.3 — shortest-path search."""
    _section("ex_05_find_path — glucose to acetyl-CoA / pyruvate")
    with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
        result = kg.find_path(
            "cpd:kegg:C00031",
            "cpd:kegg:C00024",
            max_hops=8,
        )
        print("Glucose -> Acetyl-CoA (max_hops=8)")
        if "error" in result:
            print(f"  error: {result['error']}")
        else:
            names = [n["name"] for n in result["path"]]
            print(f"  hops={result['hops']}: {' -> '.join(names)}")

        result2 = kg.find_path(
            "cpd:kegg:C00031",
            "cpd:kegg:C00022",
            max_hops=12,
        )
        print("\nGlucose -> Pyruvate (max_hops=12)")
        if "error" in result2:
            print(f"  error: {result2['error']}")
        else:
            print(f"  Path length: {result2['hops']} steps")
            for node in result2["path"]:
                print(f"    {node['kind']:10s} {node['name']}")

        nbrs = kg.store.neighbours("cpd:kegg:C00002", rels=("CONTAINS",))
        print(f"\nATP participates in {len(nbrs)} contexts (CONTAINS edges)")


def ex_06_fba() -> None:
    """EXAMPLES.md §5 — Flux Balance Analysis on glycolysis."""
    _section("ex_06_fba — simulate_fba on hsa00010")
    with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
        result = kg.simulate_fba("pwy:kegg:hsa00010", maximize=True)
        print(f"Status:    {result['status']}")
        obj = result.get("objective_value", 0.0)
        print(f"Objective: {obj:.4f}")
        fluxes = result.get("fluxes", {})
        top = sorted(fluxes.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        for rxn_id, flux in top:
            print(f"  {rxn_id}  {flux:+.4f}")


def ex_07_ode() -> None:
    """EXAMPLES.md §6 — ODE time-course simulation."""
    _section("ex_07_ode — simulate_ode on hsa00010")
    with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
        result = kg.simulate_ode(
            "pwy:kegg:hsa00010",
            t_end=20,
            t_points=50,
            initial_concentrations={"cpd:kegg:C00031": 5.0},
        )
        print(f"Status: {result['status']}")
        finals = {c: v[-1] for c, v in result["concentrations"].items() if v}
        top = sorted(finals.items(), key=lambda x: x[1], reverse=True)[:5]
        for cpd_id, conc in top:
            node = kg.store.node(cpd_id)
            label = (node["name"] or cpd_id) if node else cpd_id
            print(f"  {label:<50}  {conc:.4f} mM")


def ex_08_whatif_fba() -> None:
    """EXAMPLES.md §7 — what-if FBA, hexokinase knockout."""
    _section("ex_08_whatif_fba — HK knockout (enz:kegg:hsa:2539)")
    with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
        scenario = {
            "name": "hexokinase_knockout",
            "enzyme_knockouts": ["enz:kegg:hsa:2539"],
        }
        result = kg.simulate_whatif(
            json.dumps(scenario),
            "pwy:kegg:hsa00010",
            mode="fba",
        )
        baseline = result["baseline"].get("objective_value", 0.0)
        perturbed = result["perturbed"].get("objective_value", 0.0)
        denom = baseline if baseline else 1.0
        pct = 100.0 * (perturbed - baseline) / denom
        print(f"Baseline obj:  {baseline:.4f}")
        print(f"Perturbed obj: {perturbed:.4f}")
        print(f"Objective change: {pct:+.1f}%")
        deltas = result.get("delta_fluxes", {})
        if deltas:
            top = sorted(deltas.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
            for rxn_id, delta in top:
                print(f"  {rxn_id}  delta_flux={delta:+.4f}")


def ex_09_whatif_ode() -> None:
    """EXAMPLES.md §7 — what-if ODE, high glucose + LDHA knockout."""
    _section("ex_09_whatif_ode — high glucose + LDHA knockout")
    with MetaKG(db_path=HSA_DB, lancedb_dir=HSA_LANCE) as kg:
        scenario = {
            "name": "high_glucose_no_ldha",
            "enzyme_knockouts": ["enz:kegg:hsa:3939"],
            "initial_conc_overrides": {"cpd:kegg:C00031": 10.0},
        }
        result = kg.simulate_whatif(
            json.dumps(scenario),
            "pwy:kegg:hsa00010",
            mode="ode",
        )
        deltas = result.get("delta_final_conc", {})
        if not deltas:
            print("(no delta_final_conc returned)")
            return
        top = sorted(deltas.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        for cpd_id, delta in top:
            node = kg.store.node(cpd_id)
            label = (node["name"] or cpd_id) if node else cpd_id
            print(f"  {label:<30}  delta_final={delta:+.4f} mM")


def ex_10_cho_stats() -> None:
    """EXAMPLES.md §8 — CHO graph stats."""
    _section("ex_10_cho_stats — graph stats (cge)")
    with MetaKG(db_path=CGE_DB, lancedb_dir=CGE_LANCE) as kg:
        s = kg.store.stats()
        print(f"CHO graph: {s['total_nodes']} nodes, {s['total_edges']} edges")


def ex_11_cho_ode_glycolysis() -> None:
    """EXAMPLES.md §8 — CHO glycolysis ODE under fed-batch initial conditions."""
    _section("ex_11_cho_ode_glycolysis — cge00010 fed-batch")
    init_concs = {
        "cpd:kegg:C00031": 8.0,
        "cpd:kegg:C00022": 0.1,
        "cpd:kegg:C00186": 0.5,
    }
    with MetaKG(db_path=CGE_DB, lancedb_dir=CGE_LANCE) as kg:
        result = kg.simulate_ode(
            "pwy:kegg:cge00010",
            t_end=20,
            t_points=100,
            initial_concentrations=init_concs,
        )
        finals = {c: v[-1] for c, v in result["concentrations"].items() if v}
        lactate = finals.get("cpd:kegg:C00186")
        pyruvate = finals.get("cpd:kegg:C00022")
        print(f"Status: {result['status']}")
        print(
            "Lactate [final]:  " + (f"{lactate:.3f} mM" if lactate is not None else "not tracked")
        )
        print(
            "Pyruvate [final]: " + (f"{pyruvate:.3f} mM" if pyruvate is not None else "not tracked")
        )


def ex_12_cho_ldha_knockdown() -> None:
    """EXAMPLES.md §8 — CHO LDHA knockdown what-if."""
    _section("ex_12_cho_ldha_knockdown — cge00010 LDHA at 20% activity")
    with MetaKG(db_path=CGE_DB, lancedb_dir=CGE_LANCE) as kg:
        scenario = {
            "name": "LDHA_80pct_knockdown",
            "enzyme_factors": {"enz:kegg:cge:3939": 0.2},
        }
        result = kg.simulate_whatif(
            json.dumps(scenario),
            "pwy:kegg:cge00010",
            mode="ode",
        )
        deltas = result.get("delta_final_conc", {})
        lactate_delta = deltas.get("cpd:kegg:C00186", 0.0)
        print(f"Lactate delta_final: {lactate_delta:+.3f} mM (negative = reduction)")


def ex_13_cho_tca_high_glutamine() -> None:
    """EXAMPLES.md §8 — CHO TCA flux under high glutamine."""
    _section("ex_13_cho_tca_high_glutamine — cge00020 FBA")
    with MetaKG(db_path=CGE_DB, lancedb_dir=CGE_LANCE) as kg:
        scenario = {
            "name": "high_glutamine_tca",
            "initial_conc_overrides": {
                "cpd:kegg:C00025": 4.0,
                "cpd:kegg:C00026": 1.0,
            },
        }
        result = kg.simulate_whatif(
            json.dumps(scenario),
            "pwy:kegg:cge00020",
            mode="fba",
        )
        b = result["baseline"].get("objective_value", 0.0)
        p = result["perturbed"].get("objective_value", 0.0)
        print(f"Baseline objective:  {b:.4f}")
        print(f"Perturbed objective: {p:.4f}")


def ex_14_cho_kinetics() -> None:
    """EXAMPLES.md §8 — inspect CHO kinetic params for hexokinase."""
    _section("ex_14_cho_kinetics — kinetic params for R00299")
    with MetaKG(db_path=CGE_DB, lancedb_dir=CGE_LANCE) as kg:
        all_params = kg.store.all_kinetic_params()
        params = [p for p in all_params if p.get("reaction_id") == "rxn:kegg:R00299"]
        if not params:
            print("(no params for rxn:kegg:R00299 — run `metabokg-simulate seed-cho`)")
            return
        for p in params:
            print(
                f"  Km={p.get('km')} mM  Vmax={p.get('vmax')} mM/s  "
                f"source={p.get('source_database')}  confidence={p.get('confidence')}"
            )


def ex_15_pathway_analyzer() -> None:
    """EXAMPLES.md §10 — PathwayAnalyzer hub metabolites."""
    _section("ex_15_pathway_analyzer — top hubs")
    with PathwayAnalyzer(HSA_DB) as analyzer:
        report = analyzer.run()
        print(f"Total nodes: {report.total_nodes}")
        print("Hub metabolites (top 5):")
        for m in report.hub_metabolites[:5]:
            print(f"  {m.name:<30}  pathways={m.pathway_count}  reactions={m.reaction_count}")
        print("Cross-pathway hubs (top 5):")
        for h in report.cross_pathway_hubs[:5]:
            print(f"  {h.name:<30}  pathways={h.pathway_count}  reactions={h.reaction_count}")


EXAMPLES = [
    ex_01_build_stats,
    ex_02_query_pathway,
    ex_02b_query_pathway_article,
    ex_03_pathway_category_filter,
    ex_04_node_lookup,
    ex_05_find_path,
    ex_06_fba,
    ex_07_ode,
    ex_08_whatif_fba,
    ex_09_whatif_ode,
    ex_10_cho_stats,
    ex_11_cho_ode_glycolysis,
    ex_12_cho_ldha_knockdown,
    ex_13_cho_tca_high_glutamine,
    ex_14_cho_kinetics,
    ex_15_pathway_analyzer,
]


def main() -> int:
    requested = sys.argv[1:]
    selected = [fn for fn in EXAMPLES if fn.__name__ in requested] if requested else EXAMPLES
    if requested and not selected:
        names = "\n  ".join(fn.__name__ for fn in EXAMPLES)
        print(f"unknown example(s): {requested}\n\navailable:\n  {names}")
        return 2

    failed: list[tuple[str, BaseException]] = []
    for fn in selected:
        try:
            fn()
        except Exception as exc:
            failed.append((fn.__name__, exc))
            print(f"\n[ERROR] {fn.__name__}: {exc}")
            traceback.print_exc()

    if failed:
        print(f"\n{len(failed)} example(s) failed:")
        for name, exc in failed:
            print(f"  - {name}: {exc}")
        return 1
    print("\nall examples completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
