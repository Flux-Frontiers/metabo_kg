"""
simulate.py — Metabolic simulation engine for MetaKG.

Provides three complementary simulation modes:

  **FBA** — Flux Balance Analysis via a steady-state linear programme.
    Requires only the structural graph (stoichiometry + reaction bounds).
    Returns an optimal flux distribution across all reactions in the scope.

  **ODE** — Kinetic simulation using Michaelis-Menten rate equations.
    Requires kinetic parameters (Km, Vmax) stored in ``kinetic_parameters``.
    Falls back to normalised defaults when parameters are absent.
    Returns compound concentration time-courses.

  **WhatIf** — Perturbation analysis: run baseline vs. a modified scenario.
    Supports enzyme knockouts, up/down-regulation factors, and substrate
    concentration changes.  Works with both FBA and ODE modes.

Typical usage::

    from metakg.store import MetaStore
    from metakg.simulate import MetabolicSimulator, SimulationConfig, WhatIfScenario

    store = MetaStore(".metakg/meta.sqlite")
    sim   = MetabolicSimulator(store)

    # --- FBA ---
    config = SimulationConfig(pathway_id="pwy:kegg:hsa00010")
    fba    = sim.run_fba(config)
    print(fba.fluxes)

    # --- ODE ---
    ode = sim.run_ode(config)
    # ode.t              → list of time points
    # ode.concentrations → {compound_id: [conc, ...]}

    # --- What-if: knock out hexokinase ---
    scenario = WhatIfScenario(
        name="HK_knockout",
        enzyme_knockouts=["enz:kegg:hsa:2538"],
    )
    result = sim.run_whatif(config, scenario, mode="fba")
    print(result.delta_fluxes)

    Author: Eric G. Suchanek, PhD

    Last Revision: 2026-02-28 20:44:14
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import linprog

if TYPE_CHECKING:
    from metakg.store import MetaStore


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SimulationConfig:
    """
    Specifies the scope and parameters for a simulation run.

    :param pathway_id: Pathway node ID to scope reactions (e.g. ``"pwy:kegg:hsa00010"``).
        Mutually exclusive with *reaction_ids*.
    :param reaction_ids: Explicit list of reaction node IDs to include.
    :param t_end: End time for ODE integration (arbitrary time units, default 100).
    :param t_points: Number of time points to sample in ODE output (default 500).
    :param initial_concentrations: Map of ``{compound_id: mM}`` for ODE initial conditions.
        Compounds not listed use *default_concentration*.
    :param default_concentration: Default initial concentration (mM) for ODE runs (default 1.0).
    :param objective_reaction: Reaction ID to optimise in FBA.  ``None`` maximises
        the sum of all fluxes (biomass proxy).
    :param maximize: If ``True`` (default) maximise the objective; else minimise.
    :param flux_bounds: Override reaction flux bounds ``{reaction_id: (lb, ub)}``.
        Irreversible reactions default to ``(0, 1000)``; reversible to ``(-1000, 1000)``.
    :param vmax_overrides: Override Vmax for specific reactions in ODE mode
        ``{reaction_id: vmax_mM_per_s}``.
    :param vmax_factors: Multiply stored (or default) Vmax by a factor ``{reaction_id: factor}``.
    :param ode_method: ODE solver method (default ``"BDF"``). ``"BDF"`` is for stiff systems;
        use ``"RK45"`` for non-stiff systems, ``"Radau"`` as alternative for stiff.
    :param ode_rtol: ODE relative tolerance (default ``1e-4``).
    :param ode_atol: ODE absolute tolerance in mM (default ``1e-6``).
    :param ode_max_step: Maximum internal step size for ODE solver. ``None`` (default)
        lets the solver choose; set to a small value for stricter control.
    """

    pathway_id: str | None = None
    reaction_ids: list[str] | None = None
    t_end: float = 100.0
    t_points: int = 500
    initial_concentrations: dict[str, float] = field(default_factory=dict)
    default_concentration: float = 1.0
    objective_reaction: str | None = None
    maximize: bool = True
    flux_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
    vmax_overrides: dict[str, float] = field(default_factory=dict)
    vmax_factors: dict[str, float] = field(default_factory=dict)
    ode_method: str = "BDF"
    ode_rtol: float = 1e-3
    ode_atol: float = 1e-5
    ode_max_step: float | None = None


@dataclass
class WhatIfScenario:
    """
    Describes a perturbation relative to a baseline :class:`SimulationConfig`.

    :param name: Human-readable scenario label.
    :param enzyme_knockouts: List of enzyme node IDs to silence (Vmax → 0, flux bounds → 0).
    :param enzyme_factors: Map ``{enzyme_id: factor}`` scaling Vmax (ODE) or flux upper bound (FBA).
        A factor of 0.5 halves enzyme activity; 2.0 doubles it.
    :param initial_conc_overrides: Map ``{compound_id: mM}`` replacing baseline initial
        concentrations for ODE runs.
    """

    name: str
    enzyme_knockouts: list[str] = field(default_factory=list)
    enzyme_factors: dict[str, float] = field(default_factory=dict)
    initial_conc_overrides: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FBAResult:
    """
    Output of :meth:`MetabolicSimulator.run_fba`.

    :param status: ``"optimal"``, ``"infeasible"``, or ``"error"``.
    :param objective_value: Value of the optimised flux (``None`` on failure).
    :param fluxes: Map ``{reaction_id: flux}`` for all reactions in scope.
    :param shadow_prices: Map ``{compound_id: dual_value}`` (opportunity cost per unit
        of relaxing the steady-state constraint).
    :param message: Human-readable solver message.
    """

    status: str
    objective_value: float | None
    fluxes: dict[str, float]
    shadow_prices: dict[str, float]
    message: str


@dataclass
class ODEResult:
    """
    Output of :meth:`MetabolicSimulator.run_ode`.

    :param status: ``"ok"``, ``"failed"``, or ``"error"``.
    :param t: List of time-point values.
    :param concentrations: Map ``{compound_id: [concentration, ...]}``.
    :param message: Human-readable solver message.
    """

    status: str
    t: list[float]
    concentrations: dict[str, list[float]]
    message: str


@dataclass
class WhatIfResult:
    """
    Output of :meth:`MetabolicSimulator.run_whatif`.

    :param scenario_name: Label from the :class:`WhatIfScenario`.
    :param baseline: Baseline simulation result.
    :param perturbed: Perturbed simulation result.
    :param delta_fluxes: ``{reaction_id: perturbed_flux - baseline_flux}`` (FBA mode).
    :param delta_final_conc: ``{compound_id: Δ[final_conc]}`` (ODE mode).
    :param mode: ``"fba"`` or ``"ode"``.
    """

    scenario_name: str
    baseline: FBAResult | ODEResult
    perturbed: FBAResult | ODEResult
    delta_fluxes: dict[str, float]
    delta_final_conc: dict[str, float]
    mode: str


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------


class MetabolicSimulator:
    """
    Metabolic simulation engine backed by a :class:`~metakg.store.MetaStore`.

    :param store: Opened MetaStore instance with pathway data loaded.
    """

    # Defaults used when no kinetic parameters are stored
    DEFAULT_VMAX: float = 1.0  # mM/s (normalised)
    DEFAULT_KM: float = 0.5  # mM
    DEFAULT_KEQ: float = 1.0  # dimensionless

    def __init__(self, store: MetaStore) -> None:
        self._store = store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_fba(self, config: SimulationConfig) -> FBAResult:
        """
        Run Flux Balance Analysis on the reactions in *config*.

        Builds a stoichiometric matrix S and solves::

            min  c·v
            s.t. S·v = 0     (metabolic steady-state)
                 lb ≤ v ≤ ub  (reaction bounds)

        :param config: Simulation scope and parameters.
        :return: :class:`FBAResult` with optimal fluxes and shadow prices.
        """
        rxn_ids, cpd_ids, S, rev_flags = self._build_stoich_matrix(config)

        if not rxn_ids:
            return FBAResult(
                status="error",
                objective_value=None,
                fluxes={},
                shadow_prices={},
                message="No reactions found for the given configuration.",
            )

        n_rxn = len(rxn_ids)
        n_cpd = len(cpd_ids)

        # Reaction flux bounds
        bounds: list[tuple[float, float]] = []
        for rxn_id in rxn_ids:
            if rxn_id in config.flux_bounds:
                bounds.append(config.flux_bounds[rxn_id])
            elif rev_flags.get(rxn_id, True):
                bounds.append((-1000.0, 1000.0))
            else:
                bounds.append((0.0, 1000.0))

        # Objective vector (linprog minimises → negate to maximise)
        c = np.zeros(n_rxn)
        if config.objective_reaction and config.objective_reaction in rxn_ids:
            j = rxn_ids.index(config.objective_reaction)
            c[j] = -1.0 if config.maximize else 1.0
        else:
            # Maximise sum of all forward fluxes as surrogate
            sign = -1.0 if config.maximize else 1.0
            for j, rxn_id in enumerate(rxn_ids):
                lb, _ = bounds[j]
                if lb >= 0:  # irreversible
                    c[j] = sign / n_rxn

        result = linprog(
            c,
            A_eq=S,
            b_eq=np.zeros(n_cpd),
            bounds=bounds,
            method="highs",
        )

        if result.status == 0:
            fluxes = {rxn_ids[j]: float(result.x[j]) for j in range(n_rxn)}
            obj_val = float(-result.fun) if config.maximize else float(result.fun)
            shadow: dict[str, float] = {}
            if result.eqlin is not None and hasattr(result.eqlin, "marginals"):
                marg = result.eqlin.marginals
                if marg is not None and len(marg) == n_cpd:
                    sign = -1.0 if config.maximize else 1.0
                    shadow = {cpd_ids[i]: float(sign * marg[i]) for i in range(n_cpd)}
            return FBAResult(
                status="optimal",
                objective_value=obj_val,
                fluxes=fluxes,
                shadow_prices=shadow,
                message=f"Optimal. Objective = {obj_val:.6g}",
            )

        status_map = {2: "infeasible", 3: "unbounded"}
        return FBAResult(
            status=status_map.get(result.status, "error"),
            objective_value=None,
            fluxes={},
            shadow_prices={},
            message=result.message,
        )

    def run_ode(self, config: SimulationConfig) -> ODEResult:
        """
        Run a kinetic ODE simulation using Michaelis-Menten rate equations.

        For each compound C::

            d[C]/dt = Σ_j s_ij · v_j(y, t)

        where *v_j* is computed from stored (or default) Km/Vmax values.

        :param config: Simulation scope and parameters.
        :return: :class:`ODEResult` with concentration time-courses.
        """
        rxn_ids, cpd_ids, S, rev_flags = self._build_stoich_matrix(config)

        if not rxn_ids:
            return ODEResult(
                status="error",
                t=[],
                concentrations={},
                message="No reactions found for the given configuration.",
            )

        kparams = self._build_kinetic_params(rxn_ids, config)

        # Pre-build reaction specs (avoid repeated dict lookups in hot loop)
        n_cpd = len(cpd_ids)
        rxn_specs = []
        for j, rxn_id in enumerate(rxn_ids):
            substrates = [(i, float(-S[i, j])) for i in range(n_cpd) if S[i, j] < -1e-10]
            products = [(i, float(S[i, j])) for i in range(n_cpd) if S[i, j] > 1e-10]
            kp = kparams.get(rxn_id, {})
            vmax = kp.get("vmax") or self.DEFAULT_VMAX
            km_default = kp.get("km") or self.DEFAULT_KM
            km_by_sub = kp.get("km_by_substrate", {})
            keq = kp.get("equilibrium_constant") or self.DEFAULT_KEQ
            rxn_specs.append(
                {
                    "substrates": substrates,
                    "products": products,
                    "vmax": vmax,
                    "km_default": km_default,
                    "km_by_sub": km_by_sub,
                    "reversible": rev_flags.get(rxn_id, True),
                    "keq": keq,
                }
            )

        y0 = np.array(
            [config.initial_concentrations.get(c, config.default_concentration) for c in cpd_ids]
        )

        def _dydt(_t: float, y: np.ndarray) -> np.ndarray:
            yc = np.maximum(y, 0.0)  # clamp negatives
            dy = np.zeros(n_cpd)
            for spec in rxn_specs:
                v = _mm_rate(spec, yc, cpd_ids)
                for idx, stoich in spec["substrates"]:
                    dy[idx] -= stoich * v
                for idx, stoich in spec["products"]:
                    dy[idx] += stoich * v
            return dy

        def _mm_rate(spec: dict, y: np.ndarray, cpd_ids: list[str]) -> float:
            substrates = spec["substrates"]
            if not substrates:
                return 0.0
            vmax = spec["vmax"]
            km_default = spec["km_default"]
            km_by_sub = spec["km_by_sub"]

            v_fwd = vmax
            for idx, _stoich in substrates:
                conc = float(y[idx])
                km = km_by_sub.get(cpd_ids[idx], km_default)
                denom = km + conc
                v_fwd *= conc / denom if denom > 0 else 0.0

            if not spec["reversible"]:
                return max(0.0, v_fwd)

            products = spec["products"]
            if not products:
                return v_fwd

            # Reversible: use Haldane relationship to estimate reverse rate
            keq = max(spec["keq"], 1e-12)
            v_rev = vmax / keq
            for idx, _stoich in products:
                conc = float(y[idx])
                km_p = km_by_sub.get(cpd_ids[idx], km_default) * keq
                denom = km_p + conc
                v_rev *= conc / denom if denom > 0 else 0.0

            return v_fwd - v_rev

        t_span = (0.0, config.t_end)
        t_eval = [config.t_end * i / (config.t_points - 1) for i in range(config.t_points)]

        try:
            # Build solve_ivp kwargs, excluding max_step if None (let solver choose)
            solve_kwargs = {
                "method": config.ode_method,
                "rtol": config.ode_rtol,
                "atol": config.ode_atol,
                "first_step": 1e-3,  # Small initial step for stiff systems
            }
            if config.ode_max_step is not None:
                solve_kwargs["max_step"] = config.ode_max_step

            sol = solve_ivp(
                _dydt,
                t_span,
                y0,
                t_eval=t_eval,
                **solve_kwargs,
            )
        except (ValueError, RuntimeError) as exc:
            return ODEResult(
                status="error",
                t=[],
                concentrations={},
                message=f"ODE solver raised: {exc}",
            )

        if not sol.success:
            return ODEResult(
                status="failed",
                t=[],
                concentrations={},
                message=f"ODE solver did not converge: {sol.message}",
            )

        concs = {cpd_ids[i]: sol.y[i].tolist() for i in range(n_cpd)}
        return ODEResult(
            status="ok",
            t=sol.t.tolist(),
            concentrations=concs,
            message=(
                f"Integration OK. t=[0, {config.t_end}], "
                f"{len(sol.t)} time points, {n_cpd} compounds, {len(rxn_ids)} reactions."
            ),
        )

    def run_whatif(
        self,
        config: SimulationConfig,
        scenario: WhatIfScenario,
        mode: str = "fba",
    ) -> WhatIfResult:
        """
        Run baseline and perturbed simulations and return the difference.

        :param config: Baseline simulation scope.
        :param scenario: Perturbation descriptor.
        :param mode: ``"fba"`` (default) or ``"ode"``.
        :return: :class:`WhatIfResult` with both results and delta maps.
        :raises ValueError: If *mode* is not ``"fba"`` or ``"ode"``.
        """
        if mode not in ("fba", "ode"):
            raise ValueError(f"mode must be 'fba' or 'ode', got {mode!r}")

        run = self.run_fba if mode == "fba" else self.run_ode
        baseline = run(config)
        perturbed_cfg = self._apply_scenario(config, scenario, mode)
        perturbed = run(perturbed_cfg)

        delta_fluxes: dict[str, float] = {}
        delta_final_conc: dict[str, float] = {}

        if mode == "fba":
            assert isinstance(baseline, FBAResult) and isinstance(perturbed, FBAResult)
            all_rxns = set(baseline.fluxes) | set(perturbed.fluxes)
            for rxn_id in all_rxns:
                b = baseline.fluxes.get(rxn_id, 0.0)
                p = perturbed.fluxes.get(rxn_id, 0.0)
                delta_fluxes[rxn_id] = p - b
        else:
            assert isinstance(baseline, ODEResult) and isinstance(perturbed, ODEResult)
            all_cpds = set(baseline.concentrations) | set(perturbed.concentrations)
            for cpd_id in all_cpds:
                b_concs = baseline.concentrations.get(cpd_id, [0.0])
                p_concs = perturbed.concentrations.get(cpd_id, [0.0])
                delta_final_conc[cpd_id] = p_concs[-1] - b_concs[-1]

        return WhatIfResult(
            scenario_name=scenario.name,
            baseline=baseline,
            perturbed=perturbed,
            delta_fluxes=delta_fluxes,
            delta_final_conc=delta_final_conc,
            mode=mode,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_stoich_matrix(
        self,
        config: SimulationConfig,
    ) -> tuple[list[str], list[str], np.ndarray, dict[str, bool]]:
        """
        Build the stoichiometric matrix S from the store.

        S[i, j] = net stoichiometric coefficient of compound *i* in reaction *j*
        (negative = consumed, positive = produced).

        :return: ``(rxn_ids, cpd_ids, S, rev_flags)``
        """
        # Determine which reactions to include
        if config.reaction_ids:
            rxn_ids = list(config.reaction_ids)
        elif config.pathway_id:
            rxn_ids = self._reactions_for_pathway(config.pathway_id)
        else:
            rxn_ids = [r["id"] for r in self._store.all_nodes(kind="reaction")]

        if not rxn_ids:
            return [], [], np.zeros((0, 0)), {}

        # Accumulate stoichiometry and reversibility from edges
        stoich_map: dict[str, dict[str, float]] = {}  # cpd_id → {rxn_id: net_coeff}
        rev_flags: dict[str, bool] = {}

        for rxn_id in rxn_ids:
            rxn = self._store.node(rxn_id)
            if rxn is None:
                continue
            # Reversibility from stoichiometry blob
            reversible = True
            blob = rxn.get("stoichiometry")
            if blob:
                try:
                    direction = json.loads(blob).get("direction", "reversible")
                    reversible = direction != "irreversible"
                except (json.JSONDecodeError, TypeError):
                    pass
            rev_flags[rxn_id] = reversible

            for edge in self._store.edges_of(rxn_id):
                ev: dict = {}
                if edge.get("evidence"):
                    try:
                        ev = json.loads(edge["evidence"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                stoich_val = float(ev.get("stoich", 1.0))

                if edge["rel"] == "SUBSTRATE_OF" and edge["dst"] == rxn_id:
                    cpd_id = edge["src"]
                    stoich_map.setdefault(cpd_id, {})[rxn_id] = (
                        stoich_map.get(cpd_id, {}).get(rxn_id, 0.0) - stoich_val
                    )
                elif edge["rel"] == "PRODUCT_OF" and edge["src"] == rxn_id:
                    cpd_id = edge["dst"]
                    stoich_map.setdefault(cpd_id, {})[rxn_id] = (
                        stoich_map.get(cpd_id, {}).get(rxn_id, 0.0) + stoich_val
                    )

        if not stoich_map:
            return rxn_ids, [], np.zeros((0, len(rxn_ids))), rev_flags

        cpd_ids = sorted(stoich_map.keys())
        n_cpd = len(cpd_ids)
        n_rxn = len(rxn_ids)
        S = np.zeros((n_cpd, n_rxn))

        cpd_index = {c: i for i, c in enumerate(cpd_ids)}
        rxn_index = {r: j for j, r in enumerate(rxn_ids)}

        for cpd_id, rxn_coeffs in stoich_map.items():
            i = cpd_index[cpd_id]
            for rxn_id, coeff in rxn_coeffs.items():
                if rxn_id in rxn_index:
                    S[i, rxn_index[rxn_id]] = coeff

        return rxn_ids, cpd_ids, S, rev_flags

    def _reactions_for_pathway(self, pathway_id: str) -> list[str]:
        """Return reaction node IDs contained in a pathway."""
        pwy_id = self._store.resolve_id(pathway_id)
        if pwy_id is None:
            return []
        rxn_ids = []
        for edge in self._store.edges_of(pwy_id):
            if edge["rel"] == "CONTAINS" and edge["src"] == pwy_id:
                node = self._store.node(edge["dst"])
                if node and node["kind"] == "reaction":
                    rxn_ids.append(node["id"])
        return rxn_ids

    def _reactions_for_enzyme(self, enzyme_id: str) -> list[str]:
        """Return reaction node IDs catalysed by an enzyme."""
        enz_id = self._store.resolve_id(enzyme_id)
        if enz_id is None:
            return []
        return [
            e["dst"]
            for e in self._store.edges_of(enz_id)
            if e["rel"] == "CATALYZES" and e["src"] == enz_id
        ]

    def _build_kinetic_params(
        self,
        rxn_ids: list[str],
        config: SimulationConfig,
    ) -> dict[str, dict]:
        """
        Build per-reaction kinetic parameter dicts, merging DB values with
        any overrides or factors from *config*.

        :return: Map ``{reaction_id: {vmax, km, km_by_substrate, equilibrium_constant}}``.
        """
        result: dict[str, dict] = {}
        for rxn_id in rxn_ids:
            rows = self._store.kinetic_params_for_reaction(rxn_id)
            if rows:
                km_by_sub: dict[str, float] = {}
                vmaxs, kms, keqs = [], [], []
                for row in rows:
                    if row.get("vmax") is not None:
                        vmaxs.append(row["vmax"])
                    if row.get("km") is not None:
                        kms.append(row["km"])
                    if row.get("equilibrium_constant") is not None:
                        keqs.append(row["equilibrium_constant"])
                    if row.get("substrate_id") and row.get("km") is not None:
                        km_by_sub[row["substrate_id"]] = row["km"]
                result[rxn_id] = {
                    "vmax": float(np.mean(vmaxs)) if vmaxs else None,
                    "km": float(np.mean(kms)) if kms else None,
                    "equilibrium_constant": float(np.mean(keqs)) if keqs else None,
                    "km_by_substrate": km_by_sub,
                }
            else:
                result[rxn_id] = {
                    "vmax": self.DEFAULT_VMAX,
                    "km": self.DEFAULT_KM,
                    "equilibrium_constant": self.DEFAULT_KEQ,
                    "km_by_substrate": {},
                }

        # Apply config overrides
        for rxn_id, vmax_val in config.vmax_overrides.items():
            if rxn_id in result:
                result[rxn_id]["vmax"] = vmax_val

        for rxn_id, factor in config.vmax_factors.items():
            if rxn_id in result:
                base = result[rxn_id].get("vmax") or self.DEFAULT_VMAX
                result[rxn_id]["vmax"] = base * factor

        return result

    def _apply_scenario(
        self,
        config: SimulationConfig,
        scenario: WhatIfScenario,
        mode: str,
    ) -> SimulationConfig:
        """Return a new SimulationConfig with the scenario perturbations applied."""
        new_cfg = copy.deepcopy(config)

        for enz_id in scenario.enzyme_knockouts:
            rxn_ids = self._reactions_for_enzyme(enz_id)
            for rxn_id in rxn_ids:
                if mode == "fba":
                    new_cfg.flux_bounds[rxn_id] = (0.0, 0.0)
                else:
                    new_cfg.vmax_overrides[rxn_id] = 0.0

        for enz_id, factor in scenario.enzyme_factors.items():
            rxn_ids = self._reactions_for_enzyme(enz_id)
            for rxn_id in rxn_ids:
                if mode == "fba":
                    lb, ub = new_cfg.flux_bounds.get(rxn_id, (0.0, 1000.0))
                    new_cfg.flux_bounds[rxn_id] = (lb, ub * factor)
                else:
                    new_cfg.vmax_factors[rxn_id] = new_cfg.vmax_factors.get(rxn_id, 1.0) * factor

        for cpd_id, conc in scenario.initial_conc_overrides.items():
            new_cfg.initial_concentrations[cpd_id] = conc

        return new_cfg


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def render_fba_result(
    result: FBAResult,
    store: MetaStore | None = None,
    *,
    top_n: int = 20,
    markdown: bool = True,
) -> str:
    """
    Format an :class:`FBAResult` as a human-readable report.

    :param result: FBA result to render.
    :param store: Optional MetaStore for resolving reaction names.
    :param top_n: Maximum reactions to list.
    :param markdown: Emit Markdown (default) or plain text.
    :return: Formatted string.
    """
    h2 = "## " if markdown else ""
    h3 = "### " if markdown else "--- "
    bold = ("**", "**") if markdown else ("", "")
    lines: list[str] = []

    lines.append(f"{h2}FBA Result")
    lines.append(f"{bold[0]}Status:{bold[1]} {result.status}")
    if result.objective_value is not None:
        lines.append(f"{bold[0]}Objective value:{bold[1]} {result.objective_value:.6g}")
    lines.append(f"{bold[0]}Message:{bold[1]} {result.message}")
    lines.append("")

    if result.fluxes:
        sorted_rxns = sorted(result.fluxes.items(), key=lambda x: abs(x[1]), reverse=True)
        lines.append(f"{h3}Top {min(top_n, len(sorted_rxns))} Fluxes (by magnitude)")
        if markdown:
            lines.append("| Reaction | ID | Flux |")
            lines.append("|---|---|---:|")
        for rxn_id, flux in sorted_rxns[:top_n]:
            name = rxn_id
            if store:
                node = store.node(rxn_id)
                if node:
                    name = node.get("name", rxn_id)
            if markdown:
                lines.append(f"| {name} | `{rxn_id}` | {flux:.4f} |")
            else:
                lines.append(f"  {name:<40} {flux:>10.4f}")

    if result.shadow_prices:
        lines.append("")
        lines.append(f"{h3}Top Shadow Prices")
        sorted_sp = sorted(result.shadow_prices.items(), key=lambda x: abs(x[1]), reverse=True)
        if markdown:
            lines.append("| Compound | ID | Shadow Price |")
            lines.append("|---|---|---:|")
        for cpd_id, sp in sorted_sp[:top_n]:
            name = cpd_id
            if store:
                node = store.node(cpd_id)
                if node:
                    name = node.get("name", cpd_id)
            if markdown:
                lines.append(f"| {name} | `{cpd_id}` | {sp:.4g} |")
            else:
                lines.append(f"  {name:<40} {sp:>10.4g}")

    return "\n".join(lines)


def render_ode_result(
    result: ODEResult,
    store: MetaStore | None = None,
    *,
    top_n: int = 20,
    markdown: bool = True,
) -> str:
    """
    Format an :class:`ODEResult` showing final concentrations.

    :param result: ODE result to render.
    :param store: Optional MetaStore for resolving compound names.
    :param top_n: Maximum compounds to list.
    :param markdown: Emit Markdown (default) or plain text.
    :return: Formatted string.
    """
    h2 = "## " if markdown else ""
    h3 = "### " if markdown else "--- "
    bold = ("**", "**") if markdown else ("", "")
    lines: list[str] = []

    lines.append(f"{h2}ODE Result")
    lines.append(f"{bold[0]}Status:{bold[1]} {result.status}")
    lines.append(f"{bold[0]}Message:{bold[1]} {result.message}")
    lines.append("")

    if result.concentrations:
        final_concs = {c: vals[-1] for c, vals in result.concentrations.items() if vals}
        sorted_cpds = sorted(final_concs.items(), key=lambda x: x[1], reverse=True)
        lines.append(f"{h3}Final Concentrations (t = {result.t[-1] if result.t else '?'})")
        if markdown:
            lines.append("| Compound | ID | Final [mM] |")
            lines.append("|---|---|---:|")
        for cpd_id, conc in sorted_cpds[:top_n]:
            name = cpd_id
            if store:
                node = store.node(cpd_id)
                if node:
                    name = node.get("name", cpd_id)
            if markdown:
                lines.append(f"| {name} | `{cpd_id}` | {conc:.4f} |")
            else:
                lines.append(f"  {name:<40} {conc:>10.4f}")

    return "\n".join(lines)


def render_whatif_result(
    result: WhatIfResult,
    store: MetaStore | None = None,
    *,
    top_n: int = 20,
    markdown: bool = True,
) -> str:
    """
    Format a :class:`WhatIfResult` highlighting the largest changes.

    :param result: What-if result to render.
    :param store: Optional MetaStore for name resolution.
    :param top_n: Maximum items to list per section.
    :param markdown: Emit Markdown (default) or plain text.
    :return: Formatted string.
    """
    h2 = "## " if markdown else ""
    h3 = "### " if markdown else "--- "
    bold = ("**", "**") if markdown else ("", "")
    lines: list[str] = []

    lines.append(f"{h2}What-If: {result.scenario_name}")
    lines.append(f"{bold[0]}Mode:{bold[1]} {result.mode.upper()}")
    lines.append("")

    if result.mode == "fba":
        assert isinstance(result.baseline, FBAResult)
        assert isinstance(result.perturbed, FBAResult)
        lines.append(
            f"{bold[0]}Baseline objective:{bold[1]} "
            f"{result.baseline.objective_value:.6g if result.baseline.objective_value is not None else 'N/A'}"
        )
        lines.append(
            f"{bold[0]}Perturbed objective:{bold[1]} "
            f"{result.perturbed.objective_value:.6g if result.perturbed.objective_value is not None else 'N/A'}"
        )
        lines.append("")

        if result.delta_fluxes:
            sorted_deltas = sorted(
                result.delta_fluxes.items(), key=lambda x: abs(x[1]), reverse=True
            )
            lines.append(f"{h3}Flux Changes (Δ = perturbed − baseline)")
            if markdown:
                lines.append("| Reaction | ID | Baseline | Perturbed | Δ Flux |")
                lines.append("|---|---|---:|---:|---:|")
            for rxn_id, delta in sorted_deltas[:top_n]:
                if abs(delta) < 1e-8:
                    continue
                name = rxn_id
                if store:
                    node = store.node(rxn_id)
                    if node:
                        name = node.get("name", rxn_id)
                b_flux = result.baseline.fluxes.get(rxn_id, 0.0)
                p_flux = result.perturbed.fluxes.get(rxn_id, 0.0)
                tag = "▲" if delta > 0 else "▼"
                if markdown:
                    lines.append(
                        f"| {name} | `{rxn_id}` | {b_flux:.4f} | {p_flux:.4f} | {tag} {delta:.4f} |"
                    )
                else:
                    lines.append(
                        f"  {name:<38} {b_flux:>8.4f} → {p_flux:>8.4f}  ({tag}{abs(delta):.4f})"
                    )
    else:
        assert isinstance(result.baseline, ODEResult)
        assert isinstance(result.perturbed, ODEResult)
        if result.delta_final_conc:
            sorted_deltas = sorted(
                result.delta_final_conc.items(), key=lambda x: abs(x[1]), reverse=True
            )
            lines.append(f"{h3}Final Concentration Changes (Δ[C] at t_end)")
            if markdown:
                lines.append("| Compound | ID | Baseline [mM] | Perturbed [mM] | Δ [mM] |")
                lines.append("|---|---|---:|---:|---:|")
            for cpd_id, delta in sorted_deltas[:top_n]:
                if abs(delta) < 1e-8:
                    continue
                name = cpd_id
                if store:
                    node = store.node(cpd_id)
                    if node:
                        name = node.get("name", cpd_id)
                b_concs = result.baseline.concentrations.get(cpd_id, [0.0])
                p_concs = result.perturbed.concentrations.get(cpd_id, [0.0])
                b_final = b_concs[-1] if b_concs else 0.0
                p_final = p_concs[-1] if p_concs else 0.0
                tag = "▲" if delta > 0 else "▼"
                if markdown:
                    lines.append(
                        f"| {name} | `{cpd_id}` | {b_final:.4f} | {p_final:.4f} | {tag} {abs(delta):.4f} |"
                    )
                else:
                    lines.append(
                        f"  {name:<38} {b_final:>8.4f} → {p_final:>8.4f}  ({tag}{abs(delta):.4f})"
                    )

    return "\n".join(lines)
