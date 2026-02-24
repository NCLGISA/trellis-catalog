---
name: sophos-central
description: Sophos Central bridge -- endpoint inventory, security alerts, endpoint isolation, directory users/groups, policies, allowed/blocked items, scanning exclusions, account health dashboard, SIEM event feed, and XDR Data Lake forensic queries via REST APIs (Common v1, Endpoint v1, SIEM v1, Account Health v1, XDR Query v1).
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.16"
metadata:
  author: tendril-project
  version: "2026.02.24.1"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - sophos
    - sophos-central
    - endpoint-protection
    - endpoint-security
    - xdr
    - edr
    - forensics
    - alerts
    - threat-detection
    - isolation
    - data-lake
    - siem
    - directory
    - policies
credentials:
  - key: client_id
    env: SOPHOS_CLIENT_ID
    scope: shared
    description: OAuth2 client ID from Sophos Central Admin > Global Settings > API Credentials
  - key: client_secret
    env: SOPHOS_CLIENT_SECRET
    scope: shared
    description: OAuth2 client secret paired with the Client ID
---

# Sophos Central Bridge

Full programmatic access to a Sophos Central tenant via REST APIs. Supports any Sophos Central license tier -- Intercept X, Endpoint Protection, XDR, MTR, ZTNA, and Device Encryption features are exercised automatically based on what the tenant has licensed.

## Authentication

- **Type:** OAuth2 `client_credentials` flow via `https://id.sophos.com/api/v2/oauth2/token`
- **Tenant:** Auto-discovered via `/whoami/v1` (no hardcoded tenant ID)
- **Region:** Auto-discovered (Sophos routes to the correct regional API host)
- **Headers:** `Authorization: Bearer <jwt>` + `X-Tenant-ID: <uuid>` (managed automatically)
- **Token lifetime:** ~1 hour (auto-refreshed before expiry)

### Credential Setup

1. Log in to **Sophos Central Admin** > **Global Settings** > **API Credentials Management**
2. Click **Add Credential** to create a service principal
3. Assign the appropriate role (Super Admin for full access, or a read-only role for monitoring)
4. Copy the **Client ID** and **Client Secret**
5. Store them in the Tendril credential vault:

```
bridge_credentials(action="set", bridge="sophos-central", key="client_id", value="<your-client-id>")
bridge_credentials(action="set", bridge="sophos-central", key="client_secret", value="<your-client-secret>")
```

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `sophos_client.py` | `/opt/bridge/data/tools/` | Core REST API client -- OAuth2, whoami, pagination, all API methods |
| `sophos.py` | `/opt/bridge/data/tools/` | Unified CLI: endpoints, alerts, directory, policies, settings, health, siem, xdr |
| `sophos_check.py` | `/opt/bridge/data/tools/` | Health check: auth, endpoint count, alert count |

## Quick Start

```bash
python3 /opt/bridge/data/tools/sophos_check.py
python3 /opt/bridge/data/tools/sophos.py endpoints list --limit 20
python3 /opt/bridge/data/tools/sophos.py alerts list --severity high
python3 /opt/bridge/data/tools/sophos.py health check
python3 /opt/bridge/data/tools/sophos.py directory users --search "John"
python3 /opt/bridge/data/tools/sophos.py xdr run --sql "SELECT * FROM xdr_data WHERE query_name = 'running_processes_linux_windows' LIMIT 10"
```

## CLI Reference

### sophos.py endpoints -- Managed Endpoints

