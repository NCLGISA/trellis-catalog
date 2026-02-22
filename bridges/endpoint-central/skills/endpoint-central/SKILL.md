---
name: endpoint-central
description: ManageEngine Endpoint Central (on-premise) bridge for unified endpoint management -- patch management, asset/software inventory, software metering, license compliance, and scope of management via REST API v1.4.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.16"
metadata:
  author: tendril-project
  version: "2026.02.22.1"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - manageengine
    - endpoint-central
    - desktop-central
    - patch-management
    - inventory
    - uem
credentials:
  - key: auth_token
    env: EC_AUTH_TOKEN
    scope: per-operator
    description: Per-user API token from Endpoint Central Admin > Integrations > API Explorer
  - key: instance_url
    env: EC_INSTANCE_URL
    scope: shared
    description: On-premise server URL (e.g. https://ec.yourdomain.local:8443)
---

# Endpoint Central Bridge

Full programmatic access to a ManageEngine Endpoint Central on-premise server via the REST API v1.4. Covers server discovery, inventory (hardware, software, licenses), patch management, and scope of management (agent deployment).

## Authentication

- **Type:** Per-operator API token
- **API Base:** `{EC_INSTANCE_URL}/api/1.4`
- **Auth header:** `Authorization: {EC_AUTH_TOKEN}`
- **Token generation:** Each user generates their own token from Endpoint Central Admin > Integrations > API Explorer > Authentication
- **Per-operator:** `EC_AUTH_TOKEN` is injected per-operator from the Tendril credential vault, so actions are attributed to the correct user
- **Fallback:** If no per-operator token is set, the bridge falls back to `EC_ADMIN_TOKEN` (service account) from the container environment
- **Instance URL:** `EC_INSTANCE_URL` is shared (same server for all operators)

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `ec_client.py` | `/opt/bridge/data/tools/` | Core REST API client with auth, pagination, search helpers |
| `ec.py` | `/opt/bridge/data/tools/` | Unified CLI for all modules (server, inventory, patch, som) |
| `ec_check.py` | `/opt/bridge/data/tools/` | Health check: validates auth, reports server info and inventory counts |

## Quick Start

```bash
# Verify bridge connectivity
python3 /opt/bridge/data/tools/ec_check.py

# Test API access
python3 /opt/bridge/data/tools/ec_client.py test

# Server info
python3 /opt/bridge/data/tools/ec.py server discover

# List managed computers
python3 /opt/bridge/data/tools/ec.py inventory computers --limit 20

# Inventory summary
python3 /opt/bridge/data/tools/ec.py inventory summary

# Patch scan status
python3 /opt/bridge/data/tools/ec.py patch scan-status
```

## Tool Reference

### ec.py server -- Server Information

```bash
python3 ec.py server discover                    # Server details and version
python3 ec.py server properties                  # Domains, custom groups, branch offices
```

### ec.py inventory -- Asset and Software Inventory

```bash
python3 ec.py inventory summary                  # Inventory overview
python3 ec.py inventory computers                # List all managed computers
python3 ec.py inventory computers --domain YOURDOMAIN  # Filter by domain
python3 ec.py inventory computers --limit 100    # Limit results
python3 ec.py inventory software                 # All software
python3 ec.py inventory software --search "Chrome"  # Search software by name
python3 ec.py inventory hardware                 # Hardware inventory
python3 ec.py inventory computer-detail --resource-id 12345  # Full detail for one computer
python3 ec.py inventory installed-software --resource-id 12345  # Software on a computer
python3 ec.py inventory software-computers --software-id 678  # Computers with specific software
python3 ec.py inventory metering                 # Software metering rules
python3 ec.py inventory metering-usage --rule-id 42  # Usage data for a metering rule
python3 ec.py inventory licenses                 # Licensed software
python3 ec.py inventory software-licenses --software-id 678  # Licenses for specific software
python3 ec.py inventory scan-status              # Scan status across computers
python3 ec.py inventory scan-all                 # Trigger inventory scan on all computers
python3 ec.py inventory scan --resource-ids 123,456  # Scan specific computers
```

### ec.py patch -- Patch Management

```bash
python3 ec.py patch systems                      # All systems with patch status
python3 ec.py patch systems --domain YOURDOMAIN  # Filter by domain
python3 ec.py patch details --patch-id 23956     # Status of a patch across all computers
python3 ec.py patch details --patch-id 23956 --severity 4  # Critical only
python3 ec.py patch details --patch-id 23956 --status 202  # Missing only
python3 ec.py patch scan-status                  # Patch scan details per system
python3 ec.py patch approve --patch-ids 100,101,102  # Approve patches
python3 ec.py patch decline --patch-ids 200,201  # Decline patches
python3 ec.py patch scan                         # Trigger patch scan
```

### ec.py som -- Scope of Management

```bash
python3 ec.py som computers                      # SoM computer list
python3 ec.py som computers --domain YOURDOMAIN  # Filter by domain
python3 ec.py som remote-offices                 # Remote office list
python3 ec.py som install-agent --resource-ids 123,456   # Install agent on computers
python3 ec.py som uninstall-agent --resource-ids 123,456 # Uninstall agent
```

## API Coverage

### Server (Common)

```python
from ec_client import ECClient
client = ECClient()

client.discover()                    # Server version and details
client.server_properties()           # Domains, custom groups, branch offices
client.filter_params()               # Available filter parameters
```

### Inventory

```python
client.inventory_summary()           # Overview counts
client.inventory_computers()         # All managed computers
client.inventory_software()          # All detected software
client.inventory_hardware()          # Hardware inventory
client.computer_detail(resource_id)  # Full detail for one machine
client.installed_software(resource_id)  # Software on a specific machine
client.software_computers(software_id)  # Machines with specific software
client.metering_rules()              # Software metering rules
client.metering_usage(rule_id)       # Usage stats for a metering rule
client.licensed_software()           # Licensed software list
client.software_licenses(sw_id)      # Licenses for a specific product
client.scan_computers()              # Inventory scan status
client.trigger_scan_all()            # Trigger scan on all machines
client.trigger_scan([id1, id2])      # Trigger scan on specific machines
```

### Patch Management

```python
client.patch_alldetails(patch_id)    # Patch status across all computers
client.patch_systems()               # All systems with patch health
client.patch_scan_status()           # Scan details per system
client.patch_approve([id1, id2])     # Approve patches for deployment
client.patch_decline([id1, id2])     # Decline patches
client.patch_scan()                  # Trigger a patch scan
```

### SoM (Scope of Management)

```python
client.som_computers()               # Computers in scope
client.som_remote_offices()          # Remote/branch offices
client.som_install_agent([id1])      # Deploy EC agent to machines
client.som_uninstall_agent([id1])    # Remove EC agent from machines
```

## Common Patterns

### Patch Compliance Check
1. Get all systems: `python3 ec.py patch systems`
2. Identify vulnerable systems (health_status = Vulnerable or Highly Vulnerable)
3. Check specific patches: `python3 ec.py patch details --patch-id <id> --status 202` (missing)
4. Approve and deploy: `python3 ec.py patch approve --patch-ids <ids>`
5. Trigger scan: `python3 ec.py patch scan`

### Software Audit
1. Search for software: `python3 ec.py inventory software --search "TeamViewer"`
2. Find which computers have it: `python3 ec.py inventory software-computers --software-id <id>`
3. Cross-reference with license data: `python3 ec.py inventory software-licenses --software-id <id>`

### New Machine Onboarding
1. Check SoM: `python3 ec.py som computers`
2. Install agent: `python3 ec.py som install-agent --resource-ids <ids>`
3. Trigger inventory scan: `python3 ec.py inventory scan --resource-ids <ids>`
4. Verify: `python3 ec.py inventory computer-detail --resource-id <id>`

### Inventory Audit
1. Summary: `python3 ec.py inventory summary`
2. Computers: `python3 ec.py inventory computers --domain YOURDOMAIN`
3. Hardware: `python3 ec.py inventory hardware`
4. Software metering: `python3 ec.py inventory metering`

## Pagination

- Default page size: 25 items
- Maximum page size: 1000 items
- Use `--limit` on CLI commands to control result count
- The `ec_client.py` `get_all()` method handles automatic pagination

## Search

Paginated endpoints support search via query parameters:
- `searchtype` -- the entity type (e.g. `software_name`)
- `searchcolumn` -- the column to search
- `searchvalue` -- the search term

The CLI `--search` flag on inventory commands wraps this automatically.

## API Quirks and Known Issues

1. **Auth token format.** The token is a UUID-style string (e.g. `B42550F3-006D-48EB-8011-F6C7D6323EE7`) passed as a bare `Authorization` header value -- no `Bearer` prefix.
2. **Password encoding.** When authenticating via username/password, the password must be base64-encoded.
3. **Two-factor auth.** If 2FA is enabled on the account, token generation requires a separate OTP validation step via `/api/1.4/desktop/authentication/otpValidate`.
4. **SSL certificates.** On-premise servers often use self-signed certificates. Set `EC_VERIFY_SSL=false` (the default) to skip TLS verification.
5. **Pagination limits.** Maximum 1000 items per page. The `page` parameter is 1-indexed.
6. **Filter parameter names.** Filters use `domainfilter`, `branchofficefilter`, `customgroupfilter` -- note the inconsistent naming (no underscores).
7. **Patch status codes.** `201` = Installed, `202` = Missing, `206` = Failed to Install.
8. **Severity levels.** `0` = Unrated, `1` = Low, `2` = Moderate, `3` = Important, `4` = Critical.
9. **Response envelope.** All responses are wrapped in `{"message_type": "...", "message_response": {...}, "status": "success"}`.
10. **Resource IDs.** Computers are identified by `resource_id` (numeric), not hostname. Use inventory endpoints to look up resource IDs.
11. **API version.** Current version is 1.4. Some older documentation references 1.3 endpoints which may still work.
12. **SoM POST endpoints.** Agent install/uninstall operations accept `resource_ids` as a JSON array in the request body.

## Tenant Context

- **Deployment:** On-premise (not cloud)
- **API Version:** 1.4
- **Server URL:** Configured via `EC_INSTANCE_URL` (shared)
- **Auth model:** Per-operator tokens (each user has their own API key)
- **Domains, groups, offices:** Discovered via `server properties` command
