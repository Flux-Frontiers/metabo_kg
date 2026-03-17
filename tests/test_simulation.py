"""
Tests for metakg.simulate — Metabolic simulations (FBA, ODE, what-if).

Includes timeout guards to prevent ODE solver hangs.
"""

import json

import pytest

from metakg import MetaKG
from metakg.primitives import (
    KIND_COMPOUND,
    KIND_ENZYME,
    KIND_PATHWAY,
    KIND_REACTION,
    MetaEdge,
    MetaNode,
    node_id,
)


@pytest.fixture()
def kkg_with_minimal_pathway(tmp_path):
    """
    Create a MetaKG instance with minimal pathway for testing.

    Pathway: Glucose → Pyruvate (2 reactions, 3 compounds)
    """
    kg = MetaKG(
        db_path=tmp_path / "test.sqlite",
        lancedb_dir=tmp_path / "lancedb",
    )

    # Nodes: 3 compounds, 2 reactions, 1 pathway, 2 enzymes
    nodes = [
        MetaNode(
            id=node_id(KIND_COMPOUND, "kegg", "C00031"),
            kind=KIND_COMPOUND,
            name="D-Glucose",
            formula="C6H12O6",
            xrefs='{"kegg": "C00031"}',
            source_format="csv",
        ),
        MetaNode(
            id=node_id(KIND_COMPOUND, "kegg", "C00092"),
            kind=KIND_COMPOUND,
            name="Glucose-6-phosphate",
            formula="C6H13O9P",
            xrefs='{"kegg": "C00092"}',
            source_format="csv",
        ),
        MetaNode(
            id=node_id(KIND_COMPOUND, "kegg", "C00022"),
            kind=KIND_COMPOUND,
            name="Pyruvate",
            formula="C3H4O3",
            xrefs='{"kegg": "C00022"}',
            source_format="csv",
        ),
        MetaNode(
            id=node_id(KIND_COMPOUND, "kegg", "C00005"),
            kind=KIND_COMPOUND,
            name="ATP",
            formula="C10H16N5O13P3",
            xrefs='{"kegg": "C00005"}',
            source_format="csv",
        ),
        MetaNode(
            id=node_id(KIND_COMPOUND, "kegg", "C00008"),
            kind=KIND_COMPOUND,
            name="ADP",
            formula="C10H15N5O10P2",
            xrefs='{"kegg": "C00008"}',
            source_format="csv",
        ),
        # Reaction 1: Glucose + ATP → Glucose-6-phosphate + ADP
        MetaNode(
            id=node_id(KIND_REACTION, "kegg", "R01786"),
            kind=KIND_REACTION,
            name="Hexokinase",
            stoichiometry=json.dumps(
                {
                    "substrates": [
                        {"id": node_id(KIND_COMPOUND, "kegg", "C00031"), "stoich": 1.0},
                        {"id": node_id(KIND_COMPOUND, "kegg", "C00005"), "stoich": 1.0},
                    ],
                    "products": [
                        {"id": node_id(KIND_COMPOUND, "kegg", "C00092"), "stoich": 1.0},
                        {"id": node_id(KIND_COMPOUND, "kegg", "C00008"), "stoich": 1.0},
                    ],
                }
            ),
            xrefs='{"kegg": "R01786"}',
            source_format="csv",
        ),
        # Reaction 2: Glucose-6-phosphate → Pyruvate (simplified)
        MetaNode(
            id=node_id(KIND_REACTION, "kegg", "R02035"),
            kind=KIND_REACTION,
            name="Gluconeogenesis (simplified)",
            stoichiometry=json.dumps(
                {
                    "substrates": [
                        {"id": node_id(KIND_COMPOUND, "kegg", "C00092"), "stoich": 1.0},
                    ],
                    "products": [
                        {"id": node_id(KIND_COMPOUND, "kegg", "C00022"), "stoich": 1.0},
                    ],
                }
            ),
            xrefs='{"kegg": "R02035"}',
            source_format="csv",
        ),
        MetaNode(
            id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
            kind=KIND_PATHWAY,
            name="Glycolysis",
            xrefs='{"kegg": "hsa00010"}',
            source_format="csv",
        ),
        MetaNode(
            id=node_id(KIND_ENZYME, "ec", "2.7.1.1"),
            kind=KIND_ENZYME,
            name="Hexokinase",
            ec_number="2.7.1.1",
            xrefs='{"ec": "2.7.1.1"}',
            source_format="csv",
        ),
        MetaNode(
            id=node_id(KIND_ENZYME, "ec", "5.3.1.9"),
            kind=KIND_ENZYME,
            name="Glucose-6-phosphate isomerase",
            ec_number="5.3.1.9",
            xrefs='{"ec": "5.3.1.9"}',
            source_format="csv",
        ),
    ]

    # Edges
    edges = [
        # Reaction 1 edges
        MetaEdge(
            src=node_id(KIND_COMPOUND, "kegg", "C00031"),
            dst=node_id(KIND_REACTION, "kegg", "R01786"),
            rel="SUBSTRATE_OF",
        ),
        MetaEdge(
            src=node_id(KIND_COMPOUND, "kegg", "C00005"),
            dst=node_id(KIND_REACTION, "kegg", "R01786"),
            rel="SUBSTRATE_OF",
        ),
        MetaEdge(
            src=node_id(KIND_REACTION, "kegg", "R01786"),
            dst=node_id(KIND_COMPOUND, "kegg", "C00092"),
            rel="PRODUCT_OF",
        ),
        MetaEdge(
            src=node_id(KIND_REACTION, "kegg", "R01786"),
            dst=node_id(KIND_COMPOUND, "kegg", "C00008"),
            rel="PRODUCT_OF",
        ),
        # Reaction 2 edges
        MetaEdge(
            src=node_id(KIND_COMPOUND, "kegg", "C00092"),
            dst=node_id(KIND_REACTION, "kegg", "R02035"),
            rel="SUBSTRATE_OF",
        ),
        MetaEdge(
            src=node_id(KIND_REACTION, "kegg", "R02035"),
            dst=node_id(KIND_COMPOUND, "kegg", "C00022"),
            rel="PRODUCT_OF",
        ),
        # Enzyme catalyzes
        MetaEdge(
            src=node_id(KIND_ENZYME, "ec", "2.7.1.1"),
            dst=node_id(KIND_REACTION, "kegg", "R01786"),
            rel="CATALYZES",
        ),
        MetaEdge(
            src=node_id(KIND_ENZYME, "ec", "5.3.1.9"),
            dst=node_id(KIND_REACTION, "kegg", "R02035"),
            rel="CATALYZES",
        ),
        # Pathway contains
        MetaEdge(
            src=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
            dst=node_id(KIND_REACTION, "kegg", "R01786"),
            rel="CONTAINS",
        ),
        MetaEdge(
            src=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
            dst=node_id(KIND_REACTION, "kegg", "R02035"),
            rel="CONTAINS",
        ),
    ]

    # Write to store
    kg.store.write(nodes, edges)

    yield kg
    kg.close()


