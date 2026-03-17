# Branch Notes: claude/wire-kegg-enzymes-15Cx4

## Summary

Investigation and fix for KEGG enzyme wiring in the KGML parser.

---

## KEGG Enzyme Wiring Analysis

Running `scripts/wire_kegg_enzymes.py` across 369 downloaded human KEGG pathway
files confirmed that **all 4,165 reaction elements are fully covered by the
parser's Strategy B** (reaction element `id` == gene entry `id`), which is the
standard KEGG KGML convention. No file patching is required for real KEGG data.
This contrasts with the hand-authored sample files, which required `wire_enzymes.py`.

---

## Multi-Gene Entry Group Node Fix

**Problem:** A single KGML `<entry type="gene">` often lists multiple gene IDs
(e.g. `hsa:5160 hsa:5161 hsa:5162` for the pyruvate dehydrogenase complex).
These represent either complex subunits or isozyme families that KEGG treats as
a functional unit for that pathway step. The previous parser created one enzyme
node per gene but only wired the **last-processed** gene to its reaction via a
CATALYZES edge, leaving all others as orphaned nodes with no edges.

**Fix (`src/metakg/parsers/kgml.py`):** Create **one canonical group node** per
entry, keyed on the first gene ID and labelled with the KEGG graphics name. All
member gene IDs are stored as a list in the node's `xrefs` JSON. The
`entry_map` points to this single node, so CATALYZES wiring is correct and
complete.

**Effect across full human KEGG dataset:**
- Enzyme node count drops by ~1,797 (no more orphaned per-gene duplicates)
- CATALYZES edge count stays flat at 4,165
- ~5,255 previously orphaned enzyme nodes eliminated

---

## xref Index Update

**Fix (`src/metakg/store.py` — `MetaStore.build_xref_index`):** Updated to
expand list-valued xref entries into individual `xref_index` rows. Each member
gene ID in a group gets its own row pointing to the canonical group node, so
per-gene lookup works transparently.

**Example:** Group node `enz:kegg:5160` with `xrefs={"kegg": ["5160","5161","5162"]}`
produces three `xref_index` rows — searching by any of the three gene IDs
returns the group node.

---

## Biological Rationale

Full isozyme wiring (a CATALYZES edge per gene per reaction) would be 2.3× the
correct edge count (+5,255 edges), and most extra edges would be biologically
wrong: complex subunits cannot independently catalyze their reaction. The group
node approach is the correct semantic representation.
