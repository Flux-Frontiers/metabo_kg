"""
embed.py — Embedding infrastructure for MetaKG.

Re-exports the shared ``Embedder`` and ``SentenceTransformerEmbedder`` from
``kgmodule-utils`` and adds MetaboKG-specific helpers (``SeedHit``,
``extract_distance``, ``escape_id``) used by the LanceDB index layer.

Author: Eric G. Suchanek, PhD
Last Revision: 2026-05-02

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
