---
name: beyondtrust-rs
description: BeyondTrust Remote Support bridge -- appliance health monitoring, logged-in representative management, support team listing, session key generation, session lifecycle (join/leave/transfer/terminate), connected client inventory, support session and license usage reporting, Jump Item CRUD (Shell Jump, RDP, VNC, etc.), Jumpoint and Jump Group configuration, Vault account/endpoint inventory, group policy configuration, and software backup via Command (XML), Reporting (XML), and Configuration (JSON REST v1) APIs.
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
    - beyondtrust
    - remote-support
    - bomgar
    - jump-items
    - session-management
    - appliance-health
    - reporting
    - vault
    - jumpoint
credentials:
  - key: api_host
    env: BT_API_HOST
    scope: shared
    description: B Series Appliance hostname (e.g. support.example.com) -- no https:// prefix
  - key: client_id
    env: BT_CLIENT_ID
    scope: shared
    description: OAuth2 client ID from /login > Management > API Configuration
  - key: client_secret
    env: BT_CLIENT_SECRET
    scope: shared
    description: OAuth2 client secret paired with the Client ID
---

# BeyondTrust Remote Support Bridge

Full programmatic access to a BeyondTrust Remote Support (formerly Bomgar) B Series Appliance via the Command API (XML), Reporting API (XML), and Configuration API (JSON REST v1).

## Authentication

- **Type:** OAuth2 `client_credentials` flow via `https://<host>/oauth2/token`
- **Token lifetime:** 1 hour (auto-refreshed before expiry); max 30 concurrent tokens per API account
- **Rate limits:** 20 requests/second, 15,000 requests/hour per API account
- **Headers:** `Authorization: Bearer <token>` (managed automatically)

### Credential Setup

1. Log in to your BeyondTrust appliance at `https://<host>/login`
2. Navigate to **Management > API Configuration**
3. Create a new API account with the desired permissions:
   - **Command API**: Read-only or Full Access (for session management)
   - **Reporting API**: Support Session, License Usage, and/or Team reports
   - **Configuration API**: Enable if you need Jump Item, user, or Vault management
   - **Backup API**: Enable for configuration backups
4. Copy the **Client ID** and **Client Secret**
5. Store credentials in the Tendril vault:

```
bridge_credentials(action="set", bridge="beyondtrust-rs", key="api_host", value="support.example.com")
bridge_credentials(action="set", bridge="beyondtrust-rs", key="client_id", value="<your-client-id>")
bridge_credentials(action="set", bridge="beyondtrust-rs", key="client_secret", value="<your-client-secret>")
```

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `bt_client.py` | `/opt/bridge/data/tools/` | Core API client -- OAuth2, Command/Reporting/Config API methods, XML parsing |
| `bt.py` | `/opt/bridge/data/tools/` | Unified CLI: health, reps, teams, sessions, clients, report, jump-items, users, jumpoints, vault, backup |
| `bt_check.py` | `/opt/bridge/data/tools/` | Health check: auth validation, appliance health, API version |

## Quick Start

```bash
python3 /opt/bridge/data/tools/bt_check.py
python3 /opt/bridge/data/tools/bt.py health check
python3 /opt/bridge/data/tools/bt.py reps list
python3 /opt/bridge/data/tools/bt.py teams list
python3 /opt/bridge/data/tools/bt.py sessions generate-key --queue-id general
python3 /opt/bridge/data/tools/bt.py jump-items list --type shell-jump
```

## CLI Reference

### bt.py health -- Appliance Health & Info

```bash
python3 bt.py health check                     # Appliance health (hostname, version, failover status)
python3 bt.py health appliances                 # All appliances in cluster/failover
python3 bt.py health api-info                   # API version and account permissions
```

### bt.py reps -- Representative Management

```bash
python3 bt.py reps list                         # All logged-in representatives
python3 bt.py reps set-status --user-id 1 --status available
python3 bt.py reps set-status --user-id 1 --status busy
python3 bt.py reps set-status --user-id 1 --status do_not_disturb
python3 bt.py reps logout --user-id 1           # Force logout
```

### bt.py teams -- Support Teams

```bash
python3 bt.py teams list                        # All teams with issue queues
```

### bt.py sessions -- Session Management

