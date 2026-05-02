# Release Notes — v0.8.0

> Released: 2026-05-02

### Added

- **`ANNOUNCEMENT.md`** (root) — GitHub-style introductory announcement post: punchy intro, why it exists, the three bundled corpora, hybrid retrieval, simulation, MCP/LLM integration, 60-second quickstart, and links to the docs map. Suitable as a Discussions post or release-page body.
- **`.github/workflows/ci.yml`** — CI workflow for `push` and `pull_request` on `main`: lint + format check (`ruff`), type check (`mypy src/`), and tests (`pytest -m "not integration and not slow"`) on Python 3.12, with cached Poetry virtualenvs.

### Changed

- **License finalized as Elastic License 2.0 across all surfaces** (`README.md`, `ANNOUNCEMENT.md`) — README badge switched from `PolyForm-NC-1.0.0` to `Elastic-2.0`; the License section was rewritten to describe the actual restrictions (no hosted-service resale, no notice circumvention) instead of the noncommercial-only framing. The `LICENSE` file and `CITATION.cff` were already on Elastic 2.0; this change reconciles the README with them.
- **README "Contributing" section softened** (`README.md`) — Renamed to "Feedback & contributions" and clarified that issues and discussions are welcome but external pull requests are paused while contribution licensing (CLA vs DCO) is finalized.
- **`pycode-kg` promoted from git source to PyPI** (`pyproject.toml`) — `pycode-kg` is now published on PyPI at `>=0.18.1`; removed the `git+https` source reference and the testpypi supplemental source entry. Both `kg` and `all` extras now resolve from PyPI.
- **`doc-kg` bumped to `>=0.12.3`** (`pyproject.toml`) — Updated minimum version in `kg` and `all` extras (was `>=0.11.0`).
- **`kgmodule-utils` bumped to `>=0.2.3`** (`pyproject.toml`) — Updated minimum version in core dependencies (was `>=0.2.0`).
- **`dev` extra merged into `kg` extra** (`pyproject.toml`) — Development tools (`detect-secrets`, `mypy`, `pre-commit`, `ruff`, `pytest`, etc.) consolidated under the `kg` extra; the separate `dev` extra is removed.
- **Code style in `embed.py`** (`src/metabokg/embed.py`) — `model.encode()` call wrapped to 88-character line limit; no functional change.
- **`/release` slash command repaired and consolidated** (`.claude/commands/release.md`) — Was a stale copy from the code_kg repo with broken paths (`src/code_kg/__init__.py`, `codekg-*` commands). Now correctly references `src/metabokg/__init__.py` and `pycodekg-*` commands, includes a clean-tree + `gh auth` preflight, and folds `poetry build` + `gh release create` into the same flow so releases are cut entirely from the laptop with a single confirmation gate. The redundant `.github/workflows/publish.yml` CI workflow was removed.

### Removed

- **`agent-kg`, `ftree-kg`, `memory-kg` removed from `kg` and `all` extras** (`pyproject.toml`) — These git-only packages are no longer listed in optional extras. Install directly from their git repositories when needed.
- **testpypi supplemental source removed** (`pyproject.toml`) — No longer needed now that `pycode-kg` is on PyPI.
- **`.github/workflows/publish.yml` removed** — Tag-triggered CI build/release workflow superseded by the repaired `/release` command, which now does `poetry build` + `gh release create` locally.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
