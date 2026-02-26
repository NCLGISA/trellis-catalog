---
name: nextdns-api
description: >
  NextDNS bridge -- protective DNS profile management, security and privacy
  configuration, ad-blocking/tracker-blocking via blocklists, allowlist and
  denylist management, analytics (query status, top domains, block reasons,
  devices, protocols, destinations), and DNS query logs via the NextDNS REST
  API. Supports multi-profile accounts.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.26"
metadata:
  author: tendril-project
  version: "2026.02.26.1"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - nextdns
    - dns
    - protective-dns
    - dns-filtering
    - security
    - privacy
    - parental-controls
    - analytics
    - blocklist
    - allowlist
    - denylist
    - threat-intelligence
    - ad-blocking
credentials:
  - key: NEXTDNS_API_KEY
    env: NEXTDNS_API_KEY
    scope: shared
    description: "API key from https://my.nextdns.io/account -- grants access to all profiles on the account"
  - key: NEXTDNS_PROFILE
    env: NEXTDNS_PROFILE
    scope: shared
    description: "Default profile ID (e.g. abc123) -- optional, profile-scoped commands require --profile if unset"
---

# NextDNS Bridge

Programmatic access to the NextDNS protective DNS service via its REST API. Manages DNS filtering profiles including security settings (threat intelligence, cryptojacking, DNS rebinding, typosquatting, DGA detection), privacy settings (blocklists, native tracking), parental controls, domain allow/deny lists, and provides analytics and query log access.

## Authentication

- **Type:** API key via `X-Api-Key` header
- **Key source:** Account page at https://my.nextdns.io/account (bottom of page)
- **Scope:** A single API key grants access to all profiles owned by the account
- **Environment:** `NEXTDNS_API_KEY` (shared) + `NEXTDNS_PROFILE` (shared, optional default profile)

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `nextdns_client.py` | `/opt/bridge/data/tools/` | Core REST API client -- profiles, security, privacy, analytics, logs |
| `nextdns.py` | `/opt/bridge/data/tools/` | Unified CLI: profiles, security, privacy, parental, denylist, allowlist, settings, analytics, logs |
| `nextdns_check.py` | `/opt/bridge/data/tools/` | Health check: API key validation, profile access |
| `nextdns_bridge_tests.py` | `/opt/bridge/data/tools/` | Integration test battery |

## Quick Start

```bash
python3 /opt/bridge/data/tools/nextdns_check.py
python3 /opt/bridge/data/tools/nextdns.py profiles list
python3 /opt/bridge/data/tools/nextdns.py security get
python3 /opt/bridge/data/tools/nextdns.py analytics status --from=-24h
python3 /opt/bridge/data/tools/nextdns.py logs query --limit 20
python3 /opt/bridge/data/tools/nextdns.py denylist list
```

## CLI Reference

### nextdns.py profiles -- Profile Management

```bash
python3 nextdns.py profiles list
python3 nextdns.py profiles get
python3 nextdns.py profiles get --profile abc123
python3 nextdns.py profiles create --name "New Profile"
python3 nextdns.py profiles delete --target-profile abc123
```

### nextdns.py security -- Security Settings

```bash
python3 nextdns.py security get
python3 nextdns.py security update --json '{"threatIntelligenceFeeds": true, "aiThreatDetection": true, "cryptojacking": true}'
```

Security fields: `threatIntelligenceFeeds`, `aiThreatDetection`, `googleSafeBrowsing`, `cryptojacking`, `dnsRebinding`, `idnHomographs`, `typosquatting`, `dga`, `nrd`, `ddns`, `parking`, `csam`, `tlds[]`

### nextdns.py privacy -- Privacy and Blocklists

```bash
python3 nextdns.py privacy get
python3 nextdns.py privacy blocklists
python3 nextdns.py privacy add-blocklist --blocklist-id nextdns-recommended
python3 nextdns.py privacy add-blocklist --blocklist-id oisd
python3 nextdns.py privacy remove-blocklist --blocklist-id oisd
python3 nextdns.py privacy update --json '{"disguisedTrackers": true, "allowAffiliate": false}'
```