```bash
# Generate session keys
python3 bt.py sessions generate-key --queue-id general
python3 bt.py sessions generate-key --queue-id rep:1
python3 bt.py sessions generate-key --queue-id team:5
python3 bt.py sessions generate-key --queue-id rep_username:admin
python3 bt.py sessions generate-key --queue-id issue:other
python3 bt.py sessions generate-key --queue-id team:1 --ttl 3600 --priority 1
python3 bt.py sessions generate-key --queue-id team:1 --external-key "TICKET-1234"
python3 bt.py sessions generate-key --queue-id team:1 --skills "skill1,skill2"

# Session attributes
python3 bt.py sessions get-attributes --lsid <session-lsid>
python3 bt.py sessions set-attributes --lsid <lsid> --external-key "TICKET-5678"
python3 bt.py sessions set-attributes --lsid <lsid> --custom field1=value1 field2=value2

# Session lifecycle
python3 bt.py sessions join --lsid <lsid> --user-id 1
python3 bt.py sessions leave --lsid <lsid> --user-id 1
python3 bt.py sessions transfer --lsid <lsid> --queue-id team:2
python3 bt.py sessions terminate --lsid <lsid>
```

### bt.py clients -- Connected Clients

```bash
python3 bt.py clients list                      # All connected clients
python3 bt.py clients list --type representative
python3 bt.py clients list --type support_customer
python3 bt.py clients list --type push_agent
python3 bt.py clients list --summary            # Summary counts only
python3 bt.py clients detail                    # Detailed client info
python3 bt.py clients detail --type representative --connections
python3 bt.py clients detail --id 101,102,103
```

### bt.py report -- Reporting

```bash
# Support session reports
python3 bt.py report sessions                                   # All recent sessions
python3 bt.py report sessions --listing                         # Listing (summary) format
python3 bt.py report sessions --start "2026-01-01T00:00:00"     # From date
python3 bt.py report sessions --duration P7D                    # Last 7 days
python3 bt.py report sessions --lsid <session-lsid>             # Specific session
python3 bt.py report sessions --start "2026-02-01T00:00:00" --end "2026-02-28T23:59:59"

# License usage
python3 bt.py report license --duration P30D

# Team activity
python3 bt.py report teams --duration P7D
```

### bt.py jump-items -- Jump Item Management (Configuration API)

```bash
# List by type
python3 bt.py jump-items list                                    # Shell Jump (default)
python3 bt.py jump-items list --type remote-rdp                  # RDP Jump Items
python3 bt.py jump-items list --type remote-vnc                  # VNC Jump Items
python3 bt.py jump-items list --type local-jump                  # Local Jump Items
python3 bt.py jump-items list --type protocol-tunnel-jump        # Protocol Tunnel Jump
python3 bt.py jump-items list --type web-jump                    # Web Jump Items

# Filtering
python3 bt.py jump-items list --name "web-server-01"
python3 bt.py jump-items list --tag "production"
python3 bt.py jump-items list --jumpoint-id 1
python3 bt.py jump-items list --jump-group-id 1

# CRUD operations
python3 bt.py jump-items get --id 42
python3 bt.py jump-items create --json '{"name":"web-01","hostname":"10.0.1.5","jump_group_id":1,"jump_group_type":"shared","jumpoint_id":1,"protocol":"ssh","port":22,"username":"admin","terminal":"xterm"}'
python3 bt.py jump-items update --id 42 --json '{"name":"web-01-updated"}'
python3 bt.py jump-items delete --id 42

# RDP Jump Item
python3 bt.py jump-items create --type remote-rdp --json '{"name":"win-server","hostname":"10.0.1.10","jump_group_id":1,"jump_group_type":"shared","jumpoint_id":1,"rdp_username":"admin","quality":"performance"}'
```

### bt.py users -- User Configuration (Configuration API)

```bash
python3 bt.py users list                         # All users/representatives
python3 bt.py users get --id 1                   # Specific user detail
```

### bt.py jumpoints -- Jumpoint Configuration (Configuration API)

```bash
python3 bt.py jumpoints list                     # All Jumpoints
python3 bt.py jumpoints get --id 1               # Specific Jumpoint detail
```

### bt.py jump-groups -- Jump Group Configuration (Configuration API)

```bash
python3 bt.py jump-groups list                   # All Jump Groups
python3 bt.py jump-groups get --id 1             # Specific Jump Group detail
```

### bt.py vault -- Vault Management (Configuration API)

```bash
python3 bt.py vault accounts                     # List Vault accounts
python3 bt.py vault endpoints                    # List Vault endpoints
```

### bt.py group-policy -- Group Policy Configuration (Configuration API)

```bash
python3 bt.py group-policy list                  # All group policies
python3 bt.py group-policy get --id 1            # Specific policy detail
```

### bt.py backup -- Configuration Backup

```bash
python3 bt.py backup                             # Save to beyondtrust-backup.zip
python3 bt.py backup --output /tmp/bt-backup.zip # Custom output path
```

## Common Patterns

### Daily Operations Dashboard
1. `python3 bt.py health check` -- appliance status and version
2. `python3 bt.py reps list` -- who's logged in
3. `python3 bt.py clients list --summary` -- client counts
4. `python3 bt.py report sessions --duration P1D --listing` -- today's sessions

