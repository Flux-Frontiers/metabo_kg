# MetaKG Build

Parse KEGG KGML pathway files into the MetaKG SQLite knowledge graph and LanceDB semantic index. Execute the following steps in sequence.

## Command Argument Handling

**Usage:**
- `/metakg-build` — Interactive mode; prompts for data directory
- `/metakg-build data/hsa_pathways` — Build from the specified KGML directory

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

To add new KGML files without wiping:

```bash
metakg-update --data "$DATA_DIR"
```

## Important Rules

- Default behavior is `--wipe` — existing data is replaced.
- Use `--no-enrich` to skip name lookups (much faster).
- The embedding model (~100MB) is downloaded once on first run.
