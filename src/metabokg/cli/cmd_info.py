"""
cmd_info.py — info subcommand.

Registers:
  metabokg info  — show which corpus is active and its node/edge counts

Author: Eric G. Suchanek, PhD
Last Revision: 2026-04-20
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path

import click

from metabokg.cli.main import cli
from metabokg.cli.options import db_option, lancedb_option, resolve_db, resolve_lancedb


@cli.command("info")
@db_option
@lancedb_option
def info(db: str | None, lancedb: str | None) -> None:
    """Show the active MetaboKG corpus: resolved paths and node/edge counts.

    Example:

        metabokg info

        metabokg info --db data/cge_pathways/.metabokg/cge.sqlite
    """
    db_path = resolve_db(db)
    lancedb_dir = resolve_lancedb(lancedb)

    db_file = Path(db_path)
    lancedb_path = Path(lancedb_dir)

    corpus = db_file.stem  # e.g. "hsa" from "hsa.sqlite"

    click.echo(f"Corpus  : {corpus}")
    click.echo(f"DB      : {db_path}")
    click.echo(f"LanceDB : {lancedb_dir}  {'[exists]' if lancedb_path.exists() else '[not built]'}")

    if not db_file.exists():
        click.echo("\n[not built — run 'metabokg build' first]")
        return

    from metabokg.store import GraphStore

    store = GraphStore(db_path)
    s = store.stats()
    store.close()

    click.echo()
    click.echo(f"Nodes   : {s['total_nodes']:,}")
    for kind, count in sorted(s["node_counts"].items()):
        click.echo(f"  {kind:<12} {count:>6,}")
    click.echo(f"Edges   : {s['total_edges']:,}")
    for rel, count in sorted(s["edge_counts"].items()):
        click.echo(f"  {rel:<20} {count:>6,}")


# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------

info_main = info
