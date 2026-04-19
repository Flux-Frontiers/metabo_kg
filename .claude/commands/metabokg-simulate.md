# MetaboKG Simulate

Run metabolic pathway simulations using the MetaboKG database. Supports four modes: seed kinetics, FBA (steady-state flux), ODE (time-course), and what-if (perturbation).

## Command Argument Handling

**Usage:**
- `/metabokg-simulate` — Interactive: asks what kind of simulation to run
- `/metabokg-simulate seed` — Load kinetic parameters
- `/metabokg-simulate fba pwy:kegg:hsa00010` — FBA for Glycolysis
- `/metabokg-simulate ode pwy:kegg:hsa00010` — ODE time-course
- `/metabokg-simulate whatif pwy:kegg:hsa00010` — Perturbation analysis

---

## Prerequisites

1. Verify the database exists:
   ```bash
   ls -lh .metabokg/hsa.sqlite
   ```
2. For ODE/what-if, confirm kinetics are seeded:
   ```bash
   sqlite3 .metabokg/hsa.sqlite "SELECT COUNT(*) FROM kinetic_parameters;"
   ```
   If 0, run `metabokg-simulate seed` first.

---

## Seed Kinetic Parameters

```bash
metabokg-simulate seed
```

Python equivalent:
```python
from metabokg import MetaKG
kg = MetaKG()
kg.seed_kinetics()
```

---

## FBA — Steady-State Flux Analysis

```bash
metabokg-simulate fba pwy:kegg:hsa00010
```

Python:
```python
from metabokg import MetaKG
kg = MetaKG()
result = kg.simulate_fba("pwy:kegg:hsa00010", maximize=True)
```

---

## ODE — Time-Course Simulation

```bash
metabokg-simulate ode pwy:kegg:hsa00010
```

Python (with full options):
```python
from metabokg import MetaKG
kg = MetaKG()
result = kg.simulate_ode(
    "pwy:kegg:hsa00010",
    t_end=20,
    t_points=50,
    ode_method="BDF",          # BDF for stiff metabolic systems (default)
    initial_concentrations={"cpd:kegg:C00031": 5.0}
)
```

> ⚠️ **Always use `ode_method="BDF"` (default).** RK45 will hang on stiff metabolic systems.

---

## What-If — Perturbation Analysis

```bash
metabokg-simulate whatif pwy:kegg:hsa00010
```

Python with scenario JSON:
```python
import json
from metabokg import MetaKG
kg = MetaKG()

# Enzyme knockout
scenario = {"enzyme_knockouts": ["enz:kegg:hsa:2539"]}
result = kg.simulate_whatif("pwy:kegg:hsa00010", json.dumps(scenario), mode="fba")

# Enzyme activity change (50%)
scenario = {"enzyme_activities": {"enz:kegg:hsa:2539": 0.5}}
result = kg.simulate_whatif("pwy:kegg:hsa00010", json.dumps(scenario), mode="fba")

# Substrate override (10x glucose)
scenario = {"substrate_overrides": {"cpd:kegg:C00031": 10.0}}
result = kg.simulate_whatif("pwy:kegg:hsa00010", json.dumps(scenario), mode="fba")
```

---

## Finding Pathway IDs

```bash
sqlite3 .metabokg/hsa.sqlite "SELECT node_id, name FROM meta_nodes WHERE kind='pathway' LIMIT 20;"
```

---

## ODE Solver Reference

| Solver | Use For | Notes |
|--------|---------|-------|
| `BDF` | Metabolic pathways (default) | Implicit, stiff-optimized |
| `Radau` | Very stiff systems | Slower but more robust |
| `RK45` | **Avoid for metabolic** | Will hang on stiff systems |
