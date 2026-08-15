"""
embed.py — Embedding infrastructure for MetaKG.

Re-exports the shared ``Embedder`` and ``SentenceTransformerEmbedder`` from
``kgmodule-utils`` and adds MetaboKG-specific helpers (``SeedHit``,
``extract_distance``) used by :mod:`metabokg.index`.

Author: Eric G. Suchanek, PhD

"""

from __future__ import annotations

from dataclasses import dataclass

from kg_utils.embed import DEFAULT_MODEL as DEFAULT_MODEL
from kg_utils.embedder import Embedder as Embedder
from kg_utils.embedder import SentenceTransformerEmbedder as SentenceTransformerEmbedder

# ---------------------------------------------------------------------------
# Seed hit returned by MetaIndex.search()
# ---------------------------------------------------------------------------


@dataclass
class SeedHit:
    """
    A single result from a semantic vector search.

    :param id: Node ID.
    :param kind: Node kind (``compound``, ``reaction``, ``pathway``).
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
# Internal vector-store helpers
# ---------------------------------------------------------------------------


def extract_distance(row: dict, fallback_rank: int) -> float:
    """
    Extract a distance value from a vector-search result row.

    ``SqliteVecBackend`` returns ``_distance`` (cosine), which is the first key
    tried; the remaining fallbacks are tolerated so a row from any other
    backend still yields a usable ordering.

    :param row: Raw result dict from the vector backend.
    :param fallback_rank: Zero-based rank to use when no distance field is present.
    :return: Float distance value (lower = more similar).
    """
    for key in ("_distance", "distance"):
        if key in row and row[key] is not None:
            return float(row[key])
    if "score" in row and row["score"] is not None:
        return 1.0 / (1.0 + float(row["score"]))
    return float(fallback_rank)
