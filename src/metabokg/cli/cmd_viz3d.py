"""
cmd_viz3d.py — viz3d subcommand.

Registers:
  metabokg viz3d  — launch the 3D PyVista visualizer
"""

from __future__ import annotations

import click

from metabokg.cli.main import cli


@cli.command("viz3d")
@click.option("--db", default=None, help="Path to SQLite database.")
@click.option("--lancedb", default=None, help="Path to LanceDB directory.")
@click.option(
    "--layout",
    default="allium",
    show_default=True,
    type=click.Choice(["allium", "cake"]),
    help="3D layout strategy.",
)
@click.option("--width", default=1400, show_default=True, help="Window width in pixels.")
@click.option("--height", default=900, show_default=True, help="Window height in pixels.")
@click.option("--export-html", default=None, help="Export to HTML file instead of opening window.")
@click.option("--export-png", default=None, help="Export to PNG file.")
def viz3d(
    db: str | None,
    lancedb: str | None,
    layout: str,
    width: int,
    height: int,
    export_html: str | None,
    export_png: str | None,
) -> None:
    """Launch the 3D PyVista metabolic knowledge-graph visualizer."""
    from metabokg.metabokg_viz3d import main as viz3d_main_func

    viz3d_main_func(
        db=db,
        lancedb=lancedb,
        layout=layout,
        width=width,
        height=height,
        export_html=export_html,
        export_png=export_png,
    )


# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------

viz3d_main = viz3d
