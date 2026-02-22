#!/bin/bash
# ============================================================================
# Tendril Bridge Entrypoint - Sierra AirLink
# ============================================================================
set -e

TENDRIL_BIN="/opt/tendril/tendril"
TENDRIL_CONFIG="/opt/tendril/tendril.json"
TOOLS_DIR="/opt/bridge/data/tools"
TOOLS_SEED="/opt/bridge/_seed/tools"
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

seed_tools() {
    if [ -d "$TOOLS_SEED" ] && [ "$(ls -A $TOOLS_SEED 2>/dev/null)" ]; then
        if [ ! "$(ls -A $TOOLS_DIR 2>/dev/null)" ]; then
            echo "[sierra-airlink] First run: seeding tools from image..."
            cp -r "$TOOLS_SEED"/* "$TOOLS_DIR"/
            echo "[sierra-airlink] Seeded $(ls $TOOLS_DIR | wc -l) tool files"
        elif needs_seed; then
            echo "[sierra-airlink] Image updated (v${BRIDGE_SEED_VERSION}): re-seeding tools..."
            cp -r "$TOOLS_SEED"/* "$TOOLS_DIR"/
            echo "[sierra-airlink] Re-seeded $(ls $TOOLS_DIR | wc -l) tool files"
        else
            echo "[sierra-airlink] Tools directory populated ($(ls $TOOLS_DIR | wc -l) files)"
        fi
    fi
}

seed_skills() {
    mkdir -p "$SKILLS_DIR"
    if [ -d "$SKILLS_SEED" ] && [ "$(ls -A $SKILLS_SEED 2>/dev/null)" ]; then
        if [ ! "$(ls -A $SKILLS_DIR 2>/dev/null)" ]; then
            echo "[sierra-airlink] First run: seeding skills to /opt/tendril/skills/..."
            cp -r "$SKILLS_SEED"/* "$SKILLS_DIR"/
            echo "[sierra-airlink] Seeded $(find $SKILLS_DIR -name 'SKILL.md' | wc -l) skill(s)"
        elif needs_seed; then
            echo "[sierra-airlink] Image updated (v${BRIDGE_SEED_VERSION}): re-seeding skills..."
            cp -r "$SKILLS_SEED"/* "$SKILLS_DIR"/
            echo "[sierra-airlink] Re-seeded $(find $SKILLS_DIR -name 'SKILL.md' | wc -l) skill(s)"
        else
            echo "[sierra-airlink] Skills directory populated ($(find $SKILLS_DIR -name 'SKILL.md' | wc -l) skill(s))"
        fi
    fi
}

seed_tools
seed_skills

if [ -n "$BRIDGE_SEED_VERSION" ]; then
    echo "$BRIDGE_SEED_VERSION" > "$VERSION_STAMP"
fi

# ── Download Tendril agent if not present ──────────────────────────────────
if [ ! -f "$TENDRIL_BIN" ]; then
    DOWNLOAD_URL="${TENDRIL_DOWNLOAD_URL:?Set TENDRIL_DOWNLOAD_URL to your Tendril Root e.g. https://tendril.example.com/download/tendril?linux-amd64}"
    echo "[sierra-airlink] Downloading Tendril agent from $DOWNLOAD_URL ..."
    curl -sL "$DOWNLOAD_URL" -o "$TENDRIL_BIN"
    chmod +x "$TENDRIL_BIN"
    echo "[sierra-airlink] Agent binary downloaded ($("$TENDRIL_BIN" version 2>/dev/null || echo 'unknown version'))"
fi

# ── Launch agent ───────────────────────────────────────────────────────────
if [ ! -f "$TENDRIL_CONFIG" ] && [ -n "$TENDRIL_INSTALL_KEY" ]; then
    echo "[sierra-airlink] First run: registering with Tendril server..."
    exec "$TENDRIL_BIN" run --key "$TENDRIL_INSTALL_KEY"
elif [ -f "$TENDRIL_CONFIG" ]; then
    echo "[sierra-airlink] Starting agent (config exists)..."
    exec "$TENDRIL_BIN" run
else
    echo "[sierra-airlink] ERROR: No config and no TENDRIL_INSTALL_KEY set"
    echo "[sierra-airlink] Set TENDRIL_INSTALL_KEY in your docker-compose.yml or environment"
    exit 1
fi
