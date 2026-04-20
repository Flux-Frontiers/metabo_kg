"""
cmd_query.py — query subcommand.

Registers:
  metabokg query  — semantic (vector) or text search across the knowledge graph

Author: Eric G. Suchanek, PhD
Last Revision: 2026-04-19
License: Elastic 2.0
"""

from __future__ import annotations

import click

from metabokg.cli.main import cli
from metabokg.cli.options import (
    db_option,
    lancedb_option,
    model_option,
    resolve_db,
    resolve_lancedb,
)


@cli.command("query")
@click.argument("query_text")
@db_option
@lancedb_option
@model_option
@click.option("--k", default=10, show_default=True, type=int, help="Number of results to return.")
@click.option(
    "--hop",
    "--hops",
    default=0,
    show_default=True,
    type=int,
    help="Graph hops to expand from seed results (0 = seeds only).",
)
@click.option(
    "--text-only",
    is_flag=True,
    help="Use substring text search instead of vector search.",
)
def query(
    query_text: str,
    db: str | None,
    lancedb: str | None,
    model: str,
    k: int,
    hop: int,
    text_only: bool,
) -> None:
    """Search the MetaboKG knowledge graph by semantic similarity or text.

    Uses vector (semantic) search via LanceDB by default; falls back to
    substring text search if the index is unavailable or --text-only is set.

    Example:

        metabokg query "glucose metabolism"

        metabokg query "ATP synthase" --k 5 --text-only
    """
    from pathlib import Path

    db_path = resolve_db(db)
    lancedb_dir = resolve_lancedb(lancedb)

    if not Path(db_path).exists():
        raise click.ClickException(f"database not found: {db_path}\nRun 'metabokg build' first.")

    if text_only:
        _run_text_query(db_path, query_text, k, hop)
        return

    lancedb_path = Path(lancedb_dir)
    if lancedb_path.exists():
        _run_vector_query(db_path, lancedb_dir, model, query_text, k, hop)
    else:
        click.echo(
            f"LanceDB index not found at '{lancedb_dir}' — falling back to text search.",
            err=True,
        )
        _run_text_query(db_path, query_text, k, hop)


def _run_vector_query(
    db_path: str, lancedb_dir: str, model: str, query_text: str, k: int, hop: int
) -> None:
    from metabokg import MetaKG

    kg = MetaKG(db_path=db_path, lancedb_dir=lancedb_dir, model=model)
    click.echo(f"Semantic search: '{query_text}'  (vector, k={k}, hop={hop})", err=True)
    click.echo(f"  db      : {db_path}", err=True)
    click.echo(f"  lancedb : {lancedb_dir}\n", err=True)

    results = kg.query(query_text, k=k, hop=hop)
    hits = results.hits

    kg.close()

    if not hits:
        click.echo("No results found.")
        return

    _print_hits(hits)


def _run_text_query(db_path: str, query_text: str, k: int, hop: int) -> None:
    from metabokg.store import GraphStore

    store = GraphStore(db_path)
    click.echo(f"Text search: '{query_text}'  (substring, k={k}, hop={hop})", err=True)
    click.echo(f"  db : {db_path}\n", err=True)

    hits = store.query_text(query_text, k=k)

    if hop > 0:
        hits = store.expand_hops(hits, hop)

    store.close()

    if not hits:
        click.echo("No results found.")
        return

    _print_hits(hits)


def _print_hits(hits: list[dict]) -> None:
    for i, hit in enumerate(hits, 1):
        kind = hit.get("kind", "")
        name = hit.get("name", "")
        node_id = hit.get("id", "")
        score = hit.get("score", "")
        score_str = f"  score={score:.3f}" if isinstance(score, float) else ""
        click.echo(f"{i:>3}. [{kind:<8}] {name[:60]:<60}  {node_id}{score_str}")


# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------

query_main = query