```bash
python3 sophos.py endpoints list                              # List endpoints (default 50)
python3 sophos.py endpoints list --limit 100                  # More results
python3 sophos.py endpoints list --health bad                 # Unhealthy endpoints
python3 sophos.py endpoints list --health suspicious          # Suspicious endpoints
python3 sophos.py endpoints list --type server                # Servers only
python3 sophos.py endpoints list --type computer              # Computers only
python3 sophos.py endpoints list --search "WORKSTATION01"     # Search by hostname
python3 sophos.py endpoints list --search "192.168.1"         # Search by IP prefix
python3 sophos.py endpoints list --isolation isolated         # Currently isolated
python3 sophos.py endpoints list --group <group-id>           # Filter by endpoint group
python3 sophos.py endpoints detail --id <uuid>                # Full endpoint detail
python3 sophos.py endpoints scan --id <uuid>                  # Trigger scan
python3 sophos.py endpoints isolate --id <uuid> --comment "Investigating malware"
python3 sophos.py endpoints deisolate --id <uuid> --comment "Remediated"
python3 sophos.py endpoints tamper --id <uuid>                # Check tamper status
python3 sophos.py endpoints tamper --id <uuid> --enable       # Enable tamper protection
python3 sophos.py endpoints tamper --id <uuid> --disable      # Disable tamper protection
python3 sophos.py endpoints groups                            # List all endpoint groups
python3 sophos.py endpoints group-members --group-id <uuid>   # Endpoints in a group
```

### sophos.py alerts -- Security Alerts

```bash
python3 sophos.py alerts list                                 # All alerts
python3 sophos.py alerts list --severity high                 # High severity only
python3 sophos.py alerts list --severity medium               # Medium severity
python3 sophos.py alerts list --category malware              # Malware alerts
python3 sophos.py alerts list --category protection           # Protection alerts
python3 sophos.py alerts list --category runtimeDetections    # Runtime detections
python3 sophos.py alerts list --product endpoint              # Endpoint product
python3 sophos.py alerts list --from "2026-01-01T00:00:00Z"   # Date filter
python3 sophos.py alerts detail --id <uuid>                   # Full alert detail
python3 sophos.py alerts acknowledge --id <uuid> --message "Reviewed"
python3 sophos.py alerts clear --ids "uuid1,uuid2,uuid3"      # Bulk acknowledge
python3 sophos.py alerts clear --severity low                 # Clear all low alerts
```

### sophos.py directory -- Users & Groups

Directory users and groups synced from Azure AD, on-prem AD, or other identity providers configured in Sophos Central.

```bash
python3 sophos.py directory users --limit 50                  # List users
python3 sophos.py directory users --search "John Smith"       # Search by name/email
python3 sophos.py directory users --group-id <uuid>           # Users in a group
python3 sophos.py directory user --id <uuid>                  # Full user detail
python3 sophos.py directory groups --limit 50                 # List groups
python3 sophos.py directory groups --search "IT_Dept"         # Search groups
python3 sophos.py directory group --id <uuid>                 # Group detail with members
```

### sophos.py policies -- Endpoint Policies

```bash
python3 sophos.py policies list                               # All policies
python3 sophos.py policies list --type threat-protection      # Threat protection policies
python3 sophos.py policies list --type application-control    # App control policies
python3 sophos.py policies list --type agent-updating         # Update policies
python3 sophos.py policies list --type peripheral-control     # Peripheral control
python3 sophos.py policies list --type web-control            # Web control
python3 sophos.py policies detail --id <uuid>                 # Full policy with settings
```

Policy types: `agent-updating`, `threat-protection`, `peripheral-control`, `application-control`, `data-loss-prevention`, `web-control`, `windows-firewall`, `server-threat-protection`, `server-peripheral-control`, `server-application-control`, `server-data-loss-prevention`, `server-web-control`, `server-windows-firewall`, `server-lockdown`

### sophos.py settings -- Global Security Settings

