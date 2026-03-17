"""
cmd_analyze.py — analyze and analyze-basic subcommands.

Registers:
  metabokg analyze        — thorough pathway analysis report
  metabokg analyze-basic  — basic structured analysis report
"""

from __future__ import annotations

from pathlib import Path

import click

from metabokg.cli._utils import _timestamped_filename
from metabokg.cli.main import cli
from metabokg.cli.options import db_option

_OUTPUT_OPTION = click.option(
    "--output",
    "-o",
    default=None,
    metavar="FILE",
    help="Write Markdown report to FILE (default: timestamped filename).",
)

_TOP_OPTION = click.option(
    "--top",
    default=20,
    show_default=True,
    type=int,
    metavar="N",
    help="Number of items in each ranked list.",
)

_PLAIN_OPTION = click.option("--plain", is_flag=True, help="Plain-text output instead of Markdown.")


@cli.command("analyze")
@db_option
@_OUTPUT_OPTION
@_TOP_OPTION
@_PLAIN_OPTION
def analyze(db: str, output: str | None, top: int, plain: bool) -> None:
    """Thorough metabolic pathway analysis report.

    Identifies hub metabolites, complex reactions, cross-pathway connections,
    pathway coupling, dead-end metabolites, and top enzymes.
    Writes to a timestamped file by default (e.g. metabokg-analysis-2026-03-01-143022.md).
    """
    db_path = Path(db)
    if not db_path.exists():
        raise click.ClickException(f"database not found: {db_path}\nRun 'metabokg build' first.")

    from metabokg.analyze import PathwayAnalyzer
    from metabokg.thorough_analysis import render_thorough_report

    click.echo(f"Analysing {db_path} ...", err=True)
    with PathwayAnalyzer(db_path, top_n=top) as analyzer:
        report = analyzer.run()

    text = render_thorough_report(report, markdown=not plain)

    out_path = Path(output or _timestamped_filename("metabokg-analysis"))
    out_path.write_text(text, encoding="utf-8")
    click.echo(f"Report written to {out_path}", err=True)


@cli.command("analyze-basic")
@db_option
@_OUTPUT_OPTION
@_TOP_OPTION
@_PLAIN_OPTION
def analyze_basic(db: str, output: str | None, top: int, plain: bool) -> None:
    """Basic structured analysis report: facts, ranked lists, minimal narrative.

    Writes to a timestamped file by default (e.g. metabokg-analysis-basic-2026-03-01-143022.md).
    """
    db_path = Path(db)
    if not db_path.exists():
        raise click.ClickException(f"database not found: {db_path}\nRun 'metabokg build' first.")

    from metabokg.analyze import PathwayAnalyzer, render_report

    click.echo(f"Analysing {db_path} ...", err=True)
    with PathwayAnalyzer(db_path, top_n=top) as analyzer:
        report = analyzer.run()

    text = render_report(report, markdown=not plain)

    out_path = Path(output or _timestamped_filename("metabokg-analysis-basic"))
    out_path.write_text(text, encoding="utf-8")
    click.echo(f"Report written to {out_path}", err=True)


# ---------------------------------------------------------------------------
# Standalone entry-point aliases
# ---------------------------------------------------------------------------

analyze_main = analyze
analyze_basic_main = analyze_basic
