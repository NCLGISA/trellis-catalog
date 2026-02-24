---
name: microsoft-defender
description: >
  Unified security operations bridge spanning Microsoft Defender XDR, Defender
  for Endpoint (MDE P2), and Microsoft Sentinel.  Provides advanced hunting
  (KQL across endpoint + SIEM data), incident management, machine response
  actions, vulnerability management, threat indicator (IoC) management,
  Sentinel analytics rules, watchlists, and direct Log Analytics workspace
  queries -- all from a single bridge.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.24"
metadata:
  author: tendril-project
  version: "2026.02.24.3"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - microsoft
    - defender
    - xdr
    - mde
    - sentinel
    - siem
    - hunting
    - incidents
    - vulnerabilities
    - ioc
    - watchlists
    - kql
---

# Microsoft Defender Bridge

Unified security operations bridge covering three Microsoft security API
surfaces from a single container:

1. **Defender XDR unified API** -- cross-product advanced hunting and incident management
2. **MDE P2 API** -- endpoint inventory, response actions, vulnerability management, IoC management
3. **Sentinel ARM + Log Analytics** -- analytics rules, watchlists, automation rules, workspace KQL queries

## Architecture

The unified security portal at `security.microsoft.com` already merges
Sentinel and MDE into a single pane.  This bridge follows the same
principle: one bridge for all security operations.

```
┌─────────────────────────────────────────────────────────────┐
│                bridge-microsoft-defender                      │
│                                                              │
│  ┌──────────────┐  ┌────────────┐  ┌────────────────────┐   │
│  │ defender_    │  │ hunting.py │  │ sentinel_rules.py  │   │
│  │ client.py   │  │ incidents  │  │ watchlists.py      │   │
│  │             │  │ .py        │  │ log_query.py       │   │
│  │ Token Mgmt: │  │ machines   │  │                    │   │
│  │  - XDR      │  │ .py        │  │                    │   │
│  │  - MDE      │  │ vulnerab   │  │                    │   │
│  │  - ARM      │  │ ilities.py │  │                    │   │
│  │  - LA       │  │ indicators │  │                    │   │
│  │             │  │ .py        │  │                    │   │
│  └──────┬──────┘  └─────┬──────┘  └─────────┬──────────┘   │
│         │               │                    │              │
└─────────┼───────────────┼────────────────────┼──────────────┘
          │               │                    │
   ┌──────▼──────┐ ┌──────▼──────┐   ┌────────▼─────────┐
   │ XDR Token   │ │ MDE Token   │   │ ARM + LA Tokens  │
   │ .security.  │ │ .security   │   │ .management.     │
   │ microsoft   │ │ center.     │   │ azure.com +      │
   │ .com        │ │ microsoft   │   │ api.loganalytics  │
   │             │ │ .com        │   │ .io              │
   └──────┬──────┘ └──────┬──────┘   └────────┬─────────┘
          │               │                    │
   ┌──────▼──────┐ ┌──────▼──────────┐ ┌──────▼──────────┐
   │ api.security│ │ api.security    │ │ management.     │
   │ .microsoft  │ │ center.         │ │ azure.com       │
   │ .com        │ │ microsoft.com   │ │ + api.log       │
   │ (incidents, │ │ (machines,      │ │ analytics.io    │
   │  hunting)   │ │  vulns, IoCs)   │ │ (Sentinel, KQL) │
   └─────────────┘ └─────────────────┘ └─────────────────┘
```

## Authentication

Single Entra ID app registration with permissions across three resource providers:

**Microsoft Threat Protection (Defender XDR):**
- `AdvancedHunting.Read.All` -- KQL across all tables
- `Incident.ReadWrite.All` -- incident management
- `Alert.ReadWrite.All` -- alert management

**WindowsDefenderATP (MDE):**
- `Machine.ReadWrite.All` -- machine inventory + response actions
- `Vulnerability.Read.All` -- CVEs, software inventory
- `SecurityRecommendation.Read.All` -- TVM security recommendations
- `AdvancedQuery.Read.All` -- MDE-specific queries
- `Ti.ReadWrite.All` -- threat indicator CRUD
- `Alert.ReadWrite.All` -- MDE alert management
- `Software.Read.All` -- software inventory

**ARM RBAC (Sentinel):**
- `Microsoft Sentinel Contributor` on the workspace resource group
- `Log Analytics Reader` on the workspace resource group

