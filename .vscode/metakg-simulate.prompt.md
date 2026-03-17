---
mode: 'agent'
description: 'Run MetaKG simulations: seed kinetics, FBA steady-state, ODE time-course, or what-if perturbation analysis.'
---

# MetaKG Simulate

Run metabolic pathway simulations using the MetaKG database. Supports four modes: seed kinetics, FBA (steady-state flux), ODE (time-course), and what-if (perturbation).

## Command Argument Handling

**Usage:**
- No argument — Interactive mode; asks what kind of simulation to run
- `seed` — Load kinetic parameters from literature
- `fba <pathway_id>` — Steady-state FBA for a pathway
- `ode <pathway_id>` — Time-course ODE simulation
- `whatif <pathway_id>` — Perturbation/knockout analysis

---

## Prerequisites

1. Verify the database exists:
   ```bash
   ls -lh .metakg/meta.sqlite
   ```
2. If kinetics are needed for ODE/what-if, confirm they are seeded:
   ```bash
   sqlite3 .metakg/meta.sqlite "SELECT COUNT(*) FROM kinetic_parameters;"
   ```
   If 0, run `metakg-simulate seed` first.

---

## Seed Kinetic Parameters

Load Km, Vmax, and kcat values from literature sources:

```bash
metakg-simulate seed
```

This populates the `kinetic_parameters` table. Safe to re-run — idempotent.

Python equivalent:
```python
from metakg import MetaKG
kg = MetaKG()
kg.seed_kinetics()
```

---

## FBA — Steady-State Flux Analysis

Find optimal flux distributions at steady state:

```bash
metakg-simulate fba <pathway_id>
```

Example:
```bash
metakg-simulate fba pwy:kegg:hsa00010   # Glycolysis
```

Python equivalent:
```python
from metakg import MetaKG
kg = MetaKG()
result = kg.simulate_fba("pwy:kegg:hsa00010", maximize=True)
```

**Interpreting results:**
- Positive flux = forward reaction direction
- Zero flux = reaction not active at optimum
- Check for blocked reactions (always zero)

---

## ODE — Time-Course Simulation

Simulate metabolite concentrations over time:

```bash
metakg-simulate ode <pathway_id>
```

Python (with full options):
```python
from metakg import MetaKG
kg = MetaKG()
result = kg.simulate_ode(
    "pwy:kegg:hsa00010",
    t_end=20,
    t_points=50,
    ode_method="BDF",          # BDF for stiff metabolic systems (default)
    initial_concentrations={"cpd:kegg:C00031": 5.0}  # Override glucose
)
```

> ⚠️ **Always use `ode_method="BDF"` (default).** RK45 will hang on stiff metabolic systems.

---

## What-If — Perturbation Analysis

Test enzyme knockouts, activity changes, or substrate overrides:

```bash
metakg-simulate whatif <pathway_id>
```

Python with scenario JSON:
```python
import json
from metakg import MetaKG
kg = MetaKG()

# Enzyme knockout
scenario = {"enzyme_knockouts": ["enz:kegg:hsa:2539"]}
result = kg.simulate_whatif("pwy:kegg:hsa00010", json.dumps(scenario), mode="fba")

# Enzyme activity change
scenario = {"enzyme_activities": {"enz:kegg:hsa:2539": 0.5}}  # 50% activity
result = kg.simulate_whatif("pwy:kegg:hsa00010", json.dumps(scenario), mode="fba")

# Substrate override
scenario = {"substrate_overrides": {"cpd:kegg:C00031": 10.0}}  # 10x glucose
result = kg.simulate_whatif("pwy:kegg:hsa00010", json.dumps(scenario), mode="fba")
```

**Mode options:** `"fba"` (default) or `"ode"` for time-course what-if.

---

## Finding Pathway IDs

```python
from metakg import MetaKG
from metakg.primitives import PATHWAY_CATEGORY_METABOLIC

kg = MetaKG()
# All metabolic pathways
pathways = kg.store.all_nodes(kind="pathway", category=PATHWAY_CATEGORY_METABOLIC)
for p in pathways[:10]:
    print(p.node_id, p.name)
```

Or via SQL:
```bash
sqlite3 .metakg/meta.sqlite "SELECT node_id, name FROM meta_nodes WHERE kind='pathway' LIMIT 20;"
```

---

## ODE Solver Reference

| Solver | Use For | Notes |
|--------|---------|-------|
| `BDF` | Metabolic pathways (default) | Implicit, stiff-optimized |
| `Radau` | Very stiff systems | Slower but more robust |
| `RK45` | **Avoid for metabolic** | Will hang on stiff systems |

**Tuning params:** `ode_rtol=1e-3`, `ode_atol=1e-5`, `ode_max_step=None`
