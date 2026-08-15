# Release Notes — v0.12.1

> Released: 2026-08-15

A single-bug patch. If a build over your data directory has been reporting the
KEGG annotation tables as corrupt — `kegg_compound_names.tsv`,
`hsa_gene_names.tsv` and the rest — those errors were spurious, and this release
removes them. The only other change is cosmetic: a self-invalidating provenance
line has been stripped from every module docstring.

## What changed

**`CSVParser` no longer claims files it cannot parse.** Its `can_handle()` was
inherited from the base parser, which matches on file extension alone. That is
too eager: `.tsv` is also the extension of the annotation tables `metabokg init`
fetches into the data directory, so the parser accepted them as reaction tables
and then failed on the missing `substrate` and `product` columns. A build over
`data/` logged eight "Failed to parse" errors, every one of them for a file that
was never a reaction table.

`can_handle()` now reads the header and confirms the required columns are there
before claiming the file. The graph is unaffected — extraction over `data/`
produces the same 35,852 nodes and 118,267 edges as before — but the parse-error
count goes from eight to zero, so a real failure is no longer buried in noise.

**The `Last Revision:` docstring headers are gone.** Twenty-eight modules carried
one, and the field cannot be maintained: correcting the date is itself an edit,
which moves the file's real modification time and makes the line wrong again. The
package version already tells you which release you are holding, and `git log`
tells you when a file last moved. `Author:` and `License:` are untouched.

## Upgrading

Nothing to do beyond upgrading. No rebuild, no migration, no API change. If you
previously moved your annotation TSVs out of the data directory to silence the
errors, you can move them back.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
