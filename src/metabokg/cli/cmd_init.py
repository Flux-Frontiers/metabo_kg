"""
cmd_init.py — init subcommand.

Registers:
  metabokg init  — one-shot system initialization: integrity check,
                   TSV fetch, graph build, kinetics seed

Author: Eric G. Suchanek, PhD
Last Revision: 2026-04-30
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path

import click

from metabokg.cli.main import cli
from metabokg.downloader import (
    CORPUS_BY_NAME,
    CORPUS_SPECS,
    TsvIntegrityResult,
    check_integrity,
    download_gene_names,
    download_kegg_names,
    download_reaction_detail,
)

_ALL_CORPUS_NAMES = [c.name for c in CORPUS_SPECS]

# Status symbols used in the report table
_SYM = {"ok": "✓", "thin": "~", "empty": "!", "missing": "✗"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _colocate_db(data_dir: Path) -> tuple[str, str]:
    """Derive colocated db and lancedb paths from *data_dir*."""
    dot_dir = data_dir / ".metabokg"
    dot_dir.mkdir(parents=True, exist_ok=True)
    org = data_dir.name.split("_")[0]
    db = str(dot_dir / f"{org}.sqlite")
    lancedb = str(dot_dir / "lancedb")
    return db, lancedb


def _print_integrity_table(results: list[TsvIntegrityResult]) -> None:
    """Render the TSV integrity check table to stdout."""
    click.echo("\nTSV integrity:")
    for r in results:
        sym = _SYM.get(r.status, "?")
        if r.status == "ok":
            color = "green"
        elif r.status == "thin":
            color = "yellow"
        else:
            color = "red"
        row_str = f"{r.rows:>8,} rows" if r.rows else "      —     "
        status_str = click.style(f"{sym} {r.status.upper():<8}", fg=color)
        note = ""
        if r.status == "missing" and r.spec.download_group == "manual":
            note = " (manual download required — see fetch_sabio_cho_kinetics.py)"
        elif r.status == "thin":
            note = f" (expected ≥ {r.spec.min_rows:,})"
        click.echo(f"  {r.spec.filename:<34} {row_str}  {status_str}{note}")


def _print_corpus_table(corpus_rows: list[dict]) -> None:
    """Render the per-corpus status table to stdout."""
    click.echo("\nCorpus status:")
    header = f"  {'corpus':<6}  {'files':>6}  {'db':<4}  {'lancedb':<8}  {'kinetics':<12}  status"
    click.echo(header)
    click.echo("  " + "-" * 62)
    for row in corpus_rows:
        db_sym = click.style("✓", fg="green") if row["db_ok"] else click.style("✗", fg="red")
        ldb_sym = click.style("✓", fg="green") if row["lancedb_ok"] else click.style("✗", fg="red")
        kp_str = row["kinetics"] or "—"
        overall = (
            click.style("READY", fg="green")
            if row["ready"]
            else click.style("NEEDS BUILD", fg="yellow")
        )
        click.echo(
            f"  {row['name']:<6}  {row['files']:>6}  {db_sym}     {ldb_sym}        {kp_str:<12}  {overall}"
        )


def _corpus_status(spec) -> dict:
    """Return a status dict for one corpus."""
    import sqlite3

    data_subdir = Path(spec.data_subdir)
    files = list(data_subdir.glob("*.kgml")) + list(data_subdir.glob("*.xml"))

    db_path = data_subdir / ".metabokg" / f"{spec.name}.sqlite"
    lancedb_path = data_subdir / ".metabokg" / "lancedb"

    kinetics_str = ""
    if db_path.exists():
        try:
            con = sqlite3.connect(str(db_path))
            n_kp = con.execute("SELECT COUNT(*) FROM kinetic_parameters").fetchone()[0]
            con.close()
            kinetics_str = f"{n_kp} kp" if n_kp else "—"
        except sqlite3.DatabaseError:
            kinetics_str = "?"

    return {
        "name": spec.name,
        "files": len(files),
        "db_ok": db_path.exists(),
        "lancedb_ok": lancedb_path.exists(),
        "kinetics": kinetics_str,
        "ready": db_path.exists() and lancedb_path.exists(),
    }


def _build_one_corpus(spec, *, data_dir: Path, force: bool, no_kinetics: bool, MetaKG) -> None:
    """Build and seed one corpus; skips silently if preconditions are not met."""
    data_subdir = Path(spec.data_subdir)
    if not data_subdir.exists():
        click.echo(click.style(f"SKIP {spec.name}: {data_subdir} not found", fg="yellow"))
        return

    pathway_files = list(data_subdir.glob("*.kgml")) + list(data_subdir.glob("*.xml"))
    if not pathway_files:
        click.echo(click.style(f"SKIP {spec.name}: no pathway files in {data_subdir}", fg="yellow"))
        return

    db_path_str, lancedb_path_str = _colocate_db(data_subdir)
    db_path = Path(db_path_str)

    if db_path.exists() and not force:
        click.echo(
            f"SKIP {spec.name}: database already exists ({db_path}).\n  Use --force to rebuild."
        )
        return

    click.echo(f"Building {spec.name} ({len(pathway_files)} pathway files)...")
    kg = MetaKG(db_path=db_path_str, lancedb_dir=lancedb_path_str)
    stats = kg.build(
        data_dir=data_subdir,
        wipe=True,
        build_index=True,
        enrich=True,
        enrich_data_dir=data_dir,
        seed_kinetics=False,
    )
    click.echo(str(stats))

    if spec.has_kinetics and not no_kinetics:
        click.echo(f"  Seeding kinetic parameters for {spec.name}...")
        result = kg.seed_kinetics(force=force)
        n_kp = result["kinetic_params_written"]
        n_ri = result["regulatory_interactions_written"]
        click.echo(f"  → {n_kp} kinetic params, {n_ri} regulatory interactions")

    if spec.has_cho_kinetics and not no_kinetics:
        _seed_cho(kg, data_dir=data_dir, force=force, corpus_name=spec.name)

    kg.close()


def _seed_cho(kg, *, data_dir: Path, force: bool, corpus_name: str) -> None:
    """Seed CHO-specific kinetics; warns on missing file or missing simulate extra."""
    sabio_tsv = data_dir / "sabio_cho_kinetics.tsv"
    if not sabio_tsv.exists():
        click.echo(
            click.style(
                f"  WARNING: {sabio_tsv} not found — CHO kinetics skipped.",
                fg="yellow",
            )
        )
        return

    click.echo(f"  Seeding CHO kinetic parameters for {corpus_name}...")
    try:
        from metabokg.kinetics import seed_cho_kinetics  # noqa: PLC0415

        result_cho = seed_cho_kinetics(kg.store, sabio_tsv, force=force)
        click.echo(f"  → {result_cho} CHO kinetic params written")
    except ImportError:
        click.echo(
            click.style(
                "  WARNING: simulate extra not installed — CHO kinetics skipped.\n"
                "           Run: poetry install --extras simulate",
                fg="yellow",
            )
        )


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@cli.command("init")
@click.option(
    "--corpus",
    "corpora",
    multiple=True,
    type=click.Choice(_ALL_CORPUS_NAMES),
    help="Corpus to initialize (default: all). Repeatable: --corpus hsa --corpus cge.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Rebuild databases even if they already exist.",
)
@click.option(
    "--no-kinetics",
    is_flag=True,
    help="Skip seeding kinetic parameters after build.",
)
@click.option(
    "--no-fetch",
    is_flag=True,
    help="Do not download missing TSV files — fail if any are absent.",
)
@click.option(
    "--check",
    is_flag=True,
    help="Report status only — do not build or fetch anything.",
)
def init(
    corpora: tuple[str, ...],
    force: bool,
    no_kinetics: bool,
    no_fetch: bool,
    check: bool,
) -> None:
    """Initialize MetaboKG: check TSVs, fetch missing files, build corpora.

    On a fresh clone the pathway files and TSV annotation files are bundled
    in the repository.  This command builds the SQLite + LanceDB databases
    and seeds kinetic parameters so the system is query-ready.

    \b
    Steps:
      1. Integrity check — verify all required TSV files are present
      2. Fetch missing  — download absent TSVs from KEGG REST (unless --no-fetch)
      3. Build          — parse pathways → SQLite + LanceDB + enrichment
      4. Seed kinetics  — load curated kinetic parameters (unless --no-kinetics)
    """
    selected = list(corpora) if corpora else _ALL_CORPUS_NAMES
    selected_specs = [CORPUS_BY_NAME[n] for n in selected]
    selected_set = set(selected)

    data_dir = Path("data")
    if not data_dir.exists():
        raise click.ClickException(
            "data/ directory not found. Run this command from the repo root."
        )

    # ------------------------------------------------------------------
    # Phase 0: integrity check
    # ------------------------------------------------------------------
    click.echo(f"MetaboKG init — corpora: {', '.join(selected)}")
    click.echo("─" * 60)

    integrity = check_integrity(data_dir, corpora=selected_set)
    _print_integrity_table(integrity)

    if check:
        click.echo()
        _print_corpus_table([_corpus_status(s) for s in selected_specs])
        return

    # Classify what needs fetching
    to_fetch_names = any(r.needs_fetch and r.spec.download_group == "names" for r in integrity)
    to_fetch_reactions = any(
        r.needs_fetch and r.spec.download_group == "reactions" for r in integrity
    )
    gene_orgs_needed = [
        r.spec.download_group.split(":")[1]
        for r in integrity
        if r.needs_fetch and r.spec.download_group.startswith("genes:")
    ]
    manual_missing = [
        r
        for r in integrity
        if r.status in ("missing", "empty") and r.spec.download_group == "manual"
    ]

    for r in manual_missing:
        click.echo(
            click.style(
                f"\nWARNING: {r.spec.filename} is missing and cannot be auto-downloaded.\n"
                "         Run scripts/fetch_sabio_cho_kinetics.py manually.\n"
                "         CHO kinetics seeding will be skipped.",
                fg="yellow",
            )
        )

    # ------------------------------------------------------------------
    # Phase 1: fetch missing TSVs
    # ------------------------------------------------------------------
    if to_fetch_names or to_fetch_reactions or gene_orgs_needed:
        if no_fetch:
            missing = [r.spec.filename for r in integrity if r.needs_fetch]
            raise click.ClickException(
                f"Missing TSV files (--no-fetch prevents download): {', '.join(missing)}"
            )

        click.echo("\nFetching missing TSV files from KEGG REST...")

        if to_fetch_names:
            click.echo("  Downloading KEGG name lists (compound, reaction, glycan, ko)...")
            download_kegg_names(data_dir, quiet=False)

        if gene_orgs_needed:
            click.echo(f"  Downloading gene name lists for: {', '.join(gene_orgs_needed)}...")
            download_gene_names(gene_orgs_needed, data_dir, quiet=False)

        if to_fetch_reactions:
            kgml_dirs = [Path(s.data_subdir) for s in selected_specs if s.org is not None]
            click.echo("  Downloading reaction detail (this takes ~25 min for full human set)...")
            download_reaction_detail(data_dir, kgml_dirs, quiet=False)
    else:
        click.echo("\nAll required TSV files present.")

    # ------------------------------------------------------------------
    # Phase 2: build each corpus
    # ------------------------------------------------------------------
    click.echo()
    from metabokg import MetaKG  # noqa: PLC0415

    for spec in selected_specs:
        _build_one_corpus(
            spec, data_dir=data_dir, force=force, no_kinetics=no_kinetics, MetaKG=MetaKG
        )

    # ------------------------------------------------------------------
    # Phase 3: final report
    # ------------------------------------------------------------------
    click.echo("\n" + "─" * 60)
    click.echo("Init complete.")
    _print_corpus_table([_corpus_status(s) for s in selected_specs])
    click.echo()


# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------

init_main = init
