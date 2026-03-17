#!/usr/bin/env python3
"""
MetaKG Simulation Demo Script

Demonstrates metabolic pathway simulation capabilities with a single efficient
MetaKG instance and polished output.

Usage:
    poetry run python scripts/simulation_demo.py
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from metakg import MetaKG


def banner(title: str):
    """Print a polished banner."""
    print(f"\n{'─' * 80}")
    print(f"  {title}")
    print(f"{'─' * 80}")


def log_step(step_name: str, elapsed: float = 0):
    """Log a step with elapsed time."""
    timestamp = time.strftime("%H:%M:%S")
    if elapsed > 0:
        print(f"  [{timestamp}] ✓ {step_name} ({elapsed:.2f}s)")
    else:
        print(f"  [{timestamp}] ⟳ {step_name}...", flush=True, end="")


def main():
    """Run simulation demos with a single MetaKG instance."""
    banner("MetaKG Simulation Demos")
    print()

    # =========================================================================
    # Initialize
    # =========================================================================
    print("Initializing MetaKG...")
    start = time.time()
    kg = MetaKG()
    log_step("Database loaded", time.time() - start)

    # =========================================================================
    # Demo 0: Find Pathways (Semantic Search)
    # =========================================================================
    banner("Demo 0: Pathway Discovery")

    log_step("Searching for pathways")
    start = time.time()
    pathway_result = kg.query_pathway("glycolysis", k=5)
    log_step("Search complete", time.time() - start)

    print(f"\n  Found {len(pathway_result.hits)} pathway(s):\n")
    for i, hit in enumerate(pathway_result.hits[:3], 1):
        print(f"    {i}. {hit['name']}")
        print(f"       ID: {hit['id']}")
        print(f"       Reactions: {hit['member_count']}\n")

    if not pathway_result.hits:
        print("  (No pathways found)")
        kg.close()
        return

    # Use first pathway (shorter one)
    pathway_id = pathway_result.hits[0]["id"]
    pathway_name = pathway_result.hits[0]["name"]

    # =========================================================================
    # Demo 1: Seed Kinetic Parameters
    # =========================================================================
    banner("Demo 1: Load Kinetic Parameters")

    log_step("Seeding kinetics from literature")
    start = time.time()
    result = kg.seed_kinetics()
    elapsed = time.time() - start
    print(f" {elapsed:.2f}s")

    print(f"\n  Kinetic parameters written:    {result['kinetic_params_written']}")
    print(f"  Regulatory interactions:       {result['regulatory_interactions_written']}")

    # =========================================================================
    # Demo 2: Flux Balance Analysis
    # =========================================================================
    banner("Demo 2: Flux Balance Analysis")

    log_step("Running FBA on pathway: " + pathway_name)
    start = time.time()
    result = kg.simulate_fba(pathway_id=pathway_id, maximize=True)
    elapsed = time.time() - start
    print(f" {elapsed:.2f}s")

    print(f"\n  Status:           {result['status']}")
    print(f"  Objective value:  {result['objective_value']}")
    print(f"  Reactions found:  {len(result['fluxes'])}")

    if result["fluxes"]:
        print("\n  Top 3 reactions by flux:")
        fluxes = sorted(result["fluxes"].items(), key=lambda x: abs(x[1]), reverse=True)
        for rxn_id, flux in fluxes[:3]:
            print(f"    • {rxn_id}: {flux:.6g} mM/s")

    # =========================================================================
    # Demo 3: What-If Enzyme Knockout
    # =========================================================================
    banner("Demo 3: What-If Analysis - Enzyme Knockout")

    enzymes = kg.store.all_nodes(kind="enzyme")
    if enzymes:
        enzyme_id = enzymes[0]["id"]
        enzyme_name = enzymes[0].get("name", enzyme_id)

        log_step(f"Knocking out {enzyme_name}")
        start = time.time()

        scenario = {"name": "knockout", "enzyme_knockouts": [enzyme_id]}
        result = kg.simulate_whatif(
            pathway_id=pathway_id, scenario_json=json.dumps(scenario), mode="fba"
        )
        elapsed = time.time() - start
        print(f" {elapsed:.2f}s")

        baseline = result["baseline"]["objective_value"]
        perturbed = result["perturbed"]["objective_value"]

        print(f"\n  Enzyme:              {enzyme_name}")
        print(f"  Baseline objective:  {baseline}")
        print(f"  With knockout:       {perturbed}")

        if baseline is not None and baseline != 0 and perturbed is not None:
            change = 100 * (perturbed - baseline) / baseline
            print(f"  Change:              {change:+.1f}%")

    else:
        print("  (No enzymes in database)")

    # =========================================================================
    # Demo 4: What-If Enzyme Inhibition
    # =========================================================================
    banner("Demo 4: What-If Analysis - Enzyme Inhibition (50%)")

    if enzymes:
        enzyme_id = enzymes[0]["id"]
        enzyme_name = enzymes[0].get("name", enzyme_id)

        log_step(f"Inhibiting {enzyme_name} to 50%")
        start = time.time()

        scenario = {"name": "inhibition_50pct", "enzyme_factors": {enzyme_id: 0.5}}
        result = kg.simulate_whatif(
            pathway_id=pathway_id, scenario_json=json.dumps(scenario), mode="fba"
        )
        elapsed = time.time() - start
        print(f" {elapsed:.2f}s")

        baseline = result["baseline"]["objective_value"]
        perturbed = result["perturbed"]["objective_value"]

        print(f"\n  Enzyme:              {enzyme_name}")
        print(f"  Baseline objective:  {baseline}")
        print(f"  With 50% inhibition: {perturbed}")

        if baseline is not None and baseline != 0 and perturbed is not None:
            change = 100 * (perturbed - baseline) / baseline
            print(f"  Change:              {change:+.1f}%")

    else:
        print("  (No enzymes in database)")

    # =========================================================================
    # Demo 5: Kinetic ODE Simulation (Long-running - at end)
    # =========================================================================
    banner("Demo 5: Kinetic ODE Simulation (Time-Course)")

    log_step("Setting up ODE integration for " + pathway_name)
    print()  # newline after "..."

    start_ode = time.time()

    # Show initial setup
    print("  Configuration:")
    print("    • Timespan: 0 to 20 time units")
    print("    • Data points: 50")
    print("    • Initial glucose: 5.0 mM")
    print("    • Default [compound]: 1.0 mM")
    print()

    log_step("Integrating ODEs")
    start = time.time()

    result = kg.simulate_ode(
        pathway_id=pathway_id,
        t_end=20,
        t_points=50,
        initial_concentrations={"cpd:kegg:C00031": 5.0},  # Glucose
        default_concentration=1.0,
    )

    elapsed = time.time() - start
    print(f" {elapsed:.2f}s")

    print("\n  Results:")
    print(f"    • Status:          {result['status']}")
    print(f"    • Time points:     {len(result['t'])}")
    print(f"    • Compounds:       {len(result['concentrations'])}")

    if result["concentrations"]:
        print("\n  Final concentrations (sample):")
        conc_items = list(result["concentrations"].items())[:3]
        for cpd_id, conc_array in conc_items:
            if conc_array:
                cpd = kg.get_compound(cpd_id)
                name = cpd.get("name", cpd_id) if cpd else cpd_id
                initial = conc_array[0] if conc_array else 0
                final = conc_array[-1] if conc_array else 0
                print(f"    • {name:35s}  {initial:8.4f} → {final:8.4f} mM")

    total_elapsed = time.time() - start_ode
    print(f"\n  ODE simulation total time: {total_elapsed:.2f}s")

    # =========================================================================
    # Cleanup
    # =========================================================================
    kg.close()

    banner("Demos Complete")
    print()


if __name__ == "__main__":
    main()
