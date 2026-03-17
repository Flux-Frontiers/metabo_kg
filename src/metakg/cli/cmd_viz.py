"""
cmd_viz.py — viz subcommand.

Registers:
  metakg viz  — launch the 2D Streamlit explorer
"""

from __future__ import annotations

from metakg.cli.main import cli


@cli.command("viz")
def viz() -> None:
    """Launch the Streamlit 2D metabolic knowledge-graph explorer.

    Argument parsing is handled by :mod:`metakg.metakg_viz`.
    """
    from metakg.metakg_viz import main as viz_main_func

    viz_main_func()


# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------

viz_main = viz
