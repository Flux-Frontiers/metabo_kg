"""
metabokg.parsers — Format-specific metabolic pathway parsers.

Each parser implements the PathwayParser ABC and returns
(list[MetaNode], list[MetaEdge]) for a single input file.

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28
"""

from metabokg.parsers.base import PathwayParser
from metabokg.parsers.biopax import BioPAXParser
from metabokg.parsers.csv_tsv import CSVParser, CSVParserConfig
from metabokg.parsers.kgml import KGMLParser
from metabokg.parsers.sbml import SBMLParser

__all__ = [
    "PathwayParser",
    "KGMLParser",
    "SBMLParser",
    "BioPAXParser",
    "CSVParser",
    "CSVParserConfig",
]
