"""
cmd_mcp.py — mcp subcommand.

Registers ``metabokg mcp``, the fleet's standard MCP command from
:mod:`kg_utils.mcp`::

    metabokg mcp [--repo DIR] [--db FILE] [--vectors FILE] [--model NAME]
                 [--transport stdio|streamable-http] [--host H] [--port N]
                 [--manifest]

``--db`` and ``--vectors`` fall back to ``METABOKG_DB`` / ``METABOKG_VECTORS``,
then to the bundled human corpus under ``--repo``; a relative path is taken
from ``--repo``. Registering the command imports neither ``mcp`` nor the
server module.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kg_utils.mcp import add_mcp_command

from metabokg.cli.main import cli
from metabokg.cli.options import resolve_db, resolve_vectors

if TYPE_CHECKING:
    from kg_utils.mcp import KGServer


def _under(repo: Path, path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else repo / p


def _build_server(repo: Path, db: Path | None, vectors: Path | None, model: str | None) -> KGServer:
    from metabokg.mcp_tools import build_server  # pylint: disable=import-outside-toplevel

    repo = Path(repo).resolve()
    db_path = db or _under(repo, resolve_db(None))
    vectors_path = vectors or _under(repo, resolve_vectors(None))
    return build_server(db_path, vectors_path, model)


mcp_command = add_mcp_command(cli, _build_server)

# ---------------------------------------------------------------------------
# Standalone entry-point alias
# ---------------------------------------------------------------------------


def mcp_main(argv: list[str] | None = None) -> None:
    """Entry point for ``metabokg-mcp``: the same command as ``metabokg mcp``.

    :param argv: Arguments; ``None`` for ``sys.argv[1:]``.
    """
    mcp_command.main(args=argv, prog_name="metabokg-mcp")


__all__ = ["mcp_command", "mcp_main"]
