# Pre-Commit & Snapshot Refactor

Covers changes across `Metabo_kg`, `code_kg`, and `doc_kg`.

---

## 1. Pre-commit hook (`Metabo_kg/.git/hooks/pre-commit`)

Created from scratch, following `code_kg`'s pattern.

**Sequence:**
1. Delegates to `.pre-commit-config.yaml` via the venv `pre-commit` binary (ruff, mypy, detect-secrets, etc.)
2. Rebuilds CodeKG index with `--wipe`
3. Snapshots CodeKG → stages `.codekg/snapshots/`
4. Snapshots MetaboKG (if `.metabokg/meta.sqlite` exists) → stages `.metabokg/snapshots/`
5. Snapshots DocKG (if `.dockg/` exists) → stages `.dockg/snapshots/`

Skip hook entirely with `CODEKG_SKIP_SNAPSHOT=1 git commit`.

---

## 2. `.pre-commit-config.yaml` (Metabo_kg)

| Change | Before | After |
|--------|--------|-------|
| Poetry paths | `/Users/egs/.local/bin/poetry run ...` | `poetry run ...` |
| `check-added-large-files` exclude | named `.codekg/` only | `^\.[^/]+/` — all hidden dirs |
| `detect-secrets` exclude | `.secrets.baseline` only | adds `--exclude-files '^\.[^/]+/'` |

The pattern `^\.[^/]+/` matches any hidden directory (`.codekg/`, `.metabokg/`, `.dockg/`, `.git/`, etc.) without accidentally excluding root-level hidden files like `.pre-commit-config.yaml`.

---

## 3. `metabokg build` — flipped `--wipe` default

Aligned with `codekg build` behaviour: no wipe by default, opt-in with `--wipe`.

| | Before | After |
|--|--------|-------|
| Default | wipe before build | keep existing data |
| Opt-out flag | `--no-wipe` | _(removed)_ |
| Opt-in flag | _(none)_ | `--wipe` |

Changed in `src/metabokg/cli/options.py` (`wipe_option`) and updated docstring in `cmd_build.py`.

---

## 4. Snapshot version auto-detection (all three repos)

Previously, snapshot version was passed from the hook via a `pyproject.toml` grep — fragile and external to the libraries.

**New behaviour:** each library detects its own installed package version via `importlib.metadata`.

### Changes per repo

**`src/metabokg/snapshots.py`** / **`src/code_kg/snapshots.py`** / **`src/doc_kg/snapshots.py`:**
- Added `_package_version()` helper using `importlib.metadata.version("<package>")`
- `SnapshotManager.capture(version=None)` — auto-detects if not supplied
- `Snapshot.version` moved after required fields, given `default=""` for backward compat with old JSON
- `Snapshot.from_dict()` — `data.setdefault("version", "")` for legacy snapshots

**CLI `snapshot save` commands (all three repos):**
- `VERSION` positional argument changed from required to `required=False, default=""`
- Removed `importlib.metadata` lookup from `cmd_snapshot.py` (now lives in `snapshots.py`)

**Hooks:**
- `Metabo_kg/.git/hooks/pre-commit` — version arg dropped from all three `snapshot save` calls; `VERSION=` grep removed
- `code_kg/.git/hooks/pre-commit` — version arg dropped from `codekg snapshot save`

---

## Files changed

| File | Repo |
|------|------|
| `.git/hooks/pre-commit` | `Metabo_kg` _(created)_, `code_kg` |
| `.pre-commit-config.yaml` | `Metabo_kg` |
| `src/metabokg/cli/options.py` | `Metabo_kg` |
| `src/metabokg/cli/cmd_build.py` | `Metabo_kg` |
| `src/metabokg/snapshots.py` | `Metabo_kg` |
| `src/metabokg/cli/cmd_snapshot.py` | `Metabo_kg` |
| `src/code_kg/snapshots.py` | `code_kg` |
| `src/code_kg/cli/cmd_snapshot.py` | `code_kg` |
| `src/doc_kg/snapshots.py` | `doc_kg` |
| `src/doc_kg/cli/cmd_snapshot.py` | `doc_kg` |
| `CLAUDE.md` | `Metabo_kg` |
