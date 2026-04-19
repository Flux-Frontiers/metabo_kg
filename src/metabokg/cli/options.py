"""
options.py — Reusable Click option decorators for MetaKG CLI commands.
"""

from __future__ import annotations

import os

import click

from metabokg.embed import DEFAULT_MODEL

_DEFAULT_DB = ".metabokg/hsa.sqlite"
_DEFAULT_LANCEDB = ".metabokg/lancedb"


def resolve_db(db: str | None) -> str:
    """Return the effective db path: explicit arg > METABOKG_DB env > CWD default."""
    return db or os.environ.get("METABOKG_DB", _DEFAULT_DB)


def resolve_lancedb(lancedb: str | None) -> str:
    """Return the effective lancedb path: explicit arg > METABOKG_LANCEDB env > CWD default."""
    return lancedb or os.environ.get("METABOKG_LANCEDB", _DEFAULT_LANCEDB)


db_option = click.option(
    "--db",
    default=None,
    show_default=False,
    help=f"Path to MetaKG SQLite database (default: {_DEFAULT_DB} or METABOKG_DB env).",
)

lancedb_option = click.option(
    "--lancedb",
    default=None,
    show_default=False,
    help=f"Path to LanceDB directory (default: {_DEFAULT_LANCEDB} or METABOKG_LANCEDB env).",
)

model_option = click.option(
    "--model",
    default=DEFAULT_MODEL,
    show_default=True,
    help="Sentence-transformer model name.",
)

wipe_option = click.option(
    "--wipe",
    is_flag=True,
    default=False,
    help="Wipe existing data before building (default: keep existing).",
)

data_option = click.option(
    "--data",
    required=True,
    help="Directory containing pathway files (KGML, SBML, BioPAX, CSV).",
)
