"""Tests for the corpus-readiness reporting in ``metabokg init --check``.

The 0.10.0 migration renamed the status key ``lancedb_ok`` → ``vectors_ok`` and
repointed the probe from a ``lancedb/`` directory to a ``vectors.sqlite`` file.
The key is produced in ``_corpus_status`` and consumed in
``_print_corpus_table`` — two functions, one string, no type checking between
them.  Rename one and not the other and the table silently renders every corpus
as NOT READY (or raises a KeyError), which is exactly the class of bug a bulk
rename produces.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from metabokg.cli.cmd_init import _colocate_db, _corpus_status, _print_corpus_table


class StubSpec:
    """Stands in for a downloader CorpusSpec — only these fields are read."""

    def __init__(self, name: str, data_subdir: Path) -> None:
        self.name = name
        self.data_subdir = str(data_subdir)


@pytest.fixture
def corpus_dir(tmp_path):
    d = tmp_path / "hsa_pathways"
    d.mkdir()
    (d / "hsa00010.kgml").write_text("<pathway/>")
    (d / "hsa00020.kgml").write_text("<pathway/>")
    return d


@pytest.fixture
def spec(corpus_dir):
    return StubSpec("hsa", corpus_dir)


def _build_artifacts(corpus_dir: Path, *, db: bool, vectors: bool) -> None:
    dot = corpus_dir / ".metabokg"
    dot.mkdir(exist_ok=True)
    if db:
        # a real (empty) sqlite file, so the kinetics probe takes its normal path
        import sqlite3

        sqlite3.connect(str(dot / "hsa.sqlite")).close()
    if vectors:
        (dot / "vectors.sqlite").touch()


class TestCorpusStatus:
    def test_reports_the_new_key(self, spec, corpus_dir):
        _build_artifacts(corpus_dir, db=True, vectors=True)
        status = _corpus_status(spec)
        assert status["vectors_ok"] is True
        assert "lancedb_ok" not in status

    def test_counts_pathway_files(self, spec, corpus_dir):
        assert _corpus_status(spec)["files"] == 2

    def test_nothing_built_is_not_ready(self, spec):
        status = _corpus_status(spec)
        assert status == {
            **status,
            "db_ok": False,
            "vectors_ok": False,
            "ready": False,
        }

    def test_db_without_vectors_is_not_ready(self, spec, corpus_dir):
        _build_artifacts(corpus_dir, db=True, vectors=False)
        status = _corpus_status(spec)
        assert status["db_ok"] is True
        assert status["vectors_ok"] is False
        assert status["ready"] is False

    def test_both_artifacts_present_is_ready(self, spec, corpus_dir):
        _build_artifacts(corpus_dir, db=True, vectors=True)
        assert _corpus_status(spec)["ready"] is True

    def test_a_stale_lancedb_directory_does_not_count_as_built(self, spec, corpus_dir):
        """The pre-migration artifact must not satisfy the readiness probe.

        Otherwise `init --check` reports READY on an un-migrated corpus and
        `--force` never runs, leaving the store on LanceDB indefinitely.
        """
        _build_artifacts(corpus_dir, db=True, vectors=False)
        (corpus_dir / ".metabokg" / "lancedb").mkdir()
        status = _corpus_status(spec)
        assert status["vectors_ok"] is False
        assert status["ready"] is False


class TestCorpusTable:
    def test_renders_without_a_key_error(self, capsys, spec, corpus_dir):
        _build_artifacts(corpus_dir, db=True, vectors=True)
        _print_corpus_table([_corpus_status(spec)])
        out = capsys.readouterr().out
        assert "hsa" in out
        assert "READY" in out

    def test_header_names_the_vector_column(self, capsys, spec):
        _print_corpus_table([_corpus_status(spec)])
        out = capsys.readouterr().out
        assert "vectors" in out
        assert "lancedb" not in out.lower()

    def test_unbuilt_corpus_renders_as_needing_a_build(self, capsys, spec):
        _print_corpus_table([_corpus_status(spec)])
        assert "NEEDS BUILD" in capsys.readouterr().out


class TestColocateDb:
    def test_creates_the_dot_directory(self, tmp_path):
        target = tmp_path / "icho_model"
        target.mkdir()
        db, vectors = _colocate_db(target)
        assert (target / ".metabokg").is_dir()
        assert Path(db).name == "icho.sqlite"
        assert Path(vectors).name == "vectors.sqlite"

    def test_both_paths_share_a_parent(self, tmp_path):
        target = tmp_path / "cge_pathways"
        target.mkdir()
        db, vectors = _colocate_db(target)
        assert Path(db).parent == Path(vectors).parent