# =========================================================================
# FBA Tests
# =========================================================================


def test_simulate_fba_basic(kkg_with_minimal_pathway):
    """Test basic FBA simulation."""
    result = kkg_with_minimal_pathway.simulate_fba(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        maximize=True,
    )

    assert isinstance(result, dict)
    assert "status" in result
    assert "objective_value" in result
    assert "fluxes" in result
    assert isinstance(result["fluxes"], dict)


def test_simulate_fba_minimize(kkg_with_minimal_pathway):
    """Test FBA with minimization."""
    result = kkg_with_minimal_pathway.simulate_fba(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        maximize=False,
    )

    assert isinstance(result, dict)
    assert "objective_value" in result


def test_simulate_fba_no_pathway(kkg_with_minimal_pathway):
    """Test FBA with no pathway ID (uses all reactions)."""
    result = kkg_with_minimal_pathway.simulate_fba(
        pathway_id=None,
        maximize=True,
    )

    assert isinstance(result, dict)
    # Should still have status and objective_value even with no pathway
    assert "status" in result


# =========================================================================
# ODE Tests (with timeout guards)
# =========================================================================


@pytest.mark.timeout(5)  # 5-second timeout to catch hangs
def test_simulate_ode_bdf_default(kkg_with_minimal_pathway):
    """Test ODE simulation with default BDF solver."""
    result = kkg_with_minimal_pathway.simulate_ode(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        t_end=5.0,
        t_points=20,
        initial_concentrations={node_id(KIND_COMPOUND, "kegg", "C00031"): 5.0},
    )

    assert isinstance(result, dict)
    assert "status" in result
    assert result["status"] == "ok", f"ODE failed: {result.get('message', 'no message')}"
    assert "t" in result
    assert "concentrations" in result
    assert len(result["t"]) > 0
    assert len(result["concentrations"]) > 0


@pytest.mark.timeout(5)  # 5-second timeout
def test_simulate_ode_bdf_explicit(kkg_with_minimal_pathway):
    """Test ODE simulation with explicit BDF solver specification."""
    result = kkg_with_minimal_pathway.simulate_ode(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        t_end=5.0,
        t_points=20,
        initial_concentrations={node_id(KIND_COMPOUND, "kegg", "C00031"): 5.0},
        ode_method="BDF",
        ode_rtol=1e-3,
        ode_atol=1e-5,
        ode_max_step=None,
    )

    assert result["status"] == "ok"
    assert len(result["t"]) == 20  # Should match requested points


