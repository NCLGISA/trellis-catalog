#!/bin/bash
# ============================================================================
# Tendril Bridge Entrypoint - Verizon MyBusiness
# ============================================================================
set -e

TENDRIL_BIN="/opt/tendril/tendril"
TENDRIL_CONFIG="/opt/tendril/tendril.json"
TOOLS_DIR="/opt/bridge/data/tools"
TOOLS_SEED="/opt/bridge/_seed/tools"
REFS_DIR="/opt/bridge/data/references"
REFS_SEED="/opt/bridge/_seed/references"
SKILLS_DIR="/opt/tendril/skills"
SKILLS_SEED="/opt/bridge/_seed/skills"
VERSION_STAMP="/opt/bridge/data/.seed_version"

needs_seed() {
    if [ -n "$BRIDGE_SEED_VERSION" ] && [ -f "$VERSION_STAMP" ]; then
        local current
        current=$(cat "$VERSION_STAMP" 2>/dev/null)
        if [ "$current" = "$BRIDGE_SEED_VERSION" ]; then
            return 1
        fi
    fi
    return 0
}

seed_dir() {
    local name="$1" src="$2" dst="$3"
    if [ -d "$src" ] && [ "$(ls -A $src 2>/dev/null)" ]; then
        if [ ! "$(ls -A $dst 2>/dev/null)" ]; then
            echo "[verizon-mybusiness] First run: seeding ${name}..."
            cp -r "$src"/* "$dst"/
        elif needs_seed; then
            echo "[verizon-mybusiness] Image updated (v${BRIDGE_SEED_VERSION}): re-seeding ${name}..."
            cp -r "$src"/* "$dst"/
        else
            echo "[verizon-mybusiness] ${name} directory populated"
        fi
    fi
}

seed_dir "tools" "$TOOLS_SEED" "$TOOLS_DIR"
seed_dir "references" "$REFS_SEED" "$REFS_DIR"

mkdir -p "$SKILLS_DIR"
seed_dir "skills" "$SKILLS_SEED" "$SKILLS_DIR"

if [ -n "$BRIDGE_SEED_VERSION" ]; then
    echo "$BRIDGE_SEED_VERSION" > "$VERSION_STAMP"
fi

# ── Download Tendril agent if not present ──────────────────────────────────
if [ ! -f "$TENDRIL_BIN" ]; then
    if [ -z "$TENDRIL_DOWNLOAD_URL" ]; then
        echo "[verizon-mybusiness] ERROR: TENDRIL_DOWNLOAD_URL not set and no agent binary found"
        exit 1
    fi
    DOWNLOAD_URL="$TENDRIL_DOWNLOAD_URL"
    echo "[verizon-mybusiness] Downloading Tendril agent from $DOWNLOAD_URL ..."
    curl -sL "$DOWNLOAD_URL" -o "$TENDRIL_BIN"
    chmod +x "$TENDRIL_BIN"
    echo "[verizon-mybusiness] Agent binary downloaded"
fi

# ── Launch agent ───────────────────────────────────────────────────────────
if [ ! -f "$TENDRIL_CONFIG" ] && [ -n "$TENDRIL_INSTALL_KEY" ]; then
    echo "[verizon-mybusiness] First run: registering with Tendril server..."
    exec "$TENDRIL_BIN" run --key "$TENDRIL_INSTALL_KEY"
elif [ -f "$TENDRIL_CONFIG" ]; then
    echo "[verizon-mybusiness] Starting agent (config exists)..."
    exec "$TENDRIL_BIN" run
else
    echo "[verizon-mybusiness] ERROR: No config and no TENDRIL_INSTALL_KEY set"
    exit 1
fi
