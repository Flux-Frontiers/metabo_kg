"""
graph.py — MetabolicGraph: parser registry and file dispatch.

Discovers pathway files in a data directory, dispatches each to the
appropriate :class:`~code_kg.metakg.parsers.base.PathwayParser`, and
aggregates the resulting nodes and edges.

Analogous to ``code_kg.graph.CodeGraph``.

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28 20:55:28

"""

from __future__ import annotations

import logging
from pathlib import Path

from metakg.parsers.base import PathwayParser
from metakg.parsers.biopax import BioPAXParser
from metakg.parsers.csv_tsv import CSVParser
from metakg.parsers.kgml import KGMLParser
from metakg.parsers.sbml import SBMLParser
from metakg.primitives import MetaEdge, MetaNode

logger = logging.getLogger(__name__)

# Ordered parser registry — parsers tried in order for ambiguous extensions.
# KGML before SBML because both use .xml but KGML detects via root element check.
_PARSER_REGISTRY: list[PathwayParser] = [
    KGMLParser(),
    SBMLParser(),
    BioPAXParser(),
    CSVParser(),
]

# File extensions to skip entirely
_SKIP_EXTENSIONS = {".md", ".txt", ".json", ".log", ".py", ".rst", ".yaml", ".yml"}


class MetabolicGraph:
    """
    Orchestrates pathway file discovery and parsing.

    Scans *data_root* recursively for supported pathway files, dispatches
    each file to the first parser that reports it can handle the file, and
    merges the resulting nodes and edges.

    :param data_root: Root directory containing pathway data files.
    """

    def __init__(self, data_root: str | Path) -> None:
        """
        Initialise the graph extractor.

        :param data_root: Directory to scan for pathway files.
        """
        self.data_root = Path(data_root).resolve()
        self._nodes: list[MetaNode] | None = None
        self._edges: list[MetaEdge] | None = None
        self._parse_errors: list[dict] = []

    def extract(self, *, force: bool = False) -> MetabolicGraph:
        """
        Scan and parse all supported files under *data_root*.

        Results are cached; subsequent calls return ``self`` immediately unless
        *force* is ``True``.

        :param force: Re-parse even if results are already cached.
        :return: ``self`` (for chaining with :meth:`result`).
        """
        if self._nodes is not None and not force:
            return self

        all_nodes: dict[str, MetaNode] = {}
        all_edges: list[MetaEdge] = []
        self._parse_errors = []

        files = sorted(self.data_root.rglob("*"))
        for path in files:
            if not path.is_file():
                continue
            if path.suffix.lower() in _SKIP_EXTENSIONS:
                continue

            parser = self._find_parser(path)
            if parser is None:
                logger.debug("No parser found for %s — skipping", path)
                continue

            try:
                nodes, edges = parser.parse(path)
                for n in nodes:
                    # Last writer wins on ID collision (prefer richer data)
                    all_nodes[n.id] = n
                all_edges.extend(edges)
                logger.info(
                    "Parsed %s via %s: %d nodes, %d edges",
                    path.name,
                    type(parser).__name__,
                    len(nodes),
                    len(edges),
                )
            except (ValueError, ImportError) as exc:
                logger.warning("Failed to parse %s: %s", path, exc)
                self._parse_errors.append({"file": str(path), "error": str(exc)})

        # Deduplicate edges (same primary key: src, rel, dst)
        seen_edges: set[tuple[str, str, str]] = set()
        unique_edges: list[MetaEdge] = []
        for e in all_edges:
            key = (e.src, e.rel, e.dst)
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(e)

        self._nodes = list(all_nodes.values())
        self._edges = unique_edges
        return self

    def result(self) -> tuple[list[MetaNode], list[MetaEdge]]:
        """
        Return the parsed nodes and edges.

        :return: Two-tuple ``(nodes, edges)``.
        :raises RuntimeError: If :meth:`extract` has not been called.
        """
        if self._nodes is None:
            raise RuntimeError("Call extract() before result()")
        return self._nodes, self._edges  # type: ignore[return-value]

    @property
    def parse_errors(self) -> list[dict]:
        """
        List of files that could not be parsed.

        :return: List of dicts with ``file`` and ``error`` keys.
        """
        return list(self._parse_errors)

    def _find_parser(self, path: Path) -> PathwayParser | None:
        """
        Find the first parser in the registry that can handle *path*.

        :param path: File to match.
        :return: A :class:`~code_kg.metakg.parsers.base.PathwayParser` instance,
                 or ``None`` if no parser matched.
        """
        for parser in _PARSER_REGISTRY:
            if parser.can_handle(path):
                return parser
        return None