Tokens are acquired independently for three scopes:
- **XDR scope** (`https://api.security.microsoft.com/.default`) -- unified incidents, advanced hunting
- **MDE scope** (`https://api.securitycenter.microsoft.com/.default`) -- machines, vulnerabilities, indicators
- **ARM scope** (`https://management.azure.com/.default`) -- Sentinel rules, watchlists
- **Log Analytics scope** (`https://api.loganalytics.io/.default`) -- direct KQL queries

XDR and MDE require separate tokens because the unified XDR token does not
carry MDE-specific roles (e.g., `Machine.Read.All`). All tokens are cached
and auto-refreshed by the MSAL client.

## License Requirements

| Feature | License |
|---------|---------|
| Defender XDR incidents/alerts | M365 E5 or E5 Security add-on |
| Advanced hunting | M365 E5 or E5 Security add-on |
| MDE machine inventory | MDE P1 or P2 |
| MDE response actions | MDE P2 |
| MDE vulnerability management | MDE P2 or TVM add-on |
| MDE threat indicators | MDE P2 |
| Sentinel analytics rules | Microsoft Sentinel (Azure consumption) |
| Sentinel watchlists | Microsoft Sentinel |
| Log Analytics queries | Log Analytics workspace (included with Sentinel) |

## Tools

| Script | API Surface | Purpose |
|--------|------------|---------|
| `defender_client.py` | All | Core client: multi-scope MSAL auth, pagination, rate limiting |
| `defender_check.py` | All | Health check: env vars + API connectivity |
| `defender_bridge_tests.py` | All | Read-only battery test (17 tests, 9 categories) |
| `hunting.py` | XDR unified | Advanced hunting: KQL queries, presets, schema tables |
| `incidents.py` | XDR unified | Incident management: list, detail, assign, resolve |
| `machines.py` | MDE | Machine inventory, detail, search, response actions |
| `vulnerabilities.py` | MDE | TVM: CVE exposure, software inventory, recommendations |
| `indicators.py` | MDE | IoC management: block/alert IPs, URLs, domains, hashes |
| `sentinel_rules.py` | Sentinel ARM | Analytics rules, automation rules, enable/disable |
| `watchlists.py` | Sentinel ARM | Watchlist CRUD, item management |
| `log_query.py` | Log Analytics | Direct KQL against the workspace (custom tables) |

## Quick Start

```bash
# Health check
python3 /opt/bridge/data/tools/defender_check.py

# Connection test
python3 /opt/bridge/data/tools/defender_client.py test

# Run battery test
python3 /opt/bridge/data/tools/defender_bridge_tests.py

# Incident dashboard
python3 /opt/bridge/data/tools/incidents.py dashboard

# MDE fleet overview
python3 /opt/bridge/data/tools/machines.py overview

# Advanced hunting
python3 /opt/bridge/data/tools/hunting.py preset failed-logons
```

## Tool Reference

### hunting.py -- Advanced Hunting

```bash
python3 hunting.py query "DeviceProcessEvents | take 10"
python3 hunting.py query "SecurityEvent | where EventID == 4625 | take 20"
python3 hunting.py tables                       # Available schema tables
python3 hunting.py presets                       # Built-in query presets
python3 hunting.py preset failed-logons         # Run a preset
python3 hunting.py preset suspicious-processes
python3 hunting.py preset lateral-movement
python3 hunting.py preset new-local-admins
python3 hunting.py preset powershell-encoded
python3 hunting.py preset threat-indicators-hits
python3 hunting.py preset tendril-logs          # Custom table query
python3 hunting.py file /path/to/query.kql      # Run KQL from file
```

Advanced hunting queries span both MDE tables (Device*) and Sentinel
tables (SecurityEvent, Syslog, SigninLogs, custom tables) in a single KQL.

### incidents.py -- Incident Management

```bash
python3 incidents.py list                         # Active incidents
python3 incidents.py list --severity high         # Filter by severity
python3 incidents.py list --status active          # Filter by status
python3 incidents.py detail <incident-id>         # Full detail + alerts
python3 incidents.py alerts <incident-id>         # Alert breakdown
python3 incidents.py assign <id> analyst@org.com  # Assign to analyst
python3 incidents.py resolve <id> truePositive    # Resolve incident
python3 incidents.py dashboard                    # Summary counts
```

Classification values for resolve: `truePositive`, `falsePositive`, `informationalExpectedActivity`

### machines.py -- MDE Machine Inventory and Response

