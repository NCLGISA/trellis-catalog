---
name: microsoft-graph
description: Full management of a Microsoft 365 tenant via Graph API -- Entra ID users/groups, Exchange Online mailboxes, Intune devices/apps/config, SharePoint/OneDrive, Teams, Defender security alerts/incidents, Identity Protection, Conditional Access, LAPS passwords, licenses, audit logs, and usage reports.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.16"
metadata:
  author: tendril-project
  version: "2.1.0"
  tendril-bridge: "true"
  tags:
    - microsoft
    - m365
    - graph
    - entra-id
    - exchange-online
    - intune
    - sharepoint
    - teams
    - defender
    - laps
    - conditional-access
    - identity-protection
---

# Microsoft Graph API Bridge

Full management of your Microsoft 365 tenant via the Microsoft Graph REST API v1.0. Covers 10 product areas: Entra ID identity, Exchange Online, Intune endpoint management, SharePoint/OneDrive, Microsoft Teams, Defender XDR, Identity Protection, Conditional Access, LAPS password management, licensing, audit logs, and usage reporting.

## Authentication

MSAL `client_credentials` flow using an Entra ID App Registration ("Tendril Graph Bridge"). Tokens are valid for ~1 hour and auto-refreshed by the client library.

**App Registration:** Configured via AZURE_CLIENT_ID environment variable
**Tenant:** Configured via AZURE_TENANT_ID environment variable

**Application permissions (24, admin-consented):**

| Permission | Scope |
|------------|-------|
| `User.ReadWrite.All` | Read/write all user profiles |
| `Group.ReadWrite.All` | Read/write all groups |
| `Directory.ReadWrite.All` | Read/write directory data, service principals |
| `Mail.ReadWrite` | Read/write mail in all mailboxes |
| `MailboxSettings.ReadWrite` | Read/write mailbox settings (forwarding, OOF, timezone) |
| `Calendars.ReadWrite` | Read/write calendars and permissions |
| `Sites.ReadWrite.All` | Read/write all SharePoint sites and document libraries |
| `DeviceManagementManagedDevices.Read.All` | Read Intune managed devices |
| `DeviceManagementConfiguration.ReadWrite.All` | Read/write Intune device configurations |
| `DeviceManagementApps.ReadWrite.All` | Read/write Intune mobile/managed apps |
| `DeviceManagementRBAC.ReadWrite.All` | Read/write Intune RBAC role definitions |
| `DeviceManagementServiceConfig.ReadWrite.All` | Read/write Intune service configuration |
| `DeviceLocalCredential.Read.All` | Read Windows LAPS passwords backed up to Entra ID |
| `TeamSettings.ReadWrite.All` | Read/write Teams settings |
| `Channel.ReadBasic.All` | Read Teams channel names and descriptions |
| `SecurityAlert.ReadWrite.All` | Read/write Defender security alerts |
| `SecurityIncident.ReadWrite.All` | Read/write Defender security incidents |
| `SecurityEvents.ReadWrite.All` | Read/write security events |
| `IdentityRiskyUser.ReadWrite.All` | Read/write risky user data (Identity Protection) |
| `IdentityRiskEvent.ReadWrite.All` | Read/write risk detection events |
| `Policy.ReadWrite.ConditionalAccess` | Read/write Conditional Access policies |
| `AuditLog.Read.All` | Read all audit and sign-in logs |
| `Reports.Read.All` | Read usage reports (Office 365 active users, auth methods) |
| `Organization.Read.All` | Read tenant and domain information |

