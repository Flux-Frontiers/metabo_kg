"""
metakg — Metabolic pathway parser and semantic knowledge graph.

Parses pathway data from KEGG KGML, SBML, BioPAX, and CSV formats into a
semantic knowledge graph stored in SQLite + LanceDB, exposed via MCP tools.

Quick start::

    from metakg import MetaKG

    kg = MetaKG(db_path=".metakg/meta.sqlite")
    stats = kg.build(data_dir="./pathway_files", wipe=True)
    print(stats)

    result = kg.query_pathway("glycolysis")
    rxn = kg.get_reaction("rxn:kegg:R00200")
    path = kg.find_path("glucose", "pyruvate")

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28 20:55:28

"""

__version__ = "0.3.0"

from metakg.orchestrator import (
    MetabolicBuildStats,
    MetabolicQueryResult,
    MetabolicRuntimeStats,
    MetaKG,
)

__all__ = [
    "MetaKG",
    "MetabolicBuildStats",
    "MetabolicRuntimeStats",
    "MetabolicQueryResult",
]
