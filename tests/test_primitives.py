"""
Tests for code_kg.metakg.primitives — MetaNode, MetaEdge, node_id, synthetic_id.
"""

import json

from metakg.primitives import (
    KIND_COMPOUND,
    KIND_ENZYME,
    KIND_PATHWAY,
    KIND_REACTION,
    PATHWAY_CATEGORY_CELLULAR,
    PATHWAY_CATEGORY_DISEASE,
    PATHWAY_CATEGORY_DRUG,
    PATHWAY_CATEGORY_GIP,
    PATHWAY_CATEGORY_METABOLIC,
    PATHWAY_CATEGORY_ORGANISMAL,
    PATHWAY_CATEGORY_SIGNALING,
    PATHWAY_CATEGORY_TRANSPORT,
    MetaEdge,
    MetaNode,
    _kegg_pathway_category,
    node_id,
    synthetic_id,
)


class TestNodeId:
    def test_compound_kegg(self):
        assert node_id(KIND_COMPOUND, "kegg", "C00022") == "cpd:kegg:C00022"

    def test_reaction_kegg(self):
        assert node_id(KIND_REACTION, "kegg", "R00200") == "rxn:kegg:R00200"

    def test_enzyme_ec(self):
        assert node_id(KIND_ENZYME, "ec", "1.1.1.1") == "enz:ec:1.1.1.1"

    def test_pathway_kegg(self):
        assert node_id(KIND_PATHWAY, "kegg", "hsa00010") == "pwy:kegg:hsa00010"

    def test_unknown_kind_uses_kind_as_prefix(self):
        result = node_id("custom", "db", "123")
        assert result == "custom:db:123"


class TestSyntheticId:
    def test_deterministic(self):
        a = synthetic_id(KIND_COMPOUND, "pyruvate")
        b = synthetic_id(KIND_COMPOUND, "pyruvate")
        assert a == b

    def test_case_insensitive(self):
        a = synthetic_id(KIND_COMPOUND, "pyruvate")
        b = synthetic_id(KIND_COMPOUND, "PYRUVATE")
        assert a == b

    def test_has_correct_prefix(self):
        nid = synthetic_id(KIND_COMPOUND, "glucose")
        assert nid.startswith("cpd:syn:")

    def test_different_names_different_ids(self):
        a = synthetic_id(KIND_COMPOUND, "glucose")
        b = synthetic_id(KIND_COMPOUND, "fructose")
        assert a != b


class TestMetaNode:
    def test_basic_construction(self):
        n = MetaNode(id="cpd:kegg:C00022", kind=KIND_COMPOUND, name="Pyruvate")
        assert n.id == "cpd:kegg:C00022"
        assert n.kind == KIND_COMPOUND
        assert n.name == "Pyruvate"

    def test_xrefs_dict_parses_json(self):
        n = MetaNode(
            id="cpd:kegg:C00022",
            kind=KIND_COMPOUND,
            name="Pyruvate",
            xrefs='{"kegg": "C00022", "chebi": "CHEBI_15361"}',
        )
        d = n.xrefs_dict()
        assert d["kegg"] == "C00022"
        assert d["chebi"] == "CHEBI_15361"

    def test_xrefs_dict_empty_when_not_set(self):
        n = MetaNode(id="cpd:kegg:C00022", kind=KIND_COMPOUND, name="Pyruvate")
        assert n.xrefs_dict() == {}

    def test_stoichiometry_dict_parses(self):
        stoich = {
            "substrates": [{"id": "cpd:kegg:C00031", "stoich": 1.0}],
            "products": [],
        }
        n = MetaNode(
            id="rxn:kegg:R00200",
            kind=KIND_REACTION,
            name="Glycolysis step 1",
            stoichiometry=json.dumps(stoich),
        )
        assert n.stoichiometry_dict()["substrates"][0]["stoich"] == 1.0

    def test_stoichiometry_dict_empty_when_not_set(self):
        n = MetaNode(id="rxn:kegg:R00200", kind=KIND_REACTION, name="Rxn")
        assert n.stoichiometry_dict() == {}


