---
mode: 'agent'
description: 'Set up the CodeKG MCP server for a target repository and configure it for GitHub Copilot and other clients.'
---

# CodeKG MCP Setup & Verification

Set up the CodeKG MCP server for a target repository and configure it for use with GitHub Copilot (VS Code), Claude Code, and/or Claude Desktop. Execute the following steps in sequence.

## Command Argument Handling

**Usage:**
- No argument — Interactive mode; prompts for the target repository path
- With path argument — Set up CodeKG MCP for the specified repository

---

## Step 0: Resolve the Target Repository

1. If a path argument was provided, use it as `REPO_ROOT`.
2. If no argument was provided, ask the user:
   > "Which repository do you want to index? Please provide the absolute path."
3. Verify the path exists and contains at least one `.py` file:
   ```bash
   find "$REPO_ROOT" -name "*.py" -not -path "*/.venv/*" -not -path "*/__pycache__/*" | head -5
   ```
4. If no Python files are found, stop and report the issue.

All artifact paths use the defaults relative to `REPO_ROOT`:
- `DB_PATH` → `$REPO_ROOT/.codekg/graph.sqlite`
- `LANCEDB_DIR` → `$REPO_ROOT/.codekg/lancedb`

Do not pass `--db` or `--lancedb` flags — the commands default to `.codekg/` automatically.

---

## Step 1: Verify CodeKG Installation

1. Check that the `codekg-mcp` entry point is available:
   ```bash
   which codekg-mcp
   ```
2. If not found, try `poetry run which codekg-mcp`.
3. If the package is missing, instruct the user to install it:
   ```bash
   poetry add "code-kg[mcp]"
   ```
   Then stop — the user must install before continuing.

4. Confirm the `mcp` Python package is importable:
   ```bash
   python -c "import mcp; print('mcp OK')"
   ```
   If this fails, report the error and stop.

---

## Step 2: Build the Knowledge Graph (SQLite)

1. Check whether `DB_PATH` already exists:
   ```bash
   ls -lh "$REPO_ROOT/.codekg/graph.sqlite" 2>/dev/null
   ```
2. If it exists, ask the user:
   > "A knowledge graph already exists. Rebuild it from scratch (wipe), or keep the existing graph?"
   - **Wipe**: proceed with `--wipe`
   - **Keep**: skip to Step 3

3. Run the static analysis build:
   ```bash
   codekg-build-sqlite --repo "$REPO_ROOT" --wipe
   ```
4. Verify the database was created and is non-empty:
   ```bash
   sqlite3 "$REPO_ROOT/.codekg/graph.sqlite" "SELECT COUNT(*) FROM nodes; SELECT COUNT(*) FROM edges;"
   ```
5. Report the node and edge counts.

---

## Step 3: Build the Semantic Index (LanceDB)

1. Check whether `LANCEDB_DIR` already exists and is non-empty.
2. Run the embedding build:
   ```bash
   codekg-build-lancedb --repo "$REPO_ROOT" --wipe
   ```
3. Confirm the LanceDB directory was populated:
   ```bash
   ls -lh "$REPO_ROOT/.codekg/lancedb"
   ```

---

## Step 4: Smoke-Test the Query Pipeline

1. Run a graph stats check:
   ```bash
   python -c "
   from code_kg import CodeKG
   kg = CodeKG(repo_root='$REPO_ROOT')
   import json; print(json.dumps(kg.stats(), indent=2))
   "
   ```

2. Run a sample query:
   ```bash
   cd "$REPO_ROOT" && codekg-query "module structure"
   ```

3. If either command errors, diagnose and report the issue before proceeding.

---

## Step 5: Configure MCP Clients

### MCP config by agent — quick reference

| Agent | Config file | Per-repo? | Key name |
|-------|-------------|-----------|----------|
| **GitHub Copilot** | `.vscode/mcp.json` | ✅ Yes | `"servers"` |
| **Kilo Code** | `.mcp.json` (project root) | ✅ Yes | `"mcpServers"` |
| **Claude Code** | `.mcp.json` (project root) | ✅ Yes | `"mcpServers"` |
| **Cline** | `~/...saoudrizwan.claude-dev/settings/cline_mcp_settings.json` | ❌ Global only | `"mcpServers"` |
| **Claude Desktop** | `~/Library/Application Support/Claude/claude_desktop_config.json` | ❌ Global only | `"mcpServers"` |

> ⚠️ **Do NOT add `codekg` to any global settings file.** Global files are shared across all windows — hardcoded paths will point every window to the same repo. Use per-repo config files instead.

### 5a: GitHub Copilot (.vscode/mcp.json)

```json
{
  "servers": {
    "codekg": {
      "type": "stdio",
      "command": "poetry",
      "args": ["run", "codekg-mcp", "--repo", "<REPO_ROOT>"],
      "env": { "POETRY_VIRTUALENVS_IN_PROJECT": "false" }
    }
  }
}
```

Merge into the existing `servers` object — do not overwrite other entries. After saving, VS Code will prompt you to trust the MCP server.

### 5b: Kilo Code / Claude Code (.mcp.json)

```json
"codekg": {
  "command": "poetry",
  "args": ["run", "codekg-mcp", "--repo", "<REPO_ROOT>"],
  "env": { "POETRY_VIRTUALENVS_IN_PROJECT": "false" }
}
```

### 5c: Claude Desktop

Get the venv binary path:
```bash
poetry env info --path
```

Use `<venv_path>/bin/codekg-mcp` as the command (no `poetry run` needed).

### 5d: Install the CodeKG Skill (Global)

```bash
bash <CODE_KG_REPO>/scripts/install-skill.sh
```

---

## Step 6: Final Report

```
✓ Repository indexed:   <REPO_ROOT>
✓ SQLite graph:         <N> nodes, <M> edges
✓ LanceDB index:        <V> vectors
✓ Smoke test:           passed
✓ MCP configs updated

Restart VS Code / Claude Desktop to activate the codekg MCP server.

Available MCP tools once active:
  • graph_stats()          — codebase size and shape
  • query_codebase(q)      — semantic + structural exploration
  • pack_snippets(q)       — source-grounded code snippets
  • get_node(node_id)      — single node metadata lookup
  • callers(node_id)       — find all callers of a function
```

---

## Important Rules

- **Do NOT modify source files** in the target repository.
- **Do NOT run `git commit`** or any destructive git operations.
- Use **absolute paths** for `--repo` flags — relative paths will break MCP clients.
- If any step fails, stop and report the error clearly before proceeding.
