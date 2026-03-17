---
mode: 'agent'
description: 'Build or rebuild the MetaKG SQLite + LanceDB database from KGML pathway files.'
---

# MetaKG Build

Parse KEGG KGML pathway files into the MetaKG SQLite knowledge graph and LanceDB semantic index. Execute the following steps in sequence.

## Command Argument Handling

**Usage:**
- No argument — Interactive mode; prompts for data directory
- With path argument — Build from the specified KGML directory

---

## Step 0: Resolve Data Directory

1. If a path argument was provided, use it as `DATA_DIR`. Otherwise ask:
   > "Where are your KGML files? (default: `data/hsa_pathways`)"
2. Verify the directory exists and contains `.kgml` files:
   ```bash
   ls "$DATA_DIR"/*.kgml | head -5
   ```
3. If no KGML files are found, stop and suggest downloading first:
   ```bash
   python scripts/download_human_kegg.py --output data/hsa_pathways
   ```

---

## Step 1: Check Prerequisites

1. Confirm the database directory exists or will be created:
   ```bash
   ls -la .metakg/ 2>/dev/null || echo "Will be created"
   ```
2. If an existing database is present, warn the user it will be wiped (default behavior).

---

## Step 2: Build the Database

Run the full build (wipe + enrich by default):

```bash
metakg-build --data "$DATA_DIR"
```

**Common options:**
- `--no-wipe` — Keep existing data, add only new files
- `--no-enrich` — Skip compound/reaction name enrichment (faster)
- `--no-index` — Skip LanceDB (SQLite only)
- `--db PATH` — Custom SQLite path (default: `.metakg/meta.sqlite`)
- `--lancedb PATH` — Custom LanceDB path (default: `.metakg/lancedb`)

Monitor output for:
- Number of pathways parsed
- Node and edge counts
- Enrichment progress
- Any parse warnings

---

## Step 3: Verify the Build

Run a quick stats check:

```bash
python -c "
from metakg import MetaKG
kg = MetaKG()
store = kg.store
nodes = store.all_nodes()
pathways = store.all_nodes(kind='pathway')
print(f'Total nodes: {len(nodes)}')
print(f'Pathways: {len(pathways)}')
print(f'Categories: {set(p.category for p in pathways if p.category)}')
"
```

Or via SQL:
```bash
sqlite3 .metakg/meta.sqlite "
SELECT kind, COUNT(*) as n FROM meta_nodes GROUP BY kind;
SELECT COUNT(*), category FROM meta_nodes WHERE kind='pathway' GROUP BY category;
"
```

---

## Step 4: Seed Kinetic Parameters (Optional)

Load literature kinetic parameters (Km, Vmax, kcat) for simulations:

```bash
metakg-simulate seed
```

---

## Step 5: Report

Present a summary:
```
✓ Data directory:   <DATA_DIR>
✓ Pathways parsed:  <N>
✓ Total nodes:      <N>
✓ Total edges:      <N>
✓ Categories:       metabolic=X  signaling=X  disease=X  ...
✓ Database:         .metakg/meta.sqlite
✓ Vector index:     .metakg/lancedb
```

---

## Incremental Update

To add new KGML files without wiping existing data:

```bash
metakg-update --data "$DATA_DIR"
```

Use this when you've downloaded new pathway files and want to merge them in.

---

## Important Rules

- Default behavior is `--wipe` — existing data is replaced.
- Use `--no-enrich` if you just want the raw graph without name lookups (much faster).
- The embedding model (~100MB) is downloaded once on first run.
