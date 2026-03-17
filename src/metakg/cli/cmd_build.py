"""
cmd_build.py — build and enrich subcommands.

Registers:
  metakg build    — parse pathway files → SQLite + LanceDB
  metakg enrich   — enrich node names in an existing database
"""

from __future__ import annotations

from pathlib import Path

import click

from metakg.cli.main import cli
from metakg.cli.options import (
    data_option,
    db_option,
    lancedb_option,
    model_option,
    wipe_option,
)


@cli.command("build")
@data_option
@db_option
@lancedb_option
@model_option
@click.option("--no-index", is_flag=True, help="Skip building the LanceDB vector index.")
@wipe_option
@click.option(
    "--no-enrich",
    is_flag=True,
    help="Skip name enrichment after building (enrichment runs by default).",
)
@click.option(
    "--enrich-data",
    default=None,
    metavar="DIR",
    help="Directory containing kegg_compound_names.tsv / kegg_reaction_names.tsv (default: data/).",
)
@click.option(
    "--no-seed-kinetics",
    is_flag=True,
    help="Skip seeding kinetic parameters after building.",
)
def build(
    data: str,
    db: str,
    lancedb: str,
    model: str,
    no_index: bool,
    wipe: bool,
    no_enrich: bool,
    enrich_data: str | None,
    no_seed_kinetics: bool,
) -> None:
    """Build the MetaKG metabolic knowledge graph from pathway files.

    Wipes the existing database and vector index before building (default).
    Use --no-wipe to add files incrementally instead."""
    data_dir = Path(data).resolve()
    if not data_dir.exists():
        raise click.ClickException(f"data directory not found: {data_dir}")

    from metakg import MetaKG

    kg = MetaKG(db_path=db, lancedb_dir=lancedb, model=model)
    click.echo(f"Building MetaKG from {data_dir}...", err=True)
    stats = kg.build(
        data_dir=data_dir,
        wipe=wipe,
        build_index=not no_index,
        enrich=not no_enrich,
        enrich_data_dir=enrich_data,
        seed_kinetics=not no_seed_kinetics,
    )
    click.echo(str(stats), err=True)

    if stats.parse_errors:
        click.echo(f"\n{len(stats.parse_errors)} file(s) failed to parse:", err=True)
        for err in stats.parse_errors:
            click.echo(f"  {err['file']}: {err['error']}", err=True)

    kg.close()


@cli.command("enrich")
@db_option
@click.option(
    "--data",
    default=None,
    metavar="DIR",
    help="Directory containing kegg_compound_names.tsv / kegg_reaction_names.tsv (default: data/).",
)
def enrich(db: str, data: str | None) -> None:
    """Enrich node names in an existing MetaKG database.

    Phase 1 (always): set reaction names from catalysing enzyme gene symbols
    using CATALYZES edges already in the graph — no network required.

    Phase 2 (when TSV files present): replace bare KEGG accessions with
    human-readable names from kegg_compound_names.tsv and
    kegg_reaction_names.tsv.  Download those files first with::

        python scripts/download_kegg_names.py
    """
    db_path = Path(db)
    if not db_path.exists():
        raise click.ClickException(f"database not found: {db_path}\nRun 'metakg build' first.")

    from metakg import MetaKG

    click.echo(f"Enriching node names in {db_path}...", err=True)
    with MetaKG(db_path=db_path) as kg:
        stats = kg.enrich(data_dir=data)
    click.echo(str(stats), err=True)


@cli.command("update")
@data_option
@db_option
@lancedb_option
@model_option
@click.option("--no-index", is_flag=True, help="Skip building the LanceDB vector index.")
@click.option(
    "--no-enrich",
    is_flag=True,
    help="Skip name enrichment after building (enrichment runs by default).",
)
@click.option(
    "--enrich-data",
    default=None,
    metavar="DIR",
    help="Directory containing kegg_compound_names.tsv / kegg_reaction_names.tsv (default: data/).",
)
@click.option(
    "--no-seed-kinetics",
    is_flag=True,
    help="Skip seeding kinetic parameters after building.",
)
def update(
    data: str,
    db: str,
    lancedb: str,
    model: str,
    no_index: bool,
    no_enrich: bool,
    enrich_data: str | None,
    no_seed_kinetics: bool,
) -> None:
    """Incrementally add new pathway files to an existing MetaKG database.

    Unlike ``build``, this command does not wipe the database first — it
    merges newly parsed nodes and edges on top of the existing graph.  Use
    this when you have added new KGML/SBML files and want to avoid a full
    rebuild."""
    data_dir = Path(data).resolve()
    if not data_dir.exists():
        raise click.ClickException(f"data directory not found: {data_dir}")

    from metakg import MetaKG

    kg = MetaKG(db_path=db, lancedb_dir=lancedb, model=model)
    click.echo(f"Updating MetaKG from {data_dir} (no wipe)...", err=True)
    stats = kg.build(
        data_dir=data_dir,
        wipe=False,
        build_index=not no_index,
        enrich=not no_enrich,
        enrich_data_dir=enrich_data,
        seed_kinetics=not no_seed_kinetics,
    )
    click.echo(str(stats), err=True)

    if stats.parse_errors:
        click.echo(f"\n{len(stats.parse_errors)} file(s) failed to parse:", err=True)
        for err in stats.parse_errors:
            click.echo(f"  {err['file']}: {err['error']}", err=True)

    kg.close()


# ---------------------------------------------------------------------------
# Standalone entry-point aliases (pyproject.toml [tool.poetry.scripts])
# ---------------------------------------------------------------------------

build_main = build
update_main = update
enrich_main = enrich
