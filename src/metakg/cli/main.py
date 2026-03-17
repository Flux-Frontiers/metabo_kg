"""
main.py — Root Click group for the MetaKG CLI.

The ``metakg`` command is the top-level entry point.  All subcommands
(build, enrich, mcp, viz, viz3d, analyze, simulate …) are registered by
importing their respective ``cmd_*.py`` modules in ``__init__.py``.
"""

from __future__ import annotations

import importlib.metadata

import click


@click.group()
@click.version_option(version=importlib.metadata.version("metakg"))
def cli() -> None:
    """MetaKG — metabolic pathway knowledge graph tools."""


if __name__ == "__main__":
    cli()
