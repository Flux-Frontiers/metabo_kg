"""
base.py — Abstract base class for all metabolic pathway parsers.

Each parser is stateless and pure: given a file path it returns
(list[MetaNode], list[MetaEdge]) with no side effects.

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from metakg.primitives import MetaEdge, MetaNode


class PathwayParser(ABC):
    """
    Abstract base for all metabolic format parsers.

    Contract: stateless, pure, deterministic.  The return signature is
    identical to that of ``extract_repo()`` in the code_kg domain.

    Subclasses must implement :meth:`parse` and :meth:`supported_extensions`.
    """

    @abstractmethod
    def parse(self, path: Path) -> tuple[list[MetaNode], list[MetaEdge]]:
        """
        Parse a pathway file into graph primitives.

        :param path: Absolute path to the source file.
        :return: Two-tuple ``(nodes, edges)`` ready for insertion into MetaStore.
        :raises ValueError: If the file cannot be parsed by this parser.
        """

    @property
    @abstractmethod
    def supported_extensions(self) -> tuple[str, ...]:
        """
        File extensions this parser handles.

        :return: Tuple of lowercase extensions including the dot,
                 e.g. ``('.xml', '.kgml')``.
        """

    def can_handle(self, path: Path) -> bool:
        """
        Return whether this parser can handle the given file.

        Default implementation checks the file extension against
        :attr:`supported_extensions`. Override for format-specific detection.

        :param path: Path to inspect.
        :return: ``True`` if this parser should be tried for the file.
        """
        return path.suffix.lower() in self.supported_extensions