### Session Key Integration with Ticketing
1. `python3 bt.py sessions generate-key --queue-id team:1 --external-key "INC-12345" --priority 1`
2. Send the returned session key URL to the user
3. `python3 bt.py sessions get-attributes --lsid <lsid>` -- verify attributes

### Jump Item Inventory Audit
1. `python3 bt.py jump-items list --type shell-jump` -- SSH/Shell items
2. `python3 bt.py jump-items list --type remote-rdp` -- RDP items
3. `python3 bt.py jump-items list --type remote-vnc` -- VNC items
4. `python3 bt.py jumpoints list` -- Jumpoint inventory
5. `python3 bt.py jump-groups list` -- Jump Group structure

### Representative Management
1. `python3 bt.py reps list` -- see who's available
2. `python3 bt.py reps set-status --user-id 1 --status busy` -- mark busy
3. `python3 bt.py reps logout --user-id 1` -- force logout if needed
4. `python3 bt.py users list` -- full user roster

### Session Escalation
1. `python3 bt.py teams list` -- find the right team
2. `python3 bt.py sessions transfer --lsid <lsid> --queue-id team:2` -- transfer
3. `python3 bt.py sessions join --lsid <lsid> --user-id 5` -- add specialist

### Compliance & Reporting
1. `python3 bt.py report sessions --start "2026-01-01T00:00:00" --end "2026-01-31T23:59:59"` -- monthly sessions
2. `python3 bt.py report license --duration P30D` -- license utilization
3. `python3 bt.py report teams --duration P30D` -- team activity
4. `python3 bt.py vault accounts` -- Vault credential inventory
5. `python3 bt.py backup` -- configuration backup

## API Coverage

| API | Endpoint | Operations |
|-----|----------|------------|
| Command | `/api/command?action=check_health` | Appliance health, failover status |
| Command | `/api/command?action=get_appliances` | Cluster appliance list |
| Command | `/api/command?action=get_api_info` | API version and permissions |
| Command | `/api/command?action=get_logged_in_reps` | Logged-in representative list |
| Command | `/api/command?action=set_rep_status` | Set rep availability |
| Command | `/api/command?action=logout_rep` | Force rep logout |
| Command | `/api/command?action=get_support_teams` | Support team and issue list |
| Command | `/api/command?action=generate_session_key` | Session key generation |
| Command | `/api/command?action=get_session_attributes` | Get session custom fields |
| Command | `/api/command?action=set_session_attributes` | Set session custom fields |
| Command | `/api/command?action=join_session` | Add rep to session |
| Command | `/api/command?action=leave_session` | Remove rep from session |
| Command | `/api/command?action=transfer_session` | Transfer session to queue |
| Command | `/api/command?action=terminate_session` | End a session |
| Command | `/api/command?action=get_connected_client_list` | Connected client summary |
| Command | `/api/command?action=get_connected_clients` | Detailed client info |
| Reporting | `/api/reporting?report_type=SupportSession` | Full session reports |
| Reporting | `/api/reporting?report_type=SupportSessionListing` | Session listing (summary) |
| Reporting | `/api/reporting?report_type=LicenseUsage` | License usage report |
| Reporting | `/api/reporting?report_type=SupportTeam` | Team activity report |
| Config | `/api/config/v1/jump-item/{type}` | Jump Item CRUD |
| Config | `/api/config/v1/user` | User list/detail |
| Config | `/api/config/v1/jumpoint` | Jumpoint list/detail |
| Config | `/api/config/v1/jump-group` | Jump Group list/detail |
| Config | `/api/config/v1/vault/account` | Vault account inventory |
| Config | `/api/config/v1/vault/endpoint` | Vault endpoint inventory |
| Config | `/api/config/v1/group-policy` | Group policy list/detail |
| Backup | `/api/backup` | Software configuration backup |

## Rate Limits

| Window | Max Requests |
|--------|-------------|
| 1 second | 20 |
| 1 hour | 15,000 |

Rate limit headers `X-RateLimit-Limit` and `X-RateLimit-Remaining` are included in responses.

## Notes

- The API account permissions control which APIs are accessible. Enable only what you need.
- Command and Reporting APIs return **XML** responses; the bridge auto-parses these to JSON for output.
- Configuration API returns **JSON** natively with pagination (100 items/page max).
- Token max: 30 concurrent tokens per API account. Oldest token is invalidated when a 31st is created.
- Regenerating the client secret in `/login` immediately invalidates **all** existing tokens.
- When making consecutive calls, the client automatically closes and reopens connections.
- Backup files include configuration settings and logged data (excluding recordings). Files are limited to 200KB each, max 50 files total.
- Jump Item types include: `shell-jump`, `remote-rdp`, `remote-vnc`, `local-jump`, `protocol-tunnel-jump`, `web-jump`.