Credentials are stored as container environment variables (account-level, not per-operator).

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `graph_client.py` | `/opt/bridge/data/tools/` | Core REST API client with MSAL auth, pagination, rate limiting. All other tools depend on this. |
| `graph_check.py` | `/opt/bridge/data/tools/` | Health check: validates env vars and API access |
| `graph_bridge_tests.py` | `/opt/bridge/data/tools/` | Comprehensive read-only battery test (33 tests across 9 categories) |
| `user_lookup.py` | `/opt/bridge/data/tools/` | User search, group membership, sign-in activity |
| `mailbox_check.py` | `/opt/bridge/data/tools/` | Mailbox diagnostics: settings, forwarding, rules, folders, calendar |
| `license_check.py` | `/opt/bridge/data/tools/` | License inventory, per-user licenses, assignment/removal |
| `laps_lookup.py` | `/opt/bridge/data/tools/` | LAPS password lookup, coverage audit, stale password detection |
| `security_check.py` | `/opt/bridge/data/tools/` | Defender alerts/incidents, Secure Score, Identity Protection, Conditional Access |
| `teams_check.py` | `/opt/bridge/data/tools/` | Teams inventory, channels, membership |
| `intune_check.py` | `/opt/bridge/data/tools/` | Extended Intune: device overview, apps, configs, compliance, RBAC, stale/noncompliant |
| `mailbox_admin.py` | `/opt/bridge/data/tools/` | Shared mailbox delegation, distribution list management, room calendar admin |

## Quick Start

```bash
# Verify bridge connectivity
python3 /opt/bridge/data/tools/graph_check.py

# Test Graph API access
python3 /opt/bridge/data/tools/graph_client.py test

# Security dashboard
python3 /opt/bridge/data/tools/security_check.py dashboard

# LAPS password lookup
python3 /opt/bridge/data/tools/laps_lookup.py <hostname>

# LAPS coverage audit
python3 /opt/bridge/data/tools/laps_lookup.py audit

# Run full battery test
python3 /opt/bridge/data/tools/graph_bridge_tests.py
```

## Tool Reference

### laps_lookup.py -- LAPS Password Management

```bash
python3 laps_lookup.py <hostname>          # Get LAPS password for a device
python3 laps_lookup.py search <query>      # Search devices by partial name
python3 laps_lookup.py audit               # LAPS coverage report (all Windows devices)
python3 laps_lookup.py sample [N]          # Random sample of N devices (default 5)
python3 laps_lookup.py stale [days]        # Devices with LAPS older than N days (default 30)
```

### security_check.py -- Security Posture

```bash
python3 security_check.py dashboard              # Full security dashboard
python3 security_check.py alerts [--severity high] # Defender alerts
python3 security_check.py incidents               # Defender incidents
python3 security_check.py score                   # Microsoft Secure Score
python3 security_check.py risky-users             # Risky users (Identity Protection)
python3 security_check.py risk-detections         # Risk detection events
python3 security_check.py ca-policies             # Conditional Access policies
python3 security_check.py named-locations         # CA named locations
python3 security_check.py sign-ins [user@...]     # Recent sign-in logs
```

### teams_check.py -- Microsoft Teams

```bash
python3 teams_check.py list                     # List all teams
python3 teams_check.py info <team-name>         # Team details and channels
python3 teams_check.py members <team-name>      # Team membership
python3 teams_check.py search <query>           # Search teams by name
python3 teams_check.py summary                  # Tenant-wide Teams summary
```

### intune_check.py -- Extended Intune Management

```bash
python3 intune_check.py overview                 # Device counts by OS, compliance
python3 intune_check.py devices [--os windows]   # List managed devices
python3 intune_check.py device <name>            # Detailed device info
python3 intune_check.py apps                     # Deployed Intune apps
python3 intune_check.py configs                  # Device configuration profiles
python3 intune_check.py compliance               # Compliance policies
python3 intune_check.py roles                    # Intune RBAC roles
python3 intune_check.py stale [days]             # Devices not synced in N days
python3 intune_check.py noncompliant             # Noncompliant devices
```

### user_lookup.py -- User Management

```bash
python3 user_lookup.py search "john doe"        # Search users by name
python3 user_lookup.py info user@example.com  # Detailed user profile
python3 user_lookup.py groups user@example.com  # Group membership
python3 user_lookup.py signins user@example.com  # Sign-in history
```

### mailbox_check.py -- Exchange Online

