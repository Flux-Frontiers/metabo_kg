#!/usr/bin/env bash
# =============================================================================
# install-skill.sh — Bootstrap the metakg AI integration layer
#
# Installs SKILL.md reference files and the /metakg slash command for AI agents,
# then configures MCP server integration for the specified providers.
#
# Supported providers:
#   claude   — Claude Code  (.claude/claude_code_config.json)
#   kilo     — Kilo Code    (.mcp.json, shared with Claude Code)
#   copilot  — GitHub Copilot (.vscode/mcp.json)
#   cline    — Cline        (.claude/commands/metakg.md slash command)
#
# Usage (from a target repo, no clone needed):
#   curl -fsSL https://raw.githubusercontent.com/Flux-Frontiers/meta_kg/main/scripts/install-skill.sh | bash
#
# With provider selection:
#   curl -fsSL .../install-skill.sh | bash -s -- --providers all
#   curl -fsSL .../install-skill.sh | bash -s -- --providers claude,copilot
#   bash scripts/install-skill.sh --providers kilo,cline
#
# Flags:
#   --providers <list>   Comma-separated provider names, or "all" (default: all)
#   --wipe               Force rebuild of SQLite graph and LanceDB index
#   --dry-run            Print what would be done without making any changes
#
# What it does:
#   1. Creates skill directories for Claude Code, Kilo Code, and other agents
#      and installs SKILL.md + references/installation.md into each
#   2. Installs Claude Code slash commands (metakg, metakg-rebuild) to ~/.claude/commands/
#   3. Installs the /metakg slash command into the target repo for Cline
#   4. Installs code-kg[mcp] if metakg is not found:
#        a. pip install from latest GitHub release wheel (preferred, no git needed)
#        b. pip install from git+https (fallback, needs git)
#        c. poetry add (fallback for Poetry-managed repos)
#   5. Builds the SQLite knowledge graph (skips if already present, unless --wipe)
#   6. Builds the LanceDB vector index  (skips if already present, unless --wipe)
#   7. Writes provider MCP configs as requested
#   8. Prints a final summary
#
# Author: Eric G. Suchanek, PhD
# Last Revision: 2026-03-02 09:45:06
# =============================================================================

set -eo pipefail

# ── Parse arguments ───────────────────────────────────────────────────────────
PROVIDERS_ARG="all"
WIPE_FLAG=""
DRY_RUN=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --providers)
            PROVIDERS_ARG="${2:-all}"
            shift 2
            ;;
        --providers=*)
            PROVIDERS_ARG="${1#*=}"
            shift
            ;;
        --wipe)
            WIPE_FLAG="1"
            shift
            ;;
        --dry-run)
            DRY_RUN="1"
            shift
            ;;
        *)
            echo "Unknown flag: $1"
            echo "Usage: $0 [--providers all|claude,kilo,copilot,cline] [--wipe] [--dry-run]"
            exit 1
            ;;
    esac
done

# Run a command, or in dry-run mode just print what would be executed.
_exec() {
    if [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] $*"
    else
        "$@"
    fi
}

# Normalise to a set of boolean flags
DO_CLAUDE=0; DO_KILO=0; DO_COPILOT=0; DO_CLINE=0

_enable_provider() {
    case "$1" in
        all)    DO_CLAUDE=1; DO_KILO=1; DO_COPILOT=1; DO_CLINE=1 ;;
        claude) DO_CLAUDE=1 ;;
        kilo)   DO_KILO=1 ;;
        copilot)DO_COPILOT=1 ;;
        cline)  DO_CLINE=1 ;;
        *)
            echo "Unknown provider: $1  (valid: all, claude, kilo, copilot, cline)"
            exit 1
            ;;
    esac
}

IFS=',' read -ra _PLIST <<< "$PROVIDERS_ARG"
for _p in "${_PLIST[@]}"; do
    _enable_provider "$(echo "$_p" | tr -d ' ')"
done

REPO="Flux-Frontiers/meta_kg"
BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"

