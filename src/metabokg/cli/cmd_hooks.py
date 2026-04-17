"""
cmd_hooks.py — Install the MetaboKG pre-commit git hook.

  install-hooks — write the hook to .git/hooks/pre-commit and make it executable
"""

from __future__ import annotations

import stat
from pathlib import Path

import click

from metabokg.cli.main import cli

# ---------------------------------------------------------------------------
# Hook script (embedded so this module is self-contained when installed as
# a package in any repo, not just metabo_kg itself)
# ---------------------------------------------------------------------------

_PRE_COMMIT_HOOK = """\
#!/usr/bin/env bash
# MetaboKG pre-commit hook — runs quality checks, keeps local indices in sync,
# and captures metrics snapshots for CodeKG, MetaboKG, and DocKG.
# Installed by: metabokg install-hooks
# Skip with: CODEKG_SKIP_SNAPSHOT=1 git commit ...
set -euo pipefail

[ "${CODEKG_SKIP_SNAPSHOT:-0}" = "1" ] && exit 0

REPO_ROOT="$(git rev-parse --show-toplevel)"

# Run pre-commit framework checks (ruff, mypy, detect-secrets, etc.)
# Delegates to .pre-commit-config.yaml so quality checks stay in one place.
PRECOMMIT="$REPO_ROOT/.venv/bin/pre-commit"
if [ -x "$PRECOMMIT" ]; then
    "$PRECOMMIT" run || exit 1
elif command -v pre-commit &>/dev/null; then
    pre-commit run || exit 1
fi

cd "$REPO_ROOT"

TREE_HASH=$(git write-tree)
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# --- CodeKG: codebase knowledge graph ---
"$REPO_ROOT/.venv/bin/codekg" build --repo "$REPO_ROOT" --wipe || exit 1
"$REPO_ROOT/.venv/bin/codekg" snapshot save \\
    --repo . \\
    --tree-hash "$TREE_HASH" \\
    --branch "$BRANCH" \\
  || { echo "[codekg] snapshot skipped (run 'codekg build' to initialize)" >&2; exit 0; }
git add .codekg/snapshots/ 2>/dev/null || true

# --- MetaboKG: metabolic pathway knowledge graph ---
if [ -f ".metabokg/meta.sqlite" ]; then
    "$REPO_ROOT/.venv/bin/metabokg" snapshot save \\
        --tree-hash "$TREE_HASH" \\
        --branch "$BRANCH" \\
      || echo "[metabokg] snapshot skipped" >&2
    git add .metabokg/snapshots/ 2>/dev/null || true
fi

# --- DocKG: documentation knowledge graph ---
if [ -d ".dockg" ]; then
    "$REPO_ROOT/.venv/bin/dockg-snapshot" save \\
        --repo . \\
        --tree-hash "$TREE_HASH" \\
        --branch "$BRANCH" \\
      || echo "[dockg] snapshot skipped" >&2
    git add .dockg/snapshots/ 2>/dev/null || true
fi

exit 0
"""


@cli.command("install-hooks")
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True),
    show_default=True,
    help="Repository root.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite an existing pre-commit hook.",
)
def install_hooks(repo: str, force: bool) -> None:
    """Install the MetaboKG pre-commit git hook.

    After installation, before each commit:
      1. Runs pre-commit framework checks (ruff, mypy, detect-secrets)
      2. Rebuilds local CodeKG index (--wipe)
      3. Captures snapshots for CodeKG, MetaboKG, and DocKG (if present)
      4. Stages all snapshot directories atomically

    Package versions are auto-detected from installed packages — no
    pyproject.toml parsing required.

    Example:
        metabokg install-hooks --repo .
    """
    repo_root = Path(repo).resolve()
    git_dir = repo_root / ".git"

    if not git_dir.is_dir():
        click.echo(f"Error: {repo_root} is not a git repository.", err=True)
        raise SystemExit(1)

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_path = hooks_dir / "pre-commit"

    if hook_path.exists() and not force:
        click.echo(f"Hook already exists: {hook_path}")
        click.echo("Use --force to overwrite.")
        raise SystemExit(1)

    hook_path.write_text(_PRE_COMMIT_HOOK)
    mode = hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    hook_path.chmod(mode)

    click.echo(f"OK Installed pre-commit hook: {hook_path}")
    click.echo("  Snapshots will be captured automatically before each commit.")
    click.echo("  Skip with: CODEKG_SKIP_SNAPSHOT=1 git commit ...")
