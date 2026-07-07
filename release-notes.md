# Release Notes — v0.9.0

> Released: 2026-07-07

MetaboKG v0.9.0 is a correctness and completeness release. The KGML parser now
represents every KEGG reaction as its own node, the CHO kinetics seeder no longer
silently drops reactions, and the vector index is retuned so semantic search
surfaces compounds, reactions, and pathways instead of near-identical enzyme
embeddings. The result is a graph you can trust to resolve by individual KEGG
accession and a search index that returns the nodes you actually query for.

## What changed

**Reactions are no longer composite.** KEGG groups related R-numbers into a single
`<reaction>` element when they share substrates, products, and enzymes. The parser
previously used the whole space-separated string as one node ID, leaving ~360
composite reaction nodes in the CHO graph (and similar in human) that no
single-R-number lookup could find. The parser now emits one reaction node per
R-number — each carrying the same stoichiometry, substrate/product edges, pathway
membership, and enzyme catalysis — so `store.node("rxn:kegg:R00243")`, reaction
knockouts, and the kinetics seeders all resolve correctly.

**CHO kinetics are complete.** The seeder used to drop eight reactions whose KEGG
R-numbers were absent from the CHO pathway graph. It now consults the canonical
reaction-name table and creates a stub node before writing kinetics, so the full
set of 35 CHO reactions is seeded (39 parameter rows, 15 regulatory interactions).

**Sharper semantic search.** The LanceDB index now covers compound, reaction, and
pathway nodes and excludes enzymes, whose gene-name-only content produced
near-identical embeddings that crowded out more useful hits. Enzymes remain
reachable via one hop from reactions.

**Leaner packaging and a simpler enrichment path.** Embedding backends are now
sourced from `kgmodule-utils`, the enrichment pipeline drops two redundant phases,
the `kg` extra no longer bundles dev-only tools, the type checker moved from mypy
to `ty`, and iCHO2441 statistics were corrected consistently across the docs.

**Commit-time index hygiene.** A new pre-commit hook rebuilds the PyCodeKG and
DocKG indices and captures version-tagged snapshots after the type check and test
suite pass, keeping the local knowledge graphs in sync with the committed code.

## Upgrading

Reinstall to pick up the new dependency set and rebuild the corpora so the
reaction-splitting and index changes take effect:

```bash
poetry install --all-extras
metabokg-init          # or: metabokg-build --data data/<corpus>
```

No API changes are required, but code that relied on composite reaction IDs (the
old space-separated `rn:...` strings) should switch to individual KEGG R-numbers.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