# Install to Claude Code, Kilo Code, and other agent skill directories
SKILL_DIRS=(
    "${HOME}/.claude/skills/metakg"
    "${HOME}/.kilocode/skills/metakg"
    "${HOME}/.agents/skills/metakg"
)

# Global Claude Code command files to install to ~/.claude/commands/
CLAUDE_COMMAND_FILES=(
    "metakg.md"
    "metakg-rebuild.md"
    "setup-mcp.md"
)

# ── Detect if we're running from inside the repo ─────────────────────────────
# BASH_SOURCE[0] is unbound when piped via curl | bash.
# Use ${BASH_SOURCE:-} (no array index) which is safe even when unset.
_BASH_SOURCE="${BASH_SOURCE:-}"
if [ -n "$_BASH_SOURCE" ] && [ "$_BASH_SOURCE" != "bash" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$_BASH_SOURCE")" && pwd)"
    REPO_ROOT="$(dirname "$SCRIPT_DIR")"
else
    # Running via curl | bash — no local clone available
    SCRIPT_DIR=""
    REPO_ROOT=""
fi
LOCAL_SKILL="${REPO_ROOT:+${REPO_ROOT}/.claude/skills/metakg/SKILL.md}"

# The target repo is where the user ran the script from (CWD).
TARGET_REPO="${PWD}"
SQLITE_DB="${TARGET_REPO}/.metakg/graph.sqlite"
LANCEDB_DIR="${TARGET_REPO}/.metakg/lancedb"

echo "╔══════════════════════════════════════════════════╗"
echo "║       MetaKG Integration Installer               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
[ -n "$DRY_RUN" ] && echo "  *** DRY RUN — no changes will be made ***"
echo "  Target repo: ${TARGET_REPO}"
_PNAMES=""
[ "$DO_CLAUDE"  = "1" ] && _PNAMES="${_PNAMES} claude"
[ "$DO_KILO"    = "1" ] && _PNAMES="${_PNAMES} kilo"
[ "$DO_COPILOT" = "1" ] && _PNAMES="${_PNAMES} copilot"
[ "$DO_CLINE"   = "1" ] && _PNAMES="${_PNAMES} cline"
echo "  Providers:   ${_PNAMES# }"
echo ""

# ── Step 1: Install skill files to agent directories ─────────────────────────
echo "── Step 1: Installing skill files ──────────────────"
echo ""

for SKILL_DIR in "${SKILL_DIRS[@]}"; do
    REFS_DIR="${SKILL_DIR}/references"
    _exec mkdir -p "$SKILL_DIR"
    _exec mkdir -p "$REFS_DIR"

    if [ -f "$LOCAL_SKILL" ]; then
        if [ "${FIRST_RUN:-1}" = "1" ]; then
            echo "→ Local repo detected at: $REPO_ROOT"
            echo "  Copying skill files from local clone..."
            FIRST_RUN=0
        fi
        _exec cp "${REPO_ROOT}/.claude/skills/metakg/SKILL.md" "${SKILL_DIR}/SKILL.md"
        _exec cp "${REPO_ROOT}/.claude/skills/metakg/references/installation.md" "${REFS_DIR}/installation.md"
    else
        if [ "${FIRST_RUN:-1}" = "1" ]; then
            echo "→ No local clone detected. Downloading from GitHub..."
            FIRST_RUN=0
        fi
        if [ -n "$DRY_RUN" ]; then
            echo "  [dry-run] would download ${RAW_BASE}/.claude/skills/metakg/SKILL.md → ${SKILL_DIR}/SKILL.md"
            echo "  [dry-run] would download ${RAW_BASE}/.claude/skills/metakg/references/installation.md → ${REFS_DIR}/installation.md"
        elif command -v curl &>/dev/null; then
            curl -fsSL "${RAW_BASE}/.claude/skills/metakg/SKILL.md" -o "${SKILL_DIR}/SKILL.md"
            curl -fsSL "${RAW_BASE}/.claude/skills/metakg/references/installation.md" -o "${REFS_DIR}/installation.md"
        elif command -v wget &>/dev/null; then
            wget -q "${RAW_BASE}/.claude/skills/metakg/SKILL.md" -O "${SKILL_DIR}/SKILL.md"
            wget -q "${RAW_BASE}/.claude/skills/metakg/references/installation.md" -O "${REFS_DIR}/installation.md"
        else
            echo "ERROR: Neither curl nor wget found. Install one and retry."
            exit 1
        fi
    fi

    # Verify (skip in dry-run — files may not exist yet)
    if [ -z "$DRY_RUN" ]; then
        if [ ! -f "${SKILL_DIR}/SKILL.md" ] || [ ! -f "${REFS_DIR}/installation.md" ]; then
            echo "ERROR: Installation failed for ${SKILL_DIR}"
            exit 1
        fi
    fi

    echo "  ✓ ${SKILL_DIR}/SKILL.md"
    echo "  ✓ ${REFS_DIR}/installation.md"