class TestMetaEdge:
    def test_basic_construction(self):
        e = MetaEdge(src="cpd:kegg:C00031", rel="SUBSTRATE_OF", dst="rxn:kegg:R00200")
        assert e.src == "cpd:kegg:C00031"
        assert e.rel == "SUBSTRATE_OF"
        assert e.dst == "rxn:kegg:R00200"

    def test_evidence_dict_parses(self):
        e = MetaEdge(
            src="cpd:kegg:C00031",
            rel="SUBSTRATE_OF",
            dst="rxn:kegg:R00200",
            evidence='{"stoich": 2.0, "compartment": "cytosol"}',
        )
        assert e.evidence_dict()["stoich"] == 2.0
        assert e.evidence_dict()["compartment"] == "cytosol"

    def test_evidence_dict_empty_when_not_set(self):
        e = MetaEdge(src="a", rel="R", dst="b")
        assert e.evidence_dict() == {}


class TestKeggPathwayCategory:
    """Tests for the _kegg_pathway_category() helper and PATHWAY_CATEGORY_* constants."""

    def test_metabolic_low_end(self):
        assert _kegg_pathway_category("hsa00010") == PATHWAY_CATEGORY_METABOLIC

    def test_metabolic_high_end(self):
        assert _kegg_pathway_category("hsa01100") == PATHWAY_CATEGORY_METABOLIC

    def test_transport(self):
        assert _kegg_pathway_category("hsa02010") == PATHWAY_CATEGORY_TRANSPORT

    def test_genetic_info_processing(self):
        assert _kegg_pathway_category("hsa03010") == PATHWAY_CATEGORY_GIP

    def test_signaling(self):
        assert _kegg_pathway_category("hsa04010") == PATHWAY_CATEGORY_SIGNALING

    def test_signaling_upper_boundary(self):
        assert _kegg_pathway_category("hsa04099") == PATHWAY_CATEGORY_SIGNALING

    def test_cellular_process(self):
        assert _kegg_pathway_category("hsa04110") == PATHWAY_CATEGORY_CELLULAR

    def test_cellular_upper_boundary(self):
        assert _kegg_pathway_category("hsa04490") == PATHWAY_CATEGORY_CELLULAR

    def test_organismal_system(self):
        assert _kegg_pathway_category("hsa04500") == PATHWAY_CATEGORY_ORGANISMAL

    def test_organismal_upper_boundary(self):
        assert _kegg_pathway_category("hsa04999") == PATHWAY_CATEGORY_ORGANISMAL

    def test_human_disease(self):
        assert _kegg_pathway_category("hsa05010") == PATHWAY_CATEGORY_DISEASE

    def test_human_disease_upper_boundary(self):
        assert _kegg_pathway_category("hsa05999") == PATHWAY_CATEGORY_DISEASE

    def test_drug_development(self):
        assert _kegg_pathway_category("hsa07010") == PATHWAY_CATEGORY_DRUG

    def test_unparseable_id_returns_none(self):
        assert _kegg_pathway_category("") is None
        assert _kegg_pathway_category("no_digits") is None

    def test_number_with_no_org_prefix(self):
        # bare numeric suffix should still work
        assert _kegg_pathway_category("00010") == PATHWAY_CATEGORY_METABOLIC


class TestMetaNodeCategory:
    def test_category_defaults_to_none(self):
        n = MetaNode(id="cpd:kegg:C00022", kind=KIND_COMPOUND, name="Pyruvate")
        assert n.category is None

    def test_category_set_on_pathway_node(self):
        n = MetaNode(
            id=node_id(KIND_PATHWAY, "kegg", "hsa00010"),
            kind=KIND_PATHWAY,
            name="Glycolysis",
            category=PATHWAY_CATEGORY_METABOLIC,
        )
        assert n.category == PATHWAY_CATEGORY_METABOLIC

    def test_category_none_for_non_pathway_nodes(self):
        for kind in (KIND_COMPOUND, KIND_REACTION, KIND_ENZYME):
            n = MetaNode(id=f"{kind}:test:1", kind=kind, name="Test")
            assert n.category is None
