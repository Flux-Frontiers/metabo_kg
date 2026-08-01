"""Unit tests for metabokg.index — the sqlite-vec semantic index.

Uses a deterministic stub embedder so the whole file runs without downloading
a sentence-transformer model.  What matters here is the *storage* contract —
which nodes get indexed, what metadata survives a round-trip, and whether a
rebuild is idempotent — none of which needs real embeddings.

The 0.10.0 LanceDB → sqlite-vec migration is what these pin down: two of the
cases below (``TestRebuild`` and ``TestAbsentStore``) are regressions that the
port introduced and that nothing else in the suite would have caught.
"""

from __future__ import annotations

import math
import sqlite3

import pytest

from metabokg.embed import Embedder
from metabokg.index import MetaIndex, _build_meta_index_text
from metabokg.primitives import KIND_COMPOUND, KIND_ENZYME, KIND_PATHWAY, KIND_REACTION


class StubEmbedder(Embedder):
    """Deterministic, model-free embedder: character codes folded into 8 dims."""

    dim = 8

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for i, ch in enumerate(text):
            v[i % self.dim] += ord(ch) % 13
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_texts(self, texts, encode_batch_size=32):  # noqa: D102
        return [self._vec(t) for t in texts]

    def embed_query(self, query):  # noqa: D102
        return self._vec(query)


class StubStore:
    """Minimal stand-in for MetaStore — only ``all_nodes`` is exercised."""

    def __init__(self, nodes: list[dict]) -> None:
        self._nodes = nodes

    def all_nodes(self, **_kwargs) -> list[dict]:
        return self._nodes


NODES = [
    {
        "id": "cpd:kegg:C00031",
        "kind": KIND_COMPOUND,
        "name": "D-Glucose",
        "formula": "C6H12O6",
        "xrefs": '{"kegg": "C00031", "chebi": "17234"}',
        "description": "A hexose sugar",
    },
    {
        "id": "rxn:kegg:R00200",
        "kind": KIND_REACTION,
        "name": "pyruvate kinase",
        "description": "PEP + ADP -> pyruvate + ATP",
    },
    {
        "id": "pwy:kegg:hsa00010",
        "kind": KIND_PATHWAY,
        "name": "Glycolysis",
        "description": "Glycolysis / Gluconeogenesis",
    },
    {
        "id": "enz:kegg:hsa:2539",
        "kind": KIND_ENZYME,
        "name": "G6PD",
        "description": "gene-name-only — must not be indexed",
    },
    {
        # Ids used to be interpolated into a SQL delete predicate, so a quote
        # in one was an injection risk. Keep a quoted id in the corpus.
        "id": "cpd:o'brien",
        "kind": KIND_COMPOUND,
        "name": "quote'test",
        "description": "id with an embedded single quote",
    },
]

_INDEXED = 4  # everything but the enzyme


@pytest.fixture
def index(tmp_path):
    return MetaIndex(tmp_path / ".metabokg" / "vectors.sqlite", embedder=StubEmbedder())


@pytest.fixture
def built(index):
    index.build(StubStore(NODES), wipe=True, batch_size=2)
    return index


class TestBuild:
    def test_reports_what_it_indexed(self, index):
        stats = index.build(StubStore(NODES), wipe=True, batch_size=2)
        assert stats["indexed_rows"] == _INDEXED
        assert stats["dim"] == StubEmbedder.dim
        assert stats["vectors_path"] == str(index.vectors_path)

    def test_creates_a_single_sqlite_file(self, built):
        assert built.vectors_path.is_file()

    def test_enzymes_are_excluded(self, built):
        assert not any(h.id.startswith("enz:") for h in built.search("G6PD", k=_INDEXED))

    def test_batch_size_does_not_change_the_result(self, tmp_path):
        def ids_at(batch_size: int) -> list[str]:
            idx = MetaIndex(tmp_path / f"b{batch_size}" / "vectors.sqlite", embedder=StubEmbedder())
            idx.build(StubStore(NODES), wipe=True, batch_size=batch_size)
            return [h.id for h in idx.search("Glycolysis", k=_INDEXED)]

        assert ids_at(1) == ids_at(3) == ids_at(100)