done

# ── Step 2: Install Claude Code commands to ~/.claude/commands/ ───────────────
echo ""
echo "── Step 2: Installing Claude Code commands ──────────"
echo ""

CLAUDE_CMD_DIR="${HOME}/.claude/commands"
_exec mkdir -p "$CLAUDE_CMD_DIR"

for _CMD_FILE in "${CLAUDE_COMMAND_FILES[@]}"; do
    _DST="${CLAUDE_CMD_DIR}/${_CMD_FILE}"
    _LOCAL_CMD="${REPO_ROOT:+${REPO_ROOT}/.claude/commands/${_CMD_FILE}}"

    if [ -n "$_LOCAL_CMD" ] && [ -f "$_LOCAL_CMD" ]; then
        _exec cp "$_LOCAL_CMD" "$_DST"
        echo "  ✓ Copied from local repo → ${_DST}"
    else
        if [ -n "$DRY_RUN" ]; then
            echo "  [dry-run] would download ${RAW_BASE}/.claude/commands/${_CMD_FILE} → ${_DST}"
        elif command -v curl &>/dev/null; then
            curl -fsSL "${RAW_BASE}/.claude/commands/${_CMD_FILE}" -o "$_DST"
            echo "  ✓ Downloaded → ${_DST}"
        elif command -v wget &>/dev/null; then
            wget -q "${RAW_BASE}/.claude/commands/${_CMD_FILE}" -O "$_DST"
            echo "  ✓ Downloaded → ${_DST}"
        else
            echo "  ⚠ Neither curl nor wget found — skipping ${_CMD_FILE}"
        fi
    fi
done

# ── Step 3: Install Cline slash command into the target repo ──────────────────
echo ""
echo "── Step 3: Installing Cline slash command ───────────"
echo ""

if [ "$DO_CLINE" = "1" ]; then
    CLINE_CMD_DIR="${TARGET_REPO}/.claude/commands"
    CLINE_CMD_FILE="${CLINE_CMD_DIR}/metakg.md"
    _LOCAL_CMD="${REPO_ROOT:+${REPO_ROOT}/.claude/commands/metakg.md}"

    _exec mkdir -p "$CLINE_CMD_DIR"

    if [ -f "$CLINE_CMD_FILE" ]; then
        echo "  ✓ ${CLINE_CMD_FILE} already exists — skipping"
    elif [ -n "$_LOCAL_CMD" ] && [ -f "$_LOCAL_CMD" ]; then
        _exec cp "$_LOCAL_CMD" "$CLINE_CMD_FILE"
        echo "  ✓ Copied from local repo → ${CLINE_CMD_FILE}"
    else
        # Download from GitHub
        if [ -n "$DRY_RUN" ]; then
            echo "  [dry-run] would download ${RAW_BASE}/.claude/commands/metakg.md → ${CLINE_CMD_FILE}"
        elif command -v curl &>/dev/null; then
            curl -fsSL "${RAW_BASE}/.claude/commands/metakg.md" -o "$CLINE_CMD_FILE"
            echo "  ✓ Downloaded → ${CLINE_CMD_FILE}"
        elif command -v wget &>/dev/null; then
            wget -q "${RAW_BASE}/.claude/commands/metakg.md" -O "$CLINE_CMD_FILE"
            echo "  ✓ Downloaded → ${CLINE_CMD_FILE}"
        else
            echo "  ⚠ Neither curl nor wget found — skipping Cline command install"
        fi
    fi