```bash
python3 machines.py list                          # All endpoints
python3 machines.py list --os Windows             # Filter by OS
python3 machines.py list --health atRisk          # Filter by health
python3 machines.py detail <machine-id-or-name>   # Machine detail
python3 machines.py search <query>                # Search by name
python3 machines.py overview                      # Fleet statistics

# Response actions (write operations):
python3 machines.py isolate <id> "IR-2026-042"    # Full network isolation
python3 machines.py release <id> "Cleared"        # Release isolation
python3 machines.py scan <id> quick               # AV scan (quick/full)
python3 machines.py restrict <id> "Suspicious activity"  # Restrict code exec
python3 machines.py unrestrict <id> "Cleared"
python3 machines.py collect <id> "Investigation"  # Collect forensic package
python3 machines.py actions <id>                  # Recent action history
```

### vulnerabilities.py -- Threat and Vulnerability Management

```bash
python3 vulnerabilities.py dashboard              # TVM summary
python3 vulnerabilities.py cves                   # All CVE exposures
python3 vulnerabilities.py cves --severity critical  # Filter
python3 vulnerabilities.py cve CVE-2024-12345     # CVE detail + affected machines
python3 vulnerabilities.py software               # Software inventory
python3 vulnerabilities.py software "chrome"      # Search software
python3 vulnerabilities.py recommendations        # Security recommendations
python3 vulnerabilities.py machine <machine-id>   # Vulns for a machine
```

### indicators.py -- Threat Indicator (IoC) Management

```bash
python3 indicators.py list                        # All indicators
python3 indicators.py list --type IpAddress       # Filter by type
python3 indicators.py list --action block         # Filter by action
python3 indicators.py summary                     # Statistics

# Create indicators:
python3 indicators.py block-ip 203.0.113.50 "Phishing C2" "Reported by SOC"
python3 indicators.py block-url "https://evil.example.com" "Malware drop" "IR-042"
python3 indicators.py block-domain evil.example.com "C2 domain" "TI feed"
python3 indicators.py block-hash <sha256> "Ransomware payload" "IR-042"
python3 indicators.py alert-ip 198.51.100.10 "Suspicious" "Monitor only"

python3 indicators.py detail <indicator-id>
python3 indicators.py delete <indicator-id>
```

### sentinel_rules.py -- Sentinel Analytics and Automation Rules

```bash
python3 sentinel_rules.py analytics               # All analytics rules
python3 sentinel_rules.py analytics --enabled      # Only enabled
python3 sentinel_rules.py analytics --disabled     # Only disabled
python3 sentinel_rules.py analytics-detail <id>    # Rule detail + KQL
python3 sentinel_rules.py enable <rule-id>         # Enable a rule
python3 sentinel_rules.py disable <rule-id>        # Disable a rule
python3 sentinel_rules.py automation               # Automation rules
python3 sentinel_rules.py summary                  # Rule statistics
```

### watchlists.py -- Sentinel Watchlists

```bash
python3 watchlists.py list                        # All watchlists
python3 watchlists.py detail <alias>              # Watchlist detail + KQL usage
python3 watchlists.py items <alias>               # List items
python3 watchlists.py add-item <alias> '{"ip":"10.0.0.1","reason":"VIP"}'
python3 watchlists.py delete-item <alias> <item-id>
python3 watchlists.py create <alias> <name> <desc> <search-key>
python3 watchlists.py delete <alias>
```

In KQL, reference a watchlist: `_GetWatchlist('alias-name')`

### log_query.py -- Direct Log Analytics Queries

```bash
python3 log_query.py query "TendrilLogs_CL | take 10"
python3 log_query.py query "SecurityEvent | where EventID == 4625" P7D
python3 log_query.py tables                       # List workspace tables
python3 log_query.py tendril 24                   # Tendril logs (last 24h)
python3 log_query.py security 24                  # Security event summary
python3 log_query.py signin 24                    # Failed sign-ins
python3 log_query.py file /path/to/query.kql P1D  # KQL from file
```

Use `log_query.py` for custom workspace tables (TendrilLogs_CL, etc.)
that aren't in the XDR advanced hunting schema.  For cross-schema queries
(MDE + Sentinel tables), use `hunting.py`.

## Common Patterns

### Incident Response Workflow

1. Review dashboard: `python3 incidents.py dashboard`
2. Triage high-severity: `python3 incidents.py list --severity high`
3. Inspect incident: `python3 incidents.py detail <id>`
4. Hunt for related activity: `python3 hunting.py query "DeviceProcessEvents | where DeviceName == 'host' | where Timestamp > ago(24h)"`
5. Check machine posture: `python3 machines.py detail <machine-name>`
6. Isolate if compromised: `python3 machines.py isolate <id> "IR-2026-042"`
7. Block IoC: `python3 indicators.py block-ip 203.0.113.50 "C2 server" "IR-042"`
8. Resolve incident: `python3 incidents.py resolve <id> truePositive`

