"""
metabokg — Metabolic pathway parser and semantic knowledge graph.

Parses pathway data from KEGG KGML, SBML, BioPAX, and CSV formats into a
semantic knowledge graph stored in SQLite + sqlite-vec, exposed via MCP tools.

Quick start::

    from metabokg import MetaKG

    kg = MetaKG(db_path=".metabokg/hsa.sqlite")
    stats = kg.build(data_dir="./pathway_files", wipe=True)
    print(stats)

    result = kg.query_pathway("glycolysis")
    rxn = kg.get_reaction("rxn:kegg:R00200")
    path = kg.find_path("glucose", "pyruvate")

Author: Eric G. Suchanek, PhD

"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

try:
    # Read the version the package was installed as, so it always agrees with
    # pyproject.toml. A literal here is what drifted to 0.9.1 while pyproject
    # said 0.10.0, mislabelling every analysis report in between; the CLI has
    # always resolved its `--version` this way and never drifted.
    __version__ = _distribution_version("metabo-kg")
except PackageNotFoundError:  # pragma: no cover — source tree, never installed
    __version__ = "0.0.0+unknown"

from metabokg.orchestrator import (
    MetabolicBuildStats,
    MetabolicPack,
    MetabolicQueryResult,
    MetabolicRuntimeStats,
    MetaKG,
)

__all__ = [
    "MetaKG",
    "MetabolicBuildStats",
    "MetabolicPack",
    "MetabolicRuntimeStats",
    "MetabolicQueryResult",
]
