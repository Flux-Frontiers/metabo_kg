"""
index.py — MetaIndex: LanceDB semantic index for the metabolic knowledge graph.

Indexes compound, enzyme, and pathway nodes for semantic (vector) search.
Reactions are excluded — they are too terse for useful semantic search.

Embedding text format:
  KIND: <kind>
  NAME: <name>
  EC: <ec_number>         (enzymes only)
  FORMULA: <formula>      (compounds only)
  XREF <DB>: <ext_id>     (all cross-references)
  DESCRIPTION:
  <description>

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28 20:55:28

"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from metakg.embed import (
    DEFAULT_MODEL,
    Embedder,
    SeedHit,
    SentenceTransformerEmbedder,
    escape_id,
    extract_distance,
)
from metakg.primitives import KIND_COMPOUND, KIND_ENZYME, KIND_PATHWAY
from metakg.store import MetaStore

# Node kinds that are indexed for semantic search
_INDEXED_KINDS = {KIND_COMPOUND, KIND_ENZYME, KIND_PATHWAY}

# Default LanceDB table name for metabolic nodes
DEFAULT_TABLE = "metakg_nodes"


def _build_meta_index_text(node: dict) -> str:
    """
    Construct the embedding text for a metabolic node.

    :param node: Node dict from MetaStore (as returned by ``MetaStore.node()``).
    :return: Multi-line string suitable for sentence-transformer embedding.
    """
    parts = [f"KIND: {node['kind']}", f"NAME: {node['name']}"]

    if node.get("ec_number"):
        parts.append(f"EC: {node['ec_number']}")

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
    LanceDB semantic index for metabolic entities.

    Embeds compound, enzyme, and pathway nodes from a :class:`MetaStore`
    into LanceDB for semantic (vector) search.

    :param lancedb_dir: Directory for LanceDB storage.
    :param embedder: Embedding backend (defaults to SentenceTransformerEmbedder).
    :param table: LanceDB table name (default ``"metakg_nodes"``).
    """

    def __init__(
        self,
        lancedb_dir: str | Path,
        *,
        embedder: Embedder | None = None,
        table: str = DEFAULT_TABLE,
    ) -> None:
        """
        Initialise the MetaIndex.

        :param lancedb_dir: Path to the LanceDB storage directory.
        :param embedder: Embedding backend; defaults to
            :class:`~metakg.embed.SentenceTransformerEmbedder` with
            :data:`~metakg.embed.DEFAULT_MODEL`.
        :param table: LanceDB table name.
        """
        self.lancedb_dir = Path(lancedb_dir)
        self._embedder: Embedder = embedder or SentenceTransformerEmbedder(DEFAULT_MODEL)
        self._table_name = table
        self._tbl = None  # lazy LanceDB table handle

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, store: MetaStore, *, wipe: bool = False, batch_size: int = 256) -> dict:
        """
        Build (or rebuild) the LanceDB vector index from *store*.

        Only ``compound``, ``enzyme``, and ``pathway`` nodes are indexed.

        :param store: Populated :class:`~metakg.store.MetaStore` instance.
        :param wipe: Delete existing vectors before indexing.
        :param batch_size: Nodes embedded per batch.
        :return: Dict with ``indexed_rows``, ``dim``, ``table``, ``lancedb_dir``.
        """
        nodes = [n for n in store.all_nodes() if n["kind"] in _INDEXED_KINDS]
        tbl = self._open_table(wipe=wipe)

        indexed = 0
        for i in range(0, len(nodes), batch_size):
            chunk = nodes[i : i + batch_size]
            texts = [_build_meta_index_text(n) for n in chunk]
            vecs = self._embedder.embed_texts(texts)

            ids = [n["id"] for n in chunk]
            if ids:
                pred = " OR ".join([f"id = '{escape_id(nid)}'" for nid in ids])
                tbl.delete(pred)

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
            tbl.add(rows)
            indexed += len(rows)

        self._tbl = tbl
        return {
            "indexed_rows": indexed,
            "dim": self._embedder.dim,
            "table": self._table_name,
            "lancedb_dir": str(self.lancedb_dir),
        }

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, *, k: int = 8) -> list[SeedHit]:
        """
        Semantic search for metabolic entities.

        :param query: Natural-language query (e.g. ``"glycolysis pathway"``).
        :param k: Number of top results to return.
        :return: List of :class:`~metakg.embed.SeedHit` ordered by ascending distance.
        """
        tbl = self._get_table()
        qvec = self._embedder.embed_query(query)
        raw = tbl.search(qvec).limit(k).to_list()

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
        try:
            tbl = self._get_table()
            return {
                "indexed_rows": tbl.count_rows(),
                "dim": self._embedder.dim,
            }
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_table(self, *, wipe: bool = False):
        """Open or create the LanceDB table.

        :param wipe: If ``True``, drop the table before re-creating it.
        :return: LanceDB table handle.
        """
        import lancedb

        self.lancedb_dir.mkdir(parents=True, exist_ok=True)
        db = lancedb.connect(str(self.lancedb_dir))

        table_list = db.list_tables()
        existing = table_list.tables if hasattr(table_list, "tables") else list(table_list)

        if self._table_name in existing:
            if wipe:
                db.drop_table(self._table_name)
            else:
                return db.open_table(self._table_name)

        dummy = {
            "id": "__dummy__",
            "kind": "dummy",
            "name": "__dummy__",
            "text": "__dummy__",
            "vector": np.zeros((self._embedder.dim,), dtype="float32").tolist(),
        }
        tbl = db.create_table(self._table_name, data=[dummy])
        tbl.delete("id = '__dummy__'")
        return tbl

    def _get_table(self):
        """Return the cached LanceDB table handle, opening it if needed."""
        if self._tbl is None:
            import lancedb

            db = lancedb.connect(str(self.lancedb_dir))
            self._tbl = db.open_table(self._table_name)
        return self._tbl

    def __repr__(self) -> str:
        return (
            f"MetaIndex(lancedb_dir={self.lancedb_dir!r}, "
            f"table={self._table_name!r}, embedder={self._embedder!r})"
        )
