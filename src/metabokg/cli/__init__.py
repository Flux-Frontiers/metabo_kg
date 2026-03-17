"""
metabokg.cli — Click-based CLI entry points.

Public API
----------
The root Click group is importable from either location::

    from metabokg.cli import cli
    from metabokg.cli.main import cli

Standalone entry-point aliases (referenced by pyproject.toml [tool.poetry.scripts])
are re-exported here so that e.g. ``metabokg.cli:build_main`` resolves correctly.
"""

from metabokg.cli import (  # noqa: F401  — registers simulate (fba/ode/whatif/seed)
    cmd_analyze,  # noqa: F401  — registers analyze, analyze-basic
    cmd_build,  # noqa: F401  — registers build, update, enrich
    cmd_mcp,  # noqa: F401  — registers mcp
    cmd_simulate,
    cmd_viz,  # noqa: F401  — registers viz
    cmd_viz3d,  # noqa: F401  — registers viz3d
)

# ---------------------------------------------------------------------------
# Standalone entry-point aliases — must be importable as ``metabokg.cli:<name>``
# ---------------------------------------------------------------------------
from metabokg.cli.cmd_analyze import analyze_basic_main, analyze_main  # noqa: F401
from metabokg.cli.cmd_build import build_main, enrich_main, update_main  # noqa: F401
from metabokg.cli.cmd_mcp import mcp_main  # noqa: F401
from metabokg.cli.cmd_simulate import simulate_main  # noqa: F401
from metabokg.cli.cmd_viz import viz_main  # noqa: F401
from metabokg.cli.cmd_viz3d import viz3d_main  # noqa: F401
from metabokg.cli.main import cli

__all__ = [
    "cli",
    # subcommand entry-point aliases
    "analyze_main",
    "analyze_basic_main",
    "build_main",
    "enrich_main",
    "mcp_main",
    "simulate_main",
    "viz_main",
    "viz3d_main",
]
