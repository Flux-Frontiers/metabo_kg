"""
cmd_synthesize.py — synthesize subcommand: analysis + LLM narrative.

Registers:
  metabokg synthesize  — run analysis and synthesize with local Ollama LLM
"""

from __future__ import annotations

from pathlib import Path

import click

from metabokg.cli._utils import _timestamped_filename
from metabokg.cli.main import cli
from metabokg.cli.options import db_option, resolve_db


@cli.command("synthesize")
@db_option
@click.option("--output", "-o", default=None, metavar="FILE",
              help="Write synthesis to FILE (default: timestamped filename).")
@click.option("--top", default=20, show_default=True, type=int, metavar="N",
              help="Number of items in each ranked list.")
@click.option("--model", default="llama3.2", show_default=True,
              help="Ollama model name.")
@click.option("--host", default="http://localhost:11434", show_default=True,
              help="Ollama server URL.")
@click.option("--timeout", default=120.0, show_default=True, type=float,
              help="HTTP timeout in seconds.")
@click.option("--report-only", is_flag=True,
              help="Write the analysis report without calling Ollama.")
def synthesize(
    db: str | None,
    output: str | None,
    top: int,
    model: str,
    host: str,
    timeout: float,
    report_only: bool,
) -> None:
    """Run pathway analysis then synthesize findings with a local Ollama LLM.

    Requires Ollama running locally: https://ollama.com
    Pull a model first: ollama pull llama3.2
    """
    db_path = Path(resolve_db(db))
    if not db_path.exists():
        raise click.ClickException(f"database not found: {db_path}\nRun 'metabokg build' first.")

    from metabokg.analyze import PathwayAnalyzer
    from metabokg.thorough_analysis import render_thorough_report

    click.echo(f"Analysing {db_path} ...", err=True)
    with PathwayAnalyzer(db_path, top_n=top) as analyzer:
        report = analyzer.run()

    report_text = render_thorough_report(report, markdown=True)

    if report_only:
        out_path = Path(output or _timestamped_filename("metabokg-analysis"))
        out_path.write_text(report_text, encoding="utf-8")
        click.echo(f"Report written to {out_path}", err=True)
        return

    click.echo(f"Synthesizing with Ollama ({model} @ {host}) ...", err=True)
    from metabokg.synthesize import synthesize_with_ollama

    try:
        synthesis = synthesize_with_ollama(report_text, model=model, host=host, timeout=timeout)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    combined = (
        f"# MetaboKG Synthesis\n\n"
        f"## LLM Narrative\n\n{synthesis}\n\n"
        f"---\n\n"
        f"## Full Analysis Report\n\n{report_text}"
    )

    out_path = Path(output or _timestamped_filename("metabokg-synthesis"))
    out_path.write_text(combined, encoding="utf-8")
    click.echo(f"Synthesis written to {out_path}", err=True)


# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------

synthesize_main = synthesize
