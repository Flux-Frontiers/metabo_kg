"""
options.py — Reusable Click option decorators for MetaKG CLI commands.

Author: Eric G. Suchanek, PhD
Last Revision: 2026-08-01
License: Elastic 2.0
"""

from __future__ import annotations

import os

import click

from metabokg.embed import DEFAULT_MODEL

_DEFAULT_DB = "data/hsa_pathways/.metabokg/hsa.sqlite"
_DEFAULT_VECTORS = "data/hsa_pathways/.metabokg/vectors.sqlite"


def resolve_db(db: str | None) -> str:
    """Return the effective db path: explicit arg > METABOKG_DB env > CWD default."""
    return db or os.environ.get("METABOKG_DB", _DEFAULT_DB)


def resolve_vectors(vectors: str | None) -> str:
    """Return the effective vectors path: explicit arg > METABOKG_VECTORS env > CWD default."""
    return vectors or os.environ.get("METABOKG_VECTORS", _DEFAULT_VECTORS)


db_option = click.option(
    "--db",
    default=None,
    show_default=False,
    help=f"Path to MetaKG SQLite database (default: {_DEFAULT_DB} or METABOKG_DB env).",
)

vectors_option = click.option(
    "--vectors",
    default=None,
    show_default=False,
    help=f"Path to the sqlite-vec vector store (default: {_DEFAULT_VECTORS} or METABOKG_VECTORS env).",
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
