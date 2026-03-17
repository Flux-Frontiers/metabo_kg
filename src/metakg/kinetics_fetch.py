"""
kinetics_fetch.py — Kinetic parameter seeder for MetaKG.

Seeds the ``kinetic_parameters`` and ``regulatory_interactions`` tables with
curated literature values for the KEGG reactions present in the bundled
pathway files (glycolysis, TCA, PPP, fatty-acid degradation, and related
pathways hsa00010–hsa00650).

Sources
-------
- Mulquiney & Kuchel (1999) – Glycolysis in human erythrocytes
- Fell (1997) – Understanding the Control of Metabolism
- Beard & Qian (2008) – Chemical Biophysics
- BRENDA database (https://www.brenda-enzymes.org), Homo sapiens entries
- eQuilibrator (https://equilibrator.weizmann.ac.il) – ΔG°' values

All Km and Ki values are in **mM**, Vmax in **mM/s** (normalised to 1 mg/mL
enzyme unless otherwise noted), kcat in **1/s**, and ΔG°' in **kJ/mol** at
pH 7.0, 25 °C, ionic strength 0.1 M.

Usage::

    from metakg.store import MetaStore
    from metakg.kinetics_fetch import seed_kinetics

    with MetaStore(".metakg/meta.sqlite") as store:
        n_kp, n_ri = seed_kinetics(store)
        print(f"Seeded {n_kp} kinetic params, {n_ri} regulatory interactions.")

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28 20:55:28
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from metakg.primitives import KineticParam, RegulatoryInteraction, _kp_id, _ri_id

if TYPE_CHECKING:
    from metakg.store import MetaStore


# ---------------------------------------------------------------------------
# Curated kinetic parameters keyed by KEGG reaction ID
# ---------------------------------------------------------------------------
# Each entry: kegg_rxn_id → dict with any subset of the KineticParam fields.
# enzyme_id and reaction_id are resolved at seed time from the store.

_KEGG_KINETICS: dict[str, dict] = {
    # -----------------------------------------------------------------------
    # Glycolysis / Gluconeogenesis  (hsa00010)
    # -----------------------------------------------------------------------
    # Hexokinase  (glucose + ATP → G6P + ADP)
    "R00299": {
        "vmax": 2.8,
        "km": 0.10,
        "kcat": 100.0,
        "equilibrium_constant": 1.0e4,
        "delta_g_prime": -16.7,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "literature_reference": "PMID:10336622",
        "notes": "HK1/2; Km_glucose=0.10 mM, Km_ATP=0.50 mM",
    },
    # Glucose-6-phosphate isomerase  (G6P ↔ F6P)
    "R02740": {
        "vmax": 400.0,
        "km": 0.11,
        "kcat": 850.0,
        "equilibrium_constant": 0.30,
        "delta_g_prime": 1.7,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "literature_reference": "PMID:4950730",
        "notes": "GPI",
    },
    # 6-Phosphofructokinase  (F6P + ATP → F1,6BP + ADP)
    "R00756": {
        "vmax": 7.1,
        "km": 0.09,
        "kcat": 120.0,
        "equilibrium_constant": 1.0e3,
        "delta_g_prime": -14.2,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "literature_reference": "PMID:6296077",
        "notes": "PFKL/PFKM; allosteric; Km_F6P=0.09, Km_ATP=0.06",
    },
    # Aldolase  (F1,6BP ↔ DHAP + G3P)
    "R01068": {
        "vmax": 5.0,
        "km": 0.003,
        "kcat": 8.5,
        "equilibrium_constant": 1.0e-4,
        "delta_g_prime": 23.8,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "ALDOA/B/C",
    },
    # Triosephosphate isomerase  (DHAP ↔ G3P)
    "R01015": {
        "vmax": 420.0,
        "km": 2.5,
        "kcat": 4300.0,
        "equilibrium_constant": 0.045,
        "delta_g_prime": 7.5,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "TPI; near-diffusion-limited",
    },
    # GAPDH  (G3P + NAD⁺ + Pᵢ ↔ 1,3BPG + NADH)
    "R01061": {
        "vmax": 80.0,
        "km": 0.05,
        "kcat": 100.0,
        "equilibrium_constant": 0.066,
        "delta_g_prime": 6.3,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "notes": "GAPDH",
    },
    # Phosphoglycerate kinase  (1,3BPG + ADP ↔ 3PG + ATP)
    "R01512": {
        "vmax": 700.0,
        "km": 0.04,
        "kcat": 420.0,
        "equilibrium_constant": 3200.0,
        "delta_g_prime": -18.8,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "PGK1",
    },
    # Phosphoglycerate mutase  (3PG ↔ 2PG)
    "R01518": {
        "vmax": 150.0,
        "km": 0.16,
        "kcat": 700.0,
        "equilibrium_constant": 0.17,
        "delta_g_prime": 4.4,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "PGAM1",
    },
    # Enolase  (2PG ↔ PEP + H₂O)
    "R00430": {
        "vmax": 35.0,
        "km": 0.11,
        "kcat": 350.0,
        "equilibrium_constant": 6.7,
        "delta_g_prime": -3.2,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "ENO1/2/3",
    },
    # Pyruvate kinase  (PEP + ADP → Pyr + ATP)
    "R00196": {
        "vmax": 150.0,
        "km": 0.05,
        "kcat": 350.0,
        "equilibrium_constant": 1.0e5,
        "delta_g_prime": -31.4,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "literature_reference": "PMID:4946357",
        "notes": "PKM1/PKM2; allosteric activation by F1,6BP",
    },
    # Lactate dehydrogenase  (Pyr + NADH → Lactate + NAD⁺)
    "R00703": {
        "vmax": 200.0,
        "km": 0.16,
        "kcat": 250.0,
        "equilibrium_constant": 2.74e4,
        "delta_g_prime": -25.1,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "LDHA/LDHB",
    },
    # -----------------------------------------------------------------------
    # Pyruvate metabolism  (hsa00620) — bridge reactions
    # -----------------------------------------------------------------------
    # Pyruvate dehydrogenase complex  (Pyr + CoA + NAD⁺ → AcCoA + CO₂ + NADH)
    "R00351": {
        "vmax": 1.0,
        "km": 0.04,
        "kcat": 25.0,
        "equilibrium_constant": 1.0e8,
        "delta_g_prime": -33.4,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "notes": "PDH complex; irreversible in vivo",
    },
    # -----------------------------------------------------------------------
    # TCA cycle  (hsa00020)
    # -----------------------------------------------------------------------
    # Citrate synthase  (OAA + AcCoA → Citrate + CoA)
    "R00352": {
        "vmax": 0.5,
        "km": 0.015,
        "kcat": 30.0,
        "equilibrium_constant": 1.0e5,
        "delta_g_prime": -31.4,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "CS; Km_OAA=0.015, Km_AcCoA=0.005",
    },
    # Aconitase  (Citrate ↔ Isocitrate)
    "R01324": {
        "vmax": 0.36,
        "km": 0.5,
        "kcat": 22.0,
        "equilibrium_constant": 0.066,
        "delta_g_prime": 6.3,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "ACO2",
    },
    # Isocitrate dehydrogenase  (Isocitrate + NAD⁺ → α-KG + CO₂ + NADH)
    "R00709": {
        "vmax": 0.5,
        "km": 0.013,
        "kcat": 40.0,
        "equilibrium_constant": 1.0e8,
        "delta_g_prime": -20.9,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "IDH2/IDH3",
    },
    # α-Ketoglutarate dehydrogenase  (α-KG → Succinyl-CoA + CO₂)
    "R00621": {
        "vmax": 0.2,
        "km": 0.07,
        "kcat": 10.0,
        "equilibrium_constant": 1.0e8,
        "delta_g_prime": -33.4,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "OGDH complex; irreversible",
    },
    # Succinyl-CoA synthetase  (Succinyl-CoA + ADP + Pᵢ ↔ Succinate + ATP + CoA)
    "R00432": {
        "vmax": 0.3,
        "km": 0.25,
        "kcat": 60.0,
        "equilibrium_constant": 3.8,
        "delta_g_prime": -2.9,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "SUCLA2",
    },
    # Succinate dehydrogenase  (Succinate → Fumarate)
    "R02164": {
        "vmax": 0.15,
        "km": 0.5,
        "kcat": 17.0,
        "equilibrium_constant": 1.0,
        "delta_g_prime": 0.0,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "Complex II; SDHA",
    },
    # Fumarase  (Fumarate ↔ Malate)
    "R01082": {
        "vmax": 0.85,
        "km": 0.09,
        "kcat": 800.0,
        "equilibrium_constant": 4.4,
        "delta_g_prime": -3.8,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "FH",
    },
    # Malate dehydrogenase  (Malate ↔ OAA)
    "R00342": {
        "vmax": 0.8,
        "km": 0.25,
        "kcat": 200.0,
        "equilibrium_constant": 2.86e-5,
        "delta_g_prime": 29.7,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "MDH2",
    },
    # -----------------------------------------------------------------------
    # Pentose phosphate pathway  (hsa00030)
    # -----------------------------------------------------------------------
    # G6P dehydrogenase  (G6P + NADP⁺ → 6PGL + NADPH)
    "R00835": {
        "vmax": 1.8,
        "km": 0.067,
        "kcat": 50.0,
        "equilibrium_constant": 1.0e3,
        "delta_g_prime": -17.6,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "G6PD; committed step PPP",
    },
    # Transketolase  (X5P + R5P → G3P + S7P)
    "R01641": {
        "vmax": 5.0,
        "km": 0.8,
        "kcat": 20.0,
        "equilibrium_constant": 1.0,
        "delta_g_prime": 0.0,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "TKT",
    },
    # -----------------------------------------------------------------------
    # Oxidative phosphorylation  (hsa00190) — complex kinetics (simplified)
    # -----------------------------------------------------------------------
    # Complex I  (NADH → NAD⁺ + 2H⁺, pumps 4H⁺)
    "R02163": {
        "vmax": 0.5,
        "km": 0.01,
        "kcat": 200.0,
        "equilibrium_constant": 1.0e6,
        "delta_g_prime": -69.3,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "notes": "Complex I (NADH dehydrogenase); simplified MM",
    },
    # Complex IV  (4 cytc²⁺ + O₂ → 4 cytc³⁺ + 2H₂O)
    "R00081": {
        "vmax": 0.3,
        "km": 0.002,
        "kcat": 300.0,
        "equilibrium_constant": 1.0e15,
        "delta_g_prime": -122.0,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "Complex IV (COX); Km_O2=0.002",
    },
    # ATP synthase  (ADP + Pᵢ → ATP)
    "R00086": {
        "vmax": 2.0,
        "km": 0.5,
        "kcat": 100.0,
        "equilibrium_constant": 1.0e-4,
        "delta_g_prime": 36.0,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "literature",
        "notes": "Complex V (ATP synthase)",
    },
    # -----------------------------------------------------------------------
    # Fatty acid degradation  (hsa00071)
    # -----------------------------------------------------------------------
    # Acyl-CoA dehydrogenase  (Acyl-CoA → 2-Enoyl-CoA)
    "R01278": {
        "vmax": 0.6,
        "km": 0.02,
        "kcat": 15.0,
        "equilibrium_constant": 10.0,
        "delta_g_prime": -5.7,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "ACADS/ACADM/ACADL",
    },
    # Enoyl-CoA hydratase  (2-Enoyl-CoA → 3-Hydroxyacyl-CoA)
    "R01279": {
        "vmax": 1.0,
        "km": 0.1,
        "kcat": 600.0,
        "equilibrium_constant": 3.8,
        "delta_g_prime": -3.4,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "ECHS1",
    },
    # 3-Hydroxyacyl-CoA dehydrogenase  (→ 3-Ketoacyl-CoA)
    "R01280": {
        "vmax": 0.8,
        "km": 0.05,
        "kcat": 120.0,
        "equilibrium_constant": 8.7e-3,
        "delta_g_prime": 27.8,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "HADH",
    },
    # Thiolase  (3-Ketoacyl-CoA → Acyl-CoA(n-2) + AcCoA)
    "R00238": {
        "vmax": 0.5,
        "km": 0.04,
        "kcat": 35.0,
        "equilibrium_constant": 4.0e4,
        "delta_g_prime": -27.6,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "ACAT1/HADHB",
    },
    # -----------------------------------------------------------------------
    # Glutathione metabolism  (hsa00480)
    # -----------------------------------------------------------------------
    # Glutathione reductase  (GSSG + NADPH → 2 GSH + NADP⁺)
    "R00115": {
        "vmax": 0.12,
        "km": 0.065,
        "kcat": 60.0,
        "equilibrium_constant": 1.0e5,
        "delta_g_prime": -28.5,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "GSR",
    },
    # Glutathione peroxidase  (2 GSH + H₂O₂ → GSSG + 2 H₂O)
    "R00116": {
        "vmax": 0.5,
        "km": 0.001,
        "kcat": 500.0,
        "equilibrium_constant": 1.0e8,
        "delta_g_prime": -134.0,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "GPX1/4; Km_H2O2=0.001",
    },
    # -----------------------------------------------------------------------
    # Purine metabolism  (hsa00230) — selected
    # -----------------------------------------------------------------------
    # Adenylate kinase  (2 ADP ↔ ATP + AMP)
    "R00127": {
        "vmax": 800.0,
        "km": 0.9,
        "kcat": 3500.0,
        "equilibrium_constant": 0.44,
        "delta_g_prime": 2.0,
        "ph": 7.0,
        "temperature_celsius": 37.0,
        "source_database": "brenda",
        "notes": "AK1; extremely fast enzyme",
    },
}


# ---------------------------------------------------------------------------
# Curated regulatory interactions keyed by KEGG reaction ID
# ---------------------------------------------------------------------------

_KEGG_REGULATORY: dict[str, list[dict]] = {
    # PFK: inhibited by ATP, citrate; activated by AMP and ADP
    "R00756": [
        {
            "compound_kegg": "C00002",  # ATP
            "interaction_type": "allosteric_inhibitor",
            "ki_allosteric": 1.0,
            "site": "regulatory",
        },
        {
            "compound_kegg": "C00158",  # Citrate
            "interaction_type": "allosteric_inhibitor",
            "ki_allosteric": 0.8,
            "site": "regulatory",
        },
        {
            "compound_kegg": "C00020",  # AMP
            "interaction_type": "allosteric_activator",
            "ki_allosteric": 0.05,
            "site": "regulatory",
        },
        {
            "compound_kegg": "C00008",  # ADP
            "interaction_type": "allosteric_activator",
            "ki_allosteric": 0.1,
            "site": "regulatory",
        },
    ],
    # Pyruvate kinase: activated by F1,6BP; inhibited by ATP and alanine
    "R00196": [
        {
            "compound_kegg": "C00354",  # F1,6BP
            "interaction_type": "allosteric_activator",
            "ki_allosteric": 0.03,
            "site": "regulatory",
        },
        {
            "compound_kegg": "C00002",  # ATP
            "interaction_type": "allosteric_inhibitor",
            "ki_allosteric": 10.0,
            "site": "regulatory",
        },
    ],
    # Hexokinase: product-inhibited by G6P
    "R00299": [
        {
            "compound_kegg": "C00668",  # G6P
            "interaction_type": "feedback_inhibitor",
            "ki_allosteric": 0.3,
            "site": "active",
        },
    ],
    # Citrate synthase: inhibited by NADH, succinyl-CoA, ATP
    "R00352": [
        {
            "compound_kegg": "C00004",  # NADH
            "interaction_type": "allosteric_inhibitor",
            "ki_allosteric": 0.05,
            "site": "regulatory",
        },
        {
            "compound_kegg": "C00002",  # ATP
            "interaction_type": "allosteric_inhibitor",
            "ki_allosteric": 0.9,
            "site": "regulatory",
        },
    ],
    # Isocitrate dehydrogenase: activated by ADP; inhibited by NADH, ATP
    "R00709": [
        {
            "compound_kegg": "C00008",  # ADP
            "interaction_type": "allosteric_activator",
            "ki_allosteric": 0.1,
            "site": "regulatory",
        },
        {
            "compound_kegg": "C00004",  # NADH
            "interaction_type": "allosteric_inhibitor",
            "ki_allosteric": 0.02,
            "site": "regulatory",
        },
        {
            "compound_kegg": "C00002",  # ATP
            "interaction_type": "allosteric_inhibitor",
            "ki_allosteric": 0.5,
            "site": "regulatory",
        },
    ],
    # G6P dehydrogenase: inhibited by NADPH (product inhibition)
    "R00835": [
        {
            "compound_kegg": "C00005",  # NADPH
            "interaction_type": "feedback_inhibitor",
            "ki_allosteric": 0.15,
            "site": "active",
        },
    ],
}


# ---------------------------------------------------------------------------
# Public seeder function
# ---------------------------------------------------------------------------


def seed_kinetics(store: MetaStore, *, force: bool = False) -> tuple[int, int]:
    """
    Populate ``kinetic_parameters`` and ``regulatory_interactions`` from the
    curated literature tables above.

    Only seeds reactions that exist in the store.  Skips existing rows unless
    *force* is ``True``.

    :param store: Open :class:`~metakg.store.MetaStore` instance.
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

    for kegg_rxn_id, kdata in _KEGG_KINETICS.items():
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
                organism="Homo sapiens",
                tissue=None,
                confidence_score=0.8,
                measurement_error=None,
            )
            kp_list.append(kp)

    # -----------------------------------------------------------------------
    # Regulatory interactions
    # -----------------------------------------------------------------------
    for kegg_rxn_id, reg_list in _KEGG_REGULATORY.items():
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
                    organism="Homo sapiens",
                    source_database="literature",
                )
                ri_list.append(ri)

    n_kp = store.upsert_kinetic_params(kp_list) if kp_list else 0
    n_ri = store.upsert_regulatory_interactions(ri_list) if ri_list else 0
    return n_kp, n_ri
