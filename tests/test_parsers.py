"""
Tests for code_kg.metakg parsers — KGML, SBML, CSV.

BioPAX tests are omitted here since rdflib is an optional dependency.
"""

import textwrap

import pytest

from metakg.primitives import (
    KIND_COMPOUND,
    KIND_ENZYME,
    KIND_PATHWAY,
    KIND_REACTION,
    PATHWAY_CATEGORY_METABOLIC,
    _kegg_pathway_category,
)

# ---------------------------------------------------------------------------
# KGML parser
# ---------------------------------------------------------------------------

KGML_SAMPLE = textwrap.dedent(
    """\
<?xml version="1.0"?>
<pathway name="path:hsa00010" org="hsa" number="00010"
         title="Glycolysis / Gluconeogenesis">
  <entry id="1" name="cpd:C00031" type="compound">
    <graphics name="D-Glucose" type="circle"/>
  </entry>
  <entry id="2" name="cpd:C00022" type="compound">
    <graphics name="Pyruvate" type="circle"/>
  </entry>
  <entry id="3" name="hsa:2645" type="gene">
    <graphics name="GCK" type="rectangle"/>
  </entry>
  <reaction id="4" name="rn:R00200" type="irreversible">
    <substrate name="cpd:C00031"/>
    <product name="cpd:C00022"/>
  </reaction>
</pathway>
"""
)

SBML_SAMPLE = textwrap.dedent(
    """\
<?xml version="1.0"?>
<sbml xmlns="http://www.sbml.org/sbml/level2" level="2" version="1">
  <model id="glycolysis" name="Glycolysis">
    <listOfSpecies>
      <species id="glucose" name="D-Glucose" compartment="cytosol"/>
      <species id="pyruvate" name="Pyruvate" compartment="cytosol"/>
    </listOfSpecies>
    <listOfReactions>
      <reaction id="R00200" name="Glucose to Pyruvate" reversible="false">
        <listOfReactants>
          <speciesReference species="glucose" stoichiometry="1"/>
        </listOfReactants>
        <listOfProducts>
          <speciesReference species="pyruvate" stoichiometry="2"/>
        </listOfProducts>
      </reaction>
    </listOfReactions>
  </model>
</sbml>
"""
)

CSV_SAMPLE = textwrap.dedent(
    """\
reaction_id,reaction_name,substrate,product,enzyme,stoich_substrate,stoich_product,pathway,ec_number
R001,Hexokinase reaction,D-Glucose,Glucose-6-phosphate,Hexokinase,1,1,Glycolysis,2.7.1.1
R002,PGI reaction,Glucose-6-phosphate,Fructose-6-phosphate,Phosphoglucose isomerase,1,1,Glycolysis,5.3.1.9
"""
)


