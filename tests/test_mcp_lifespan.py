"""The MCP server's lifespan hook closes the graph's SQLite connection on
shutdown -- the resource-cleanup pattern genealogy_kg set and kgrag_priv's
FLEET_STANDARDS.md records (sweep item 5). FastMCP's ``lifespan=`` fires on
both the stdio and SSE transports, since both route through the same
underlying ``Server.run()``.

Drives the real server through ``mcp.shared.memory``'s in-process transport:
an actual ``Server.run()``/lifespan cycle, not a mock of ``close``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from metabokg import MetaKG
from metabokg.mcp_tools import create_server

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_lifespan_closes_kg_on_server_shutdown(tmp_path: Path) -> None:
    # Unlike the other fleet servers, this one is built by a factory that is
    # handed the MetaKG, so the lifespan closes that instance directly rather
    # than looking up a module global. An empty graph is enough -- what is
    # under test is that an open connection does not survive shutdown, so
    # open one and let the server tear down.
    kg = MetaKG(db_path=tmp_path / "hsa.sqlite", vectors_path=tmp_path / "vectors.sqlite")
    kg.store  # noqa: B018 - constructing MetaStore opens the connection eagerly
    server = create_server(kg)

    async with create_connected_server_and_client_session(server) as session:
        await session.list_tools()

    # The server task has fully unwound by the time the block above exits,
    # so the lifespan's `finally: metabokg.close()` has already run. MetaStore
    # closes its connection without dropping the reference, so the observable
    # effect is that the handle no longer works.
    assert kg._store is not None  # noqa: SLF001
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        kg._store._conn.execute("SELECT 1")  # noqa: SLF001
