# MetaKG Session Notes — 2026-03-06

Three significant improvements were implemented in this session:

1. Eliminated all isolated nodes (12,245 → 0)
2. Added pathway category / provenance field across the full stack
3. Expanded test coverage from 97 to 123 tests

---

## 1. Eliminated 12,245 Isolated Nodes

### Root Causes

| # | Cause | Impact |
|---|-------|--------|
| A | **Strategy C missing** — KGML `<entry type="gene">` elements carry a `reaction="rn:RXXXXX"` attribute that was never used for wiring | ~8,500 orphan enzymes |
| B | **CONTAINS fallback missing** — 278 pathway files with zero `<reaction>` elements (signaling 04xxx, disease 05xxx, genetic info 03xxx) had no path to wire entries to anything | ~3,500 orphan nodes |
| C | **Multi-compound entry clobber** — `<entry name="cpd:C001 cpd:C002">` only stored the last ID in `entry_map` | dozens of orphan compounds |
| D | **Enrichment opt-in** — bare `metakg build` never ran enrichment | pipeline hygiene |

### Files Changed

**`src/metakg/parsers/kgml.py`**

- Added `reaction_attr_map: dict[str, str]` — populated during gene/ortholog entry processing from `entry.attrib.get("reaction", "")`.
- Added **Strategy C** wiring: after Strategies A and B fail, look up `reaction_attr_map` and create `CATALYZES` edge.
- Added **CONTAINS fallback block** at end of `parse()`:
  - Any enzyme not wired via `CATALYZES` → `pwy CONTAINS enz`
  - Any compound not wired via `SUBSTRATE_OF`/`PRODUCT_OF` → `pwy CONTAINS cpd`
  - Multi-compound entries handled by splitting the raw `name` attribute on whitespace (not just the last ID)

**`src/metakg/cli/cmd_build.py`**

- `--enrich` flag (opt-in) replaced with `--no-enrich` flag (enrich now default-on) for both `build` and `update` commands.

**`src/metakg/orchestrator.py`**

- `MetaKG.build(enrich: bool = False)` → `enrich: bool = True`

### Result

```
Before  →  After
────────────────────────────────────────
Isolated nodes :  12,245  →      0
CONTAINS edges :   3,809  →  32,689
Total edges    :  10,693  →  40,166
```

---

## 2. Pathway Category / Provenance Field

### Motivation

KEGG pathways span very different biological domains. Storing the biological category on each pathway node enables type-based rendering in the visualizers and filtered queries via the API/MCP tools.

### KEGG Numeric-Range → Category Mapping

| KEGG ID range | Category constant | Value string |
|---|---|---|
| 00xxx – 01xxx | `PATHWAY_CATEGORY_METABOLIC` | `"metabolic"` |
| 02xxx | `PATHWAY_CATEGORY_TRANSPORT` | `"transport"` |
| 03xxx | `PATHWAY_CATEGORY_GIP` | `"genetic_info_processing"` |
| 04010 – 04099 | `PATHWAY_CATEGORY_SIGNALING` | `"signaling"` |
| 04100 – 04499 | `PATHWAY_CATEGORY_CELLULAR` | `"cellular_process"` |
| 04500 – 04999 | `PATHWAY_CATEGORY_ORGANISMAL` | `"organismal_system"` |
| 05xxx | `PATHWAY_CATEGORY_DISEASE` | `"human_disease"` |
| 07xxx | `PATHWAY_CATEGORY_DRUG` | `"drug_development"` |

### Files Changed

**`src/metakg/primitives.py`**

- Added `import re`
- Added 8 `PATHWAY_CATEGORY_*` string constants + `ALL_PATHWAY_CATEGORIES` tuple
- Added `_kegg_pathway_category(pathway_id: str) -> str | None` — extracts the trailing 5-digit number and maps it to a constant; returns `None` for unparseable IDs
- Added `category: str | None = None` field to `MetaNode` dataclass (after `source_file`)

**`src/metakg/store.py`**

