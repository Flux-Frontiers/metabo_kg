#!/usr/bin/env bash
# Rebuild PyCodeKG + DocKG and capture version-tagged temporal snapshots.
#
# Invoked by pre-commit AFTER the ty and pytest hooks pass. Those hooks are
# marked fail_fast, so a type-check or test failure aborts the run before this
# script executes -- the knowledge graphs are only ever rebuilt from code that
# already passed the full suite.
set -euo pipefail

VENV="$(cd "$(dirname "$0")/.." && pwd)/.venv/bin"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)"

# Subcommand form throughout, not the `<cli>-<sub>` aliases: pycode_kg dropped
# those in 0.23.0 (this script's `pycodekg-build` call broke with it) and
# doc_kg still ships them. `<cli> <sub>` works under both policies.
echo ">> pycodekg build"
"$VENV/pycodekg" build
echo ">> pycodekg snapshot save $VERSION"
"$VENV/pycodekg" snapshot save "$VERSION"

echo ">> dockg build"
"$VENV/dockg" build
echo ">> dockg snapshot save $VERSION"
"$VENV/dockg" snapshot save "$VERSION"

# Stage the freshly written snapshots so they ride along with this commit.
# (Build artifacts -- graph.sqlite, vectors.sqlite -- are gitignored and skipped.)
git add .pycodekg/snapshots .dockg/snapshots
