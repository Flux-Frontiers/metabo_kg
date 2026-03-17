"""
cmd_viz.py — viz subcommand.

Registers:
  metabokg viz  — launch the 2D Streamlit explorer
"""

from __future__ import annotations

from metabokg.cli.main import cli


@cli.command("viz")
def viz() -> None:
    """Launch the Streamlit 2D metabolic knowledge-graph explorer.

    Argument parsing is handled by :mod:`metabokg.metabokg_viz`.
    """
    from metabokg.metabokg_viz import main as viz_main_func

    viz_main_func()


# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------

viz_main = viz
