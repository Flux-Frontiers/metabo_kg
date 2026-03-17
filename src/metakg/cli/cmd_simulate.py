"""
cmd_simulate.py — simulate subcommand group with fba / ode / whatif / seed sub-subcommands.

Registers:
  metakg simulate fba     — Flux Balance Analysis
  metakg simulate ode     — ODE kinetic simulation
  metakg simulate whatif  — perturbation / what-if analysis
  metakg simulate seed    — seed kinetic parameters from literature
"""

from __future__ import annotations

from pathlib import Path

import click

from metakg.cli._utils import _parse_conc_args, _parse_factor_args, _write_output
from metakg.cli.main import cli
from metakg.cli.options import db_option


@cli.group("simulate")
@db_option
@click.option(
    "--output",
    "-o",
    default=None,
    metavar="FILE",
    help="Write Markdown report to FILE (default: timestamped filename).",
)
@click.option("--plain", is_flag=True, help="Plain-text output instead of Markdown.")
@click.option(
    "--top",
    default=25,
    show_default=True,
    type=int,
    metavar="N",
    help="Maximum items to list in each table.",
)
@click.pass_context
def simulate(ctx: click.Context, db: str, output: str | None, plain: bool, top: int) -> None:
    """Metabolic simulation: FBA, ODE kinetics, and what-if analysis."""
    ctx.ensure_object(dict)
    ctx.obj.update({"db": db, "output": output, "plain": plain, "top": top})


@simulate.command("fba")
@click.option(
    "--pathway",
    "-p",
    default=None,
    help="Pathway node ID or name (e.g. pwy:kegg:hsa00010 or 'Glycolysis').",
)
@click.option(
    "--objective",
    default=None,
    metavar="RXN_ID",
    help="Reaction ID to optimise (default: maximise total forward flux).",
)
@click.option("--minimize", is_flag=True, help="Minimise rather than maximise the objective.")
@click.pass_obj
def fba(obj: dict, pathway: str | None, objective: str | None, minimize: bool) -> None:
    """Flux Balance Analysis — steady-state optimal flux distribution."""
    db_path = Path(obj["db"])
    if not db_path.exists():
        raise click.ClickException(f"database not found: {db_path}\nRun 'metakg build' first.")

    from metakg import MetaKG
    from metakg.simulate import SimulationConfig, render_fba_result

    with MetaKG(db_path=db_path) as kg:
        store = kg.store
        pathway_id = store.resolve_id(pathway) if pathway else None
        config = SimulationConfig(
            pathway_id=pathway_id,
            objective_reaction=objective,
            maximize=not minimize,
        )
        click.echo("Running FBA...", err=True)
        result = kg.simulator.run_fba(config)
        text = render_fba_result(result, store, top_n=obj["top"], markdown=not obj["plain"])

    _write_output(text, obj["output"], "metakg-simulate-fba")


@simulate.command("ode")
@click.option("--pathway", "-p", default=None, help="Pathway node ID or name.")
@click.option(
    "--time",
    "-t",
    default=100.0,
    show_default=True,
    type=float,
    help="Simulation end time (arbitrary units).",
)
@click.option(
    "--points",
    default=500,
    show_default=True,
    type=int,
    help="Number of time points to sample.",
)
@click.option(
    "--conc",
    multiple=True,
    metavar="ID:VALUE",
    help="Set initial concentration for a compound: e.g. --conc cpd:kegg:C00031:5.0  (repeatable).",
)
@click.option(
    "--default-conc",
    default=1.0,
    show_default=True,
    type=float,
    metavar="MM",
    help="Default initial concentration in mM for all compounds.",
)
@click.pass_obj
def ode(
    obj: dict,
    pathway: str | None,
    time: float,
    points: int,
    conc: tuple[str, ...],
    default_conc: float,
) -> None:
    """ODE kinetic simulation — concentration time-courses via Michaelis-Menten."""
    db_path = Path(obj["db"])
    if not db_path.exists():
        raise click.ClickException(f"database not found: {db_path}\nRun 'metakg build' first.")

    from metakg import MetaKG
    from metakg.simulate import SimulationConfig, render_ode_result

    with MetaKG(db_path=db_path) as kg:
        store = kg.store
        pathway_id = store.resolve_id(pathway) if pathway else None
        config = SimulationConfig(
            pathway_id=pathway_id,
            t_end=time,
            t_points=points,
            initial_concentrations=_parse_conc_args(conc),
            default_concentration=default_conc,
        )
        click.echo(f"Running ODE (t=0..{time}, {points} pts)...", err=True)
        result = kg.simulator.run_ode(config)
        text = render_ode_result(result, store, top_n=obj["top"], markdown=not obj["plain"])

    _write_output(text, obj["output"], "metakg-simulate-ode")


