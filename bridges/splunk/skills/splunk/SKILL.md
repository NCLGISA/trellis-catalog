---
name: splunk
description: Splunk bridge -- ad-hoc SPL log searches, saved searches, fired alerts, index inventory, and server health via the Splunk REST API. Supports both Splunk Cloud and Splunk Enterprise (on-prem).
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.24"
metadata:
  author: tendril-project
  version: "2026.02.24.2"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - splunk
    - splunk-cloud
    - splunk-enterprise
    - on-prem
    - siem
    - log-search
    - spl
    - saved-searches
    - alerts
    - indexes
    - security
    - incident-response
credentials:
  - key: SPLUNK_URL
    env: SPLUNK_URL
    scope: shared
    description: "Splunk search head URL (e.g. https://yourorg.splunkcloud.com:8089 or https://splunk.internal:8089)"
  - key: SPLUNK_TOKEN
    env: SPLUNK_TOKEN
    scope: operator
    description: Per-user bearer authentication token from Splunk Web > Settings > Tokens
  - key: SPLUNK_VERIFY_TLS
    env: SPLUNK_VERIFY_TLS
    scope: shared
    description: "Set to false for on-prem instances with self-signed certificates (default: true)"
---

# Splunk Bridge

Programmatic access to a Splunk instance via REST API. Supports both **Splunk Cloud** and **Splunk Enterprise (on-prem)**. Provides ad-hoc SPL searches, saved searches, fired alerts, index inventory, and server diagnostics.

## Authentication

- **Type:** Per-user bearer token via `Authorization: Bearer <token>` header
- **Token source:** Splunk Web > Settings > Tokens > New Token
- **IdP:** Tokens authenticate as the creating user (supports SAML, LDAP, or local auth)
- **Environment:** `SPLUNK_URL` (shared) + `SPLUNK_TOKEN` (per-operator) + `SPLUNK_VERIFY_TLS` (shared, optional)
- **Scope:** Token inherits the creating user's roles and index permissions

## Deployment Prerequisites

### Splunk Cloud

1. **Enable Token Authentication** in Splunk Web: Settings > Server settings > General settings > Token Authentication > Enabled
2. **IP Allow List:** Add the Docker host's public IP as a `/32` to the `search-api` feature allow list via the Splunk Cloud Admin Config Service (ACS). Port 8089 is closed by default.

### Splunk Enterprise (On-Prem)

1. **Enable Token Authentication** in Splunk Web: Settings > Tokens (requires Splunk 7.3+)
2. **Network Access:** Ensure the Docker host can reach the search head on port 8089 (firewall rules)
3. **Self-Signed Certs:** If the search head uses a self-signed TLS certificate, set `SPLUNK_VERIFY_TLS=false` in `.env`

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `splunk_client.py` | `/opt/bridge/data/tools/` | Core REST API client -- auth, search jobs, saved searches, indexes, alerts |
| `splunk.py` | `/opt/bridge/data/tools/` | Unified CLI: search, oneshot, jobs, savedsearches, indexes, alerts, info |
| `splunk_check.py` | `/opt/bridge/data/tools/` | Health check: auth, user context, index access |

## Quick Start

```bash
python3 /opt/bridge/data/tools/splunk_check.py
python3 /opt/bridge/data/tools/splunk.py info
python3 /opt/bridge/data/tools/splunk.py indexes
python3 /opt/bridge/data/tools/splunk.py oneshot "index=_internal | stats count by sourcetype | head 10" --earliest="-15m"
python3 /opt/bridge/data/tools/splunk.py search "index=main error" --earliest="-1h" --max 500
```

## CLI Reference

### splunk.py search -- Ad-Hoc SPL Search (async)

```bash
python3 splunk.py search "index=main error" --earliest="-24h"
python3 splunk.py search "index=* | stats count by index" --earliest="-1h"
```

Options: `--earliest` (default: -24h), `--latest` (default: now), `--max` (default: 10000), `--timeout` (default: 300)

### splunk.py oneshot -- Quick Search (blocking)

```bash
python3 splunk.py oneshot "| tstats count where index=* by index" --earliest="-1h"
python3 splunk.py oneshot "| metadata type=sourcetypes index=main"
```

Options: `--earliest` (default: -1h), `--latest` (default: now), `--max` (default: 100)

### splunk.py jobs -- Search Job Management

```bash
python3 splunk.py jobs list
python3 splunk.py jobs status --sid <sid>
python3 splunk.py jobs results --sid <sid>
python3 splunk.py jobs cancel --sid <sid>
```

### splunk.py savedsearches -- Saved Searches

```bash
python3 splunk.py savedsearches list
python3 splunk.py savedsearches detail --name "My Search"
python3 splunk.py savedsearches run --name "My Search"
```

### splunk.py indexes / alerts / info

```bash
python3 splunk.py indexes
python3 splunk.py alerts
python3 splunk.py info
```

## SPL Quick Reference

| Pattern | Description |
|---------|-------------|
| `index=main keyword` | Full-text search |
| `\| stats count by field` | Aggregate counts |
| `\| timechart span=1h count` | Time-series chart |
| `\| top 10 field` | Top N values |
| `\| table _time, field1, field2` | Select columns |
| `\| tstats count where index=* by index` | Fast index event counts |

## Notes

- REST API is on port 8089 (management port), not 443 (Splunk Web)
- Per-user bearer tokens inherit the creating user's role-based access
- Use `--earliest="value"` syntax to avoid shell argument parsing issues with negative values
- For on-prem with self-signed certs, set `SPLUNK_VERIFY_TLS=false`
