"""
cmd_viz.py — viz subcommand.

Registers:
  metabokg viz  — launch the 2D Streamlit explorer
"""

from __future__ import annotations

import click

from metabokg.cli.main import cli


@cli.command("viz")
@click.option("--db", default=None, help="Path to SQLite database.")
@click.option("--lancedb", default=None, help="Path to LanceDB directory.")
@click.option("--port", default="8500", show_default=True, help="Streamlit server port.")
@click.option("--no-browser", is_flag=True, help="Do not open a browser window.")
def viz(db: str | None, lancedb: str | None, port: str, no_browser: bool) -> None:
    """Launch the Streamlit 2D metabolic knowledge-graph explorer."""
    from metabokg.metabokg_viz import main as viz_main_func

    viz_main_func(db=db, lancedb=lancedb, port=port, no_browser=no_browser)


# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------

viz_main = viz
