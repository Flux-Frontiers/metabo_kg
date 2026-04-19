"""
cho_kinetics.py — CHO-specific kinetic parameter seeder for MetaKG.

CHO-specific extension to ``kinetics_fetch.py``.  Seeds the
``kinetic_parameters`` and ``regulatory_interactions`` tables with curated
values relevant to Chinese Hamster Ovary (CHO) cell culture metabolism.
Parameters are drawn from published flux-balance and enzyme-kinetic studies of
CHO K1 and CHO DG44 cells.

Sources
-------
- Ahn & Antoniewicz (2011) – 13C MFA of CHO cells, PMID:21786370
- Zagari et al. (2013) – Lactate metabolism in CHO, PMID:23744439
- Templeton et al. (2013) – Metabolomics of CHO fed-batch, PMID:24297498
- BRENDA database (https://www.brenda-enzymes.org), *Cricetulus griseus* entries
  where available; otherwise CHO culture literature values.

Units
-----
- Km, Ki  : mM
- Vmax    : mM/s  (normalised to 1 mg/mL enzyme unless otherwise noted)
- kcat    : 1/s
- ΔG°'    : kJ/mol at pH 7.2, 37 °C, ionic strength 0.1 M

Usage::

    from metabokg.store import MetaStore
    from metabokg.cho_kinetics import seed_cho_kinetics

    with MetaStore(".metabokg/meta.sqlite") as store:
        n_kp, n_ri = seed_cho_kinetics(store)
        print(f"Seeded {n_kp} CHO kinetic params, {n_ri} regulatory interactions.")

Author: Eric G. Suchanek, PhD
Last Revision: 2026-04-19
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from metabokg.primitives import KineticParam, RegulatoryInteraction, _kp_id, _ri_id

if TYPE_CHECKING:
    from metabokg.store import MetaStore


# ---------------------------------------------------------------------------
# CHO biomass composition — module-level constant for FBA objective builders
# ---------------------------------------------------------------------------
# Informational metadata only; not directly inserted into the database via
# KineticParam.  A future FBA objective builder can import this dict to
# construct the CHO biomass drain reaction.

CHO_BIOMASS: dict = {
    "description": (
        "CHO cell biomass composition for FBA objective "
        "(Ahn & Antoniewicz 2011, Templeton et al. 2013)"
    ),
    "protein_fraction": 0.63,       # g protein / g DCW
    "lipid_fraction": 0.12,         # g lipid / g DCW
    "rna_fraction": 0.06,           # g RNA / g DCW
    "dna_fraction": 0.02,           # g DNA / g DCW
    "carbohydrate_fraction": 0.05,  # g carbohydrate / g DCW
    "atp_maintenance_mmol_gDCW_h": 0.40,  # non-growth ATP demand
    "glucose_uptake_mmol_1e6cells_h": (0.5, 2.0),   # typical range
    "glutamine_uptake_mmol_1e6cells_h": (0.2, 0.8),
    "lactate_production_mmol_1e6cells_h": (0.2, 0.8),
    "ammonia_production_mmol_1e6cells_h": (0.1, 0.4),
    "references": [
        "PMID:21786370",   # Ahn & Antoniewicz 2011
        "PMID:23744439",   # Zagari et al. 2013
        "PMID:24297498",   # Templeton et al. 2013
    ],
}


# ---------------------------------------------------------------------------
# Curated CHO kinetic parameters keyed by KEGG reaction ID
# ---------------------------------------------------------------------------
# Each entry: kegg_rxn_id → dict with any subset of the KineticParam fields.
# enzyme_id and reaction_id are resolved at seed time from the store.

_CHO_KINETICS: dict[str, dict] = {
    # -----------------------------------------------------------------------
    # Glycolysis entry — Hexokinase
    # CHO Km_glucose lower than human (more efficient at low glucose)
    # -----------------------------------------------------------------------
    "R00299": {
        "vmax": 2.2,
        "km": 0.046,
        "kcat": 90.0,
        "equilibrium_constant": 1.0e4,
        "delta_g_prime": -16.7,
        "ph": 7.2,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "literature_reference": "PMID:21786370",
        "notes": "HK; CHO Km_glucose=0.046 mM (Ahn & Antoniewicz 2011)",
    },
    # -----------------------------------------------------------------------
    # Lactate dehydrogenase — CHO overflow metabolism
    # CHO produces excess lactate (overflow); higher Vmax than human
    # -----------------------------------------------------------------------
    "R00703": {
        "vmax": 350.0,
        "km": 0.13,
        "kcat": 430.0,
        "equilibrium_constant": 2.74e4,
        "delta_g_prime": -25.1,
        "ph": 7.2,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "literature_reference": "PMID:23744439",
        "notes": "LDHA; CHO overflow lactate; Vmax 75% higher than human erythrocyte",
    },
    # -----------------------------------------------------------------------
    # Glutaminase — Glutamine → Glutamate + NH3 (key CHO N-source)
    # -----------------------------------------------------------------------
    "R00256": {
        "vmax": 1.2,
        "km": 1.5,
        "kcat": 35.0,
        "equilibrium_constant": 1.0e4,
        "delta_g_prime": -14.2,
        "ph": 7.2,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "literature_reference": "PMID:23744439",
        "notes": "GLS1; glutaminolysis entry; Km_Gln=1.5 mM in CHO",
    },
    # -----------------------------------------------------------------------
    # Glutamate dehydrogenase — Glutamate → α-KG (feeds TCA)
    # -----------------------------------------------------------------------
    "R00243": {
        "vmax": 0.8,
        "km": 3.5,
        "kcat": 25.0,
        "equilibrium_constant": 1.0e-3,
        "delta_g_prime": 30.5,
        "ph": 7.2,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "literature_reference": "PMID:15634345",
        "notes": "GLUD1; Km_Glu=3.5 mM CHO culture",
    },
    # -----------------------------------------------------------------------
    # Glutamine synthetase — Glu + NH3 + ATP → Gln
    # GS selection marker in CHO expression systems
    # -----------------------------------------------------------------------
    "R00254": {
        "vmax": 0.35,
        "km": 0.35,
        "kcat": 18.0,
        "equilibrium_constant": 1.2e3,
        "delta_g_prime": -14.8,
        "ph": 7.2,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "literature_reference": "PMID:2153473",
        "notes": "GLUL/GS; CHO GS selection marker; Km_Glu=0.35 mM",
    },
    # -----------------------------------------------------------------------
    # Asparagine synthetase — Asp + Gln + ATP → Asn + Glu
    # CHO cells are asparagine auxotrophs without functional ASNS
    # -----------------------------------------------------------------------
    "R01954": {
        "vmax": 0.18,
        "km": 0.8,
        "kcat": 8.0,
        "equilibrium_constant": 1.0e3,
        "delta_g_prime": -18.2,
        "ph": 7.2,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "literature_reference": "PMID:6296077",
        "notes": "ASNS; CHO asparagine auxotroph rescue; Km_Gln=0.8 mM",
    },
    # -----------------------------------------------------------------------
    # Alanine aminotransferase — Pyr + Glu ↔ Ala + α-KG
    # Major alanine secretion route coupled to glutaminolysis in CHO
    # -----------------------------------------------------------------------
    "R00258": {
        "vmax": 1.5,
        "km": 0.9,
        "kcat": 55.0,
        "equilibrium_constant": 1.5,
        "delta_g_prime": -0.9,
        "ph": 7.2,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "literature_reference": "PMID:23744439",
        "notes": "GPT/ALT1; CHO alanine secretion coupled to glutaminolysis",
    },
    # -----------------------------------------------------------------------
    # Pyruvate carboxylase — Pyr + CO2 + ATP → OAA (TCA anaplerosis)
    # -----------------------------------------------------------------------
    "R00344": {
        "vmax": 0.4,
        "km": 0.15,
        "kcat": 20.0,
        "equilibrium_constant": 1.0e3,
        "delta_g_prime": -19.6,
        "ph": 7.2,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "literature_reference": "PMID:21786370",
        "notes": "PC; TCA anaplerosis from pyruvate; active in CHO",
    },
    # -----------------------------------------------------------------------
    # Phosphofructokinase — pH optimum shifted for CHO culture pH 7.2
    # Same reaction as human but slightly lower Vmax at pH 7.2 vs 7.0
    # -----------------------------------------------------------------------
    "R00756": {
        "vmax": 6.5,
        "km": 0.09,
        "kcat": 110.0,
        "equilibrium_constant": 1.0e3,
        "delta_g_prime": -14.2,
        "ph": 7.2,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "literature_reference": "PMID:21786370",
        "notes": "PFK; CHO pH 7.2 culture condition; slightly lower Vmax vs. pH 7.0",
    },
}


# ---------------------------------------------------------------------------
# Curated CHO regulatory interactions keyed by KEGG reaction ID
# ---------------------------------------------------------------------------

_CHO_REGULATORY: dict[str, list[dict]] = {
    # LDH: activated by low pH (acidosis drives lactate production in CHO)
    "R00703": [
        {
            "compound_kegg": "C00033",  # Acetate (proxy for acidosis signal)
            "interaction_type": "allosteric_activator",
            "ki_allosteric": 5.0,
            "site": "regulatory",
        },
    ],
    # Glutaminase: inhibited by its product glutamate (feedback inhibition)
    "R00256": [
        {
            "compound_kegg": "C00025",  # L-Glutamate
            "interaction_type": "feedback_inhibitor",
            "ki_allosteric": 25.0,
            "site": "active",
        },
    ],
    # GS: inhibited by glutamine (product feedback — regulates GS activity
    # under the CHO GS selection system)
    "R00254": [
        {
            "compound_kegg": "C00064",  # L-Glutamine
            "interaction_type": "feedback_inhibitor",
            "ki_allosteric": 4.5,
            "site": "active",
        },
    ],
}


# ---------------------------------------------------------------------------
# Public seeder function
# ---------------------------------------------------------------------------

_CHO_ORGANISM = "Cricetulus griseus (CHO)"
_CHO_CONFIDENCE = 0.7  # Slightly lower than human: some values inferred from
                        # culture data rather than purified enzyme assays


def seed_cho_kinetics(store: MetaStore, *, force: bool = False) -> tuple[int, int]:
    """
    Populate ``kinetic_parameters`` and ``regulatory_interactions`` with
    CHO-specific values from the curated literature tables above.

    Only seeds reactions that exist in the store.  Skips existing rows unless
    *force* is ``True``.

    :param store: Open :class:`~metabokg.store.MetaStore` instance.
    :param force: If ``True``, overwrite existing rows.
    :return: ``(n_kinetic_params, n_regulatory_interactions)`` counts of rows written.
    """
    kp_list: list[KineticParam] = []
    ri_list: list[RegulatoryInteraction] = []

    existing_kp_ids: set[str] = set()
    existing_ri_ids: set[str] = set()

    if not force:
        existing_kp_ids = {row["id"] for row in store.all_kinetic_params()}
        cur = store._conn.execute("SELECT id FROM regulatory_interactions")  # pylint: disable=protected-access
        existing_ri_ids = {row["id"] for row in cur.fetchall()}

    for kegg_rxn_id, kdata in _CHO_KINETICS.items():
        rxn_node = store.node(f"rxn:kegg:{kegg_rxn_id}")
        if rxn_node is None:
            continue  # Reaction not loaded — skip silently

        rxn_id = rxn_node["id"]

        # Find enzymes catalysing this reaction
        enzyme_ids: list[str | None] = []
        for edge in store.edges_of(rxn_id):
            if edge["rel"] == "CATALYZES" and edge["dst"] == rxn_id:
                enzyme_ids.append(edge["src"])

        # Always create at least one row with enzyme_id=None if no enzyme found
        if not enzyme_ids:
            enzyme_ids = [None]

        for enz_id in enzyme_ids:
            kp_id = _kp_id(
                enz_id or "none",
                rxn_id,
                None,
                kdata.get("source_database", "literature"),
            )
            if not force and kp_id in existing_kp_ids:
                continue

            kp = KineticParam(
                id=kp_id,
                enzyme_id=enz_id,
                reaction_id=rxn_id,
                substrate_id=None,
                km=kdata.get("km"),
                kcat=kdata.get("kcat"),
                vmax=kdata.get("vmax"),
                ki=kdata.get("ki"),
                hill_coefficient=kdata.get("hill_coefficient"),
                delta_g_prime=kdata.get("delta_g_prime"),
                equilibrium_constant=kdata.get("equilibrium_constant"),
                ph=kdata.get("ph"),
                temperature_celsius=kdata.get("temperature_celsius"),
                ionic_strength=kdata.get("ionic_strength"),
                source_database=kdata.get("source_database", "literature"),
                literature_reference=kdata.get("literature_reference"),
                organism=_CHO_ORGANISM,
                tissue=None,
                confidence_score=_CHO_CONFIDENCE,
                measurement_error=None,
            )
            kp_list.append(kp)

    # -----------------------------------------------------------------------
    # Regulatory interactions
    # -----------------------------------------------------------------------
    for kegg_rxn_id, reg_list in _CHO_REGULATORY.items():
        rxn_node = store.node(f"rxn:kegg:{kegg_rxn_id}")
        if rxn_node is None:
            continue

        rxn_id = rxn_node["id"]

        # Find catalysing enzymes
        reg_enzyme_ids: list[str] = [
            cast(str, e["src"])
            for e in store.edges_of(rxn_id)
            if e["rel"] == "CATALYZES" and e["dst"] == rxn_id
        ]
        if not reg_enzyme_ids:
            continue  # No enzyme to attach regulation to

        for reg in reg_list:
            cpd_node = store.node(f"cpd:kegg:{reg['compound_kegg']}")
            if cpd_node is None:
                continue
            cpd_id = cpd_node["id"]

            for enz_id in reg_enzyme_ids:
                ri_id = _ri_id(enz_id, cpd_id, reg["interaction_type"])
                if not force and ri_id in existing_ri_ids:
                    continue
                ri = RegulatoryInteraction(
                    id=ri_id,
                    enzyme_id=enz_id,
                    compound_id=cpd_id,
                    interaction_type=reg["interaction_type"],
                    ki_allosteric=reg.get("ki_allosteric"),
                    hill_coefficient=reg.get("hill_coefficient"),
                    site=reg.get("site"),
                    organism=_CHO_ORGANISM,
                    source_database="literature",
                )
                ri_list.append(ri)

    n_kp = store.upsert_kinetic_params(kp_list) if kp_list else 0
    n_ri = store.upsert_regulatory_interactions(ri_list) if ri_list else 0
    return n_kp, n_ri