```bash
# Allowed items (SHA256/path allowlist)
python3 sophos.py settings allowed-items                      # List allowed items
python3 sophos.py settings add-allowed --type sha256 --value <hash> --comment "Approved app"
python3 sophos.py settings add-allowed --type path --value "C:\Apps\tool.exe" --comment "Internal tool"
python3 sophos.py settings delete-allowed --id <uuid>

# Blocked items (SHA256 blocklist)
python3 sophos.py settings blocked-items                      # List blocked items
python3 sophos.py settings add-blocked --type sha256 --value <hash> --comment "Known malware"
python3 sophos.py settings delete-blocked --id <uuid>

# Scanning exclusions
python3 sophos.py settings scanning-exclusions                # List exclusions
python3 sophos.py settings add-exclusion --type path --value "C:\MyApp\data" --comment "App data dir"
python3 sophos.py settings add-exclusion --type process --value "myapp.exe" --scan-mode onAccess
python3 sophos.py settings delete-exclusion --id <uuid>

# Exploit mitigation
python3 sophos.py settings exploit-mitigation                 # Protected applications

# Web control local sites
python3 sophos.py settings web-control-sites                  # IOC suspect sites
python3 sophos.py settings add-web-site --url "evil.example.com" --tags "IOC_SUSPECT"
python3 sophos.py settings delete-web-site --id <uuid>

# Global tamper protection
python3 sophos.py settings tamper-protection                  # Global tamper status

# Installer downloads
python3 sophos.py settings downloads                          # Windows/Linux/macOS installers
```

### sophos.py health -- Account Health Dashboard

```bash
python3 sophos.py health check                                # Full health dashboard
```

Returns protection scores (0-100), tamper protection status, policy compliance, exclusion security risks, and MDR data telemetry status for both computers and servers.

### sophos.py siem -- SIEM Event Feed

```bash
python3 sophos.py siem events                                 # Latest 200 events
python3 sophos.py siem events --limit 500                     # More events
python3 sophos.py siem events --from "2026-01-01T00:00:00Z"   # From specific time
python3 sophos.py siem alerts                                 # SIEM alert feed
python3 sophos.py siem alerts --from "2026-01-01T00:00:00Z"   # Alerts from time
```

SIEM events include: peripheral allowed/blocked, application blocked, malware detected, web filtering, device events, user logons. Min page size is 200.

### sophos.py xdr -- XDR Data Lake Forensics

Requires XDR or MTR license. Provides SQL-like queries against the Sophos Data Lake.

```bash
python3 sophos.py xdr queries                                 # List all saved queries
python3 sophos.py xdr categories                              # Query categories
python3 sophos.py xdr run --sql "SELECT * FROM xdr_data WHERE query_name = 'running_processes_linux_windows' LIMIT 50"
python3 sophos.py xdr run --sql "SELECT * FROM xdr_data WHERE query_name = 'sophos_detections' LIMIT 100" --from "2026-01-01T00:00:00Z"
python3 sophos.py xdr status --run-id <uuid>                  # Poll async query
python3 sophos.py xdr results --run-id <uuid> --limit 200     # Get results
```

XDR query categories include: Anomalies, Compliance, Device, Events, Files, Threat hunting, ATT&CK, Network, Processes, Registry, User, Email, Microsoft 365, ZTNA, NDR, DNS Protection, OS updates.

## Common Patterns

### Incident Response: Isolate Compromised Endpoint
1. `python3 sophos.py endpoints list --search "INFECTED-PC"`
2. `python3 sophos.py alerts list --severity high`
3. `python3 sophos.py endpoints isolate --id <id> --comment "Malware - IR ticket #1234"`
4. `python3 sophos.py endpoints scan --id <id>`
5. `python3 sophos.py xdr run --sql "SELECT * FROM xdr_data WHERE query_name = 'running_processes_linux_windows' AND meta_hostname = 'INFECTED-PC'"`
6. After remediation: `python3 sophos.py endpoints deisolate --id <id>`

### IOC Threat Hunting
1. Block the hash: `python3 sophos.py settings add-blocked --type sha256 --value <hash> --comment "IOC from TI feed"`
2. Search Data Lake: `python3 sophos.py xdr run --sql "SELECT meta_hostname, name, sha256 FROM xdr_data WHERE query_name = 'running_processes_linux_windows' AND sha256 = '<hash>'"`
3. `python3 sophos.py xdr status --run-id <id>` then `xdr results --run-id <id>`
4. Isolate affected endpoints

