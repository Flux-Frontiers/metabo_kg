"""
index.py — MetaIndex: sqlite-vec semantic index for the metabolic knowledge graph.

Indexes compound, reaction, and pathway nodes for semantic (vector) search.
Enzyme nodes are excluded — they contain only gene-name lists with no functional
descriptions, so their embeddings are near-identical and pollute every search.
Enzymes remain reachable via hop-1 graph expansion from reactions/pathways.

Embedding text format:
  KIND: <kind>
  NAME: <name>
  FORMULA: <formula>      (compounds only)
  XREF <DB>: <ext_id>     (all cross-references)
  DESCRIPTION:
  <description>

Author: Eric G. Suchanek, PhD
Last Revision: 2026-08-01

"""

from __future__ import annotations

import json
from pathlib import Path

from kg_utils.vector_backend import SqliteVecBackend

from metabokg.embed import (
    DEFAULT_MODEL,
    Embedder,
    SeedHit,
    SentenceTransformerEmbedder,
    extract_distance,
)
from metabokg.primitives import KIND_COMPOUND, KIND_PATHWAY, KIND_REACTION
from metabokg.store import MetaStore

# Enzyme nodes are excluded: 9,427 nodes with gene-name-only descriptions produce
# near-identical embeddings that swamp compound/pathway/reaction results.
_INDEXED_KINDS = {KIND_COMPOUND, KIND_REACTION, KIND_PATHWAY}

# Metadata persisted alongside each vector. ``id`` is implicit. ``text`` is the
# canonical embedding text — not read back by :meth:`MetaIndex.search`, but kept
# so the store remains self-describing and debuggable without the graph.
_META_COLUMNS = ("kind", "name", "text")


def _build_meta_index_text(node: dict) -> str:
    """
    Construct the embedding text for a metabolic node.

    :param node: Node dict from MetaStore (as returned by ``MetaStore.node()``).
    :return: Multi-line string suitable for sentence-transformer embedding.
    """
    parts = [f"KIND: {node['kind']}", f"NAME: {node['name']}"]

    if node.get("formula"):
        parts.append(f"FORMULA: {node['formula']}")

    xrefs_raw = node.get("xrefs")
    if xrefs_raw:
        try:
            xrefs = json.loads(xrefs_raw)
            for db, eid in xrefs.items():
                parts.append(f"XREF {db.upper()}: {eid}")
        except (json.JSONDecodeError, TypeError):
            pass

    if node.get("description"):
        parts.append("DESCRIPTION:\n" + node["description"].strip())

    return "\n".join(parts)


