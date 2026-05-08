# MetaboKG Installation Reference

## Table of Contents
1. [CLI Flags Reference](#cli-flags-reference)
2. [Agent Config Matrix](#agent-config-matrix)
3. [MCP Config Templates](#mcp-config-templates)
4. [Data Download Scripts](#data-download-scripts)
5. [Gitignore Recommendations](#gitignore-recommendations)
6. [Smoke-Test Commands](#smoke-test-commands)
7. [Full Troubleshooting Table](#full-troubleshooting-table)

---

## CLI Flags Reference

### `metabokg-init`

| Flag | Default | Description |
|---|---|---|
| `--check` | false | Status-only — show TSV integrity and corpus build state without modifying anything |
| `--corpus NAME` | all | Initialize a single corpus; repeatable (`--corpus hsa --corpus cge`) |
| `--no-enrich` | false | Skip enrichment phases |
| `--no-index` | false | Skip LanceDB build |

### `metabokg-info`

No required flags. Prints the active corpus, resolved db/lancedb paths, and node/edge counts.

### `metabokg-build`

| Flag | Default | Description |
|---|---|---|
| `--data DIR` | required | Directory containing KGML pathway files or SBML model |
| `--db PATH` | `<data-dir>/.metabokg/<name>.sqlite` | Override SQLite output path |
| `--lancedb PATH` | `<data-dir>/.metabokg/lancedb/` | Override LanceDB output path |
| `--no-wipe` | wipe by default | Keep existing data — merge new files on top |
| `--no-index` | false | Skip LanceDB — SQLite only |
| `--no-enrich` | false | Skip all enrichment phases |

### `metabokg-update`

| Flag | Default | Description |
|---|---|---|
| `--data DIR` | required | Directory of new files to ingest incrementally |
| `--db PATH` | auto-resolved | Existing SQLite to extend |

### `metabokg-enrich`

| Flag | Default | Description |
|---|---|---|
| `--db PATH` | auto-resolved | SQLite db to enrich |
| `--phases LIST` | all | Comma-separated phase names to run |

### `metabokg-mcp`

| Flag | Default | Description |
|---|---|---|
| `--repo PATH` | `.` | Repository root |
| `--db PATH` | `.metabokg/hsa.sqlite` | SQLite path |
| `--lancedb PATH` | `.metabokg/lancedb` | LanceDB directory |
| `--transport` | `stdio` | `stdio` or `sse` |

### `metabokg-query`

| Flag | Default | Description |
|---|---|---|
| `QUERY` | required | Search string |
| `--k INT` | `8` | Number of results |
| `--hop INT` | `1` | Graph expansion hops |
| `--text-only` | false | Skip vector search, substring only |
| `--db PATH` | auto-resolved | SQLite path |
| `--lancedb PATH` | auto-resolved | LanceDB path |

### `metabokg-pack`

| Flag | Default | Description |
|---|---|---|
| `QUERY` | required | Search string |
| `--k INT` | `8` | Number of results |
| `--hop INT` | `1` | Graph expansion hops |
| `--format` | `markdown` | `markdown` or `json` |

### `metabokg-simulate`

| Subcommand | Required | Key flags |
|---|---|---|
| `fba --pathway ID` | pathway ID | `--maximize`, `--db`, `--lancedb` |
| `ode --pathway ID` | pathway ID | `--t-end`, `--t-points`, `--method BDF\|Radau`, `--rtol`, `--atol`, `--db` |
| `whatif --pathway ID --scenario JSON` | pathway + scenario | `--mode fba\|ode`, `--db` |
| `seed` | — | `--db`, `--force` |
| `seed-cho` | — | `--db`, `--force` |

### `metabokg-analyze` / `metabokg-analyze-basic`

| Flag | Default | Description |
|---|---|---|
| `--output FILE` | stdout | Write report to file |
| `--db PATH` | auto-resolved | SQLite path |

### `metabokg-snapshot`

| Subcommand | Purpose |
|---|---|
| `save <version>` | Capture metrics snapshot (commit, branch, version) |
| `list` | List all snapshots in reverse chronological order |
| `show <id>` | Full details for one snapshot |
| `diff <a> <b>` | Side-by-side comparison |

### `metabokg-viz` / `metabokg-viz3d`

| Flag | Default | Description |
|---|---|---|
| `--port INT` | `8500` (viz) | Streamlit port |
| `--layout` | `allium` (viz3d) | `allium` or `cake` |
| `--width INT` | 1200 | 3D window width |
| `--height INT` | 800 | 3D window height |
| `--db PATH` | auto-resolved | SQLite path |

---

## Agent Config Matrix

| Agent | Config file | Key | Per-repo? |
|---|---|---|---|
| **Claude Code** | `.mcp.json` (project root) | `"mcpServers"` | ✅ Yes |
| **Kilo Code** | `.mcp.json` (project root) | `"mcpServers"` | ✅ Yes |
| **GitHub Copilot** | `.vscode/mcp.json` (workspace root) | `"servers"` | ✅ Yes |
| **Claude Desktop** | `~/Library/Application Support/Claude/claude_desktop_config.json` | `"mcpServers"` | ❌ Global |
| **Cline** | `~/...saoudrizwan.claude-dev/settings/cline_mcp_settings.json` | `"mcpServers"` | ❌ Global only |

> Use a uniquely-named Cline entry per repo (e.g. `metabokg-myproject`) to avoid collisions.

---

## MCP Config Templates

### Claude Code / Kilo Code (`.mcp.json`)

```json
{
  "mcpServers": {
    "metabokg": {
      "command": "metabokg",
      "args": [
        "mcp",
        "--repo", "/absolute/path/to/repo"
      ]
    }
  }
}
```

### GitHub Copilot (`.vscode/mcp.json`)

```json
{
  "servers": {
    "metabokg": {
      "type": "stdio",
      "command": "metabokg",
      "args": [
        "mcp",
        "--repo", "/absolute/path/to/repo",
        "--db",   "/absolute/path/to/repo/data/hsa_pathways/.metabokg/hsa.sqlite"
      ]
    }
  }
}
```

### Cline (`cline_mcp_settings.json`)

```json
{
  "mcpServers": {
    "metabokg-myrepo": {
      "command": "metabokg",
      "args": [
        "mcp",
        "--repo", "/absolute/path/to/repo",
        "--db",   "/absolute/path/to/repo/data/hsa_pathways/.metabokg/hsa.sqlite"
      ]
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

Claude Desktop has no Poetry on PATH — use the absolute venv binary:

```bash
poetry env info --path
# → /path/to/venv  (binary at /path/to/venv/bin/metabokg)
```

```json
{
  "mcpServers": {
    "metabokg": {
      "command": "/path/to/venv/bin/metabokg",
      "args": [
        "mcp",
        "--repo", "/abs/path",
        "--db",   "/abs/path/data/hsa_pathways/.metabokg/hsa.sqlite"
      ]
    }
  }
}
```

---

## Data Download Scripts

All source data is bundled in the repo (`data/hsa_pathways/`, `data/cge_pathways/`, `data/icho_model/*.xml`, all `data/*.tsv`). TSV annotation files are fetched automatically by `metabokg-init` if missing.

Scripts below are for **refreshing pathway files** only (e.g. after a KEGG update):

| Script | Purpose | Output |
|---|---|---|
| `scripts/download_human_kegg.py` | Re-download hsa KGML files | `data/hsa_pathways/*.kgml` |
| `scripts/download_cho_kegg.py` | Re-download cge KGML files | `data/cge_pathways/*.kgml` |
| `scripts/download_icho_model.py` | Re-download iCHO2441 SBML | `data/icho_model/*.xml` |
| `scripts/download_kegg_names.py` | Compound + reaction name lists | `data/kegg_compound_names.tsv`, `data/kegg_reaction_names.tsv` |
| `scripts/download_kegg_names.py --genes hsa cge` | Enzyme gene name lists | `data/hsa_gene_names.tsv`, `data/cge_gene_names.tsv` |
| `scripts/download_kegg_reactions.py` | Reaction detail + EC numbers | `data/kegg_reaction_detail.tsv` |
| `scripts/fetch_sabio_cho_kinetics.py` | *Cricetulus griseus* kinetics from SABIO-RK (credentials needed) | `data/sabio_cho_kinetics.tsv` |

---

## Gitignore Recommendations

```gitignore
# MetaboKG build artifacts (reproducible)
**/.metabokg/*.sqlite
**/.metabokg/lancedb/

# Snapshots are tracked — do NOT ignore:
# **/.metabokg/snapshots/
```

---

## Smoke-Test Commands

```bash
# Verify env
metabokg-info

# Verify build (fast, no LanceDB or enrichment)
metabokg-build --data data/hsa_pathways --no-index --no-enrich
# → should complete in < 60s

# Verify query
metabokg-query "glycolysis" --k 3

# Verify pack
metabokg-pack "TCA cycle" --k 4

# Verify MCP server starts
metabokg-mcp --repo . &
sleep 2 && kill %1

# Verify FBA
metabokg-simulate fba --pathway pwy:kegg:hsa00010

# Verify ODE (must be BDF, not RK45)
metabokg-simulate ode --pathway pwy:kegg:hsa00010 --t-end 5 --t-points 10 --method BDF
```

---

## Full Troubleshooting Table

| Error | Cause | Fix |
|---|---|---|
| ODE simulation hangs indefinitely | RK45 solver on stiff metabolic network | Set `ode_method="BDF"` or `"Radau"` |
| `--knockout Ldha` raises KeyError | Phase 3 enrichment not run | `metabokg-init` (fetches gene name TSVs and rebuilds) |
| Enzyme names show as bare integers | `data/{org}_gene_names.tsv` missing | `metabokg-init`, or manually `python scripts/download_kegg_names.py --genes hsa cge` |
| Glycan nodes unresolved (`gl:G#####`) | `data/kegg_glycan_names.tsv` missing | `metabokg-init`, or `python scripts/download_kegg_names.py` |
| Empty vector query results | LanceDB index missing or empty | `metabokg-build --data DIR` (do NOT use `--no-index`) |
| Wrong DB loaded | Multiple corpora in repo | Use explicit `--db` pointing to the correct `.sqlite` |
| MCP server not appearing in agent | Relative path in config | Switch to absolute paths; reload VS Code |
| `mcp package not found` | `[mcp]` extra not installed | `poetry install --all-extras` |
| `detect-secrets` pre-commit failure | API key or token in staged file | Run `detect-secrets scan --update .secrets.baseline` |
| Large file pre-commit failure | KGML or TSV > 1 MB | Already excluded — check `.pre-commit-config.yaml` exclude pattern |
| `metabokg-init --check` reports missing TSVs | TSV download script never ran | Run `metabokg-init` (auto-fetches) or run a `scripts/download_*.py` directly |
