"""
test_mcp_server.py

Regression tests for metabokg.mcp_tools against the installed ``mcp`` release.

mcp 2.0 removed the bundled ``mcp.server.fastmcp`` module (FastMCP was split
out into the standalone ``fastmcp`` package) and rebuilt mcp.server around new
submodules. `pyproject.toml` pins ``mcp<2`` for that reason; these tests fail
loudly if the pin is lifted without porting the server, instead of shipping a
console script that dies the moment someone starts it.

Unlike the sibling KG repos, MetaKG does *not* build its server at module
import — ``create_server()`` constructs ``FastMCP`` behind a function-level
import and ``register_tools()`` attaches the tools imperatively. An
import-only test would therefore pass against an incompatible ``mcp`` while
``metabokg mcp`` stayed broken, so these call ``create_server()`` for real.
Same lesson kgrag learned, whose server is built inside ``_make_server()``.

``MetaKG.__init__`` only resolves paths — no database or index is opened — so
building a server against a throwaway directory is cheap and touches nothing.
"""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path

import pytest

# The 13 tools registered by register_tools(), in registration order.
EXPECTED_TOOLS = {
    "pack",
    "query_pathway",
    "get_compound",
    "get_reaction",
    "find_path",
    "simulate_fba",
    "simulate_ode",
    "simulate_whatif",
    "get_kinetic_params",
    "seed_kinetics",
    "snapshot_list",
    "snapshot_show",
    "snapshot_diff",
}


@pytest.fixture
def server(tmp_path: Path):
    """A real FastMCP server with every MetaKG tool registered."""
    from metabokg import MetaKG
    from metabokg.mcp_tools import create_server

    kg = MetaKG(db_path=tmp_path / "hsa.sqlite", vectors_path=tmp_path / "vectors.sqlite")
    return create_server(kg)


def test_tools_module_imports():
    """The module must import cleanly against the installed mcp release."""
    importlib.import_module("metabokg.mcp_tools")


def test_fastmcp_import_path_exists():
    """``mcp.server.fastmcp`` must exist — mcp 2.0 removed it.

    Asserted directly so the failure names the actual incompatibility rather
    than surfacing as an opaque ImportError from inside ``create_server()``.
    """
    importlib.import_module("mcp.server.fastmcp")


def test_entry_point_target_exists():
    """``metabokg-mcp`` resolves to metabokg.cli:mcp_main."""
    cli = importlib.import_module("metabokg.cli")
    assert callable(cli.mcp_main)


def test_create_server_builds_against_installed_mcp(server):
    """``create_server()`` must construct FastMCP — the call-time failure mode."""
    assert server is not None


def test_tools_are_registered(server):
    """Every documented tool survives registration."""
    names = {t.name for t in _list_tools(server)}
    assert names == EXPECTED_TOOLS


def test_tool_count_matches_documented_surface(server):
    """The server advertises 13 tools, as stated in the README and MCP docs."""
    assert len(_list_tools(server)) == 13


def _list_tools(server):
    """Return the registered FastMCP tools.

    ``FastMCP.list_tools()`` is async; run it on a private loop rather than
    depending on an async test plugin.
    """
    return asyncio.run(server.list_tools())