@pytest.mark.timeout(10)  # 10-second timeout for RK45 on non-stiff system
def test_simulate_ode_rk45_non_stiff(kkg_with_minimal_pathway):
    """
    Test ODE with RK45 on very short integration to verify it doesn't hang.

    Note: RK45 should work on non-stiff systems; we use very small t_end
    to ensure it completes quickly even if less efficient than BDF.
    """
    result = kkg_with_minimal_pathway.simulate_ode(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        t_end=0.1,  # Very short integration
        t_points=5,
        initial_concentrations={node_id(KIND_COMPOUND, "kegg", "C00031"): 5.0},
        ode_method="RK45",
        ode_rtol=1e-3,
        ode_atol=1e-5,
        ode_max_step=None,
    )

    # Status should be ok or have a message
    assert "status" in result


@pytest.mark.timeout(5)  # 5-second timeout
def test_simulate_ode_radau(kkg_with_minimal_pathway):
    """Test ODE simulation with Radau solver."""
    result = kkg_with_minimal_pathway.simulate_ode(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        t_end=5.0,
        t_points=20,
        initial_concentrations={node_id(KIND_COMPOUND, "kegg", "C00031"): 5.0},
        ode_method="Radau",
        ode_rtol=1e-3,
        ode_atol=1e-5,
        ode_max_step=None,
    )

    assert isinstance(result, dict)
    assert "status" in result


@pytest.mark.timeout(5)  # 5-second timeout
def test_simulate_ode_with_default_concentration(kkg_with_minimal_pathway):
    """Test ODE with default concentration for unmapped compounds."""
    result = kkg_with_minimal_pathway.simulate_ode(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        t_end=5.0,
        t_points=20,
        initial_concentrations={},
        default_concentration=2.0,
    )

    assert isinstance(result, dict)
    assert "concentrations" in result


@pytest.mark.timeout(5)  # 5-second timeout
def test_simulate_ode_tolerances(kkg_with_minimal_pathway):
    """Test ODE with various tolerance settings."""
    for rtol, atol in [(1e-2, 1e-4), (1e-3, 1e-5), (1e-4, 1e-6)]:
        result = kkg_with_minimal_pathway.simulate_ode(
            pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
            t_end=2.0,
            t_points=10,
            initial_concentrations={node_id(KIND_COMPOUND, "kegg", "C00031"): 5.0},
            ode_rtol=rtol,
            ode_atol=atol,
        )

        assert isinstance(result, dict)
        assert "status" in result


# =========================================================================
# What-If Tests (with timeout guards)
# =========================================================================


@pytest.mark.timeout(5)
def test_simulate_whatif_fba_baseline(kkg_with_minimal_pathway):
    """Test what-if analysis baseline (no perturbation) in FBA mode."""
    scenario = {"name": "baseline", "enzyme_knockouts": []}

    result = kkg_with_minimal_pathway.simulate_whatif(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        scenario_json=json.dumps(scenario),
        mode="fba",
    )

    assert isinstance(result, dict)
    assert "baseline" in result
    assert "perturbed" in result
    assert result["baseline"] == result["perturbed"]  # No change for no perturbation


@pytest.mark.timeout(5)
def test_simulate_whatif_fba_knockout(kkg_with_minimal_pathway):
    """Test what-if analysis with enzyme knockout in FBA mode."""
    scenario = {
        "name": "hexokinase_knockout",
        "enzyme_knockouts": [node_id(KIND_ENZYME, "ec", "2.7.1.1")],
    }

    result = kkg_with_minimal_pathway.simulate_whatif(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        scenario_json=json.dumps(scenario),
        mode="fba",
    )

    assert isinstance(result, dict)
    assert "baseline" in result
    assert "perturbed" in result
    assert "delta_fluxes" in result


@pytest.mark.timeout(5)
def test_simulate_whatif_fba_inhibition(kkg_with_minimal_pathway):
    """Test what-if analysis with enzyme inhibition (50%) in FBA mode."""
    scenario = {
        "name": "hexokinase_inhibition",
        "enzyme_factors": {node_id(KIND_ENZYME, "ec", "2.7.1.1"): 0.5},
    }

    result = kkg_with_minimal_pathway.simulate_whatif(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        scenario_json=json.dumps(scenario),
        mode="fba",
    )

    assert isinstance(result, dict)
    assert "baseline" in result
    assert "perturbed" in result


