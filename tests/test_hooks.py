"""Tests for ``metabokg install-hooks`` — the generated pre-commit hook.

The hook is an embedded shell string, so nothing type-checks it and nothing
imports it.  It had rotted into a state where it invoked ``codekg``, the
retired predecessor of PyCodeKG, with ``set -euo pipefail`` above it and
``|| exit 1`` beside it — so *every commit* in a repo that installed the hook
failed.  A second, independent bug aborted the very first commit of a fresh
repo.  Both were invisible to the suite because no test ever ran the hook.

These execute it: a real ``git init``, a real commit, a real exit code.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

import metabokg.cli  # noqa: F401 — registers subcommands
from metabokg.cli.cmd_hooks import _PRE_COMMIT_HOOK
from metabokg.cli.main import cli

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="hook execution needs git and bash",
)


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


@pytest.fixture
def repo(tmp_path):
    """A real git repository with the hook installed."""
    _git("init", "-q", ".", cwd=tmp_path)
    _git("config", "user.email", "test@example.com", cwd=tmp_path)
    _git("config", "user.name", "Test", cwd=tmp_path)
    result = CliRunner().invoke(cli, ["install-hooks", "--repo", str(tmp_path)])
    assert result.exit_code == 0, result.output
    return tmp_path


def _stage(repo: Path, name: str) -> None:
    (repo / name).write_text("content\n")
    _git("add", name, cwd=repo)


class TestHookContents:
    def test_invokes_pycodekg_not_the_retired_codekg(self):
        """`codekg` is not a console script in any repo in the fleet."""
        assert "pycodekg" in _PRE_COMMIT_HOOK
        assert "/codekg" not in _PRE_COMMIT_HOOK
        assert "bin/codekg" not in _PRE_COMMIT_HOOK

    def test_does_not_pass_wipe_to_a_full_build(self):
        """`pycodekg build` always wipes and has no --wipe flag; passing one exits 2."""
        build_lines = [ln for ln in _PRE_COMMIT_HOOK.splitlines() if '" build' in ln]
        assert build_lines
        assert not any("--wipe" in ln for ln in build_lines)

    def test_stages_the_pycodekg_snapshot_directory(self):
        assert ".pycodekg/snapshots/" in _PRE_COMMIT_HOOK
        assert ".codekg/snapshots/" not in _PRE_COMMIT_HOOK

    def test_skip_switch_is_namespaced_to_this_tool(self):
        assert "METABOKG_SKIP_SNAPSHOT" in _PRE_COMMIT_HOOK
        assert "CODEKG_SKIP_SNAPSHOT" not in _PRE_COMMIT_HOOK

    def test_is_valid_bash(self, tmp_path):
        script = tmp_path / "hook.sh"
        script.write_text(_PRE_COMMIT_HOOK)
        assert subprocess.run(["bash", "-n", str(script)]).returncode == 0


class TestInstall:
    def test_writes_an_executable_hook(self, repo):
        hook = repo / ".git" / "hooks" / "pre-commit"
        assert hook.is_file()
        assert hook.stat().st_mode & 0o111

    def test_refuses_to_clobber_without_force(self, repo):
        result = CliRunner().invoke(cli, ["install-hooks", "--repo", str(repo)])
        assert result.exit_code != 0
        assert "--force" in result.output

    def test_force_overwrites(self, repo):
        hook = repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 0\n")
        result = CliRunner().invoke(cli, ["install-hooks", "--repo", str(repo), "--force"])
        assert result.exit_code == 0
        assert "pycodekg" in hook.read_text()

    def test_rejects_a_non_git_directory(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        result = CliRunner().invoke(cli, ["install-hooks", "--repo", str(plain)])
        assert result.exit_code != 0
        assert "not a git repository" in result.output


class TestHookExecution:
    """The part that actually regressed: does a commit still go through?"""

    def test_first_commit_in_a_fresh_repo_succeeds(self, repo):
        """Unborn HEAD — `rev-parse --abbrev-ref HEAD` is fatal there."""
        _stage(repo, "a.txt")
        result = _git("commit", "-m", "init", cwd=repo)
        assert result.returncode == 0, result.stderr

    def test_subsequent_commits_succeed(self, repo):
        _stage(repo, "a.txt")
        _git("commit", "-m", "init", cwd=repo)
        _stage(repo, "b.txt")
        result = _git("commit", "-m", "second", cwd=repo)
        assert result.returncode == 0, result.stderr

    def test_hook_exits_zero_when_no_sibling_kgs_are_installed(self, repo):
        """MetaboKG does not depend on PyCodeKG — its absence must not be fatal."""
        _stage(repo, "a.txt")
        _git("commit", "-m", "init", cwd=repo)
        _stage(repo, "b.txt")
        result = subprocess.run(
            ["bash", str(repo / ".git" / "hooks" / "pre-commit")],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_skip_switch_short_circuits(self, repo):
        _stage(repo, "a.txt")
        _git("commit", "-m", "init", cwd=repo)
        result = subprocess.run(
            ["bash", str(repo / ".git" / "hooks" / "pre-commit")],
            cwd=repo,
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin", "METABOKG_SKIP_SNAPSHOT": "1", "HOME": str(repo)},
        )
        assert result.returncode == 0, result.stderr
