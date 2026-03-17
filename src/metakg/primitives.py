"""
primitives.py — Core data types for the MetaKG metabolic knowledge graph.

Defines MetaNode, MetaEdge dataclasses, stable node_id() constructor,
and the kind/relation constants used throughout the metakg subpackage.

    Author: Eric G. Suchanek, PhD

    Last Revision: 2026-02-28 20:44:14
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Node kind constants
# ---------------------------------------------------------------------------

KIND_COMPOUND = "compound"
KIND_REACTION = "reaction"
KIND_ENZYME = "enzyme"
KIND_PATHWAY = "pathway"

ALL_KINDS = (KIND_COMPOUND, KIND_REACTION, KIND_ENZYME, KIND_PATHWAY)

# ---------------------------------------------------------------------------
# Pathway category constants  (based on KEGG BRITE hierarchy)
# ---------------------------------------------------------------------------

PATHWAY_CATEGORY_METABOLIC = "metabolic"
PATHWAY_CATEGORY_TRANSPORT = "transport"
PATHWAY_CATEGORY_GIP = "genetic_info_processing"
PATHWAY_CATEGORY_SIGNALING = "signaling"
PATHWAY_CATEGORY_CELLULAR = "cellular_process"
PATHWAY_CATEGORY_ORGANISMAL = "organismal_system"
PATHWAY_CATEGORY_DISEASE = "human_disease"
PATHWAY_CATEGORY_DRUG = "drug_development"

ALL_PATHWAY_CATEGORIES: tuple[str, ...] = (
    PATHWAY_CATEGORY_METABOLIC,
    PATHWAY_CATEGORY_TRANSPORT,
    PATHWAY_CATEGORY_GIP,
    PATHWAY_CATEGORY_SIGNALING,
    PATHWAY_CATEGORY_CELLULAR,
    PATHWAY_CATEGORY_ORGANISMAL,
    PATHWAY_CATEGORY_DISEASE,
    PATHWAY_CATEGORY_DRUG,
)


def _kegg_pathway_category(pathway_id: str) -> str | None:
    """
    Map a KEGG pathway ID to its biological category.

    Uses the 5-digit numeric suffix of the pathway identifier to determine
    which BRITE tier the pathway belongs to.

    :param pathway_id: Identifier such as ``hsa00010`` or ``hsa04110``.
    :return: One of the ``PATHWAY_CATEGORY_*`` constants, or ``None`` if
        the ID cannot be parsed.
    """
    m = re.search(r"(\d{5})$", pathway_id)
    if not m:
        return None
    num = int(m.group(1))
    if num < 2000:
        return PATHWAY_CATEGORY_METABOLIC
    if num < 3000:
        return PATHWAY_CATEGORY_TRANSPORT
    if num < 4000:
        return PATHWAY_CATEGORY_GIP
    if num < 4100:
        return PATHWAY_CATEGORY_SIGNALING
    if num < 4500:
        return PATHWAY_CATEGORY_CELLULAR
    if num < 5000:
        return PATHWAY_CATEGORY_ORGANISMAL
    if num < 6000:
        return PATHWAY_CATEGORY_DISEASE
    if num < 8000:
        return PATHWAY_CATEGORY_DRUG
    return None


# ---------------------------------------------------------------------------
# Edge relation constants
# ---------------------------------------------------------------------------

REL_SUBSTRATE_OF = "SUBSTRATE_OF"  # compound → reaction
REL_PRODUCT_OF = "PRODUCT_OF"  # reaction → compound
REL_CATALYZES = "CATALYZES"  # enzyme → reaction
REL_INHIBITS = "INHIBITS"  # compound → reaction
REL_ACTIVATES = "ACTIVATES"  # compound → reaction
REL_CONTAINS = "CONTAINS"  # pathway → reaction|compound
REL_XREF = "XREF"  # any → any (cross-database identity)

DEFAULT_RELS: tuple[str, ...] = (
    REL_SUBSTRATE_OF,
    REL_PRODUCT_OF,
    REL_CATALYZES,
    REL_CONTAINS,
)

# ---------------------------------------------------------------------------
# Node ID construction
# ---------------------------------------------------------------------------

# Namespace prefixes for stable IDs
_NS = {
    KIND_COMPOUND: "cpd",
    KIND_REACTION: "rxn",
    KIND_ENZYME: "enz",
    KIND_PATHWAY: "pwy",
}


def node_id(kind: str, db: str, ext_id: str) -> str:
    """
    Build a stable, URI-style node identifier.

    Examples::

        node_id("compound", "kegg", "C00022")    → "cpd:kegg:C00022"
        node_id("reaction", "kegg", "R00200")    → "rxn:kegg:R00200"
        node_id("enzyme",   "ec",   "1.1.1.1")  → "enz:ec:1.1.1.1"
        node_id("pathway",  "kegg", "hsa00010")  → "pwy:kegg:hsa00010"

    :param kind: One of ``compound``, ``reaction``, ``enzyme``, ``pathway``.
    :param db: Source database namespace, e.g. ``kegg``, ``chebi``, ``uniprot``.
    :param ext_id: External identifier within that database.
    :return: Stable string identifier.
    """
    prefix = _NS.get(kind, kind)
    return f"{prefix}:{db}:{ext_id}"


def synthetic_id(kind: str, name: str) -> str:
    """
    Build a stable synthetic node ID for entities without a database identifier.

    Uses a short hash of the lowercased name so IDs are deterministic across
    parser runs on identical input.

    :param kind: Node kind.
    :param name: Display name of the entity.
    :return: Stable string identifier of the form ``<prefix>:syn:<hash8>``.
    """
    prefix = _NS.get(kind, kind)
    h = hashlib.sha1(name.lower().encode()).hexdigest()[:8]
    return f"{prefix}:syn:{h}"


# ---------------------------------------------------------------------------
# MetaNode
# ---------------------------------------------------------------------------


@dataclass
class MetaNode:
    """
    A node in the metabolic knowledge graph.

    :param id: Stable URI-style identifier (e.g. ``cpd:kegg:C00022``).
    :param kind: Node kind: ``compound``, ``reaction``, ``enzyme``, or ``pathway``.
    :param name: Primary display name.
    :param description: Free-text description used for embedding and semantic search.
    :param formula: Molecular formula (compounds only, e.g. ``C3H4O3``).
    :param charge: Net formal charge (compounds only).
    :param ec_number: EC classification number (enzymes only, e.g. ``1.1.1.1``).
    :param stoichiometry: JSON-serialised stoichiometry dict (reactions only).
        Format: ``{"substrates": [{"id": "...", "stoich": 1.0}], "products": [...]}``
    :param xrefs: JSON-serialised cross-reference dict (e.g. ``{"kegg": "C00022", "chebi": "CHEBI_15361"}``).
    :param source_format: Parser format that produced this node (``kgml``, ``biopax``, ``sbml``, ``csv``).
    :param source_file: Absolute path to the originating file.
    :param category: Biological category for pathway nodes (one of the
        ``PATHWAY_CATEGORY_*`` constants, e.g. ``metabolic``). ``None`` for
        non-pathway nodes.
    """

    id: str
    kind: str
    name: str
    description: str = ""
    formula: str | None = None
    charge: int | None = None
    ec_number: str | None = None
    stoichiometry: str | None = None  # JSON blob
    xrefs: str | None = None  # JSON blob
    source_format: str = ""
    source_file: str | None = None
    category: str | None = None

    def xrefs_dict(self) -> dict[str, str]:
        """
        Deserialise the ``xrefs`` JSON blob to a plain dict.

        :return: Dict mapping database name to external ID, or ``{}`` if not set.
        """
        if not self.xrefs:
            return {}
        try:
            return json.loads(self.xrefs)
        except (json.JSONDecodeError, TypeError):
            return {}

    def stoichiometry_dict(self) -> dict:
        """
        Deserialise the ``stoichiometry`` JSON blob.

        :return: Stoichiometry dict with ``substrates`` and ``products`` lists,
                 or ``{}`` if not set.
        """
        if not self.stoichiometry:
            return {}
        try:
            return json.loads(self.stoichiometry)
        except (json.JSONDecodeError, TypeError):
            return {}


# ---------------------------------------------------------------------------
# MetaEdge
# ---------------------------------------------------------------------------


@dataclass
class MetaEdge:
    """
    A directed edge in the metabolic knowledge graph.

    :param src: Source node ID.
    :param rel: Relation type (e.g. ``SUBSTRATE_OF``, ``CATALYZES``).
    :param dst: Destination node ID.
    :param evidence: Optional JSON-serialised evidence dict
        (e.g. ``{"stoich": 2.0, "compartment": "cytosol"}``).
    """

    src: str
    rel: str
    dst: str
    evidence: str | None = None

    def evidence_dict(self) -> dict:
        """
        Deserialise the ``evidence`` JSON blob.

        :return: Evidence dict, or ``{}`` if not set.
        """
        if not self.evidence:
            return {}
        try:
            return json.loads(self.evidence)
        except (json.JSONDecodeError, TypeError):
            return {}


# ---------------------------------------------------------------------------
# KineticParam
# ---------------------------------------------------------------------------


def _kp_id(
    enzyme_id: str,
    reaction_id: str | None,
    substrate_id: str | None,
    source: str | None,
) -> str:
    """Build a deterministic ID for a KineticParam row."""
    key = f"{enzyme_id}|{reaction_id or ''}|{substrate_id or ''}|{source or ''}"
    return "kp_" + hashlib.sha1(key.encode()).hexdigest()[:12]


@dataclass
class KineticParam:
    """
    Kinetic and thermodynamic parameters for an enzyme-catalysed reaction.

    :param id: Deterministic hash ID (use :func:`_kp_id` to construct).
    :param enzyme_id: Node ID of the catalysing enzyme (FK → meta_nodes).
    :param reaction_id: Node ID of the reaction (FK → meta_nodes).
    :param substrate_id: Node ID of the specific substrate this Km applies to.
    :param km: Michaelis constant (mM).
    :param kcat: Catalytic rate constant (1/s).
    :param vmax: Maximum velocity (mM/s, normalised to 1 mg/mL enzyme).
    :param ki: Inhibition constant for a competitive inhibitor (mM).
    :param hill_coefficient: Hill coefficient *n* for cooperative kinetics.
    :param delta_g_prime: Standard transformed Gibbs free energy ΔG°' (kJ/mol).
    :param equilibrium_constant: Thermodynamic equilibrium constant *Keq*.
    :param ph: pH at which parameters were measured.
    :param temperature_celsius: Temperature (°C) at measurement.
    :param ionic_strength: Ionic strength (M) at measurement.
    :param source_database: Provenance tag (``"brenda"``, ``"sabio"``, ``"literature"``, ``"default"``).
    :param literature_reference: PubMed ID or DOI string.
    :param organism: Organism taxon (e.g. ``"Homo sapiens"``).
    :param tissue: Tissue or cell-type context.
    :param confidence_score: Numeric confidence 0–1.
    :param measurement_error: Reported measurement uncertainty (same units as parameter).
    """

    id: str
    enzyme_id: str | None
    reaction_id: str | None = None
    substrate_id: str | None = None

    # Enzyme kinetics
    km: float | None = None
    kcat: float | None = None
    vmax: float | None = None
    ki: float | None = None
    hill_coefficient: float | None = None

    # Thermodynamics
    delta_g_prime: float | None = None
    equilibrium_constant: float | None = None

    # Measurement conditions
    ph: float | None = None
    temperature_celsius: float | None = None
    ionic_strength: float | None = None

    # Provenance
    source_database: str | None = None
    literature_reference: str | None = None
    organism: str | None = None
    tissue: str | None = None
    confidence_score: float | None = None
    measurement_error: float | None = None

    def as_dict(self) -> dict:
        """Return all fields as a plain dict."""
        from dataclasses import asdict

        return asdict(self)


# ---------------------------------------------------------------------------
# RegulatoryInteraction
# ---------------------------------------------------------------------------


def _ri_id(enzyme_id: str, compound_id: str, interaction_type: str) -> str:
    """Build a deterministic ID for a RegulatoryInteraction row."""
    key = f"{enzyme_id}|{compound_id}|{interaction_type}"
    return "ri_" + hashlib.sha1(key.encode()).hexdigest()[:12]


@dataclass
class RegulatoryInteraction:
    """
    Allosteric or covalent regulatory relationship between a compound and an enzyme.

    :param id: Deterministic hash ID (use :func:`_ri_id` to construct).
    :param enzyme_id: Regulated enzyme node ID (FK → meta_nodes).
    :param compound_id: Effector compound node ID (FK → meta_nodes).
    :param interaction_type: One of ``"allosteric_inhibitor"``, ``"allosteric_activator"``,
        ``"feedback_inhibitor"``, ``"competitive_inhibitor"``.
    :param ki_allosteric: Half-saturation concentration of effector (mM).
    :param hill_coefficient: Hill coefficient for cooperative effector binding.
    :param site: Binding site tag (``"active"`` or ``"regulatory"``).
    :param organism: Organism taxon.
    :param source_database: Provenance tag.
    """

    id: str
    enzyme_id: str
    compound_id: str
    interaction_type: str

    ki_allosteric: float | None = None
    hill_coefficient: float | None = None
    site: str | None = None
    organism: str | None = None
    source_database: str | None = None

    def as_dict(self) -> dict:
        """Return all fields as a plain dict."""
        from dataclasses import asdict

        return asdict(self)
