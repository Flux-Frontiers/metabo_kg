"""
options.py — Reusable Click option decorators for MetaKG CLI commands.
"""

from __future__ import annotations

import click

from metakg.embed import DEFAULT_MODEL

db_option = click.option(
    "--db",
    default=".metakg/meta.sqlite",
    show_default=True,
    help="Path to MetaKG SQLite database.",
)

lancedb_option = click.option(
    "--lancedb",
    default=".metakg/lancedb",
    show_default=True,
    help="Path to LanceDB directory.",
)

model_option = click.option(
    "--model",
    default=DEFAULT_MODEL,
    show_default=True,
    help="Sentence-transformer model name.",
)

wipe_option = click.option(
    "--no-wipe",
    "wipe",
    is_flag=True,
    flag_value=False,
    default=True,
    help="Skip wiping existing data before building (default: wipe).",
)

data_option = click.option(
    "--data",
    required=True,
    help="Directory containing pathway files (KGML, SBML, BioPAX, CSV).",
)
