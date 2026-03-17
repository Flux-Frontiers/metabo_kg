"""
cmd_viz3d.py — viz3d subcommand.

Registers:
  metakg viz3d  — launch the 3D PyVista visualizer
"""

from __future__ import annotations

import click

from metakg.cli.main import cli
from metakg.cli.options import db_option, lancedb_option


@cli.command("viz3d")
@db_option
@lancedb_option
@click.option(
    "--layout",
    type=click.Choice(["allium", "cake"], case_sensitive=False),
    default="cake",
    show_default=True,
    help=(
        "3-D layout strategy. "
        "'allium' renders each pathway as a Giant Allium plant; "
        "'cake' stratifies nodes by kind across Z layers."
    ),
)
@click.option(
    "--width",
    type=int,
    default=1400,
    show_default=True,
    help="Window width in pixels.",
)
@click.option(
    "--height",
    type=int,
    default=900,
    show_default=True,
    help="Window height in pixels.",
)
@click.option(
    "--export-html",
    metavar="PATH",
    default=None,
    help="Export to HTML file instead of opening interactive window.",
)
@click.option(
    "--export-png",
    metavar="PATH",
    default=None,
    help="Export to PNG file instead of opening interactive window.",
)
def viz3d(
    db: str,
    lancedb: str,
    layout: str,
    width: int,
    height: int,
    export_html: str | None,
    export_png: str | None,
) -> None:
    """Launch the 3D PyVista metabolic knowledge-graph visualizer."""
    from pathlib import Path

    db_path = Path(db)
    if not db_path.exists():
        raise click.ClickException(
            f"Database not found: {db_path}\n"
            "Run 'metakg build' first to build your metabolic knowledge graph."
        )

    from metakg.viz3d import launch

    launch(
        db_path=str(db_path),
        lancedb_dir=lancedb,
        layout_name=layout,
        width=width,
        height=height,
        export_html=export_html,
        export_png=export_png,
    )


# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------

viz3d_main = viz3d