else
    echo "  – Skipped (cline not selected)"
fi

# ── Step 4: Install code-kg if not already present ────────────────────────────
echo ""
echo "── Step 4: Checking code-kg installation ────────────"
echo ""

# Resolve the latest GitHub release wheel URL (requires curl or wget + python3).
# Returns empty string if no release exists yet.
_latest_wheel_url() {
    local _api="https://api.github.com/repos/${REPO}/releases/latest"
    local _json=""
    if command -v curl &>/dev/null; then
        _json="$(curl -fsSL "$_api" 2>/dev/null || true)"
    elif command -v wget &>/dev/null; then
        _json="$(wget -qO- "$_api" 2>/dev/null || true)"
    fi
    [ -z "$_json" ] && return
    python3 - <<PYEOF
import json, sys
try:
    data = json.loads('''$_json''')
    assets = data.get("assets", [])
    whl = next((a["browser_download_url"] for a in assets if a["name"].endswith(".whl")), None)
    if whl:
        print(whl)
except Exception:
    pass
PYEOF
}

metakg_BIN=""
# Check if metakg is already on PATH
if command -v metakg &>/dev/null; then
    metakg_BIN="$(command -v metakg)"
    echo "  ✓ Found metakg at: ${metakg_BIN}"
fi

if [ -z "$metakg_BIN" ]; then
    if [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] would install code-kg[mcp] (wheel from GitHub Releases or git fallback)"
        metakg_BIN="metakg"
    else
        # ── Preferred: install from latest GitHub release wheel (no git needed) ──
        WHEEL_URL="$(_latest_wheel_url || true)"
        if [ -n "$WHEEL_URL" ]; then
            echo "  → Installing code-kg[mcp] from GitHub release wheel..."
            pip install --quiet "code-kg[mcp] @ ${WHEEL_URL}"
        else
            # ── Fallback: pip from git (always works, needs git) ──────────────
            echo "  → No release found. Installing code-kg[mcp] from git..."
            pip install --quiet "code-kg[mcp] @ git+https://github.com/${REPO}.git"
        fi
        metakg_BIN="$(command -v metakg 2>/dev/null || true)"

        if [ -n "$metakg_BIN" ]; then
            echo "  ✓ Installed code-kg — metakg at: ${metakg_BIN}"
        else
            echo "  ✗ Installation failed. Install manually:"
            echo "      pip install 'code-kg[mcp] @ git+https://github.com/${REPO}.git'"
            exit 1
        fi
    fi
fi

# ── Step 4b: Write Cline MCP settings (cline_mcp_settings.json) ─────────────
# Must run after metakg_BIN is resolved above.
echo ""
echo "── Step 4b: Configuring Cline MCP settings ──────────"
echo ""

if [ "$DO_CLINE" = "1" ]; then
    # Cline global MCP settings — macOS/Linux paths
    CLINE_SETTINGS=""
    if [ -f "${HOME}/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json" ]; then
        CLINE_SETTINGS="${HOME}/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
    elif [ -f "${HOME}/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json" ]; then
        CLINE_SETTINGS="${HOME}/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
    fi

    if [ -z "$CLINE_SETTINGS" ]; then
        echo "  ⚠ cline_mcp_settings.json not found — is Cline installed?"
        echo "    Expected: ~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
    elif [ -n "$DRY_RUN" ]; then
        REPO_NAME="$(basename "${TARGET_REPO}")"
        echo "  [dry-run] would upsert metakg-${REPO_NAME} in ${CLINE_SETTINGS}"
    else
        REPO_NAME="$(basename "${TARGET_REPO}")"
        python3 - "$CLINE_SETTINGS" "$TARGET_REPO" "$REPO_NAME" <<'PYEOF'
import json, sys
cline_settings = sys.argv[1]
target_repo    = sys.argv[2]
repo_name      = sys.argv[3]
server_key     = f"metakg-{repo_name}"

with open(cline_settings, "r") as f:
    data = json.load(f)
if "mcpServers" not in data:
    data["mcpServers"] = {}