class TestKGMLParser:
    def test_parse_returns_nodes_and_edges(self, tmp_path):
        from metakg.parsers.kgml import KGMLParser

        f = tmp_path / "hsa00010.xml"
        f.write_text(KGML_SAMPLE)
        parser = KGMLParser()
        nodes, edges = parser.parse(f)
        assert len(nodes) > 0
        assert len(edges) > 0

    def test_pathway_node_present(self, tmp_path):
        from metakg.parsers.kgml import KGMLParser

        f = tmp_path / "hsa00010.xml"
        f.write_text(KGML_SAMPLE)
        nodes, _ = KGMLParser().parse(f)
        kinds = {n.kind for n in nodes}
        assert KIND_PATHWAY in kinds

    def test_reaction_node_present(self, tmp_path):
        from metakg.parsers.kgml import KGMLParser

        f = tmp_path / "hsa00010.xml"
        f.write_text(KGML_SAMPLE)
        nodes, _ = KGMLParser().parse(f)
        kinds = {n.kind for n in nodes}
        assert KIND_REACTION in kinds

    def test_compound_nodes_present(self, tmp_path):
        from metakg.parsers.kgml import KGMLParser

        f = tmp_path / "hsa00010.xml"
        f.write_text(KGML_SAMPLE)
        nodes, _ = KGMLParser().parse(f)
        compounds = [n for n in nodes if n.kind == KIND_COMPOUND]
        assert len(compounds) >= 2

    def test_substrate_edge_present(self, tmp_path):
        from metakg.parsers.kgml import KGMLParser

        f = tmp_path / "hsa00010.xml"
        f.write_text(KGML_SAMPLE)
        _, edges = KGMLParser().parse(f)
        rels = {e.rel for e in edges}
        assert "SUBSTRATE_OF" in rels
        assert "PRODUCT_OF" in rels

    def test_can_handle_kgml_extension(self, tmp_path):
        from metakg.parsers.kgml import KGMLParser

        f = tmp_path / "test.kgml"
        f.write_text(KGML_SAMPLE)
        assert KGMLParser().can_handle(f)

    def test_cannot_handle_non_pathway_xml(self, tmp_path):
        from metakg.parsers.kgml import KGMLParser

        f = tmp_path / "test.xml"
        f.write_text('<?xml version="1.0"?><sbml/>')
        assert not KGMLParser().can_handle(f)

    def test_invalid_xml_raises_value_error(self, tmp_path):
        from metakg.parsers.kgml import KGMLParser

        f = tmp_path / "bad.xml"
        f.write_text("<pathway><unclosed>")
        # can_handle may return False for malformed XML, but parse should raise
        with pytest.raises(ValueError):
            KGMLParser().parse(f)

    def test_source_format_is_kgml(self, tmp_path):
        from metakg.parsers.kgml import KGMLParser

        f = tmp_path / "test.xml"
        f.write_text(KGML_SAMPLE)
        nodes, _ = KGMLParser().parse(f)
        assert all(n.source_format == "kgml" for n in nodes)

    def test_pathway_has_kegg_xref(self, tmp_path):
        from metakg.parsers.kgml import KGMLParser

        f = tmp_path / "test.xml"
        f.write_text(KGML_SAMPLE)
        nodes, _ = KGMLParser().parse(f)
        pwy_nodes = [n for n in nodes if n.kind == KIND_PATHWAY]
        assert len(pwy_nodes) == 1
        xrefs = pwy_nodes[0].xrefs_dict()
        assert "kegg" in xrefs

    def test_pathway_category_metabolic(self, tmp_path):
        from metakg.parsers.kgml import KGMLParser

        # KGML_SAMPLE encodes hsa00010 — a metabolic pathway
        f = tmp_path / "hsa00010.xml"
        f.write_text(KGML_SAMPLE)
        nodes, _ = KGMLParser().parse(f)
        pwy_nodes = [n for n in nodes if n.kind == KIND_PATHWAY]
        assert len(pwy_nodes) == 1
        assert pwy_nodes[0].category == PATHWAY_CATEGORY_METABOLIC

    def test_pathway_category_disease(self, tmp_path):
        from metakg.parsers.kgml import KGMLParser

        # Swap the pathway ID to a disease pathway (hsa05010)
        kgml_disease = KGML_SAMPLE.replace('name="path:hsa00010"', 'name="path:hsa05010"')
        f = tmp_path / "hsa05010.xml"
        f.write_text(kgml_disease)
        nodes, _ = KGMLParser().parse(f)
        pwy = next(n for n in nodes if n.kind == KIND_PATHWAY)
        assert pwy.category == _kegg_pathway_category("hsa05010")


class TestSBMLParser:
    def test_parse_returns_nodes_and_edges(self, tmp_path):
        from metakg.parsers.sbml import SBMLParser

        f = tmp_path / "glycolysis.xml"
        f.write_text(SBML_SAMPLE)
        nodes, edges = SBMLParser().parse(f)
        assert len(nodes) > 0
        assert len(edges) > 0

    def test_compound_nodes_from_species(self, tmp_path):
        from metakg.parsers.sbml import SBMLParser

        f = tmp_path / "glycolysis.xml"
        f.write_text(SBML_SAMPLE)
        nodes, _ = SBMLParser().parse(f)
        compounds = [n for n in nodes if n.kind == KIND_COMPOUND]
        assert len(compounds) >= 2

    def test_reaction_node_present(self, tmp_path):
        from metakg.parsers.sbml import SBMLParser

        f = tmp_path / "glycolysis.xml"
        f.write_text(SBML_SAMPLE)
        nodes, _ = SBMLParser().parse(f)
        reactions = [n for n in nodes if n.kind == KIND_REACTION]
        assert len(reactions) == 1

    def test_stoichiometry_in_edges(self, tmp_path):
        from metakg.parsers.sbml import SBMLParser

        f = tmp_path / "glycolysis.xml"
        f.write_text(SBML_SAMPLE)
        _, edges = SBMLParser().parse(f)
        prod_edges = [e for e in edges if e.rel == "PRODUCT_OF"]
        assert len(prod_edges) == 1
        ev = prod_edges[0].evidence_dict()
        assert ev.get("stoich") == 2.0

    def test_cannot_handle_non_sbml_xml(self, tmp_path):
        from metakg.parsers.sbml import SBMLParser

        f = tmp_path / "test.xml"
        f.write_text(KGML_SAMPLE)  # KGML, not SBML
        assert not SBMLParser().can_handle(f)

    def test_source_format_is_sbml(self, tmp_path):
        from metakg.parsers.sbml import SBMLParser

        f = tmp_path / "test.xml"
        f.write_text(SBML_SAMPLE)
        nodes, _ = SBMLParser().parse(f)
        assert all(n.source_format == "sbml" for n in nodes)