class TestSearch:
    def test_returns_metadata_not_just_ids(self, built):
        """`kind` and `name` are read off the hit, so they must be persisted.

        A default-configured SqliteVecBackend would drop them silently.
        """
        for hit in built.search("Glycolysis pathway", k=_INDEXED):
            assert hit.kind and hit.name

    def test_ranks_are_dense_and_ordered_by_distance(self, built):
        hits = built.search("Glycolysis pathway", k=_INDEXED)
        assert [h.rank for h in hits] == list(range(_INDEXED))
        assert hits == sorted(hits, key=lambda h: h.distance)

    def test_distances_are_cosine_ranged(self, built):
        """sqlite-vec reports cosine distance in [0, 2] — not squared L2."""
        assert all(0.0 <= h.distance <= 2.0 for h in built.search("glucose", k=_INDEXED))

    def test_k_caps_the_result_count(self, built):
        assert len(built.search("glucose", k=2)) == 2

    def test_quoted_id_round_trips(self, built):
        ids = [h.id for h in built.search("quote", k=_INDEXED)]
        assert "cpd:o'brien" in ids

    def test_embedding_text_is_stored_verbatim(self, built):
        """The store stays self-describing: `text` is the exact embedded string."""
        con = sqlite3.connect(str(built.vectors_path))
        stored = con.execute("SELECT text FROM vec_meta WHERE id = ?", (NODES[0]["id"],)).fetchone()
        con.close()
        assert stored[0] == _build_meta_index_text(NODES[0])


class TestRebuild:
    """Regression: SqliteVecBackend fixes its dedup strategy at open() time.

    A freshly created or wiped store skips upsert's delete-before-insert, and
    that verdict is never revisited — so a second build on a cached backend
    used to fail with `UNIQUE constraint failed: vec_meta.id`.
    """

    def test_second_build_without_wipe_does_not_duplicate(self, built):
        stats = built.build(StubStore(NODES), wipe=False, batch_size=3)
        assert stats["indexed_rows"] == _INDEXED
        assert built.stats()["indexed_rows"] == _INDEXED

    def test_second_build_with_wipe_replaces(self, built):
        built.build(StubStore(NODES), wipe=True, batch_size=5)
        assert built.stats()["indexed_rows"] == _INDEXED

    def test_update_from_a_cold_instance(self, built):
        """`metabokg update` opens an existing store it did not create."""
        cold = MetaIndex(built.vectors_path, embedder=StubEmbedder())
        cold.build(StubStore(NODES), wipe=False, batch_size=2)
        assert cold.stats()["indexed_rows"] == _INDEXED

    def test_wipe_drops_nodes_that_are_gone(self, built):
        built.build(StubStore(NODES[:1]), wipe=True, batch_size=8)
        assert built.stats()["indexed_rows"] == 1


class TestAbsentStore:
    """Reporting on a store must never bring it into being.

    A zero-row vectors.sqlite reads as "built" to every `.exists()` check in
    the CLI, which would then take the vector path against an empty index.
    """

    def test_stats_returns_empty(self, index):
        assert index.stats() == {}

    def test_stats_does_not_create_the_store(self, index):
        index.stats()
        assert not index.vectors_path.exists()

    def test_search_raises_with_an_actionable_message(self, index):
        with pytest.raises(FileNotFoundError, match="metabokg build"):
            index.search("glucose", k=4)

    def test_search_does_not_create_the_store(self, index):
        with pytest.raises(FileNotFoundError):
            index.search("glucose", k=4)
        assert not index.vectors_path.exists()


class TestStats:
    def test_counts_indexed_rows(self, built):
        assert built.stats() == {"indexed_rows": _INDEXED, "dim": StubEmbedder.dim}


def test_repr_names_the_vector_store(index):
    assert "vectors_path" in repr(index)
    assert "lancedb" not in repr(index).lower()
