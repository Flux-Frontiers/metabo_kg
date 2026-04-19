"""
cho_kinetics.py — CHO-specific kinetic parameter seeder for MetaKG.

CHO-specific extension to ``kinetics_fetch.py``.  Seeds the
``kinetic_parameters`` and ``regulatory_interactions`` tables with curated
values relevant to Chinese Hamster Ovary (CHO) cell culture metabolism.
Parameters are drawn from published flux-balance and enzyme-kinetic studies of
CHO K1 and CHO DG44 cells.

All values are at pH 7.2, 37 °C (standard CHO bioreactor conditions), which
differs from the human values in ``kinetics_fetch.py`` (pH 7.0, 37 °C).

Sources
-------
- Ahn & Antoniewicz (2011) – ¹³C MFA of CHO cells, PMID:21786370
- Zagari et al. (2013) – Lactate metabolism in CHO, PMID:23744439
- Templeton et al. (2013) – Metabolomics of CHO fed-batch, PMID:24297498
- Mulukutla et al. (2012) – Lactate metabolism switch in CHO, PMID:22287518
- Lao & Toth (1997) – Amino acid metabolism in CHO, PMID:9171865
- Quek et al. (2010) – CHO metabolic flux, PMID:20091739
- BRENDA database (https://www.brenda-enzymes.org), *Cricetulus griseus* entries
  where available; otherwise CHO culture literature values.

Confidence scores
-----------------
- 0.85 : Direct CHO enzyme assay or ¹³C-MFA constrained value
- 0.70 : CHO culture inference / mammalian value at CHO pH/temperature
- 0.55 : Mammalian literature value adapted to CHO conditions

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
    # ===================================================================
    # GLYCOLYSIS / GLUCONEOGENESIS  (cge00010)
    # All values at pH 7.2 / 37 °C (CHO bioreactor conditions)
    # ===================================================================

    # Hexokinase — CHO Km_glucose lower than human (high glucose affinity)
    "R00299": {
        "vmax": 2.2, "km": 0.046, "kcat": 90.0,
        "equilibrium_constant": 1.0e4, "delta_g_prime": -16.7,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:21786370",
        "confidence_score": 0.85,
        "notes": "HK1/2; CHO Km_glucose=0.046 mM (Ahn & Antoniewicz 2011)",
    },
    # Glucose-6-phosphate isomerase — similar to human; pH 7.2 shift minor
    "R02740": {
        "vmax": 380.0, "km": 0.11, "kcat": 820.0,
        "equilibrium_constant": 0.30, "delta_g_prime": 1.7,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:21786370",
        "confidence_score": 0.70,
        "notes": "GPI; mammalian value adapted to CHO pH 7.2",
    },
    # Phosphofructokinase — pH optimum shifted; slightly lower Vmax at pH 7.2
    "R00756": {
        "vmax": 6.5, "km": 0.09, "kcat": 110.0,
        "equilibrium_constant": 1.0e3, "delta_g_prime": -14.2,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:21786370",
        "confidence_score": 0.85,
        "notes": "PFKL/PFKM; CHO pH 7.2; allosteric node — see regulatory table",
    },
    # Aldolase — CHO similar to mammalian; slightly lower Vmax
    "R01068": {
        "vmax": 4.5, "km": 0.003, "kcat": 7.8,
        "equilibrium_constant": 1.0e-4, "delta_g_prime": 23.8,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:21786370",
        "confidence_score": 0.70,
        "notes": "ALDOA; CHO value from mammalian BRENDA at pH 7.2",
    },
    # Triosephosphate isomerase — near-diffusion-limited; very similar across mammals
    "R01015": {
        "vmax": 410.0, "km": 2.4, "kcat": 4200.0,
        "equilibrium_constant": 0.045, "delta_g_prime": 7.5,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:21786370",
        "confidence_score": 0.70,
        "notes": "TPI1; near-diffusion-limited; conserved across mammals",
    },
    # GAPDH — slightly lower Vmax in CHO vs. human erythrocytes
    "R01061": {
        "vmax": 72.0, "km": 0.05, "kcat": 90.0,
        "equilibrium_constant": 0.066, "delta_g_prime": 6.3,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:21786370",
        "confidence_score": 0.70,
        "notes": "GAPDH; CHO at pH 7.2; slightly lower than erythrocyte assay pH 7.0",
    },
    # Phosphoglycerate kinase — highly conserved; similar to human
    "R01512": {
        "vmax": 680.0, "km": 0.04, "kcat": 410.0,
        "equilibrium_constant": 3200.0, "delta_g_prime": -18.8,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:21786370",
        "confidence_score": 0.70,
        "notes": "PGK1; conserved; mammalian value at CHO pH",
    },
    # Phosphoglycerate mutase — conserved; minor pH effect
    "R01518": {
        "vmax": 145.0, "km": 0.16, "kcat": 680.0,
        "equilibrium_constant": 0.17, "delta_g_prime": 4.4,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:21786370",
        "confidence_score": 0.70,
        "notes": "PGAM1; conserved mammalian",
    },
    # Enolase — slightly lower activity at pH 7.2
    "R00430": {
        "vmax": 32.0, "km": 0.11, "kcat": 320.0,
        "equilibrium_constant": 6.7, "delta_g_prime": -3.2,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:21786370",
        "confidence_score": 0.70,
        "notes": "ENO1/2; CHO pH 7.2",
    },
    # Pyruvate kinase — CHO predominantly PKM2 isoform (lower affinity vs PKM1)
    "R00196": {
        "vmax": 130.0, "km": 0.07, "kcat": 300.0,
        "equilibrium_constant": 1.0e5, "delta_g_prime": -31.4,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:21786370",
        "confidence_score": 0.85,
        "notes": "PKM2 dominant isoform in CHO; Km_PEP slightly higher than PKM1",
    },
    # Lactate dehydrogenase — overflow lactate phenotype; higher Vmax than human
    "R00703": {
        "vmax": 350.0, "km": 0.13, "kcat": 430.0,
        "equilibrium_constant": 2.74e4, "delta_g_prime": -25.1,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:23744439",
        "confidence_score": 0.85,
        "notes": "LDHA; CHO overflow lactate; Vmax 75% higher than human erythrocyte",
    },
    # Pyruvate dehydrogenase complex — reduced activity in CHO overflow phenotype
    "R00351": {
        "vmax": 0.6, "km": 0.04, "kcat": 15.0,
        "equilibrium_constant": 1.0e8, "delta_g_prime": -33.4,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:22287518",
        "confidence_score": 0.85,
        "notes": "PDH complex; CHO Vmax ~40% lower than human — metabolic overflow",
    },

    # ===================================================================
    # TCA CYCLE  (cge00020)
    # High flux due to glutaminolysis feeding α-KG directly
    # ===================================================================

    # Citrate synthase — elevated in CHO due to high glutamine → TCA flux
    "R00352": {
        "vmax": 0.65, "km": 0.015, "kcat": 38.0,
        "equilibrium_constant": 1.0e5, "delta_g_prime": -31.4,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:21786370",
        "confidence_score": 0.85,
        "notes": "CS; elevated in CHO (active glutaminolysis); Km_OAA=0.015 mM",
    },
    # Aconitase — similar to human
    "R01324": {
        "vmax": 0.34, "km": 0.5, "kcat": 21.0,
        "equilibrium_constant": 0.066, "delta_g_prime": 6.3,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:21786370",
        "confidence_score": 0.70,
        "notes": "ACO2; mitochondrial; mammalian value",
    },
    # Isocitrate dehydrogenase — high NADPH demand in CHO; IDH2 prominent
    "R00709": {
        "vmax": 0.55, "km": 0.013, "kcat": 44.0,
        "equilibrium_constant": 1.0e8, "delta_g_prime": -20.9,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:21786370",
        "confidence_score": 0.85,
        "notes": "IDH2/IDH3; CHO high NADPH demand; slightly elevated vs human",
    },
    # α-Ketoglutarate dehydrogenase — rate-limiting step in CHO TCA
    "R00621": {
        "vmax": 0.18, "km": 0.07, "kcat": 9.0,
        "equilibrium_constant": 1.0e8, "delta_g_prime": -33.4,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:21786370",
        "confidence_score": 0.85,
        "notes": "OGDH complex; rate-limiting in CHO TCA; lower Vmax than CS",
    },
    # Succinyl-CoA synthetase — similar to human
    "R00432": {
        "vmax": 0.28, "km": 0.25, "kcat": 57.0,
        "equilibrium_constant": 3.8, "delta_g_prime": -2.9,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:21786370",
        "confidence_score": 0.70,
        "notes": "SUCLA2; conserved mammalian",
    },
    # Succinate dehydrogenase (Complex II) — mitochondrial inner membrane
    "R02164": {
        "vmax": 0.14, "km": 0.5, "kcat": 16.0,
        "equilibrium_constant": 1.0, "delta_g_prime": 0.0,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:21786370",
        "confidence_score": 0.70,
        "notes": "SDHA/Complex II; conserved",
    },
    # Fumarase — similar to human; high turnover
    "R01082": {
        "vmax": 0.80, "km": 0.09, "kcat": 760.0,
        "equilibrium_constant": 4.4, "delta_g_prime": -3.8,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:21786370",
        "confidence_score": 0.70,
        "notes": "FH; highly conserved across mammals",
    },
    # Malate dehydrogenase — high flux in CHO due to malate-aspartate shuttle
    "R00342": {
        "vmax": 0.85, "km": 0.25, "kcat": 210.0,
        "equilibrium_constant": 2.86e-5, "delta_g_prime": 29.7,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:21786370",
        "confidence_score": 0.70,
        "notes": "MDH2; malate-aspartate shuttle active in CHO",
    },

    # ===================================================================
    # OXIDATIVE PHOSPHORYLATION  (cge00190)
    # ===================================================================

    # Complex I — NADH dehydrogenase; CHO similar to human
    "R02163": {
        "vmax": 0.48, "km": 0.01, "kcat": 190.0,
        "equilibrium_constant": 1.0e6, "delta_g_prime": -69.3,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:24297498",
        "confidence_score": 0.70,
        "notes": "Complex I; CHO mitochondria; conserved",
    },
    # Complex IV — cytochrome c oxidase; CHO similar to human
    "R00081": {
        "vmax": 0.28, "km": 0.002, "kcat": 280.0,
        "equilibrium_constant": 1.0e15, "delta_g_prime": -122.0,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:24297498",
        "confidence_score": 0.70,
        "notes": "Complex IV / COX; Km_O2=0.002 mM; conserved",
    },
    # ATP synthase — CHO mitochondria; P/O ratio ~2.5 (standard mammalian)
    "R00086": {
        "vmax": 1.9, "km": 0.5, "kcat": 95.0,
        "equilibrium_constant": 1.0e-4, "delta_g_prime": 36.0,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:24297498",
        "confidence_score": 0.70,
        "notes": "Complex V / ATP synthase; P/O ratio ~2.5 in CHO",
    },

    # ===================================================================
    # GLUTAMINOLYSIS — CHO primary nitrogen and carbon source
    # ===================================================================

    # Glutaminase — rate-limiting entry to glutaminolysis
    "R00256": {
        "vmax": 1.2, "km": 1.5, "kcat": 35.0,
        "equilibrium_constant": 1.0e4, "delta_g_prime": -14.2,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:23744439",
        "confidence_score": 0.85,
        "notes": "GLS1; glutaminolysis entry; Km_Gln=1.5 mM in CHO",
    },
    # Glutamate dehydrogenase — Glu → α-KG + NH3 (feeds TCA)
    "R00243": {
        "vmax": 0.8, "km": 3.5, "kcat": 25.0,
        "equilibrium_constant": 1.0e-3, "delta_g_prime": 30.5,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:15634345",
        "confidence_score": 0.70,
        "notes": "GLUD1; Km_Glu=3.5 mM in CHO culture",
    },
    # Glutamine synthetase — GS selection marker; re-synthesis of Gln from Glu+NH3
    "R00254": {
        "vmax": 0.35, "km": 0.35, "kcat": 18.0,
        "equilibrium_constant": 1.2e3, "delta_g_prime": -14.8,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:2153473",
        "confidence_score": 0.85,
        "notes": "GLUL/GS; selection marker in CHO GS system; Km_Glu=0.35 mM",
    },
    # Alanine aminotransferase — Pyr + Glu ↔ Ala + α-KG (major Ala secretion)
    "R00258": {
        "vmax": 1.5, "km": 0.9, "kcat": 55.0,
        "equilibrium_constant": 1.5, "delta_g_prime": -0.9,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:23744439",
        "confidence_score": 0.85,
        "notes": "GPT/ALT1; alanine secretion coupled to glutaminolysis in CHO",
    },

    # ===================================================================
    # AMINO ACID METABOLISM — key CHO biosynthetic routes
    # ===================================================================

    # Aspartate aminotransferase — OAA + Glu ↔ Asp + α-KG (malate-Asp shuttle)
    "R00355": {
        "vmax": 2.2, "km": 0.5, "kcat": 140.0,
        "equilibrium_constant": 6.6, "delta_g_prime": -4.7,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:9171865",
        "confidence_score": 0.70,
        "notes": "GOT1/GOT2; malate-aspartate shuttle; active in CHO mitochondria",
    },
    # Asparagine synthetase — Asp + Gln + ATP → Asn + Glu (CHO auxotrophy)
    "R01954": {
        "vmax": 0.18, "km": 0.8, "kcat": 8.0,
        "equilibrium_constant": 1.0e3, "delta_g_prime": -18.2,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:6296077",
        "confidence_score": 0.85,
        "notes": "ASNS; CHO asparagine auxotroph; Km_Gln=0.8 mM",
    },
    # Serine hydroxymethyltransferase — Ser + THF ↔ Gly + 5,10-MTHF (one-carbon)
    "R00945": {
        "vmax": 0.45, "km": 0.6, "kcat": 22.0,
        "equilibrium_constant": 2.2, "delta_g_prime": -2.7,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:9171865",
        "confidence_score": 0.70,
        "notes": "SHMT1/2; serine-glycine-one-carbon metabolism; active in CHO",
    },
    # Phosphoglycerate dehydrogenase — 3-PG → PHP (serine biosynthesis entry)
    "R02736": {
        "vmax": 0.12, "km": 0.18, "kcat": 6.0,
        "equilibrium_constant": 2.5e-3, "delta_g_prime": 16.7,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:9171865",
        "confidence_score": 0.55,
        "notes": "PHGDH; serine biosynthesis from glycolytic intermediate",
    },

    # ===================================================================
    # ANAPLEROSIS — TCA replenishment
    # ===================================================================

    # Pyruvate carboxylase — Pyr + CO2 + ATP → OAA
    "R00344": {
        "vmax": 0.4, "km": 0.15, "kcat": 20.0,
        "equilibrium_constant": 1.0e3, "delta_g_prime": -19.6,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "literature", "literature_reference": "PMID:21786370",
        "confidence_score": 0.85,
        "notes": "PC; active anaplerosis in CHO; replenishes OAA when Gln limited",
    },
    # Malic enzyme — Malate + NADP⁺ → Pyruvate + CO2 + NADPH (cytosolic NADPH)
    "R00214": {
        "vmax": 0.22, "km": 0.8, "kcat": 30.0,
        "equilibrium_constant": 14.0, "delta_g_prime": -3.9,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:20091739",
        "confidence_score": 0.70,
        "notes": "ME1; cytosolic NADPH generation; active in CHO lipid synthesis",
    },

    # ===================================================================
    # PENTOSE PHOSPHATE PATHWAY  (cge00030)
    # ===================================================================

    # G6P dehydrogenase — NADPH generation; feedback-inhibited by NADPH
    "R00835": {
        "vmax": 1.7, "km": 0.065, "kcat": 47.0,
        "equilibrium_constant": 1.0e3, "delta_g_prime": -17.6,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:20091739",
        "confidence_score": 0.70,
        "notes": "G6PD; PPP committed step; NADPH for biosynthesis and ROS defence",
    },
    # Transketolase — connects PPP to glycolysis
    "R01641": {
        "vmax": 4.8, "km": 0.8, "kcat": 19.0,
        "equilibrium_constant": 1.0, "delta_g_prime": 0.0,
        "ph": 7.2, "temperature_celsius": 37.0,
        "source_database": "brenda", "literature_reference": "PMID:20091739",
        "confidence_score": 0.55,
        "notes": "TKT; PPP ↔ glycolysis carbon redistribution",
    },
}


# ---------------------------------------------------------------------------
# Curated CHO regulatory interactions keyed by KEGG reaction ID
# ---------------------------------------------------------------------------

_CHO_REGULATORY: dict[str, list[dict]] = {
    # PFK: allosteric hub — inhibited by ATP/citrate, activated by AMP/ADP
    # Same logic as human but at CHO pH 7.2 shifts Ki slightly
    "R00756": [
        {"compound_kegg": "C00002", "interaction_type": "allosteric_inhibitor",
         "ki_allosteric": 1.1, "site": "regulatory"},   # ATP
        {"compound_kegg": "C00158", "interaction_type": "allosteric_inhibitor",
         "ki_allosteric": 0.9, "site": "regulatory"},   # Citrate
        {"compound_kegg": "C00020", "interaction_type": "allosteric_activator",
         "ki_allosteric": 0.06, "site": "regulatory"},  # AMP
        {"compound_kegg": "C00008", "interaction_type": "allosteric_activator",
         "ki_allosteric": 0.12, "site": "regulatory"},  # ADP
    ],
    # Pyruvate kinase (PKM2): activated by F1,6BP; inhibited by ATP
    # PKM2 isoform dominant in CHO — lower F1,6BP affinity than PKM1
    "R00196": [
        {"compound_kegg": "C00354", "interaction_type": "allosteric_activator",
         "ki_allosteric": 0.05, "site": "regulatory"},  # F-1,6-BP
        {"compound_kegg": "C00002", "interaction_type": "allosteric_inhibitor",
         "ki_allosteric": 10.0, "site": "regulatory"},  # ATP
    ],
    # LDH: activated by low pH (acidosis drives overflow lactate in CHO)
    "R00703": [
        {"compound_kegg": "C00033", "interaction_type": "allosteric_activator",
         "ki_allosteric": 5.0, "site": "regulatory"},   # Acetate (acidosis proxy)
    ],
    # PDH complex: inhibited by NADH and acetyl-CoA (product feedback)
    # Key switch point for CHO lactate metabolism
    "R00351": [
        {"compound_kegg": "C00004", "interaction_type": "allosteric_inhibitor",
         "ki_allosteric": 0.05, "site": "regulatory"},  # NADH
        {"compound_kegg": "C00024", "interaction_type": "feedback_inhibitor",
         "ki_allosteric": 0.02, "site": "active"},      # Acetyl-CoA
    ],
    # Citrate synthase: inhibited by NADH and ATP (energy charge)
    "R00352": [
        {"compound_kegg": "C00004", "interaction_type": "allosteric_inhibitor",
         "ki_allosteric": 0.05, "site": "regulatory"},  # NADH
        {"compound_kegg": "C00002", "interaction_type": "allosteric_inhibitor",
         "ki_allosteric": 0.9, "site": "regulatory"},   # ATP
    ],
    # Isocitrate DH: activated by ADP; inhibited by NADH and ATP
    "R00709": [
        {"compound_kegg": "C00008", "interaction_type": "allosteric_activator",
         "ki_allosteric": 0.1, "site": "regulatory"},   # ADP
        {"compound_kegg": "C00004", "interaction_type": "allosteric_inhibitor",
         "ki_allosteric": 0.02, "site": "regulatory"},  # NADH
        {"compound_kegg": "C00002", "interaction_type": "allosteric_inhibitor",
         "ki_allosteric": 0.5, "site": "regulatory"},   # ATP
    ],
    # Glutaminase: product-inhibited by glutamate (feedback)
    "R00256": [
        {"compound_kegg": "C00025", "interaction_type": "feedback_inhibitor",
         "ki_allosteric": 25.0, "site": "active"},      # L-Glutamate
    ],
    # GS: product-inhibited by glutamine (GS selection system regulation)
    "R00254": [
        {"compound_kegg": "C00064", "interaction_type": "feedback_inhibitor",
         "ki_allosteric": 4.5, "site": "active"},       # L-Glutamine
    ],
    # G6PD: inhibited by NADPH (product feedback — controls PPP flux)
    "R00835": [
        {"compound_kegg": "C00005", "interaction_type": "feedback_inhibitor",
         "ki_allosteric": 0.15, "site": "active"},      # NADPH
    ],
    # Hexokinase: feedback-inhibited by G6P (Crabtree effect in CHO)
    "R00299": [
        {"compound_kegg": "C00668", "interaction_type": "feedback_inhibitor",
         "ki_allosteric": 0.3, "site": "active"},       # G6P
    ],
}


# ---------------------------------------------------------------------------
# Public seeder function
# ---------------------------------------------------------------------------

_CHO_ORGANISM = "Cricetulus griseus (CHO)"
_CHO_CONFIDENCE_DEFAULT = 0.7  # Fallback; per-reaction scores in _CHO_KINETICS take precedence


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
                confidence_score=kdata.get("confidence_score", _CHO_CONFIDENCE_DEFAULT),
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
