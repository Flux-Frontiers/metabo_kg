# Release Workflow

You will create a new versioned release of MetaboKG by promoting the `[Unreleased]` section of `CHANGELOG.md` into a dated version entry, committing the changes, tagging the commit, building the wheel and sdist, pushing the tag, and creating the GitHub Release with the build artifacts attached. Execute the following steps in sequence.

This command does **everything locally** — no CI workflow runs. The repo does not publish to PyPI; the only output is a GitHub Release page with attached `dist/*` artifacts.

**Release-notes policy:** the GitHub Release page is the only place release notes are published. We do **not** keep a `release-notes.md` file in the repo — the per-file CHANGELOG is the audit trail, and the GitHub Release body is auto-generated from commits/PRs via `--generate-notes`. Do not create or commit a `release-notes.md` file.

---

## Step 0: Gather Release Context

1. Read `CHANGELOG.md` in full.
2. Read `pyproject.toml` and `src/metabokg/__init__.py` to find the current version string.
3. Run `git status` and `git log --oneline -10` to understand the state of the working tree. The tree must be clean — abort and tell the user if it is not.
4. Confirm there is content under `## [Unreleased]`; if the section is empty, stop and tell the user there is nothing to release.
5. Verify `gh auth status` shows an authenticated session — abort with a clear message if not.

---

## Step 1: Determine the New Version

1. Parse the current version from `pyproject.toml` (e.g. `0.8.0`).
2. Ask the user which semver component to bump — **patch**, **minor**, or **major** — unless they already specified it in their message (e.g. `/release minor`).
3. Compute the new version string (e.g. `0.8.0` → `0.8.1` for patch).
4. Confirm the new tag will be `v<new_version>` (e.g. `v0.8.1`).

---

## Step 2: Update CHANGELOG.md

1. Replace `## [Unreleased]` with `## [<new_version>] - <today's date in YYYY-MM-DD>`.
2. Insert a fresh `## [Unreleased]` section with empty `### Added`, `### Changed`, `### Removed`, `### Fixed` subsections **above** the newly-versioned section.
3. Write the updated file.

---

## Step 3: Bump the Version in Source Files

Update the version string in **both** of the following files:

- `pyproject.toml` — the `version = "..."` field under `[tool.poetry]`
- `src/metabokg/__init__.py` — the `__version__` assignment

Set both to the new version string (without the `v` prefix).

---

## Step 4: Update Version Badge in README.md

In `README.md`, find the version badge line:

```
[![Version](https://img.shields.io/badge/version-<current_version>-blue.svg)](https://github.com/flux-frontiers/metabo_kg/releases)
```

Replace `<current_version>` with `<new_version>`.

---

## Step 5: Generate Versioned PyCodeKG Analysis

1. Rebuild the PyCodeKG index against the current source:
   ```bash
   poetry run pycodekg-build-sqlite --repo . --wipe
   poetry run pycodekg-build-lancedb --repo . --wipe
   ```
2. Run the architectural analysis (repo path is positional, not a flag):
   ```bash
   poetry run pycodekg-analyze . --output docs/analysis_v<new_version>.md --quiet
   ```
3. Open `docs/analysis_v<new_version>.md` and ensure the header contains:
   ```
   **Version:** <new_version>
   **Generated:** <today's date in YYYY-MM-DD>
   ```
   Add or update these fields if missing.
4. Delete any previous `docs/analysis_v<old_version>.md` if it exists and differs from the new version (`git rm docs/analysis_v<old_version>.md`).

> Note: the bulk of `.pycodekg/` is gitignored (lancedb, sqlite, models), so the rebuild itself produces no staged changes. Only the `docs/analysis_v<new_version>.md` artifact is committed.

---

## Step 5: Commit the Release Files

1. Stage the following files:
   - `CHANGELOG.md`
   - `pyproject.toml`
   - `src/metabokg/__init__.py`
   - `README.md`
   - `docs/analysis_v<new_version>.md` (and any `git rm` of an old analysis)
2. Create a commit with message:
   ```
   chore(release): v<new_version>

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   ```

---

## Step 7: Create the Git Tag

Run:
```bash
git tag -a v<new_version> -m "v<new_version>"
```

---

## Step 8: Build the Distribution

```bash
poetry build
```

Verify the artifacts look correct:
```bash
ls -lh dist/
```

You should see a `.whl` and a `.tar.gz` matching the new version. If `dist/` contains stale artifacts from previous releases, scope the artifact glob in Step 9 to the new version (`dist/metabo_kg-<new_version>.*`) rather than `dist/*`.

---

## Step 9: Confirm and Publish

**Before publishing**, display a summary and ask the user to confirm. Everything before this step is local and reversible; this step makes the release public.

> Ready to push tag `v<new_version>` and create the GitHub Release with the new-version artifacts attached? (yes / no)

If confirmed, run in sequence:

```bash
git push origin main
git push origin v<new_version>
gh release create v<new_version> \
  dist/metabo_kg-<new_version>.tar.gz dist/metabo_kg-<new_version>-py3-none-any.whl \
  --title "MetaboKG v<new_version>" \
  --generate-notes
```

The `--generate-notes` flag tells GitHub to auto-build the release body from commits/PRs since the previous tag. We deliberately do not maintain a `release-notes.md` file in the repo — the GitHub Release page is the only place release notes are published. If you want to edit the auto-generated body, do it on the Release page after creation, or add `--notes-from-tag` and write the body into the annotated tag message at Step 7.

If `gh release create` reports the release already exists (e.g. from a previous attempt), upload assets to the existing release instead:

```bash
gh release upload v<new_version> \
  dist/metabo_kg-<new_version>.tar.gz dist/metabo_kg-<new_version>-py3-none-any.whl --clobber
```

If the user declines, tell them they can publish later with the same three commands (push branch, push tag, create release).

---

## Completion

After all steps succeed, print a summary:

```
✓ CHANGELOG.md promoted [Unreleased] → [<new_version>] - <date>
✓ pyproject.toml + src/metabokg/__init__.py bumped to <new_version>
✓ README.md badge updated to <new_version>
✓ docs/analysis_v<new_version>.md generated
✓ Commit created
✓ Tag v<new_version> created
✓ dist/ built (wheel + sdist)
✓ Branch + tag pushed to origin
✓ GitHub Release created with artifacts   (or: ready to publish manually)
```

Include the GitHub Release URL from `gh release view v<new_version> --json url -q .url` if the release was created.