Privacy fields: `blocklists[]`, `natives[]`, `disguisedTrackers`, `allowAffiliate`

### nextdns.py parental -- Parental Controls

```bash
python3 nextdns.py parental get
python3 nextdns.py parental update --json '{"safeSearch": true, "youtubeRestrictedMode": true}'
```

Parental fields: `services[]`, `categories[]`, `safeSearch`, `youtubeRestrictedMode`, `blockBypass`

### nextdns.py denylist -- Blocked Domains

```bash
python3 nextdns.py denylist list
python3 nextdns.py denylist add --domain malware.example.com
python3 nextdns.py denylist add --domain ads.example.com --inactive
python3 nextdns.py denylist remove --domain malware.example.com
python3 nextdns.py denylist toggle --domain ads.example.com
python3 nextdns.py denylist toggle --domain ads.example.com --inactive
```

### nextdns.py allowlist -- Allowed Domains

```bash
python3 nextdns.py allowlist list
python3 nextdns.py allowlist add --domain trusted.example.com
python3 nextdns.py allowlist remove --domain trusted.example.com
python3 nextdns.py allowlist toggle --domain trusted.example.com --inactive
```

### nextdns.py settings -- Profile Settings

```bash
python3 nextdns.py settings get
python3 nextdns.py settings update --json '{"logs": {"enabled": true, "retention": 7776000}, "performance": {"ecs": true, "cacheBoost": true}}'
```

Settings fields: `logs` (enabled, drop, retention, location), `blockPage` (enabled), `performance` (ecs, cacheBoost, cnameFlattening), `web3`

### nextdns.py analytics -- Query Analytics

```bash
python3 nextdns.py analytics status --from=-7d
python3 nextdns.py analytics domains --from=-24h --limit 20
python3 nextdns.py analytics domains --from=-24h --status blocked --limit 50
python3 nextdns.py analytics reasons --from=-7d
python3 nextdns.py analytics devices --from=-30d
python3 nextdns.py analytics protocols --from=-7d
python3 nextdns.py analytics querytypes --from=-24h
python3 nextdns.py analytics ips --from=-7d --limit 10
python3 nextdns.py analytics destinations --from=-7d --dest-type countries
python3 nextdns.py analytics destinations --from=-7d --dest-type gafam
python3 nextdns.py analytics dnssec --from=-7d
python3 nextdns.py analytics encryption --from=-7d
python3 nextdns.py analytics ipversions --from=-7d
```

Options: `--from` (date/relative), `--to` (date/relative), `--limit` (1-500), `--device` (device ID), `--status` (domains only: default|blocked|allowed), `--dest-type` (destinations only: countries|gafam)

Date formats: ISO 8601, Unix timestamp, relative (`-6h`, `-1d`, `-3M`, `now`), or `YYYY-MM-DD`

### nextdns.py logs -- DNS Query Logs

```bash
python3 nextdns.py logs query --limit 50
python3 nextdns.py logs query --search facebook --status blocked
python3 nextdns.py logs query --from=-1h --raw
python3 nextdns.py logs query --device 8TD1G --limit 100
python3 nextdns.py logs clear
```

Options: `--from`, `--to`, `--limit` (10-1000, default 100), `--search` (domain substring), `--status` (default|error|blocked|allowed), `--device`, `--raw` (show all query types including non-navigational)

## Notes

- The API is officially in beta but has been stable for production use
- A single API key controls all profiles on the account -- there are no per-profile keys
- Analytics date ranges use flexible formats: `-24h`, `-7d`, `-3M`, ISO 8601, Unix timestamps
- Log queries return deduplicated navigational queries by default; use `--raw` for all DNS query types
- Parental control service/category entries use `active: true/false` to enable/disable without removing
- The `--profile` flag on any command overrides the `NEXTDNS_PROFILE` environment variable