```bash
python3 mailbox_check.py user@example.com           # Full mailbox diagnostics
python3 mailbox_check.py user@example.com settings   # Mailbox settings
python3 mailbox_check.py user@example.com rules      # Inbox rules (forwarding)
python3 mailbox_check.py user@example.com folders    # Folder sizes
```

### license_check.py -- License Management

```bash
python3 license_check.py inventory              # All tenant SKUs with counts
python3 license_check.py user user@...          # Licenses for a user
python3 license_check.py assign user@... SPE_E3 # Assign license
python3 license_check.py remove user@... SPE_E3 # Remove license
```

### mailbox_admin.py -- Shared Mailbox, DL, and Room Calendar Admin

```bash
python3 mailbox_admin.py delegates user@example.com           # List calendar delegates
python3 mailbox_admin.py grant user@example.com delegate@example.com  # Grant delegate access
python3 mailbox_admin.py dl-list                                     # List distribution groups
python3 mailbox_admin.py dl-search "IT Staff"                       # Search DLs by name
python3 mailbox_admin.py dl-members "IT Staff"                      # List members of a DL
python3 mailbox_admin.py dl-add <group-id> user@example.com   # Add user to DL
python3 mailbox_admin.py dl-remove <group-id> <user-id>             # Remove user from DL
python3 mailbox_admin.py rooms                                       # List conference rooms
python3 mailbox_admin.py room-calendar room@example.com       # Room calendar (7 days)
python3 mailbox_admin.py shared-mailboxes                            # List shared mailboxes
```

### graph_client.py -- CLI Quick Access

```bash
python3 graph_client.py test                    # Health check / connection test
python3 graph_client.py users                   # List all users
python3 graph_client.py groups                  # List all groups
python3 graph_client.py licenses                # License inventory
python3 graph_client.py domains                 # Verified domains
```

## API Coverage

### Users (Entra ID)

```python
from graph_client import GraphClient
client = GraphClient()

client.list_users(select="id,displayName,mail", filter_expr="department eq 'IT'")
client.get_user("user@example.com")
client.search_users("john doe")
client.update_user("user@example.com", {"jobTitle": "Network Admin"})
client.disable_user("user@example.com")
client.enable_user("user@example.com")
```

### Groups

```python
client.list_groups(filter_expr="displayName eq 'VPN Users'")
client.get_group("<group-id>")
client.list_group_members("<group-id>")
client.add_group_member("<group-id>", "<user-id>")
client.remove_group_member("<group-id>", "<user-id>")
```

### Licenses

```python
client.list_subscribed_skus()           # All tenant SKUs with consumed/available
client.get_user_licenses("user@...")    # Licenses assigned to a user
client.assign_license("user@...", "<sku-id>")
client.remove_license("user@...", "<sku-id>")
```

### Mailbox (Exchange Online)

```python
client.get_mailbox_settings("user@...")  # Auto-reply, timezone, forwarding
client.get_mail_folders("user@...")      # Folder names, sizes, unread counts
client.get_inbox_rules("user@...")       # Forwarding rules, auto-move, auto-delete
client.list_messages("user@...", folder="inbox", top=10)
client.send_mail("user@...", "Subject", "Body text", ["recipient@..."])
```

### Mailbox Delegation

```python
client.list_mailbox_permissions("user@...")             # List calendar delegates
client.grant_mailbox_delegate("mailbox@...", "delegate@example.com", role="editor")  # Grant access
```

### Distribution Lists (Mail-Enabled Groups)

```python
client.list_distribution_groups()                       # All distribution groups
client.search_distribution_groups("IT Staff")           # Search by name
client.list_distribution_group_members("<group-id>")    # DL membership
client.add_distribution_group_member("<group-id>", "<user-id>")
client.remove_distribution_group_member("<group-id>", "<member-id>")
```

### Room Calendars (Conference Rooms)

```python
client.list_rooms()                                     # All conference rooms
client.list_room_lists()                                # Room lists/buildings
client.get_room_calendar("room@...", start="2026-02-16T00:00:00Z")  # Room schedule
```