@pytest.mark.timeout(10)
def test_simulate_whatif_ode_mode(kkg_with_minimal_pathway):
    """Test what-if analysis in ODE mode (more computationally intensive)."""
    scenario = {
        "name": "knockout",
        "enzyme_knockouts": [node_id(KIND_ENZYME, "ec", "2.7.1.1")],
    }

    result = kkg_with_minimal_pathway.simulate_whatif(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        scenario_json=json.dumps(scenario),
        mode="ode",
        t_end=2.0,
        t_points=10,
        ode_method="BDF",
    )

    assert isinstance(result, dict)
    assert "baseline" in result
    assert "perturbed" in result


# =========================================================================
# Kinetics Tests
# =========================================================================


def test_seed_kinetics(kkg_with_minimal_pathway):
    """Test seeding kinetic parameters."""
    result = kkg_with_minimal_pathway.seed_kinetics(force=False)

    assert isinstance(result, dict)
    assert "kinetic_params_written" in result
    assert "regulatory_interactions_written" in result
    assert result["kinetic_params_written"] >= 0
    assert result["regulatory_interactions_written"] >= 0


def test_seed_kinetics_force_overwrite(kkg_with_minimal_pathway):
    """Test re-seeding kinetic parameters with force=True."""
    # Seed once
    result1 = kkg_with_minimal_pathway.seed_kinetics(force=False)
    assert isinstance(result1, dict)

    # Seed again with force=True
    result2 = kkg_with_minimal_pathway.seed_kinetics(force=True)

    assert isinstance(result2, dict)
    assert result2["kinetic_params_written"] >= 0


# =========================================================================
# Error Handling and Edge Cases
# =========================================================================


def test_simulate_fba_nonexistent_pathway(kkg_with_minimal_pathway):
    """Test FBA with non-existent pathway ID."""
    result = kkg_with_minimal_pathway.simulate_fba(
        pathway_id="pwy:kegg:nonexistent",
        maximize=True,
    )

    # Should return a result dict (may have empty/error status)
    assert isinstance(result, dict)


@pytest.mark.timeout(5)
def test_simulate_ode_empty_concentrations(kkg_with_minimal_pathway):
    """Test ODE with empty initial concentrations."""
    result = kkg_with_minimal_pathway.simulate_ode(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        t_end=2.0,
        t_points=10,
        initial_concentrations={},
        default_concentration=1.0,
    )

    assert isinstance(result, dict)


@pytest.mark.timeout(5)
def test_simulate_ode_very_short_integration(kkg_with_minimal_pathway):
    """Test ODE with very short integration time."""
    result = kkg_with_minimal_pathway.simulate_ode(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        t_end=0.01,
        t_points=2,
        initial_concentrations={node_id(KIND_COMPOUND, "kegg", "C00031"): 5.0},
    )

    assert isinstance(result, dict)
    assert "status" in result


def test_simulate_whatif_invalid_mode(kkg_with_minimal_pathway):
    """Test what-if with invalid mode raises ValueError."""
    scenario = {"name": "test"}

    with pytest.raises(ValueError, match="mode must be"):
        kkg_with_minimal_pathway.simulate_whatif(
            pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
            scenario_json=json.dumps(scenario),
            mode="invalid",
        )


# =========================================================================
# Performance and Regression Tests
# =========================================================================


@pytest.mark.timeout(3)  # BDF should complete well under 3 seconds
def test_ode_bdf_performance(kkg_with_minimal_pathway):
    """
    Regression test: BDF solver should complete quickly.

    This guards against reverting to slow/hanging solvers.
    """
    import time

    start = time.time()
    result = kkg_with_minimal_pathway.simulate_ode(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        t_end=10.0,
        t_points=50,
        initial_concentrations={node_id(KIND_COMPOUND, "kegg", "C00031"): 5.0},
        ode_method="BDF",
    )
    elapsed = time.time() - start

    assert result["status"] == "ok"
    assert elapsed < 2.0, f"BDF took {elapsed:.2f}s (should be <2s)"


@pytest.mark.timeout(3)  # Should not regress to hanging
def test_ode_no_hardcoded_max_step_hang(kkg_with_minimal_pathway):
    """
    Regression test: Verify ode_max_step=None doesn't cause hanging.

    The old code had max_step=t_end/50 which caused hanging on stiff systems.
    This test ensures that default (None) works efficiently.
    """
    result = kkg_with_minimal_pathway.simulate_ode(
        pathway_id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
        t_end=10.0,
        t_points=50,
        initial_concentrations={node_id(KIND_COMPOUND, "kegg", "C00031"): 5.0},
        ode_method="BDF",
        ode_rtol=1e-3,
        ode_atol=1e-5,
        ode_max_step=None,  # Should not hang
    )

    assert result["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
