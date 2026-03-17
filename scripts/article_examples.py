#!/usr/bin/env python3
"""
Article Examples Script

Run all worked examples from article Section 6 and capture real output.

Usage:
    poetry run python scripts/article_examples.py

This script assumes metakg-build --data ./pathways has been run already.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from metakg import MetaKG


def example_1_building():
    """Example 6.2.1: Building the knowledge graph from KGML files."""
    print("\n" + "=" * 80)
    print("Example 6.2.1: Building the Knowledge Graph")
    print("=" * 80)
    print("$ metakg-build --data ./pathways --wipe")
    print("Building MetaKG from ./pathways...")
    print("data_root   : ./pathways")
    print("db_path     : .metakg/meta.sqlite")

    # Get actual stats from database
    kg = MetaKG()
    stats = kg.get_stats()

    print(f"nodes       : {stats.total_nodes:6d}  {stats.node_counts}")
    print(f"edges       : {stats.total_edges:6d}  {stats.edge_counts}")

    if stats.indexed_rows is not None:
        print(f"indexed     : {stats.indexed_rows:6d} vectors  dim={stats.index_dim}")

    kg.close()


def example_2_structural_queries():
    """Example 6.3.1: Compound retrieval and neighbourhood traversal."""
    print("\n" + "=" * 80)
    print("Example 6.3.1: Structural Queries via Python API")
    print("=" * 80)
    print("""
from metakg import MetaKG

kg = MetaKG()

# Retrieve pyruvate and its connected reactions
cpd = kg.get_compound("cpd:kegg:C00022")
print(cpd["name"])        # Pyruvate
print(cpd["formula"])     # C3H4O3
for rxn in cpd["reactions"]:
    print(rxn["name"], rxn["role"])
""")

    kg = MetaKG()
    cpd = kg.get_compound("cpd:kegg:C00022")

    if cpd:
        print("\n--- Output ---")
        print(cpd["name"])
        print(cpd.get("formula", "N/A"))

        print("\n# Connected reactions:")
        if cpd.get("reactions"):
            for rxn in cpd["reactions"][:5]:  # First 5
                print(f"  {rxn['name']:40s} {rxn['role']:15s}")
            if len(cpd["reactions"]) > 5:
                print(f"  ... and {len(cpd['reactions']) - 5} more")
        else:
            print("  (no reactions found)")

        print("\n# Full reaction detail")
        print("""
rxn = kg.get_reaction("rxn:kegg:R00200")
print(rxn["substrates"])  # [{'name': 'Pyruvate', ...}]
print(rxn["products"])    # [{'name': 'Acetaldehyde', ...}]
print(rxn["enzymes"])     # [{'ec_number': '4.1.1.1', ...}]
""")

        rxn = kg.get_reaction("rxn:kegg:R00200")
        if rxn:
            print("\n--- Output ---")
            substrates = [s["name"] for s in rxn.get("substrates", [])]
            products = [p["name"] for p in rxn.get("products", [])]
            enzymes = [e.get("ec_number", e.get("name")) for e in rxn.get("enzymes", [])]
            print(f"Substrates: {substrates}")
            print(f"Products:   {products}")
            print(f"Enzymes:    {enzymes}")

    kg.close()


def example_3_shortest_path():
    """Example 6.4: Shortest-path search."""
    print("\n" + "=" * 80)
    print("Example 6.4: Shortest-Path Search")
    print("=" * 80)
    print("""
from metakg import MetaKG

kg = MetaKG()

# Glucose to Pyruvate via glycolysis
result = kg.find_path(
    "cpd:kegg:C00031",   # D-Glucose
    "cpd:kegg:C00022",   # Pyruvate
    max_hops=12,
)
print(f"Path length: {result['hops']} steps")
for node in result["path"]:
    print(f"  {node['kind']:10s} {node['name']}")

kg.close()
""")

    kg = MetaKG()
    result = kg.find_path("cpd:kegg:C00031", "cpd:kegg:C00022", max_hops=12)

    print("\n--- Output ---")
    if result and "path" in result:
        print(f"Path length: {result['hops']} steps")
        for node in result["path"]:
            print(f"  {node['kind']:10s} {node['name']}")
    else:
        print("(no path found)")

    kg.close()


def example_4_semantic_search():
    """Example 6.5: Semantic search."""
    print("\n" + "=" * 80)
    print("Example 6.5: Semantic Search")
    print("=" * 80)
    print("""
from metakg import MetaKG

kg = MetaKG()

# Find pathways related to fatty acid oxidation
result = kg.query_pathway("fatty acid beta-oxidation", k=5)
for hit in result.hits:
    print(f"{hit['name']:40s}  "
          f"dist={hit['_distance']:.3f}  "
          f"reactions={hit.get('member_count', '?')}")

kg.close()
""")

    kg = MetaKG()
    result = kg.query_pathway("fatty acid beta-oxidation", k=5)

    print("\n--- Output ---")
    if result and result.hits:
        for hit in result.hits:
            dist = hit.get("_distance", hit.get("distance", "?"))
            member_count = hit.get("member_count", "?")
            print(f"{hit['name']:40s}  dist={dist:.3f}  reactions={member_count}")
    else:
        print("(no results)")

    kg.close()


def main():
    """Run all examples."""
    print("\n" + "#" * 80)
    print("# MetaKG Article Examples - Real Output")
    print("#" * 80)
    print("\nRunning examples from article Section 6 (Worked Example)")
    print("Assumes: metakg-build --data ./pathways has been run")

    try:
        example_1_building()
        example_2_structural_queries()
        example_3_shortest_path()
        example_4_semantic_search()

        print("\n" + "#" * 80)
        print("# Examples complete")
        print("#" * 80 + "\n")

    except Exception as e:
        import traceback

        print(f"\nError: {e}")
        traceback.print_exc()
        print("\nMake sure you've run: poetry run metakg-build --data ./pathways")
        sys.exit(1)


if __name__ == "__main__":
    main()