### Calendar

```python
client.get_calendar_permissions("user@...")  # Who has access to calendar
```

### Intune (Device Management)

```python
client.list_managed_devices()                   # All Intune-managed devices
client.get_managed_device("<device-id>")        # Single device details
client.list_compliance_policies()               # Compliance policy list
client.list_intune_apps()                       # Deployed apps
client.list_device_configurations()             # Configuration profiles
client.get_managed_device_overview()            # OS/compliance counts
client.list_intune_role_definitions()           # RBAC roles
```

### LAPS (Windows Local Admin Passwords)

```python
client.list_laps_devices()                      # All devices with LAPS backed up
client.get_device_laps("<entra-device-id>")     # LAPS credentials for a device
```

**Notes:**
- LAPS passwords are base64-encoded (UTF-8). The `laps_lookup.py` tool handles decoding.
- The `credentials` array contains the current password plus rotation history.
- Windows 11 devices have OS versions starting with `10.0.2` (e.g., `10.0.22631.xxxx`).
- Requires `DeviceLocalCredential.Read.All` permission.

### SharePoint / OneDrive

```python
client.list_sites(search="hr")          # Search SharePoint sites
client.get_site("<site-id>")            # Site details
client.list_site_drives("<site-id>")    # Document libraries
```

### Teams

```python
client.list_teams()                          # All teams in the tenant
client.get_team("<team-id>")                 # Team settings
client.list_team_channels("<team-id>")       # Channels in a team
client.list_team_members("<team-id>")        # Team membership
```

### Security / Defender XDR

```python
client.list_security_alerts(top=50)          # Defender alerts
client.list_security_incidents(top=50)       # Defender incidents
client.get_secure_scores(top=1)              # Microsoft Secure Score
```

### Identity Protection (Entra ID P2)

```python
client.list_risky_users()                    # Users flagged as risky
client.list_risk_detections(top=50)          # Risk detection events
```

### Conditional Access

```python
client.list_conditional_access_policies()    # All CA policies
client.list_named_locations()                # CA named locations (IP ranges, countries)
```

### Reports

```python
client.get_office365_active_users(period="D7")           # Active user report (CSV)
client.get_auth_methods_registration()                    # MFA/SSPR registration details
```

### Directory / Organization

```python
client.get_organization()               # Tenant info
client.list_domains()                   # Verified domains
client.list_service_principals()        # App registrations
```

### Audit Logs

```python
client.list_sign_ins(user_id="<user-object-id>", top=20)   # Sign-in logs
client.list_directory_audit_logs(top=20)                     # Directory changes
```

## Common Patterns

### Onboarding Workflow
1. Create user via your identity management tool (on-prem AD, syncs to Entra via Azure AD Connect)
2. Wait for sync (~30 min) or force sync
3. Assign M365 license: `python3 license_check.py assign user@example.com SPE_E3`
4. Add to security groups: use `graph_client.py` or `user_lookup.py groups`
5. Verify mailbox: `python3 mailbox_check.py user@example.com`

### Offboarding Workflow
1. Disable sign-in: `client.disable_user("user@example.com")`
2. Check forwarding rules: `python3 mailbox_check.py user@example.com`
3. Convert to shared mailbox (requires Exchange admin, not yet automated)
4. Remove licenses: `python3 license_check.py remove user@example.com SPE_E3`
5. Remove from groups: use `user_lookup.py groups` to audit, then remove

### Shared Mailbox Delegation
1. List shared mailboxes: `python3 mailbox_admin.py shared-mailboxes`
2. View existing delegates: `python3 mailbox_admin.py delegates shared-mailbox@example.com`
3. Grant delegate access: `python3 mailbox_admin.py grant shared-mailbox@example.com user@example.com`

### Distribution List Management
1. Find the DL: `python3 mailbox_admin.py dl-search "IT Staff"`
2. View members: `python3 mailbox_admin.py dl-members "IT Staff"`
3. Add member: `python3 mailbox_admin.py dl-add <group-id> user@example.com`
4. Remove member: `python3 mailbox_admin.py dl-remove <group-id> <user-id>`

