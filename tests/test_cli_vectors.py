"""CLI wiring tests for the ``--vectors`` surface (0.10.0 sqlite-vec migration).

Every command touched by the LanceDB → sqlite-vec rename had **zero** test
coverage, which is the exact condition under which a bulk rename produces a
latent ``NameError``: the flag is declared on the decorator, the function
parameter still carries the old name, and nothing notices until someone runs
the command.  `--help` alone does not catch it — Click renders help without
ever calling the body.

So these assert two things per command: that it accepts ``--vectors``, and
that the value actually reaches ``MetaKG(vectors_path=...)``.  The KG itself is
stubbed, so nothing here loads an embedding model or touches a real store.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

import metabokg.cli  # noqa: F401 — registers every subcommand on `cli`
from metabokg.cli.main import cli
from metabokg.cli.options import resolve_db, resolve_vectors

# Commands that take --db/--vectors and construct a MetaKG.
_KG_COMMANDS = ["build", "update", "query", "pack", "mcp"]


@pytest.fixture
def runner():
    return CliRunner()


class StubKG:
    """Records the kwargs it was constructed with; no model, no store."""

    calls: list[dict] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        StubKG.calls.append(kwargs)

    def build(self, **_kwargs):
        return _StubStats()

    def query(self, *_args, **_kwargs):
        return _StubResult()

    def pack(self, *_args, **_kwargs):
        return _StubPack()

    def close(self):
        pass


class _StubStats:
    parse_errors: list[dict] = []

    def __str__(self):
        return "stub build stats"


class _StubResult:
    hits: list[dict] = []


class _StubPack:
    sections: list[dict] = []

    def to_markdown(self):
        return "# stub"

    def to_json(self):
        return "{}"


@pytest.fixture
def stub_kg(monkeypatch):
    """Replace ``metabokg.MetaKG`` — commands import it inside the function body."""
    StubKG.calls = []
    monkeypatch.setattr("metabokg.MetaKG", StubKG)
    return StubKG


@pytest.fixture
def corpus(tmp_path):
    """A minimal on-disk corpus: the files the commands stat before running."""
    data = tmp_path / "hsa_pathways"
    data.mkdir()
    (data / "hsa00010.kgml").write_text("<pathway/>")
    dot = data / ".metabokg"
    dot.mkdir()
    db = dot / "hsa.sqlite"
    db.touch()
    vectors = dot / "vectors.sqlite"
    vectors.touch()
    return {"data": data, "db": db, "vectors": vectors}


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestResolveVectors:
    """Precedence: explicit arg > env > CWD default."""

    def test_explicit_argument_wins(self, monkeypatch):
        monkeypatch.setenv("METABOKG_VECTORS", "/from/env.sqlite")
        assert resolve_vectors("/explicit.sqlite") == "/explicit.sqlite"

    def test_env_var_is_the_new_name(self, monkeypatch):
        monkeypatch.setenv("METABOKG_VECTORS", "/from/env.sqlite")
        assert resolve_vectors(None) == "/from/env.sqlite"

    def test_old_env_var_is_not_honoured(self, monkeypatch):
        """METABOKG_LANCEDB is gone — silently honouring it would hide the rename."""
        monkeypatch.delenv("METABOKG_VECTORS", raising=False)
        monkeypatch.setenv("METABOKG_LANCEDB", "/stale/lancedb")
        assert resolve_vectors(None) != "/stale/lancedb"

    def test_default_is_a_sqlite_file_not_a_directory(self, monkeypatch):
        monkeypatch.delenv("METABOKG_VECTORS", raising=False)
        default = resolve_vectors(None)
        assert default.endswith("vectors.sqlite")
        assert "lancedb" not in default

    def test_db_resolution_is_unchanged(self, monkeypatch):
        monkeypatch.setenv("METABOKG_DB", "/from/env.sqlite")
        assert resolve_db(None) == "/from/env.sqlite"
        assert resolve_db("/explicit.sqlite") == "/explicit.sqlite"


class TestColocatedDefaults:
    """Derived paths must land on vectors.sqlite beside the graph db."""

    def test_build_derives_vectors_beside_the_db(self, tmp_path):
        from metabokg.cli.cmd_build import _colocate_defaults

        db, vectors = _colocate_defaults(tmp_path / "hsa_pathways", None, None)
        assert Path(db).name == "hsa.sqlite"
        assert Path(vectors) == Path(db).parent / "vectors.sqlite"

    def test_build_honours_an_explicit_vectors_path(self, tmp_path):
        from metabokg.cli.cmd_build import _colocate_defaults

        _db, vectors = _colocate_defaults(tmp_path / "hsa_pathways", None, "/custom.sqlite")
        assert vectors == "/custom.sqlite"

    def test_init_derives_vectors_beside_the_db(self, tmp_path):
        from metabokg.cli.cmd_init import _colocate_db

        db, vectors = _colocate_db(tmp_path / "cge_pathways")
        assert Path(db).name == "cge.sqlite"
        assert Path(vectors) == Path(db).parent / "vectors.sqlite"


# ---------------------------------------------------------------------------
# Flag surface
# ---------------------------------------------------------------------------


class TestFlagSurface:
    def _params(self, name: str) -> set[str]:
        opts: set[str] = set()
        for param in cli.commands[name].params:
            opts.update(getattr(param, "opts", []))
        return opts

    @pytest.mark.parametrize("name", [*_KG_COMMANDS, "info", "viz", "viz3d"])
    def test_command_exposes_vectors_and_not_lancedb(self, name):
        opts = self._params(name)
        assert "--vectors" in opts
        assert "--lancedb" not in opts

    @pytest.mark.parametrize("name", sorted(cli.commands))
    def test_no_command_anywhere_still_offers_lancedb(self, name):
        assert "--lancedb" not in self._params(name)

    @pytest.mark.parametrize("name", sorted(cli.commands))
    def test_help_renders_and_mentions_no_lancedb(self, runner, name):
        """A rename that breaks a decorator surfaces here as a non-zero exit."""
        result = runner.invoke(cli, [name, "--help"])
        assert result.exit_code == 0, result.output
        assert "lancedb" not in result.output.lower()


# ---------------------------------------------------------------------------
# The value actually reaches MetaKG
# ---------------------------------------------------------------------------


class TestVectorsReachesTheKG:
    """`--help` proves the flag parses; only invocation proves it is threaded."""

    def test_build(self, runner, stub_kg, corpus, tmp_path):
        custom = tmp_path / "custom.sqlite"
        result = runner.invoke(
            cli,
            ["build", "--data", str(corpus["data"]), "--vectors", str(custom)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert stub_kg.calls[-1]["vectors_path"] == str(custom)

    def test_update(self, runner, stub_kg, corpus, tmp_path):
        custom = tmp_path / "custom.sqlite"
        result = runner.invoke(
            cli,
            ["update", "--data", str(corpus["data"]), "--vectors", str(custom)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert stub_kg.calls[-1]["vectors_path"] == str(custom)

    def test_build_without_the_flag_uses_the_colocated_default(self, runner, stub_kg, corpus):
        result = runner.invoke(
            cli, ["build", "--data", str(corpus["data"])], catch_exceptions=False
        )
        assert result.exit_code == 0, result.output
        assert stub_kg.calls[-1]["vectors_path"] == str(corpus["vectors"])

    def test_query(self, runner, stub_kg, corpus):
        result = runner.invoke(
            cli,
            [
                "query",
                "glycolysis",
                "--db",
                str(corpus["db"]),
                "--vectors",
                str(corpus["vectors"]),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert stub_kg.calls[-1]["vectors_path"] == str(corpus["vectors"])

    def test_pack(self, runner, stub_kg, corpus):
        result = runner.invoke(
            cli,
            [
                "pack",
                "glycolysis",
                "--db",
                str(corpus["db"]),
                "--vectors",
                str(corpus["vectors"]),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert stub_kg.calls[-1]["vectors_path"] == str(corpus["vectors"])

    def test_mcp(self, runner, stub_kg, corpus, monkeypatch):
        started: dict = {}

        class _Server:
            def run(self, **kwargs):
                started.update(kwargs)

        monkeypatch.setattr("metabokg.mcp_tools.create_server", lambda _kg: _Server())
        result = runner.invoke(
            cli,
            ["mcp", "--db", str(corpus["db"]), "--vectors", str(corpus["vectors"])],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert stub_kg.calls[-1]["vectors_path"] == str(corpus["vectors"])
        assert started["transport"] == "stdio"

    def test_no_command_passes_the_removed_table_parameter(self, runner, stub_kg, corpus):
        """`table` was LanceDB-only and is gone from the constructor."""
        runner.invoke(cli, ["build", "--data", str(corpus["data"])], catch_exceptions=False)
        assert "table" not in stub_kg.calls[-1]
        assert "lancedb_dir" not in stub_kg.calls[-1]


# ---------------------------------------------------------------------------
# Commands that report or launch rather than construct a KG
# ---------------------------------------------------------------------------


class TestInfo:
    def test_reports_the_resolved_vectors_path(self, runner, corpus):
        result = runner.invoke(
            cli,
            ["info", "--db", str(corpus["db"]), "--vectors", str(corpus["vectors"])],
            catch_exceptions=False,
        )
        assert "Vectors :" in result.output
        assert str(corpus["vectors"]) in result.output
        assert "LanceDB" not in result.output

    def test_marks_a_missing_store_as_not_built(self, runner, corpus, tmp_path):
        result = runner.invoke(
            cli,
            [
                "info",
                "--db",
                str(corpus["db"]),
                "--vectors",
                str(tmp_path / "absent.sqlite"),
            ],
            catch_exceptions=False,
        )
        assert "[not built]" in result.output

    def test_marks_a_present_store_as_existing(self, runner, corpus):
        result = runner.invoke(
            cli,
            ["info", "--db", str(corpus["db"]), "--vectors", str(corpus["vectors"])],
            catch_exceptions=False,
        )
        assert "[exists]" in result.output


class TestVizLaunchers:
    """The launchers hand paths off by env var / kwarg — both were renamed."""

    def test_viz_exports_the_new_env_var(self, monkeypatch, tmp_path):
        import metabokg.metabokg_viz as viz

        captured: dict = {}
        monkeypatch.setattr(viz.subprocess, "run", lambda *_a, **kw: captured.update(kw) or None)
        monkeypatch.setattr(viz.Path, "exists", lambda _self: True)

        viz.main(db=str(tmp_path / "hsa.sqlite"), vectors=str(tmp_path / "v.sqlite"))

        env = captured["env"]
        assert env["METABOKG_VECTORS"] == str(tmp_path / "v.sqlite")
        assert "METABOKG_LANCEDB" not in env

    def test_viz3d_passes_vectors_path_to_launch(self, monkeypatch, tmp_path):
        import metabokg.metabokg_viz3d as viz3d

        db = tmp_path / "hsa.sqlite"
        db.touch()
        captured: dict = {}
        fake = type(sys)("metabokg.viz3d")
        fake.launch = lambda **kwargs: captured.update(kwargs)
        monkeypatch.setitem(sys.modules, "metabokg.viz3d", fake)

        viz3d.main(db=str(db), vectors=str(tmp_path / "v.sqlite"))

        assert captured["vectors_path"] == str(tmp_path / "v.sqlite")
        assert "lancedb_dir" not in captured

    def test_viz_command_threads_the_flag_through(self, runner, monkeypatch, tmp_path):
        captured: dict = {}
        monkeypatch.setattr("metabokg.metabokg_viz.main", lambda **kwargs: captured.update(kwargs))
        result = runner.invoke(
            cli, ["viz", "--vectors", str(tmp_path / "v.sqlite")], catch_exceptions=False
        )
        assert result.exit_code == 0, result.output
        assert captured["vectors"] == str(tmp_path / "v.sqlite")

    def test_viz3d_command_threads_the_flag_through(self, runner, monkeypatch, tmp_path):
        captured: dict = {}
        monkeypatch.setattr(
            "metabokg.metabokg_viz3d.main", lambda **kwargs: captured.update(kwargs)
        )
        result = runner.invoke(
            cli,
            ["viz3d", "--vectors", str(tmp_path / "v.sqlite")],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert captured["vectors"] == str(tmp_path / "v.sqlite")


# ---------------------------------------------------------------------------
# Missing-store guidance
# ---------------------------------------------------------------------------


class TestMissingStoreMessages:
    def test_query_falls_back_to_text_search(self, runner, corpus, tmp_path, monkeypatch):
        """A missing vector store must degrade, not crash — and say so."""
        monkeypatch.setattr(
            "metabokg.store.GraphStore",
            lambda *_a, **_k: _StubGraphStore(),
        )
        result = runner.invoke(
            cli,
            [
                "query",
                "glycolysis",
                "--db",
                str(corpus["db"]),
                "--vectors",
                str(tmp_path / "absent.sqlite"),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "falling back to text search" in result.output
        assert "lancedb" not in result.output.lower()

    def test_pack_refuses_without_a_vector_store(self, runner, corpus, tmp_path):
        """pack has no text fallback, so it must fail with a build instruction."""
        result = runner.invoke(
            cli,
            [
                "pack",
                "glycolysis",
                "--db",
                str(corpus["db"]),
                "--vectors",
                str(tmp_path / "absent.sqlite"),
            ],
        )
        assert result.exit_code != 0
        assert "Vector index not found" in result.output
        assert "metabokg build" in result.output


class _StubGraphStore:
    def query_text(self, *_args, **_kwargs):
        return []

    def expand_hops(self, hits, _hop):
        return hits

    def close(self):
        pass


def test_options_module_exports_no_lancedb_symbols():
    """`resolve_lancedb` / `lancedb_option` are gone, not merely unused."""
    from metabokg.cli import options

    assert not [n for n in dir(options) if "lancedb" in n.lower()]
    assert isinstance(options.vectors_option, type(click.option("--x")))