data["mcpServers"][server_key] = {
    "command": "metakg",
    "args": ["mcp", "--repo", target_repo,
             "--db", f"{target_repo}/.metakg/graph.sqlite"]
}

with open(cline_settings, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(f"  ✓ Upserted {server_key} in {cline_settings}")
PYEOF
    fi
else
    echo "  – Skipped (cline not selected)"
fi

# ── Step 4: Build the SQLite knowledge graph ──────────────────────────────────
echo ""
echo "── Step 5: Building SQLite knowledge graph ──────────"
echo ""

if [ -f "$SQLITE_DB" ] && [ -z "$WIPE_FLAG" ]; then
    echo "  ✓ SQLite graph already exists: ${SQLITE_DB} — skipping build"
    echo "    (Run with --wipe to force rebuild)"
else
    if [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] would run: metakg build-sqlite --repo ${TARGET_REPO}${WIPE_FLAG:+ --wipe}"
    else
        _exec mkdir -p "$(dirname "$SQLITE_DB")"
        echo "  → Building SQLite graph at: ${SQLITE_DB}"
        _WIPE_ARG=${WIPE_FLAG:+--wipe}
        (cd "${TARGET_REPO}" && "${metakg_BIN}" build-sqlite --repo "${TARGET_REPO}" ${_WIPE_ARG})
        if [ -f "$SQLITE_DB" ]; then
            echo "  ✓ Built: ${SQLITE_DB}"
        else
            echo "  ✗ Build failed — ${SQLITE_DB} not created"
            exit 1
        fi
    fi
fi

# ── Step 5: Build the LanceDB vector index ────────────────────────────────────
echo ""
echo "── Step 6: Building LanceDB vector index ────────────"
echo ""

if [ -d "$LANCEDB_DIR" ] && [ "$(ls -A "$LANCEDB_DIR" 2>/dev/null)" ] && [ -z "$WIPE_FLAG" ]; then
    echo "  ✓ LanceDB index already exists: ${LANCEDB_DIR} — skipping build"
    echo "    (Run with --wipe to force rebuild)"
else
    if [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] would run: metakg build-lancedb --repo ${TARGET_REPO}${WIPE_FLAG:+ --wipe}"
    else
        echo "  → Building LanceDB index at: ${LANCEDB_DIR}"
        _WIPE_ARG=${WIPE_FLAG:+--wipe}
        (cd "${TARGET_REPO}" && "${metakg_BIN}" build-lancedb --repo "${TARGET_REPO}" ${_WIPE_ARG})
        if [ -d "$LANCEDB_DIR" ] && [ "$(ls -A "$LANCEDB_DIR" 2>/dev/null)" ]; then
            echo "  ✓ Built: ${LANCEDB_DIR}"
        else
            echo "  ✗ Build failed — ${LANCEDB_DIR} not populated"
            exit 1
        fi
    fi
fi

# ── Step 7: Write .mcp.json (Claude Code + Kilo Code) ────────────────────────
echo ""
echo "── Step 7: Configuring .mcp.json (Claude Code + Kilo Code) ──"
echo ""

MCP_JSON="${TARGET_REPO}/.mcp.json"

if [ "$DO_KILO" = "0" ] && [ "$DO_CLAUDE" = "0" ]; then
    echo "  – Skipped (neither claude nor kilo selected)"
elif [ -n "$DRY_RUN" ]; then
    echo "  [dry-run] would upsert metakg entry in ${MCP_JSON}"
elif [ ! -f "$MCP_JSON" ]; then
    cat > "$MCP_JSON" <<EOF
{
  "mcpServers": {
    "metakg": {
      "command": "metakg-mcp",
      "args": [
        "--repo", "${TARGET_REPO}"
      ]
    }
  }
}
EOF
    echo "  ✓ Created ${MCP_JSON}"
else
    python3 - "$MCP_JSON" "$TARGET_REPO" <<'PYEOF'
import json, sys
mcp_json    = sys.argv[1]
target_repo = sys.argv[2]
with open(mcp_json, "r") as f:
    data = json.load(f)
if "mcpServers" not in data:
    data["mcpServers"] = {}
data["mcpServers"]["metakg"] = {
    "command": "metakg-mcp",
    "args": ["--repo", target_repo]
}
with open(mcp_json, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF
    echo "  ✓ Updated metakg entry in ${MCP_JSON}"
fi

# ── Step 8: Write .vscode/mcp.json (GitHub Copilot) ──────────────────────────
echo ""
echo "── Step 8: Configuring .vscode/mcp.json (GitHub Copilot) ──"
echo ""

VSCODE_DIR="${TARGET_REPO}/.vscode"
VSCODE_MCP="${VSCODE_DIR}/mcp.json"

if [ "$DO_COPILOT" = "0" ]; then
    echo "  – Skipped (copilot not selected)"
elif [ -n "$DRY_RUN" ]; then
    if [ ! -f "$VSCODE_MCP" ]; then
        echo "  [dry-run] would create ${VSCODE_MCP}"
    else
        echo "  [dry-run] would upsert metakg entry in existing ${VSCODE_MCP}"
    fi
else
    _exec mkdir -p "$VSCODE_DIR"

    if [ ! -f "$VSCODE_MCP" ]; then
        cat > "$VSCODE_MCP" <<EOF
{
  "servers": {
    "metakg": {
      "type": "stdio",
      "command": "metakg",
      "args": [
        "mcp",
        "--repo", "${TARGET_REPO}",
        "--db",   "${TARGET_REPO}/.metakg/graph.sqlite"
      ]
    }
  }
}
EOF
        echo "  ✓ Created ${VSCODE_MCP}"
    else
        python3 - "$VSCODE_MCP" "$TARGET_REPO" <<'PYEOF'
import json, sys
vscode_mcp  = sys.argv[1]
target_repo = sys.argv[2]
with open(vscode_mcp, "r") as f:
    data = json.load(f)
if "servers" not in data:
    data["servers"] = {}
data["servers"]["metakg"] = {
    "type": "stdio",
    "command": "metakg",
    "args": ["mcp", "--repo", target_repo,
             "--db", f"{target_repo}/.metakg/graph.sqlite"]
}
with open(vscode_mcp, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF
        echo "  ✓ Updated metakg entry in ${VSCODE_MCP}"
    fi
fi  # DO_COPILOT

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
if [ -n "$DRY_RUN" ]; then
echo "╔══════════════════════════════════════════════════╗"
echo "║   metakg dry-run complete — no changes made.     ║"
echo "╚══════════════════════════════════════════════════╝"
else
echo "╔══════════════════════════════════════════════════╗"
echo "║   metakg installed and configured successfully!  ║"
echo "╚══════════════════════════════════════════════════╝"
fi
echo ""
echo "  Repo:    ${TARGET_REPO}"
echo "  SQLite:  ${SQLITE_DB}"
echo "  LanceDB: ${LANCEDB_DIR}"
echo ""
echo "  Claude commands installed:"
echo "    ✓ ~/.claude/commands/metakg.md"
echo "    ✓ ~/.claude/commands/metakg-rebuild.md"
echo "    ✓ ~/.claude/commands/setup-mcp.md"
echo ""
echo "  Providers configured:"
( [ "$DO_CLAUDE" = "1" ] || [ "$DO_KILO" = "1" ] ) && echo "    ✓ Claude Code + Kilo Code  (.mcp.json)"
[ "$DO_COPILOT" = "1" ] && echo "    ✓ GitHub Copilot (.vscode/mcp.json)"
[ "$DO_CLINE"   = "1" ] && echo "    ✓ Cline          (.claude/commands/metakg.md + cline_mcp_settings.json)"
echo ""
echo "  ⚠ One manual step required:"
echo "    Reload VS Code to activate the MCP servers:"
echo "    Cmd+Shift+P → 'Developer: Reload Window'"
echo ""
[ "$DO_COPILOT" = "1" ] && echo "  GitHub Copilot: VS Code will prompt you to Trust the metakg server on first use."
echo ""
echo "  Full docs: https://github.com/Flux-Frontiers/meta_kg/blob/main/docs/MCP.md"
