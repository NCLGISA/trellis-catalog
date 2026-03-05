#!/bin/bash
# Copyright 2026 The Tendril Project Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ============================================================================
# Tendril Bridge Entrypoint - Microsoft Exchange
# ============================================================================
# Handles:
#   1. Seed tools and skills on first run (image -> persistent volume)
#   2. Download the Tendril agent binary if not present
#   3. Register (first run) or launch (subsequent runs) the agent
#
# Persistent layout (/opt/tendril and /opt/bridge/data are Docker volumes):
#   /opt/tendril/tendril       - Agent binary (self-upgrades in place)
#   /opt/tendril/tendril.json  - Agent config (written once by --key)
#   /opt/tendril/skills/       - Skills discovered by agent (seeded from image)
#   /opt/bridge/data/tools/    - Exchange Online PowerShell wrapper scripts
#   /opt/bridge/certs/         - Certificate for Exchange Online auth (mounted)
# ============================================================================
set -e

TENDRIL_BIN="/opt/tendril/tendril"
TENDRIL_CONFIG="/opt/tendril/tendril.json"
TOOLS_DIR="/opt/bridge/data/tools"
SEED_DIR="/opt/bridge/_seed/tools"
SKILLS_SEED_DIR="/opt/bridge/_seed/skills"
SKILLS_DIR="/opt/tendril/skills"
SEED_VERSION_FILE="/opt/bridge/data/.seed_version"

# ── Step 1: Seed tools on first run (or re-seed on version bump) ──────────
needs_seed=false
if [ ! "$(ls -A $TOOLS_DIR 2>/dev/null)" ]; then
    needs_seed=true
    echo "[exchange-bridge] First run: seeding tools and skills from image..."
elif [ -n "$BRIDGE_SEED_VERSION" ]; then
    current_version=$(cat "$SEED_VERSION_FILE" 2>/dev/null || echo "")
    if [ "$current_version" != "$BRIDGE_SEED_VERSION" ]; then
        needs_seed=true
        echo "[exchange-bridge] Seed version changed ($current_version -> $BRIDGE_SEED_VERSION): re-seeding..."
    fi
fi

if [ "$needs_seed" = true ]; then
    if [ -d "$SEED_DIR" ] && [ "$(ls -A $SEED_DIR 2>/dev/null)" ]; then
        cp -r "$SEED_DIR"/* "$TOOLS_DIR"/
        echo "[exchange-bridge] Seeded $(ls $TOOLS_DIR | wc -l) tool files"
    fi
    mkdir -p "$SKILLS_DIR"
    if [ -d "$SKILLS_SEED_DIR" ] && [ "$(ls -A $SKILLS_SEED_DIR 2>/dev/null)" ]; then
        cp -r "$SKILLS_SEED_DIR"/* "$SKILLS_DIR"/
        echo "[exchange-bridge] Seeded skills to $SKILLS_DIR"
    fi
    if [ -n "$BRIDGE_SEED_VERSION" ]; then
        echo "$BRIDGE_SEED_VERSION" > "$SEED_VERSION_FILE"
    fi
else
    echo "[exchange-bridge] Tools directory populated ($(ls $TOOLS_DIR 2>/dev/null | wc -l) files)"
fi

mkdir -p "$SKILLS_DIR"

# ── Step 2: Download Tendril agent if not present ──────────────────────────
if [ ! -f "$TENDRIL_BIN" ]; then
    DOWNLOAD_URL="${TENDRIL_DOWNLOAD_URL:-https://your-tendril-root/download/tendril?linux-amd64}"
    echo "[exchange-bridge] Downloading Tendril agent..."
    curl -sL "$DOWNLOAD_URL" -o "$TENDRIL_BIN"
    chmod +x "$TENDRIL_BIN"
    echo "[exchange-bridge] Agent downloaded"
fi

# ── Step 3: Launch agent ───────────────────────────────────────────────────
if [ ! -f "$TENDRIL_CONFIG" ] && [ -n "$TENDRIL_INSTALL_KEY" ]; then
    echo "[exchange-bridge] First run: registering with Tendril server..."
    exec "$TENDRIL_BIN" run --key "$TENDRIL_INSTALL_KEY"
elif [ -f "$TENDRIL_CONFIG" ]; then
    echo "[exchange-bridge] Starting agent..."
    exec "$TENDRIL_BIN" run
else
    echo "[exchange-bridge] ERROR: No config and no TENDRIL_INSTALL_KEY set"
    echo "[exchange-bridge] Set TENDRIL_INSTALL_KEY in docker-compose.yml"
    exit 1
fi