### Vulnerability Assessment

1. TVM overview: `python3 vulnerabilities.py dashboard`
2. Critical CVEs: `python3 vulnerabilities.py cves --severity critical`
3. Check a specific CVE: `python3 vulnerabilities.py cve CVE-2024-12345`
4. Software inventory: `python3 vulnerabilities.py software`
5. Review recommendations: `python3 vulnerabilities.py recommendations`

### Proactive Threat Hunting

1. Run built-in presets: `python3 hunting.py presets`
2. Failed logons: `python3 hunting.py preset failed-logons`
3. Suspicious processes: `python3 hunting.py preset suspicious-processes`
4. Lateral movement: `python3 hunting.py preset lateral-movement`
5. Custom KQL: `python3 hunting.py query "your KQL here"`

### Sentinel Rule Audit

1. Rule summary: `python3 sentinel_rules.py summary`
2. List disabled rules: `python3 sentinel_rules.py analytics --disabled`
3. Inspect rule KQL: `python3 sentinel_rules.py analytics-detail <id>`
4. Enable rule: `python3 sentinel_rules.py enable <id>`

### Tendril Log Investigation

1. Recent logs: `python3 log_query.py tendril 24`
2. Custom query: `python3 log_query.py query "TendrilLogs_CL | where Level_s == 'Error' | take 50"`

## Cross-Bridge References

| Operation | Bridge |
|-----------|--------|
| Security dashboard (Secure Score, Identity Protection, CA) | `bridge-microsoft-graph` (`security_check.py`) |
| User/group management, Entra ID | `bridge-microsoft-graph` |
| Quarantine management, message trace | `bridge-microsoft-exchange` |
| DLP, retention, sensitivity labels | `bridge-microsoft-purview` |
| Teams messaging | `bridge-microsoft-teams-bot` |

The Graph bridge `security_check.py` provides a lightweight security
posture dashboard (Secure Score, risky users, CA policies).  This bridge
handles active investigation and response when an issue needs deep analysis.

## API Quirks and Known Issues

- **Four token scopes:** The bridge manages four independent MSAL token
  caches (XDR, MDE, ARM, Log Analytics). Token refresh is automatic.
  XDR and MDE require separate tokens -- the unified XDR token does not
  carry MDE-specific roles like `Machine.Read.All`.
- **MDE scope:** MDE endpoints require tokens scoped to
  `https://api.securitycenter.microsoft.com/.default`. Despite Microsoft
  marketing the unified `security.microsoft.com` portal, the API permissions
  remain split between the two resource providers.
- **Advanced hunting table availability:** Not all Sentinel custom tables
  appear in the XDR advanced hunting schema. Use `log_query.py` for
  workspace-specific tables.
- **TendrilLogs_CL workspace note:** The `log_query.py tendril` command
  queries the Sentinel workspace configured via `SENTINEL_WORKSPACE_ID`.
  If Tendril logs are ingested into a different Log Analytics workspace
  (e.g., AzureLogs in IT-Infrastructure-RG), use `hunting.py query` with
  a cross-workspace KQL query or configure the target workspace separately.
- **Rate limits:** The XDR API has aggressive rate limits on advanced
  hunting (15 calls/minute, 10 concurrent).  The client handles 429
  responses with `Retry-After` backoff.
- **Machine actions are async:** Response actions (isolate, scan, etc.)
  return immediately with an action ID.  Use `machines.py actions <id>`
  to check completion status.
- **IoC propagation:** New threat indicators can take up to 30 minutes
  to propagate to all MDE-onboarded endpoints.
- **Sentinel API version:** This bridge uses API version `2024-09-01`.
  Analytics rule schema varies by rule kind (Scheduled, Fusion,
  MicrosoftSecurityIncidentCreation, etc.).
- **Watchlist size:** Sentinel watchlists support up to 10 million items.
  For very large lists, use CSV upload via the Sentinel portal.
- **BRIDGE_SEED_VERSION:** Increment this in `.env` when updating tools
  in the image, then `docker compose down && docker compose up -d` to
  trigger re-seeding from the updated image.
- **Permission propagation:** After adding new API permissions or RBAC
  roles, allow 5-15 minutes for full propagation.

## MDE-Only Deployment

If you only need MDE capabilities (no Sentinel), omit the `SENTINEL_*`
environment variables.  The bridge will skip Sentinel-related health
checks and tools will report "not configured" for Sentinel operations.
Advanced hunting via the XDR API will still work for MDE tables.
