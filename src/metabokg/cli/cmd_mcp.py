"""
cmd_mcp.py — mcp subcommand.

Registers:
  metabokg mcp  — start the MetaKG MCP server
"""

from __future__ import annotations

from pathlib import Path

import click

from metabokg.cli.main import cli
from metabokg.cli.options import (
    db_option,
    lancedb_option,
    model_option,
    resolve_db,
    resolve_lancedb,
)


@cli.command("mcp")
@db_option
@lancedb_option
@model_option
@click.option(
    "--transport",
    default="stdio",
    show_default=True,
    type=click.Choice(["stdio", "sse"]),
    help="MCP transport: stdio or sse (HTTP).",
)
def mcp(db: str | None, lancedb: str | None, model: str, transport: str) -> None:
    """Start the MetaKG MCP server."""
    from metabokg import MetaKG
    from metabokg.mcp_tools import create_server

    db_path = Path(resolve_db(db))
    lancedb = resolve_lancedb(lancedb)
    if not db_path.exists():
        click.echo(
            f"WARNING: database not found at '{db_path}'.\nRun 'metabokg build' first.",
            err=True,
        )

    click.echo(
        f"MetaKG MCP server starting\n"
        f"  db       : {db_path}\n"
        f"  lancedb  : {lancedb}\n"
        f"  model    : {model}\n"
        f"  transport: {transport}",
        err=True,
    )

    kg = MetaKG(db_path=db_path, lancedb_dir=lancedb, model=model)
    server = create_server(kg)
    server.run(transport=transport)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------

mcp_main = mcp