### Daily Security Review
1. `python3 sophos.py health check` -- protection scores and compliance
2. `python3 sophos.py alerts list --severity high --limit 100`
3. `python3 sophos.py endpoints list --health bad`
4. `python3 sophos.py endpoints list --health suspicious`
5. `python3 sophos.py endpoints list --isolation isolated`
6. `python3 sophos.py siem events --limit 200` -- recent event feed

### Software Allowlisting
1. `python3 sophos.py settings allowed-items` -- current allowlist
2. `python3 sophos.py settings add-allowed --type sha256 --value <hash> --comment "Approved: VendorApp v2.1"`
3. Verify: `python3 sophos.py settings allowed-items`

### Policy Audit
1. `python3 sophos.py policies list` -- all policies
2. `python3 sophos.py policies list --type threat-protection` -- threat policies only
3. `python3 sophos.py policies detail --id <id>` -- full settings
4. `python3 sophos.py health check` -- policy compliance scores

### User/Endpoint Association
1. `python3 sophos.py directory users --search "Jane Doe"` -- find user
2. `python3 sophos.py endpoints list --search "JANE-PC"` -- find their endpoint
3. `python3 sophos.py endpoints detail --id <id>` -- full detail with associated person

## API Coverage

| API | Endpoint | Operations |
|-----|----------|------------|
| Alerts | `common/v1/alerts` | list, get, acknowledge, clear |
| Directory Users | `common/v1/directory/users` | list, search, get |
| Directory Groups | `common/v1/directory/user-groups` | list, search, get |
| Admins | `common/v1/admins` | list, get |
| Roles | `common/v1/roles` | list |
| Endpoints | `endpoint/v1/endpoints` | list, search, get, scan, isolate, tamper |
| Endpoint Groups | `endpoint/v1/endpoint-groups` | list, get, members |
| Policies | `endpoint/v1/policies` | list, get |
| Allowed Items | `endpoint/v1/settings/allowed-items` | list, add, delete |
| Blocked Items | `endpoint/v1/settings/blocked-items` | list, add, delete |
| Scanning Exclusions | `endpoint/v1/settings/exclusions/scanning` | list, add, delete |
| Exploit Mitigation | `endpoint/v1/settings/exploit-mitigation/applications` | list |
| Web Control Sites | `endpoint/v1/settings/web-control/local-sites` | list, add, delete |
| Tamper Protection | `endpoint/v1/settings/tamper-protection` | get |
| Installer Downloads | `endpoint/v1/downloads` | list |
| Account Health | `account-health-check/v1/health-check` | get |
| SIEM Events | `siem/v1/events` | list (min 200/page, cursor-based) |
| SIEM Alerts | `siem/v1/alerts` | list (min 200/page, cursor-based) |
| XDR Saved Queries | `xdr-query/v1/queries` | list |
| XDR Categories | `xdr-query/v1/queries/categories` | list |
| XDR Run | `xdr-query/v1/queries/runs` | run, status, results |

## Rate Limits

| Window | Max Calls |
|--------|-----------|
| 1 second | 10 |
| 1 minute | 100 (bursts to 300) |
| 1 hour | 1,000 |
| 1 day | 200,000 |

## Notes

- Tenant ID and regional API host are auto-discovered at startup via `/whoami/v1` -- no manual configuration needed beyond the OAuth2 credentials.
- The service principal role determines what APIs are accessible. Super Admin grants full read/write; read-only roles restrict mutation operations (isolate, scan, add/delete items).
- Directory users/groups reflect whatever identity provider is synced to Sophos Central (Azure AD, on-prem AD, etc.).
- XDR Data Lake queries require an XDR or MTR license. Without it, the `xdr` module will return 403 errors.
- SIEM endpoints use cursor-based pagination with a minimum page size of 200.
