"""
embed.py — Embedding infrastructure for MetaKG.

Provides a pluggable Embedder interface and a SentenceTransformer-backed
implementation for producing float32 vectors from text.

This module is self-contained — no dependency on code_kg.

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28 20:55:28

"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Default sentence-transformer model used throughout MetaKG
DEFAULT_MODEL = "all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# Embedder interface (pluggable)
# ---------------------------------------------------------------------------


class Embedder:
    """
    Abstract embedding backend.

    Subclass and implement :meth:`embed_texts` to plug in any model.

    :param dim: Embedding dimension (must be set by subclass ``__init__``).
    """

    dim: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of strings.

        :param texts: Input strings.
        :return: List of float32 vectors, one per input.
        """
        raise NotImplementedError

    def embed_query(self, query: str) -> list[float]:
        """
        Embed a single query string.

        Default implementation calls :meth:`embed_texts` with a one-element list.

        :param query: Query string.
        :return: Float32 vector.
        """
        return self.embed_texts([query])[0]


class SentenceTransformerEmbedder(Embedder):
    """
    Local embedding via ``sentence-transformers``.

    :param model_name: HuggingFace model name or local path.
                       Defaults to :data:`DEFAULT_MODEL`.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        """
        Load the sentence-transformer model.

        :param model_name: HuggingFace model name or local path.
        """
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.dim: int = self.model.get_sentence_embedding_dimension() or 384

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of strings into float32 vectors.

        :param texts: Input strings to embed.
        :return: List of float32 vectors, one per input string.
        """
        vecs = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [np.asarray(v, dtype="float32").tolist() for v in vecs]

    def embed_query(self, query: str) -> list[float]:
        """
        Embed a single query string into a float32 vector.

        :param query: Query string to embed.
        :return: Float32 vector representation of the query.
        """
        vec = self.model.encode([query], normalize_embeddings=True)[0]
        return np.asarray(vec, dtype="float32").tolist()

    def __repr__(self) -> str:
        return f"SentenceTransformerEmbedder(model={self.model_name!r}, dim={self.dim})"


# ---------------------------------------------------------------------------
# Seed hit returned by MetaIndex.search()
# ---------------------------------------------------------------------------


@dataclass
class SeedHit:
    """
    A single result from a semantic vector search.

    :param id: Node ID.
    :param kind: Node kind (``compound``, ``enzyme``, ``pathway``).
    :param name: Short name.
    :param distance: Vector distance (lower = more similar).
    :param rank: Zero-based rank in the result list.
    """

    id: str
    kind: str
    name: str
    distance: float
    rank: int


# ---------------------------------------------------------------------------
# Internal LanceDB helpers
# ---------------------------------------------------------------------------


def extract_distance(row: dict, fallback_rank: int) -> float:
    """
    Extract a distance value from a LanceDB result row.

    :param row: Raw result dict from LanceDB.
    :param fallback_rank: Zero-based rank to use when no distance field is present.
    :return: Float distance value (lower = more similar).
    """
    for key in ("_distance", "distance"):
        if key in row and row[key] is not None:
            return float(row[key])
    if "score" in row and row["score"] is not None:
        return 1.0 / (1.0 + float(row["score"]))
    return float(fallback_rank)


def escape_id(s: str) -> str:
    """
    Escape single quotes in a string for use in LanceDB delete predicates.

    :param s: String to escape.
    :return: String with single quotes doubled.
    """
    return s.replace("'", "''")
