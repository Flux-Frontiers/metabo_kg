"""
cmd_pack.py — pack subcommand.

Registers:
  metabokg pack  — semantic search + graph expansion → rich context pack

Author: Eric G. Suchanek, PhD
Last Revision: 2026-04-20
License: Elastic 2.0
"""

from __future__ import annotations

import sys

import click

from metabokg.cli.main import cli
from metabokg.cli.options import (
    db_option,
    lancedb_option,
    model_option,
    resolve_db,
    resolve_lancedb,
)


@cli.command("pack")
@click.argument("query_text")
@db_option
@lancedb_option
@model_option
@click.option(
    "--k", default=8, show_default=True, type=int, help="Seed results from vector search."
)
@click.option(
    "--hop",
    "--hops",
    default=1,
    show_default=True,
    type=int,
    help="Graph hops to expand from seed results.",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Write pack to this file (.md or .json).  Defaults to stdout.",
)
@click.option(
    "--fmt",
    type=click.Choice(["md", "json"], case_sensitive=False),
    default="md",
    show_default=True,
    help="Output format: Markdown or JSON.",
)
@click.option(
    "--max-rxn",
    default=30,
    show_default=True,
    type=int,
    help="Maximum reactions shown per pathway section.",
)
def pack(
    query_text: str,
    db: str | None,
    lancedb: str | None,
    model: str,
    k: int,
    hop: int,
    output: str | None,
    fmt: str,
    max_rxn: int,
) -> None:
    """Build a context-rich metabolic pack from a semantic query.

    Runs vector search, expands through graph neighbours, then bundles
    each matched node with its biological context (reactions, substrates,
    products, enzymes) into a structured Markdown or JSON document.

    Suitable for dropping directly into an LLM context window.

    Examples:

        metabokg pack "glucose metabolism"

        metabokg pack "fatty acid oxidation" --k 5 --hop 2 -o fa_pack.md

        metabokg pack "TCA cycle" --fmt json -o tca.json
    """
    from pathlib import Path

    db_path = resolve_db(db)
    lancedb_dir = resolve_lancedb(lancedb)

    if not Path(db_path).exists():
        raise click.ClickException(f"database not found: {db_path}\nRun 'metabokg build' first.")

    if not Path(lancedb_dir).exists():
        raise click.ClickException(
            f"LanceDB index not found at '{lancedb_dir}'.\n"
            "Run 'metabokg build' (without --no-index) to create it."
        )

    from metabokg import MetaKG

    click.echo(
        f"Packing: {query_text!r}  (k={k}, hop={hop})",
        err=True,
    )

    kg = MetaKG(db_path=db_path, lancedb_dir=lancedb_dir, model=model)
    result = kg.pack(query_text, k=k, hop=hop, max_rxn_per_pathway=max_rxn)
    kg.close()

    click.echo(f"  {len(result.sections)} sections", err=True)

    content = result.to_markdown() if fmt == "md" else result.to_json()

    if output:
        Path(output).write_text(content, encoding="utf-8")
        click.echo(f"  written → {output}", err=True)
    else:
        sys.stdout.write(content)


# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------

pack_main = pack
