"""
mcp_tools.py — the MetaKG MCP server, on the fleet's shared base ``kg_utils.mcp``.

The server answers the fleet's canonical tools -- ``stats``, ``query``,
``pack``, ``get_node``, ``neighbors`` -- under the same names as every other
KG server, then MetaKG's own::

    query_pathway(name, k)                      — semantic pathway search
    get_compound(id)                            — compound + connected reactions
    get_reaction(id)                            — full stoichiometric detail
    find_path(compound_a, compound_b, max_hops) — shortest metabolic path
    simulate_fba / simulate_ode / simulate_whatif
                                                — FBA, ODE time course, perturbation
    get_kinetic_params(reaction_id)             — stored Km/Vmax/kcat
    seed_kinetics(force)                        — curated literature kinetics
    snapshot_list / snapshot_show / snapshot_diff
                                                — the graph's history across builds

``query`` and ``pack`` are MetaKG's own search through ``server.canonical``.
The tool list is generated from the tools themselves: ``metabokg mcp
--manifest`` prints it as JSON without opening the graph.

The ``_mcp_*`` handlers take the :class:`~metabokg.orchestrator.MetaKG`
explicitly, so they are unit-testable without a server; each tool wraps one
and takes its description from it.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kg_utils.mcp import Context, KGServer, kg_from, make_server

if TYPE_CHECKING:
    from metabokg.orchestrator import MetaKG


# ---------------------------------------------------------------------------
# Module-level handler functions — unit-testable without FastMCP
# ---------------------------------------------------------------------------


def _mcp_query_pathway(metabokg: MetaKG, name: str, k: int = 8) -> str:
    """
    Find metabolic pathways by name or description using semantic search.

    :param name: Pathway name or description, e.g. ``"glycolysis"`` or
        ``"fatty acid beta oxidation"``.
    :param k: Maximum results to return (default 8).
    :return: JSON list of matching pathway nodes with ``member_count`` field.
    """
    result = metabokg.query_pathway(name, k=k)
    return result.to_json()


def _mcp_get_compound(metabokg: MetaKG, compound_id: str) -> str:
    """
    Retrieve a compound node by its internal ID or external database ID.

    Accepts internal IDs (``cpd:kegg:C00022``), shorthand (``kegg:C00022``),
    or a compound name (case-insensitive).

    :param compound_id: Compound identifier in any supported format.
    :return: JSON object with compound fields and a ``reactions`` list.
    """
    node = metabokg.get_compound(compound_id)
    if node is None:
        return json.dumps({"error": f"compound not found: {compound_id!r}"})
    return json.dumps(node, indent=2, default=str)


def _mcp_get_reaction(metabokg: MetaKG, reaction_id: str) -> str:
    """
    Retrieve a reaction node with its full substrate/product/enzyme context.

    :param reaction_id: Reaction node ID (e.g. ``rxn:kegg:R00200``) or shorthand
        (e.g. ``kegg:R00200``).
    :return: JSON object with ``substrates``, ``products``, and ``enzymes`` lists.
    """
    detail = metabokg.get_reaction(reaction_id)
    if detail is None:
        return json.dumps({"error": f"reaction not found: {reaction_id!r}"})
    return json.dumps(detail, indent=2, default=str)


def _mcp_find_path(metabokg: MetaKG, compound_a: str, compound_b: str, max_hops: int = 6) -> str:
    """
    Find the shortest metabolic path between two compounds.

    Uses bidirectional BFS through ``SUBSTRATE_OF`` and ``PRODUCT_OF`` edges.

    :param compound_a: Source compound ID, shorthand, or name.
    :param compound_b: Target compound ID, shorthand, or name.
    :param max_hops: Maximum reaction steps (default 6).
    :return: JSON with ``path``, ``hops``, ``edges``, or ``{"error": ...}``.
    """
    result = metabokg.find_path(compound_a, compound_b, max_hops=max_hops)
    return json.dumps(result, indent=2, default=str)


def _mcp_simulate_fba(
    metabokg: MetaKG,
    pathway_id: str,
    objective_reaction: str = "",
    maximize: bool = True,
) -> str:
    """
    Run Flux Balance Analysis (FBA) on a metabolic pathway.

    Builds a stoichiometric linear programme (S·v = 0) and finds the
    optimal steady-state flux distribution.  No kinetic parameters are
    required; only the structural graph (stoichiometry + reversibility).

    :param pathway_id: Pathway node ID or name (e.g. ``"pwy:kegg:hsa00010"``
        or ``"Glycolysis"``).
    :param objective_reaction: Reaction ID to optimise.  Leave blank to
        maximise the sum of all forward fluxes (biomass proxy).
    :param maximize: If ``True`` (default) maximise; else minimise.
    :return: JSON with ``status``, ``objective_value``, ``fluxes`` dict, and
        ``shadow_prices`` dict.
    """
    from metabokg.simulate import MetabolicSimulator, SimulationConfig

    store = metabokg.store
    pwy_id = store.resolve_id(pathway_id) if pathway_id else None
    config = SimulationConfig(
        pathway_id=pwy_id,
        objective_reaction=objective_reaction or None,
        maximize=maximize,
    )
    sim = MetabolicSimulator(store)
    result = sim.run_fba(config)

    # Enrich flux dict with reaction names
    enriched_fluxes = {}
    for rxn_id, flux in result.fluxes.items():
        node = store.node(rxn_id)
        name = node["name"] if node else rxn_id
        enriched_fluxes[rxn_id] = {"name": name, "flux": flux}

    return json.dumps(
        {
            "status": result.status,
            "objective_value": result.objective_value,
            "message": result.message,
            "fluxes": enriched_fluxes,
            "shadow_prices": result.shadow_prices,
        },
        indent=2,
        default=str,
    )


def _mcp_simulate_ode(
    metabokg: MetaKG,
    pathway_id: str,
    t_end: float = 100.0,
    t_points: int = 200,
    initial_concentrations_json: str = "{}",
    default_concentration: float = 1.0,
) -> str:
    """
    Run a kinetic ODE simulation using Michaelis-Menten rate equations.

    Requires kinetic parameters to be seeded via ``seed_kinetics`` first.
    Falls back to normalised defaults (Km=0.5 mM, Vmax=1.0 mM/s) for
    reactions without stored parameters.

    :param pathway_id: Pathway node ID or name.
    :param t_end: End time for integration (arbitrary units, default 100).
    :param t_points: Number of output time points (default 200).
    :param initial_concentrations_json: JSON object mapping compound IDs to
        initial concentrations in mM, e.g.
        ``'{"cpd:kegg:C00031": 5.0, "cpd:kegg:C00002": 3.0}'``.
    :param default_concentration: Fallback initial concentration in mM (default 1.0).
    :return: JSON with ``status``, ``message``, ``t`` (time array), and
        ``concentrations`` (compound_id → [mM, ...]).
    """
    from metabokg.simulate import MetabolicSimulator, SimulationConfig

    try:
        init_concs: dict[str, float] = json.loads(initial_concentrations_json)
    except (json.JSONDecodeError, TypeError):
        init_concs = {}

    store = metabokg.store
    pwy_id = store.resolve_id(pathway_id) if pathway_id else None
    config = SimulationConfig(
        pathway_id=pwy_id,
        t_end=t_end,
        t_points=t_points,
        initial_concentrations=init_concs,
        default_concentration=default_concentration,
    )
    sim = MetabolicSimulator(store)
    result = sim.run_ode(config)

    # Enrich concentrations with compound names and summary stats
    summary: list[dict] = []
    for cpd_id, concs in result.concentrations.items():
        node = store.node(cpd_id)
        name = node["name"] if node else cpd_id
        summary.append(
            {
                "id": cpd_id,
                "name": name,
                "initial_mM": concs[0] if concs else None,
                "final_mM": concs[-1] if concs else None,
            }
        )
    summary.sort(key=lambda x: x["final_mM"] or 0.0, reverse=True)

    return json.dumps(
        {
            "status": result.status,
            "message": result.message,
            "t": result.t,
            "concentrations": result.concentrations,
            "summary": summary,
        },
        indent=2,
        default=str,
    )


def _mcp_simulate_whatif(
    metabokg: MetaKG,
    pathway_id: str,
    scenario_json: str,
    mode: str = "fba",
) -> str:
    """
    Run a perturbation (what-if) analysis: baseline vs. modified scenario.

    The scenario is a JSON object with optional keys:

    - ``name`` (str): Label for the scenario.
    - ``enzyme_knockouts`` (list[str]): Enzyme node IDs to silence.
    - ``enzyme_factors`` (dict[str, float]): Map enzyme ID → activity multiplier
      (0.5 halves activity, 2.0 doubles it).
    - ``initial_conc_overrides`` (dict[str, float]): Override compound initial
      concentrations in mM (ODE mode only).

    Example ``scenario_json``::

        {
          "name": "hexokinase_50pct",
          "enzyme_factors": {"enz:kegg:hsa:2538": 0.5}
        }

    :param pathway_id: Pathway node ID or name.
    :param scenario_json: JSON-encoded scenario object (see above).
    :param mode: ``"fba"`` (default) or ``"ode"``.
    :return: JSON with baseline result, perturbed result, delta_fluxes (FBA)
        or delta_final_conc (ODE), and a ranked change summary.
    """
    from metabokg.simulate import (
        MetabolicSimulator,
        SimulationConfig,
        WhatIfScenario,
    )

    try:
        scenario_dict: dict = json.loads(scenario_json)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"error": f"Invalid scenario_json: {scenario_json!r}"})

    store = metabokg.store
    pwy_id = store.resolve_id(pathway_id) if pathway_id else None
    config = SimulationConfig(pathway_id=pwy_id)

    # Resolve enzyme IDs in scenario
    knockouts = [store.resolve_id(e) or e for e in scenario_dict.get("enzyme_knockouts", [])]
    factors = scenario_dict.get("enzyme_factors", {})
    resolved_factors = {}
    for enz_id, factor in factors.items():
        resolved = store.resolve_id(enz_id) or enz_id
        resolved_factors[resolved] = float(factor)

    scenario = WhatIfScenario(
        name=scenario_dict.get("name", "whatif"),
        enzyme_knockouts=knockouts,
        enzyme_factors=resolved_factors,
        initial_conc_overrides={
            k: float(v) for k, v in scenario_dict.get("initial_conc_overrides", {}).items()
        },
    )

    sim = MetabolicSimulator(store)
    result = sim.run_whatif(config, scenario, mode=mode)

    # Build top-changes summary
    if mode == "fba":
        changes = sorted(
            [
                {
                    "id": rxn_id,
                    "name": (store.node(rxn_id) or {}).get("name", rxn_id),
                    "baseline_flux": (result.baseline.fluxes or {}).get(rxn_id, 0.0),  # ty: ignore[unresolved-attribute]
                    "perturbed_flux": (result.perturbed.fluxes or {}).get(rxn_id, 0.0),  # ty: ignore[unresolved-attribute]
                    "delta": delta,
                }
                for rxn_id, delta in result.delta_fluxes.items()
                if abs(delta) > 1e-8
            ],
            key=lambda x: abs(x["delta"]),
            reverse=True,
        )
    else:
        changes = sorted(
            [
                {
                    "id": cpd_id,
                    "name": (store.node(cpd_id) or {}).get("name", cpd_id),
                    "baseline_final_mM": (
                        (result.baseline.concentrations or {}).get(cpd_id, [0.0])[-1]  # ty: ignore[unresolved-attribute]
                    ),
                    "perturbed_final_mM": (
                        (result.perturbed.concentrations or {}).get(cpd_id, [0.0])[-1]  # ty: ignore[unresolved-attribute]
                    ),
                    "delta_mM": delta,
                }
                for cpd_id, delta in result.delta_final_conc.items()
                if abs(delta) > 1e-8
            ],
            key=lambda x: abs(x["delta_mM"]),
            reverse=True,
        )

    baseline_obj = getattr(result.baseline, "objective_value", None)
    perturbed_obj = getattr(result.perturbed, "objective_value", None)

    return json.dumps(
        {
            "scenario_name": result.scenario_name,
            "mode": result.mode,
            "baseline_status": result.baseline.status,
            "perturbed_status": result.perturbed.status,
            "baseline_objective": baseline_obj,
            "perturbed_objective": perturbed_obj,
            "top_changes": changes[:25],
        },
        indent=2,
        default=str,
    )


def _mcp_get_kinetic_params(metabokg: MetaKG, reaction_id: str) -> str:
    """
    Retrieve stored kinetic parameters for a reaction.

    Returns all rows from ``kinetic_parameters`` associated with the given
    reaction, enriched with enzyme and substrate names.

    :param reaction_id: Reaction node ID, shorthand, or name.
    :return: JSON list of kinetic parameter rows, or ``{"error": ...}``.
    """
    store = metabokg.store
    resolved = store.resolve_id(reaction_id)
    if resolved is None:
        return json.dumps({"error": f"Reaction not found: {reaction_id!r}"})

    rows = store.kinetic_params_for_reaction(resolved)
    enriched = []
    for row in rows:
        r = dict(row)
        if r.get("enzyme_id"):
            enz = store.node(r["enzyme_id"])
            r["enzyme_name"] = enz["name"] if enz else r["enzyme_id"]
        if r.get("substrate_id"):
            sub = store.node(r["substrate_id"])
            r["substrate_name"] = sub["name"] if sub else r["substrate_id"]
        enriched.append(r)

    regs = store.regulatory_interactions_for_reaction(resolved)
    for reg in regs:
        cpd = store.node(reg["compound_id"])
        reg["compound_name"] = cpd["name"] if cpd else reg["compound_id"]

    return json.dumps(
        {
            "reaction_id": resolved,
            "kinetic_params": enriched,
            "regulatory_interactions": regs,
        },
        indent=2,
        default=str,
    )


def _mcp_pack(metabokg: MetaKG, text: str, k: int = 8, hop: int = 1) -> str:
    """
    Build a context-rich metabolic pack from a semantic query.

    Runs vector search + graph expansion, then bundles each matched node
    with its biological context (reactions, substrates, products, enzymes)
    into a structured Markdown document ready for LLM context injection.

    :param text: Natural-language query, e.g. ``"glycolysis"`` or
        ``"fatty acid beta oxidation"``.
    :param k: Seed results from vector search (default 8).
    :param hop: Graph hops to expand from seeds (default 1).
    :return: Markdown-formatted context pack.
    """
    result = metabokg.pack(text, k=k, hop=hop)
    return result.to_markdown()


def _mcp_snapshot_list(limit: int = 20) -> str:
    """
    List MetaKG metric snapshots in reverse chronological order.

    Returns a JSON array of snapshot metadata dicts, each with keys:
    ``key``, ``timestamp``, ``branch``, ``version``, ``metrics``
    (total_nodes, total_edges, pathway_count, kinetic_params), and
    ``deltas.vs_previous``.

    :param limit: Maximum number of snapshots to return (default 20;
        pass 0 for all).
    :return: JSON array of snapshot metadata dicts.
    """
    from pathlib import Path

    from metabokg.snapshots import SnapshotManager

    snapshots_dir = Path.cwd() / ".metabokg" / "snapshots"
    mgr = SnapshotManager(snapshots_dir)
    snaps = mgr.list_snapshots(limit=limit if limit > 0 else None)
    return json.dumps(snaps, indent=2, default=str)


def _mcp_snapshot_show(key: str) -> str:
    """
    Show full details for a single MetaKG snapshot.

    :param key: Tree-hash snapshot key, or ``"latest"`` for the most
        recent snapshot.
    :return: JSON object with full snapshot data including metrics,
        hub metabolites, and deltas vs. previous and baseline.
    """
    from pathlib import Path

    from metabokg.snapshots import SnapshotManager

    snapshots_dir = Path.cwd() / ".metabokg" / "snapshots"
    mgr = SnapshotManager(snapshots_dir)
    snap = mgr.load_snapshot(key)
    if snap is None:
        return json.dumps({"error": f"snapshot not found: {key!r}"})
    return json.dumps(snap.to_dict(), indent=2, default=str)


def _mcp_snapshot_diff(key_a: str, key_b: str) -> str:
    """
    Compare two MetaKG snapshots side-by-side (B − A).

    :param key_a: First snapshot key (tree hash or ``"latest"``).
    :param key_b: Second snapshot key (tree hash or ``"latest"``).
    :return: JSON object with metrics from both snapshots, aggregate delta,
        per-kind node count deltas, and per-relation edge count deltas.
    """
    from pathlib import Path

    from metabokg.snapshots import SnapshotManager

    snapshots_dir = Path.cwd() / ".metabokg" / "snapshots"
    mgr = SnapshotManager(snapshots_dir)
    return json.dumps(mgr.diff_snapshots(key_a, key_b), indent=2, default=str)


def _mcp_seed_kinetics(metabokg: MetaKG, force: bool = False) -> str:
    """
    Seed the database with curated literature kinetic parameters.

    Populates ``kinetic_parameters`` and ``regulatory_interactions`` tables
    for the reactions present in the loaded pathway graph.  Values are drawn
    from BRENDA, SABIO-RK, and published metabolic models (see
    ``kinetics_fetch.py`` for full provenance).

    Safe to call multiple times — existing rows are skipped unless
    ``force=True``.

    :param force: If ``True``, overwrite existing kinetic parameter rows.
    :return: JSON with ``kinetic_params_written`` and
        ``regulatory_interactions_written`` counts.
    """
    from metabokg.kinetics_fetch import seed_kinetics as _seed

    n_kp, n_ri = _seed(metabokg.store, force=force)
    return json.dumps(
        {
            "kinetic_params_written": n_kp,
            "regulatory_interactions_written": n_ri,
            "message": (
                f"Seeded {n_kp} kinetic parameter row(s) and {n_ri} regulatory interaction row(s)."
            ),
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# The server, on kg_utils.mcp
# ---------------------------------------------------------------------------

PREAMBLE = (
    "MetaKG is a metabolic knowledge graph: KEGG pathways and genome-scale models as "
    "pathway, reaction, compound and enzyme nodes ('pwy:kegg:hsa00010', "
    "'rxn:kegg:R00200', 'cpd:kegg:C00031', 'enz:kegg:hsa:2539'), linked by CONTAINS, "
    "SUBSTRATE_OF, PRODUCT_OF and CATALYZES.\n\n"
    "## Recommended workflows\n\n"
    "- **Orientation**: stats\n"
    "- **Find entities**: query (any kind) or query_pathway → get_node, get_compound, "
    "get_reaction\n"
    "- **Read the biology**: pack bundles each match with its reactions, substrates, "
    "products and enzymes\n"
    "- **Trace routes**: find_path between compounds; neighbors(node_id) for one step\n"
    "- **Simulate**: seed_kinetics once, then simulate_fba (steady state), "
    "simulate_ode (time course) or simulate_whatif (knockouts, activity changes); "
    "get_kinetic_params shows Km/Vmax/kcat\n"
    "- **History**: snapshot_list / snapshot_show / snapshot_diff"
)


def query(
    q: str,
    k: int = 10,
    hop: int = 0,
    max_nodes: int = 25,
    rels: list[str] | None = None,
    *,
    ctx: Context,
) -> dict[str, Any]:
    """
    Semantic search across every node kind: pathways, reactions, compounds, enzymes.

    :param q: Natural-language query, e.g. "glucose phosphorylation".
    :param k: Semantic hits (default 10).
    :param hop: Graph hops to expand from the hits (0-5, default 0: hits only).
    :param max_nodes: Most results, hits first (default 25).
    :param rels: Edge types to expand along; omit for CONTAINS, SUBSTRATE_OF,
        PRODUCT_OF and CATALYZES.
    """
    result = kg_from(ctx).query(q, k=k, hop=hop, max_nodes=max_nodes, rels=rels)
    return {"query": result.query, "hits": result.hits}


def pack(
    q: str,
    k: int = 8,
    hop: int = 1,
    max_nodes: int = 15,
    rels: list[str] | None = None,
    *,
    ctx: Context,
) -> str:
    """
    A context-rich Markdown pack: each match with its reactions, substrates, products and enzymes.

    :param q: Natural-language query, e.g. "glycolysis".
    :param k: Seed results from vector search (default 8).
    :param hop: Graph hops to expand from the seeds (0-5, default 1).
    :param max_nodes: Most sections (default 15).
    :param rels: Edge types to expand along; omit for the default set.
    """
    return kg_from(ctx).pack(q, k=k, hop=hop, max_nodes=max_nodes, rels=rels).to_markdown()


def query_pathway(name: str, k: int = 8, *, ctx: Context) -> str:
    return _mcp_query_pathway(kg_from(ctx), name, k)


def get_compound(compound_id: str, *, ctx: Context) -> str:
    return _mcp_get_compound(kg_from(ctx), compound_id)


def get_reaction(reaction_id: str, *, ctx: Context) -> str:
    return _mcp_get_reaction(kg_from(ctx), reaction_id)


def find_path(compound_a: str, compound_b: str, max_hops: int = 6, *, ctx: Context) -> str:
    return _mcp_find_path(kg_from(ctx), compound_a, compound_b, max_hops)


def simulate_fba(
    pathway_id: str, objective_reaction: str = "", maximize: bool = True, *, ctx: Context
) -> str:
    return _mcp_simulate_fba(kg_from(ctx), pathway_id, objective_reaction, maximize)


def simulate_ode(
    pathway_id: str,
    t_end: float = 100.0,
    t_points: int = 200,
    initial_concentrations_json: str = "{}",
    default_concentration: float = 1.0,
    *,
    ctx: Context,
) -> str:
    return _mcp_simulate_ode(
        kg_from(ctx),
        pathway_id,
        t_end,
        t_points,
        initial_concentrations_json,
        default_concentration,
    )


def simulate_whatif(pathway_id: str, scenario_json: str, mode: str = "fba", *, ctx: Context) -> str:
    return _mcp_simulate_whatif(kg_from(ctx), pathway_id, scenario_json, mode)


def get_kinetic_params(reaction_id: str, *, ctx: Context) -> str:
    return _mcp_get_kinetic_params(kg_from(ctx), reaction_id)


def seed_kinetics(force: bool = False, *, ctx: Context) -> str:
    return _mcp_seed_kinetics(kg_from(ctx), force)


def snapshot_list(limit: int = 20) -> str:
    return _mcp_snapshot_list(limit)


def snapshot_show(key: str) -> str:
    return _mcp_snapshot_show(key)


def snapshot_diff(key_a: str, key_b: str) -> str:
    return _mcp_snapshot_diff(key_a, key_b)


#: MetaKG's own tools, after the five canonical ones. Each takes its
#: description from the unit-tested ``_mcp_*`` handler it wraps.
EXTRA_TOOLS = (
    query_pathway,
    get_compound,
    get_reaction,
    find_path,
    simulate_fba,
    simulate_ode,
    simulate_whatif,
    get_kinetic_params,
    seed_kinetics,
    snapshot_list,
    snapshot_show,
    snapshot_diff,
)
for _tool in EXTRA_TOOLS:
    _tool.__doc__ = globals()[f"_mcp_{_tool.__name__}"].__doc__


def build_server(
    db: str | Path,
    vectors: str | Path,
    model: str | None = None,
) -> KGServer:
    """
    Build the MetaKG MCP server for one corpus, without opening its graph.

    :param db: The corpus's SQLite database.
    :param vectors: Its sqlite-vec vector store.
    :param model: Embedding model; ``None`` for the default.
    :return: The server; serve it with :func:`kg_utils.mcp.run`.
    """
    from metabokg import __version__  # pylint: disable=import-outside-toplevel
    from metabokg.orchestrator import MetaKG  # pylint: disable=import-outside-toplevel

    def open_kg() -> MetaKG:
        return MetaKG(db_path=db, vectors_path=vectors, model=model)

    server = make_server(
        open_kg, name="metabokg", kind="metabolic", version=__version__, instructions=PREAMBLE
    )
    server.canonical("query")(query)
    server.canonical("pack")(pack)
    for tool in EXTRA_TOOLS:
        server.tool()(tool)
    return server