- Added `category TEXT` column to `meta_nodes` `CREATE TABLE` in `_SCHEMA_SQL`
- Added `_migrate()` — reads `PRAGMA table_info(meta_nodes)` and issues `ALTER TABLE meta_nodes ADD COLUMN category TEXT` if absent; called from `_apply_schema()` so existing databases upgrade transparently on first open
- Extended `write()` INSERT to 12 columns with `n.category` as the 12th value
- Extended `all_nodes(*, kind=None, category=None)` to support `WHERE category=?` (combinable with `kind=`)

**`src/metakg/parsers/kgml.py`**

- Imported `_kegg_pathway_category`
- Set `category=_kegg_pathway_category(pathway_kegg_id)` on `pwy_node` at creation

### Category Distribution After Rebuild (369 human pathways)

```
metabolic                99
organismal_system        98
human_disease            84
cellular_process         39
genetic_info_processing  29
signaling                19
transport                 1
────────────────────────────
Total                   369   (0 NULL)
```

### Usage

```python
from metakg import MetaKG
from metakg.primitives import PATHWAY_CATEGORY_METABOLIC

kg = MetaKG()

# All metabolic pathways
kg.store.all_nodes(kind="pathway", category="metabolic")

# All human disease pathways
kg.store.all_nodes(category=PATHWAY_CATEGORY_DISEASE)

# Mix with kind filter
kg.store.all_nodes(kind="pathway", category="signaling")
```

```sql
-- Direct SQL
SELECT name, category FROM meta_nodes WHERE kind='pathway' ORDER BY category, name;
SELECT category, COUNT(*) FROM meta_nodes WHERE kind='pathway' GROUP BY category;
```

---

## 3. Test Coverage

26 new tests added; all **123 tests pass**.

### New Test Classes

| File | Class | Tests | What's Covered |
|------|-------|-------|----------------|
| `test_primitives.py` | `TestKeggPathwayCategory` | 15 | Every category boundary, edge cases (empty string, no digits, bare numeric suffix) |
| `test_primitives.py` | `TestMetaNodeCategory` | 3 | Default `None`, explicit set, non-pathway nodes always `None` |
| `test_store.py` | `TestNodeCategory` | 7 | Round-trip persistence, NULL for non-pathway, `category=` filter, combined `kind+category` filter, baseline no-filter, schema migration from legacy DB |
| `test_parsers.py` | `TestKGMLParser` (2 new) | 2 | `hsa00010` → `metabolic`, `hsa05010` → `human_disease` |

### Coverage Summary (key modules)

| Module | Coverage |
|---|---|
| `primitives.py` | 90% |
| `parsers/kgml.py` | 83% |
| `store.py` | 74% |
| `parsers/csv_tsv.py` | 97% |

Low-coverage modules (`analyze.py`, `app.py`, `viz3d.py`, CLI) are UI/IO-heavy layers not exercised by unit tests — expected.

---

## Current Database State

```
db_path  : .metakg/meta.sqlite
nodes    : 17,050  {compound: 5115, enzyme: 9427, pathway: 369, reaction: 2139}
edges    : 40,166  {CATALYZES: 2394, CONTAINS: 32689, PRODUCT_OF: 2532, SUBSTRATE_OF: 2551}
xrefs    : 24,037
vectors  : 14,911 (dim=384)
isolated : 0
```

---

## Pending Next Steps

- **`viz3d.py` category filter** — `VizState` has no `selected_category` field. Add a category dropdown to the sidebar so users can render networks by type (metabolic, signaling, etc.). The data is all there; this is purely a UI addition.
- **`app.py` category filter** — Streamlit 2D explorer sidebar similarly has no category filter.
- **Category index** — Consider adding `CREATE INDEX IF NOT EXISTS idx_meta_nodes_category ON meta_nodes(category)` to `_SCHEMA_SQL` if query performance becomes relevant at scale.
- **Non-KGML parsers** — SBML, CSV, BioPAX parsers don't set `category` (they produce no KEGG pathway nodes, so `None` is correct for now).