### Room Calendar Booking Check
1. List rooms: `python3 mailbox_admin.py rooms`
2. Check availability: `python3 mailbox_admin.py room-calendar room@example.com`

### Email Troubleshooting
1. Check mailbox health: `python3 mailbox_check.py user@example.com`
2. Look for forwarding rules (often cause of "not receiving email")
3. Check folder sizes (large Deleted Items or Junk can cause issues)
4. Verify calendar permissions for shared calendar issues

### LAPS Password Retrieval
1. Look up by hostname: `python3 laps_lookup.py <hostname>`
2. Audit coverage: `python3 laps_lookup.py audit` to find devices without LAPS
3. Check for stale passwords: `python3 laps_lookup.py stale 30` to find passwords not rotated in 30+ days
4. Random spot-check: `python3 laps_lookup.py sample 10`

### Security Investigation
1. Run dashboard: `python3 security_check.py dashboard` for full overview
2. Check Defender alerts: `python3 security_check.py alerts --severity high`
3. Review risky users: `python3 security_check.py risky-users`
4. Check sign-ins for a user: `python3 security_check.py sign-ins user@example.com`
5. Review CA policies: `python3 security_check.py ca-policies`

### Intune Device Audit
1. Overview: `python3 intune_check.py overview`
2. Find stale devices: `python3 intune_check.py stale 30`
3. Find noncompliant: `python3 intune_check.py noncompliant`
4. Device detail: `python3 intune_check.py device <name>`

## Battery Test

Run the comprehensive read-only battery test to verify all 24 permissions and API connectivity:

```bash
python3 /opt/bridge/data/tools/graph_bridge_tests.py
```

The test covers 33 tests across 9 categories: Bridge Health, Users/Entra ID, Groups, Directory/AD Sync, Security/Audit, Licensing, SharePoint/OneDrive, Intune, and Exchange Online.

## API Quirks and Known Issues

- **Pagination:** Graph uses `@odata.nextLink` for cursor-based pagination. The `get_all()` method handles this automatically.
- **$search requires ConsistencyLevel:** User search requires the `ConsistencyLevel: eventual` header, which the client sets automatically.
- **Shared mailbox detection:** Graph does not have a clean `recipientType` filter for shared mailboxes. Detection requires checking `accountEnabled` and absence of licenses.
- **Mailbox size:** Graph does not expose total mailbox size directly. Sum folder `sizeInBytes` for an approximation.
- **Azure AD Connect sync delay:** Users created on-prem take ~30 minutes to appear in Entra ID. The `onPremisesSyncEnabled` and `onPremisesLastSyncDateTime` properties track sync status.
- **Rate limits:** Graph API has per-app and per-tenant rate limits. The client handles 429 responses with `Retry-After` backoff automatically.
- **Application vs delegated permissions:** This bridge uses application permissions (no user context). Some operations that require user context (e.g., sending mail "as" a user) work with `Mail.Send` application permission but the sender is the app, not the user.
- **LAPS passwords are base64:** The `passwordBase64` field in LAPS credentials is base64-encoded UTF-8. The `laps_lookup.py` tool decodes automatically. Do NOT display the raw base64 -- always decode first.
- **Windows 11 detection:** Windows 11 devices show `osVersion` starting with `10.0.2` (build 22000+). Do not filter by "11" in the version string.
- **Usage reports return CSV:** Endpoints like `getOffice365ActiveUserDetail` return CSV, not JSON. The `get_office365_active_users()` method returns raw text.
- **Permission propagation:** After adding new Graph permissions, allow 5-15 minutes for full propagation across all Microsoft services (Intune, Exchange, Defender).
- **SharePoint personal sites:** Some SharePoint sites (personal OneDrive sites) may return 403 even with `Sites.ReadWrite.All`. The battery test handles this gracefully.
