"""
mcp_tools.py — MCP tool registrations for MetaKG.

Exposes tools on a FastMCP instance:

    query_pathway(name, k)                      — semantic pathway search
    get_compound(id)                            — compound + connected reactions
    get_reaction(id)                            — full stoichiometric detail
    find_path(compound_a, compound_b, max_hops) — shortest metabolic path

    simulate_fba(pathway_id, objective_reaction, maximize)
        — Flux Balance Analysis on a pathway
    simulate_ode(pathway_id, t_end, t_points, initial_concentrations_json,
                 default_concentration)
        — ODE kinetic simulation; returns concentration time-courses
    simulate_whatif(pathway_id, scenario_json, mode)
        — Perturbation analysis: baseline vs. modified enzyme/substrate scenario
    get_kinetic_params(reaction_id)
        — Retrieve stored kinetic parameters for a reaction
    seed_kinetics(force)
        — Populate kinetic parameters from curated literature values

Register via::

    from metakg import MetaKG
    from metakg.mcp_tools import create_server

    mcp = create_server(MetaKG(db_path=".metakg/meta.sqlite"))
    mcp.run()

Or mount onto an existing FastMCP instance::

    from metakg.mcp_tools import register_tools
    register_tools(mcp, metakg)
Author: Eric G. Suchanek, PhD

Last Revision: 2026-02-28 20:54:34
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from metakg.orchestrator import MetaKG


# ---------------------------------------------------------------------------
# Module-level handler functions — unit-testable without FastMCP
# ---------------------------------------------------------------------------


def _mcp_query_pathway(metakg: MetaKG, name: str, k: int = 8) -> str:
    """
    Find metabolic pathways by name or description using semantic search.

    :param name: Pathway name or description, e.g. ``"glycolysis"`` or
        ``"fatty acid beta oxidation"``.
    :param k: Maximum results to return (default 8).
    :return: JSON list of matching pathway nodes with ``member_count`` field.
    """
    result = metakg.query_pathway(name, k=k)
    return result.to_json()


def _mcp_get_compound(metakg: MetaKG, compound_id: str) -> str:
    """
    Retrieve a compound node by its internal ID or external database ID.

    Accepts internal IDs (``cpd:kegg:C00022``), shorthand (``kegg:C00022``),
    or a compound name (case-insensitive).

    :param compound_id: Compound identifier in any supported format.
    :return: JSON object with compound fields and a ``reactions`` list.
    """
    node = metakg.get_compound(compound_id)
    if node is None:
        return json.dumps({"error": f"compound not found: {compound_id!r}"})
    return json.dumps(node, indent=2, default=str)


def _mcp_get_reaction(metakg: MetaKG, reaction_id: str) -> str:
    """
    Retrieve a reaction node with its full substrate/product/enzyme context.

    :param reaction_id: Reaction node ID (e.g. ``rxn:kegg:R00200``) or shorthand
        (e.g. ``kegg:R00200``).
    :return: JSON object with ``substrates``, ``products``, and ``enzymes`` lists.
    """
    detail = metakg.get_reaction(reaction_id)
    if detail is None:
        return json.dumps({"error": f"reaction not found: {reaction_id!r}"})
    return json.dumps(detail, indent=2, default=str)


def _mcp_find_path(metakg: MetaKG, compound_a: str, compound_b: str, max_hops: int = 6) -> str:
    """
    Find the shortest metabolic path between two compounds.

    Uses bidirectional BFS through ``SUBSTRATE_OF`` and ``PRODUCT_OF`` edges.

    :param compound_a: Source compound ID, shorthand, or name.
    :param compound_b: Target compound ID, shorthand, or name.
    :param max_hops: Maximum reaction steps (default 6).
    :return: JSON with ``path``, ``hops``, ``edges``, or ``{"error": ...}``.
    """
    result = metakg.find_path(compound_a, compound_b, max_hops=max_hops)
    return json.dumps(result, indent=2, default=str)


def _mcp_simulate_fba(
    metakg: MetaKG,
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
    from metakg.simulate import MetabolicSimulator, SimulationConfig

    store = metakg.store
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
    metakg: MetaKG,
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
    from metakg.simulate import MetabolicSimulator, SimulationConfig

    try:
        init_concs: dict[str, float] = json.loads(initial_concentrations_json)
    except (json.JSONDecodeError, TypeError):
        init_concs = {}

    store = metakg.store
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
    metakg: MetaKG,
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
    from metakg.simulate import (
        MetabolicSimulator,
        SimulationConfig,
        WhatIfScenario,
    )

    try:
        scenario_dict: dict = json.loads(scenario_json)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"error": f"Invalid scenario_json: {scenario_json!r}"})

    store = metakg.store
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
                    "baseline_flux": (result.baseline.fluxes or {}).get(rxn_id, 0.0),  # type: ignore[union-attr]
                    "perturbed_flux": (result.perturbed.fluxes or {}).get(rxn_id, 0.0),  # type: ignore[union-attr]
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
                        (result.baseline.concentrations or {}).get(cpd_id, [0.0])[-1]  # type: ignore[union-attr]
                    ),
                    "perturbed_final_mM": (
                        (result.perturbed.concentrations or {}).get(cpd_id, [0.0])[-1]  # type: ignore[union-attr]
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


def _mcp_get_kinetic_params(metakg: MetaKG, reaction_id: str) -> str:
    """
    Retrieve stored kinetic parameters for a reaction.

    Returns all rows from ``kinetic_parameters`` associated with the given
    reaction, enriched with enzyme and substrate names.

    :param reaction_id: Reaction node ID, shorthand, or name.
    :return: JSON list of kinetic parameter rows, or ``{"error": ...}``.
    """
    store = metakg.store
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


def _mcp_seed_kinetics(metakg: MetaKG, force: bool = False) -> str:
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
    from metakg.kinetics_fetch import seed_kinetics as _seed

    n_kp, n_ri = _seed(metakg.store, force=force)
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
# Tool registration
# ---------------------------------------------------------------------------


def register_tools(mcp, metakg: MetaKG) -> None:
    """
    Register all MetaKG MCP tools on *mcp*.

    :param mcp: A ``FastMCP`` instance (from ``mcp.server.fastmcp``).
    :param metakg: Initialised :class:`~metakg.orchestrator.MetaKG` instance.
    """

    def query_pathway(name: str, k: int = 8) -> str:
        return _mcp_query_pathway(metakg, name, k)

    query_pathway.__doc__ = _mcp_query_pathway.__doc__
    mcp.tool()(query_pathway)

    def get_compound(compound_id: str) -> str:
        return _mcp_get_compound(metakg, compound_id)

    get_compound.__doc__ = _mcp_get_compound.__doc__
    mcp.tool()(get_compound)

    def get_reaction(reaction_id: str) -> str:
        return _mcp_get_reaction(metakg, reaction_id)

    get_reaction.__doc__ = _mcp_get_reaction.__doc__
    mcp.tool()(get_reaction)

    def find_path(compound_a: str, compound_b: str, max_hops: int = 6) -> str:
        return _mcp_find_path(metakg, compound_a, compound_b, max_hops)

    find_path.__doc__ = _mcp_find_path.__doc__
    mcp.tool()(find_path)

    def simulate_fba(
        pathway_id: str,
        objective_reaction: str = "",
        maximize: bool = True,
    ) -> str:
        return _mcp_simulate_fba(metakg, pathway_id, objective_reaction, maximize)

    simulate_fba.__doc__ = _mcp_simulate_fba.__doc__
    mcp.tool()(simulate_fba)

    def simulate_ode(
        pathway_id: str,
        t_end: float = 100.0,
        t_points: int = 200,
        initial_concentrations_json: str = "{}",
        default_concentration: float = 1.0,
    ) -> str:
        return _mcp_simulate_ode(
            metakg, pathway_id, t_end, t_points, initial_concentrations_json, default_concentration
        )

    simulate_ode.__doc__ = _mcp_simulate_ode.__doc__
    mcp.tool()(simulate_ode)

    def simulate_whatif(
        pathway_id: str,
        scenario_json: str,
        mode: str = "fba",
    ) -> str:
        return _mcp_simulate_whatif(metakg, pathway_id, scenario_json, mode)

    simulate_whatif.__doc__ = _mcp_simulate_whatif.__doc__
    mcp.tool()(simulate_whatif)

    def get_kinetic_params(reaction_id: str) -> str:
        return _mcp_get_kinetic_params(metakg, reaction_id)

    get_kinetic_params.__doc__ = _mcp_get_kinetic_params.__doc__
    mcp.tool()(get_kinetic_params)

    def seed_kinetics(force: bool = False) -> str:
        return _mcp_seed_kinetics(metakg, force)

    seed_kinetics.__doc__ = _mcp_seed_kinetics.__doc__
    mcp.tool()(seed_kinetics)


def create_server(metakg: MetaKG, *, name: str = "metakg"):
    """
    Create a standalone FastMCP server with all MetaKG tools registered.

    :param metakg: Initialised :class:`~metakg.orchestrator.MetaKG` instance.
    :param name: Server name advertised to MCP clients.
    :return: Configured ``FastMCP`` instance ready to ``.run()``.
    """
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(
        name,
        instructions=(
            "MetaKG gives you semantic access to a metabolic pathway knowledge graph. "
            "Use query_pathway to find pathways, get_compound/get_reaction for entity "
            "detail, and find_path to trace biochemical routes between compounds. "
            "For simulation: call seed_kinetics once to populate kinetic parameters, "
            "then use simulate_fba for steady-state flux analysis, simulate_ode for "
            "kinetic time-course simulation, and simulate_whatif for perturbation "
            "analysis (enzyme knockouts, activity changes, substrate overrides). "
            "Use get_kinetic_params to inspect stored Km/Vmax/kcat values."
        ),
    )
    register_tools(server, metakg)
    return server