@simulate.command("whatif")
@click.option("--pathway", "-p", default=None, help="Pathway node ID or name.")
@click.option(
    "--mode",
    default="fba",
    show_default=True,
    type=click.Choice(["fba", "ode"]),
    help="Simulation mode.",
)
@click.option(
    "--knockout",
    multiple=True,
    metavar="ENZ_ID",
    help="Enzyme node ID to knock out (repeatable).",
)
@click.option(
    "--factor",
    multiple=True,
    metavar="ENZ_ID:FACTOR",
    help="Scale enzyme activity: e.g. --factor enz:kegg:hsa:2538:0.5  (repeatable).",
)
@click.option(
    "--conc",
    multiple=True,
    metavar="ID:VALUE",
    help="Override initial compound concentration for ODE mode: ID:mM (repeatable).",
)
@click.option(
    "--name",
    default="whatif_scenario",
    show_default=True,
    help="Scenario label for the report.",
)
@click.option(
    "--time",
    "-t",
    default=100.0,
    show_default=True,
    type=float,
    help="ODE end time (ignored for FBA).",
)
@click.pass_obj
def whatif(
    obj: dict,
    pathway: str | None,
    mode: str,
    knockout: tuple[str, ...],
    factor: tuple[str, ...],
    conc: tuple[str, ...],
    name: str,
    time: float,
) -> None:
    """Perturbation / what-if analysis — baseline vs. modified scenario."""
    db_path = Path(obj["db"])
    if not db_path.exists():
        raise click.ClickException(f"database not found: {db_path}\nRun 'metakg build' first.")

    from metakg import MetaKG
    from metakg.simulate import SimulationConfig, WhatIfScenario, render_whatif_result

    with MetaKG(db_path=db_path) as kg:
        store = kg.store
        pathway_id = store.resolve_id(pathway) if pathway else None
        config = SimulationConfig(pathway_id=pathway_id, t_end=time)
        scenario = WhatIfScenario(
            name=name,
            enzyme_knockouts=[store.resolve_id(e) or e for e in knockout],
            enzyme_factors=_parse_factor_args(factor),
            initial_conc_overrides=_parse_conc_args(conc),
        )
        click.echo(f"Running what-if '{name}' ({mode.upper()})...", err=True)
        result = kg.simulator.run_whatif(config, scenario, mode=mode)
        text = render_whatif_result(result, store, top_n=obj["top"], markdown=not obj["plain"])

    _write_output(text, obj["output"], "metakg-simulate-whatif")


@simulate.command("seed")
@click.option("--force", is_flag=True, help="Overwrite existing kinetic parameter rows.")
@click.pass_obj
def seed(obj: dict, force: bool) -> None:
    """Seed kinetic parameters from curated literature values (BRENDA, SABIO-RK)."""
    db_path = Path(obj["db"])
    if not db_path.exists():
        raise click.ClickException(f"database not found: {db_path}\nRun 'metakg build' first.")

    from metakg import MetaKG

    click.echo(f"Seeding kinetic parameters into {db_path}...", err=True)
    with MetaKG(db_path=db_path) as kg:
        result = kg.seed_kinetics(force=force)
    n_kp = result["kinetic_params_written"]
    n_ri = result["regulatory_interactions_written"]
    click.echo(
        f"Done. Wrote {n_kp} kinetic parameter row(s) and {n_ri} regulatory interaction row(s).",
        err=True,
    )


# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------

simulate_main = simulate