class MetaIndex:
    """
    sqlite-vec semantic index for metabolic entities.

    Embeds compound, reaction, and pathway nodes from a :class:`MetaStore`
    into a single ``vectors.sqlite`` store for semantic (vector) search.

    Changed in 0.10.0: the store was a LanceDB directory. The embedding text
    built by :func:`_build_meta_index_text` is unchanged — only where the
    vectors live changed.

    :param vectors_path: Path to the ``vectors.sqlite`` store.
    :param embedder: Embedding backend (defaults to SentenceTransformerEmbedder).
    """

    def __init__(
        self,
        vectors_path: str | Path,
        *,
        embedder: Embedder | None = None,
    ) -> None:
        """
        Initialise the MetaIndex.

        :param vectors_path: Path to the sqlite-vec store file.
        :param embedder: Embedding backend; defaults to
            :class:`~metabokg.embed.SentenceTransformerEmbedder` with
            :data:`~metabokg.embed.DEFAULT_MODEL`.
        """
        self.vectors_path = Path(vectors_path)
        self._embedder: Embedder = embedder or SentenceTransformerEmbedder(DEFAULT_MODEL)
        self._backend: SqliteVecBackend | None = None

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, store: MetaStore, *, wipe: bool = False, batch_size: int = 256) -> dict:
        """
        Build (or rebuild) the sqlite-vec vector index from *store*.

        Only ``compound``, ``enzyme``, and ``pathway`` nodes are indexed.

        :param store: Populated :class:`~metabokg.store.MetaStore` instance.
        :param wipe: Delete existing vectors before indexing.
        :param batch_size: Nodes embedded per batch.
        :return: Dict with ``indexed_rows``, ``dim``, ``vectors_path``.
        """
        nodes = [n for n in store.all_nodes() if n["kind"] in _INDEXED_KINDS]
        backend = self._open_for_build(wipe=wipe)

        indexed = 0
        for i in range(0, len(nodes), batch_size):
            chunk = nodes[i : i + batch_size]
            texts = [_build_meta_index_text(n) for n in chunk]
            vecs = self._embedder.embed_texts(texts)

            rows = [
                {
                    "id": n["id"],
                    "kind": n["kind"],
                    "name": n["name"],
                    "text": text,
                    "vector": vec,
                }
                for n, text, vec in zip(chunk, texts, vecs)
            ]
            # upsert deletes any prior rows for these ids and re-inserts, so the
            # explicit delete-by-predicate this used to issue is gone. That
            # predicate was an OR-joined `id = '...'` string, one term per node
            # in the batch — the shape that overflowed LanceDB's Rust evaluator
            # at depth on large batches.
            indexed += backend.upsert(rows, batch_size=batch_size)

        return {
            "indexed_rows": indexed,
            "dim": self._embedder.dim,
            "vectors_path": str(self.vectors_path),
        }

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, *, k: int = 8) -> list[SeedHit]:
        """
        Semantic search for metabolic entities.

        :param query: Natural-language query (e.g. ``"glycolysis pathway"``).
        :param k: Number of top results to return.
        :return: List of :class:`~metabokg.embed.SeedHit` ordered by ascending distance.
        """
        if self._backend is None and not self.vectors_path.exists():
            raise FileNotFoundError(
                f"vector index not found at '{self.vectors_path}'.\n"
                "Run 'metabokg build' (without --no-index) to create it."
            )
        backend = self._get_backend()
        qvec = self._embedder.embed_query(query)
        raw = backend.search(qvec, k)

        hits: list[SeedHit] = []
        for rank, row in enumerate(raw):
            dist = extract_distance(row, rank)
            hits.append(
                SeedHit(
                    id=row["id"],
                    kind=row.get("kind", ""),
                    name=row.get("name", ""),
                    distance=dist,
                    rank=rank,
                )
            )
        return hits

    def stats(self) -> dict:
        """
        Get statistics about the current index.

        :return: Dict with ``indexed_rows`` and ``dim`` keys, or empty dict if index doesn't exist.
        """
        # Opening the backend would CREATE the store, and a zero-row
        # vectors.sqlite reads as "built" to every `.exists()` check in the CLI.
        # Reporting on a store must not bring it into being.
        if self._backend is None and not self.vectors_path.exists():
            return {}
        try:
            return {
                "indexed_rows": self._get_backend().count(),
                "dim": self._embedder.dim,
            }
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _new_backend(self) -> SqliteVecBackend:
        """Construct (but do not open) the sqlite-vec backend."""
        self.vectors_path.parent.mkdir(parents=True, exist_ok=True)
        return SqliteVecBackend(
            self.vectors_path,
            dim=self._embedder.dim,
            meta_columns=_META_COLUMNS,
        )

    def _get_backend(self) -> SqliteVecBackend:
        """Return the sqlite-vec backend for reading, opening it on first use.

        Constructing the backend touches :attr:`_embedder.dim`, which loads the
        model, so it stays lazy — :meth:`stats` on an absent store must not pay
        for a model download.

        :return: The open :class:`~kg_utils.vector_backend.SqliteVecBackend`.
        """
        if self._backend is None:
            self._backend = self._new_backend()
            self._backend.open()
        return self._backend

    def _open_for_build(self, *, wipe: bool) -> SqliteVecBackend:
        """Open the backend for a write pass, re-opening a cached one.

        ``SqliteVecBackend`` decides in :meth:`~kg_utils.vector_backend.
        SqliteVecBackend.open` whether ``upsert`` needs its delete-before-insert
        dedup — a freshly created or wiped store has nothing to replace, so the
        delete is skipped — and never revisits that verdict. Re-opening is what
        makes a second build on the same :class:`MetaIndex` correct: without it
        the first build's "fresh" verdict survives, the dedup stays off, and
        re-indexing the same nodes raises ``UNIQUE constraint failed:
        vec_meta.id``.

        :param wipe: Drop existing vectors before indexing.
        :return: The open :class:`~kg_utils.vector_backend.SqliteVecBackend`.
        """
        if self._backend is None:
            self._backend = self._new_backend()
        else:
            # open() rebinds the connection without closing the old one.
            self._backend.close()
        self._backend.open(wipe=wipe)
        return self._backend

    def __repr__(self) -> str:
        return f"MetaIndex(vectors_path={self.vectors_path!r}, embedder={self._embedder!r})"