class TestCSVParser:
    def test_parse_returns_nodes_and_edges(self, tmp_path):
        from metakg.parsers.csv_tsv import CSVParser

        f = tmp_path / "reactions.csv"
        f.write_text(CSV_SAMPLE)
        nodes, edges = CSVParser().parse(f)
        assert len(nodes) > 0
        assert len(edges) > 0

    def test_compound_nodes_created(self, tmp_path):
        from metakg.parsers.csv_tsv import CSVParser

        f = tmp_path / "reactions.csv"
        f.write_text(CSV_SAMPLE)
        nodes, _ = CSVParser().parse(f)
        compounds = [n for n in nodes if n.kind == KIND_COMPOUND]
        # D-Glucose, Glucose-6-phosphate, Fructose-6-phosphate
        assert len(compounds) >= 3

    def test_enzyme_nodes_with_ec(self, tmp_path):
        from metakg.parsers.csv_tsv import CSVParser

        f = tmp_path / "reactions.csv"
        f.write_text(CSV_SAMPLE)
        nodes, _ = CSVParser().parse(f)
        enzymes = [n for n in nodes if n.kind == KIND_ENZYME]
        assert len(enzymes) >= 2
        ec_numbers = {e.ec_number for e in enzymes if e.ec_number}
        assert "2.7.1.1" in ec_numbers

    def test_pathway_node_created(self, tmp_path):
        from metakg.parsers.csv_tsv import CSVParser

        f = tmp_path / "reactions.csv"
        f.write_text(CSV_SAMPLE)
        nodes, _ = CSVParser().parse(f)
        pathways = [n for n in nodes if n.kind == KIND_PATHWAY]
        assert len(pathways) == 1
        assert pathways[0].name == "Glycolysis"

    def test_catalyzes_edges_present(self, tmp_path):
        from metakg.parsers.csv_tsv import CSVParser

        f = tmp_path / "reactions.csv"
        f.write_text(CSV_SAMPLE)
        _, edges = CSVParser().parse(f)
        rels = {e.rel for e in edges}
        assert "CATALYZES" in rels

    def test_missing_required_column_raises(self, tmp_path):
        from metakg.parsers.csv_tsv import CSVParser

        f = tmp_path / "bad.csv"
        f.write_text("reaction_id,enzyme\nR001,HK\n")
        with pytest.raises(ValueError, match="missing required columns"):
            CSVParser().parse(f)

    def test_stoichiometry_blob_on_reaction(self, tmp_path):
        from metakg.parsers.csv_tsv import CSVParser

        f = tmp_path / "reactions.csv"
        f.write_text(CSV_SAMPLE)
        nodes, _ = CSVParser().parse(f)
        reactions = [n for n in nodes if n.kind == KIND_REACTION]
        for rxn in reactions:
            d = rxn.stoichiometry_dict()
            assert "substrates" in d
            assert "products" in d

    def test_tsv_parsing(self, tmp_path):
        from metakg.parsers.csv_tsv import CSVParser

        tsv_content = CSV_SAMPLE.replace(",", "\t")
        f = tmp_path / "reactions.tsv"
        f.write_text(tsv_content)
        nodes, edges = CSVParser().parse(f)
        assert len(nodes) > 0


class TestMetabolicGraph:
    def test_extract_directory(self, tmp_path):
        from metakg.graph import MetabolicGraph

        # Create a CSV file in tmp directory
        f = tmp_path / "reactions.csv"
        f.write_text(CSV_SAMPLE)
        graph = MetabolicGraph(tmp_path)
        graph.extract()
        nodes, edges = graph.result()
        assert len(nodes) > 0

    def test_extract_mixed_formats(self, tmp_path):
        from metakg.graph import MetabolicGraph

        (tmp_path / "reactions.csv").write_text(CSV_SAMPLE)
        (tmp_path / "pathway.xml").write_text(KGML_SAMPLE)
        graph = MetabolicGraph(tmp_path)
        graph.extract()
        nodes, _ = graph.result()
        kinds = {n.kind for n in nodes}
        assert KIND_PATHWAY in kinds
        assert KIND_COMPOUND in kinds

    def test_caches_result(self, tmp_path):
        from metakg.graph import MetabolicGraph

        (tmp_path / "reactions.csv").write_text(CSV_SAMPLE)
        graph = MetabolicGraph(tmp_path)
        graph.extract()
        n1, _ = graph.result()
        graph.extract()  # should not re-parse
        n2, _ = graph.result()
        assert len(n1) == len(n2)

    def test_result_before_extract_raises(self, tmp_path):
        from metakg.graph import MetabolicGraph

        graph = MetabolicGraph(tmp_path)
        with pytest.raises(RuntimeError):
            graph.result()
