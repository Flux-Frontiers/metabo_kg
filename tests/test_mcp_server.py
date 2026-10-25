"""
test_mcp_server.py

The MetaKG MCP server on the fleet's shared base, ``kg_utils.mcp``.

Import-level regression tests first: an incompatible ``mcp`` release breaks
the server at import or build time, and only for people installing from PyPI.

Then what step 4 of kgrag_priv's MCP centralization plan promises: the five
canonical tools first, MetaKG's twelve after them, each extra described by the
``_mcp_*`` handler it wraps; ``stats``, ``get_node`` and ``neighbors`` never
load the model; the manifest answers without a graph; ``metabokg``'s other
commands do not import ``mcp``; ``--db``/``METABOKG_DB`` resolve under
``--repo``; a missing graph is refused; and a real stdio subprocess serves.

The graph is the five-node glycolysis fixture written straight into
``MetaStore``; the semantic index is a stub, so no model is downloaded.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import anyio
import pytest
from click.testing import CliRunner
from kg_utils.mcp import CANONICAL_TOOLS, manifest
from kg_utils.stats import stats_problems
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

import metabokg
from metabokg.cli.main import cli
from metabokg.mcp_tools import EXTRA_TOOLS, build_server
from metabokg.orchestrator import MetaKG
from metabokg.primitives import (
    KIND_COMPOUND,
    KIND_ENZYME,
    KIND_PATHWAY,
    KIND_REACTION,
    MetaEdge,
    MetaNode,
    node_id,
)
from metabokg.store import MetaStore

_SRC = str(Path(metabokg.__file__).resolve().parents[1])
_EXTRAS = [
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
]
GLC = node_id(KIND_COMPOUND, "kegg", "C00031")
PYR = node_id(KIND_COMPOUND, "kegg", "C00022")
RXN = node_id(KIND_REACTION, "kegg", "R00200")
PWY = node_id(KIND_PATHWAY, "kegg", "hsa00010")
ENZ = node_id(KIND_ENZYME, "ec", "2.7.1.1")


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / ".metabokg" / "hsa.sqlite"
    store = MetaStore(path)
    store.write(
        [
            MetaNode(id=GLC, kind=KIND_COMPOUND, name="D-Glucose", source_format="csv"),
            MetaNode(id=PYR, kind=KIND_COMPOUND, name="Pyruvate", source_format="csv"),
            MetaNode(id=RXN, kind=KIND_REACTION, name="Glycolysis reaction", source_format="csv"),
            MetaNode(id=PWY, kind=KIND_PATHWAY, name="Glycolysis", source_format="csv"),
            MetaNode(id=ENZ, kind=KIND_ENZYME, name="Hexokinase", source_format="csv"),
        ],
        [
            MetaEdge(src=GLC, rel="SUBSTRATE_OF", dst=RXN),
            MetaEdge(src=RXN, rel="PRODUCT_OF", dst=PYR),
            MetaEdge(src=ENZ, rel="CATALYZES", dst=RXN),
            MetaEdge(src=PWY, rel="CONTAINS", dst=RXN),
        ],
    )
    store.close()
    return path


class _Hit:
    def __init__(self, nid: str, distance: float):
        self.id, self.distance = nid, distance


class _StubIndex:
    """Answers every search with glucose, then the pathway."""

    def search(self, _text: str, k: int = 8):
        return [_Hit(GLC, 0.1), _Hit(PWY, 0.3)][:k]


@pytest.fixture
def stub_index(monkeypatch):
    monkeypatch.setattr(MetaKG, "index", property(lambda _self: _StubIndex()))


def _refuse_model(monkeypatch):
    def refuse(*_a, **_k):
        raise RuntimeError("embedding model load refused by test")

    monkeypatch.setattr("metabokg.embed.SentenceTransformerEmbedder", refuse)


def _server(db: Path):
    return build_server(db, db.parent / "vectors.sqlite")


def _session(server, fn):
    async def main():
        async with create_connected_server_and_client_session(server) as client:
            return await fn(client)

    return anyio.run(main)


# ---------------------------------------------------------------------------
# Import level
# ---------------------------------------------------------------------------


def test_fastmcp_import_path_exists():
    """``mcp.server.fastmcp`` must exist -- mcp 2.0 removed it."""
    import importlib

    importlib.import_module("mcp.server.fastmcp")


def test_entry_point_target_exists():
    """``metabokg-mcp`` resolves to metabokg.cli:mcp_main."""
    from metabokg.cli import mcp_main

    assert callable(mcp_main)


# ---------------------------------------------------------------------------
# The tool surface
# ---------------------------------------------------------------------------


def test_canonical_tools_then_the_extras(tmp_path):
    tools = manifest(_server(tmp_path / "x.sqlite"))["tools"]
    assert [t["name"] for t in tools] == [*CANONICAL_TOOLS, *_EXTRAS]
    assert [t.__name__ for t in EXTRA_TOOLS] == _EXTRAS


def test_extras_carry_their_handlers_descriptions(tmp_path):
    tools = {t["name"]: t for t in manifest(_server(tmp_path / "x.sqlite"))["tools"]}
    assert tools["get_compound"]["description"].startswith("Retrieve a compound node")
    assert "metabokg" not in tools["get_compound"]["input_schema"]["properties"]


def test_graph_tools_answer_without_a_model(db, monkeypatch):
    _refuse_model(monkeypatch)

    async def calls(client: ClientSession):
        return (
            await client.call_tool("stats", {}),
            await client.call_tool("get_node", {"node_id": RXN}),
            await client.call_tool("neighbors", {"node_id": RXN, "direction": "in"}),
            await client.call_tool("get_node", {"node_id": "nope"}),
            await client.call_tool("get_reaction", {"reaction_id": RXN}),
            await client.call_tool("query", {"q": "glucose"}),
        )

    stats, node, near, missing, rxn, query = _session(_server(db), calls)
    assert not stats.isError and stats_problems(stats.structuredContent) == []
    assert stats.structuredContent["nodes"]["total"] == 5
    assert stats.structuredContent["kind"] == "metabolic"
    assert not node.isError and node.structuredContent["name"] == "Glycolysis reaction"
    assert [(e["src"], e["rel"]) for e in near.structuredContent["edges"]] == [
        (ENZ, "CATALYZES"),
        (PWY, "CONTAINS"),
        (GLC, "SUBSTRATE_OF"),
    ]
    assert missing.isError and "no node with id 'nope'" in missing.content[0].text
    assert not rxn.isError and "R00200" in rxn.content[0].text
    assert query.isError and "embedding model load refused by test" in query.content[0].text


def test_query_and_pack_through_mcp(db, stub_index):
    async def calls(client: ClientSession):
        return (
            await client.call_tool("query", {"q": "glucose", "k": 1}),
            await client.call_tool("query", {"q": "glucose", "k": 1, "hop": 2, "max_nodes": 3}),
            await client.call_tool(
                "query", {"q": "glucose", "k": 1, "hop": 1, "rels": ["CONTAINS"]}
            ),
            await client.call_tool("pack", {"q": "glycolysis", "k": 2, "hop": 0}),
        )

    seeds, capped, narrowed, packed = _session(_server(db), calls)
    assert [h["id"] for h in seeds.structuredContent["hits"]] == [GLC]
    capped_ids = [h["id"] for h in capped.structuredContent["hits"]]
    assert capped_ids[0] == GLC and len(capped_ids) == 3
    assert [h["id"] for h in narrowed.structuredContent["hits"]] == [GLC]
    assert "Glycolysis" in packed.content[0].text


# ---------------------------------------------------------------------------
# MetaKG's canonical surface
# ---------------------------------------------------------------------------


def test_neighbors_contract(db):
    kg = MetaKG(db_path=db, vectors_path=db.parent / "vectors.sqlite")
    out = kg.neighbors(RXN, direction="out")
    assert [e["dst"] for e in out["edges"]] == [PYR]
    assert [n["id"] for n in out["nodes"]] == [PYR]
    assert len(kg.neighbors(RXN, limit=2)["edges"]) == 2
    assert kg.neighbors("nope") is None
    for bad in ({"direction": "up"}, {"limit": 0}):
        with pytest.raises(ValueError):
            kg.neighbors(RXN, **bad)
    kg.close()


def test_query_bounds_name_the_parameter(db, stub_index):
    kg = MetaKG(db_path=db, vectors_path=db.parent / "vectors.sqlite")
    with pytest.raises(ValueError, match="hop"):
        kg.query("x", hop=6)
    with pytest.raises(ValueError, match="max_nodes"):
        kg.query("x", max_nodes=0)
    kg.close()


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


def test_manifest_answers_without_a_graph_and_creates_nothing(tmp_path):
    result = CliRunner().invoke(cli, ["mcp", "--repo", str(tmp_path), "--manifest"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["canonical"] == list(CANONICAL_TOOLS)
    assert list(tmp_path.iterdir()) == []


def test_db_resolves_under_repo_and_from_the_env(db, monkeypatch):
    seen: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        "metabokg.mcp_tools.build_server",
        lambda d, v, m=None: seen.append((Path(d), Path(v))) or build_server(d, v, m),
    )
    repo = db.parent.parent
    monkeypatch.delenv("METABOKG_DB", raising=False)
    monkeypatch.delenv("METABOKG_VECTORS", raising=False)
    CliRunner().invoke(cli, ["mcp", "--repo", str(repo), "--manifest"], catch_exceptions=False)
    monkeypatch.setenv("METABOKG_DB", ".metabokg/hsa.sqlite")
    CliRunner().invoke(cli, ["mcp", "--repo", str(repo), "--manifest"], catch_exceptions=False)
    CliRunner().invoke(cli, ["mcp", "--repo", str(repo), "--db", "other.sqlite", "--manifest"])
    assert seen[0][0] == repo.resolve() / "data/hsa_pathways/.metabokg/hsa.sqlite"
    assert seen[1][0] == repo.resolve() / ".metabokg/hsa.sqlite"
    assert seen[2][0] == repo.resolve() / "other.sqlite"


def test_a_missing_graph_is_refused(tmp_path):
    with pytest.raises(BaseException) as info:  # noqa: PT011 -- ExceptionGroup from the task group
        _session(_server(tmp_path / "absent.sqlite"), lambda c: c.call_tool("stats", {}))
    assert "no graph at" in repr(info.value) or any(
        "no graph at" in str(e) for e in getattr(info.value, "exceptions", ())
    )


def test_sse_is_refused(tmp_path):
    result = CliRunner().invoke(cli, ["mcp", "--repo", str(tmp_path), "--transport", "sse"])
    assert result.exit_code == 2


def test_other_commands_do_not_import_mcp():
    out = subprocess.run(
        [sys.executable, "-c", "import sys, metabokg.cli; print('mcp' in sys.modules)"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert out == "False"


def test_stdio_subprocess_serves(db, tmp_path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from metabokg.cli import mcp_main; mcp_main()", "--db", str(db)],
        env={**os.environ, "PYTHONPATH": _SRC},
    )

    async def run():
        with open(tmp_path / "stderr.log", "w", encoding="utf-8") as errlog:
            async with stdio_client(params, errlog=errlog) as (read, write):
                async with ClientSession(read, write) as client:
                    init = await client.initialize()
                    tools = await client.list_tools()
                    stats = await client.call_tool("stats", {})
                    return init, tools, stats

    init, tools, stats = anyio.run(run)
    assert (init.serverInfo.name, init.serverInfo.version) == ("metabokg", metabokg.__version__)
    assert [t.name for t in tools.tools] == [*CANONICAL_TOOLS, *_EXTRAS]
    assert stats.structuredContent["nodes"]["total"] == 5
    err = (tmp_path / "stderr.log").read_text(encoding="utf-8")
    assert "metabokg MCP server starting (stdio)" in err and f"db      : {db}" in err
