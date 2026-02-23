---
name: microsoft-exchange
description: Exchange Online admin operations not available through Microsoft Graph API -- quarantine management, message trace, full mailbox delegation (FullAccess/Send-As/Send-on-Behalf), shared mailbox conversion, transport rules, and EOP policy management. Uses Exchange Online PowerShell with certificate-based authentication on Linux.
compatibility:
  - platform: linux
    arch: amd64
metadata:
  author: tendril-project
  version: "2026.02.23.1"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - microsoft
    - exchange-online
    - quarantine
    - mail-flow
    - message-trace
    - mailbox-permissions
    - shared-mailbox
    - transport-rules
    - eop
---

# Microsoft Exchange Bridge

Exchange Online admin operations that are **not available through Microsoft Graph REST API**. This bridge uses the ExchangeOnlineManagement PowerShell module with certificate-based app-only authentication, running on Linux (PowerShell 7). All connections are outbound HTTPS to `outlook.office365.com` -- no WinRM, no Windows dependency.

This bridge complements `bridge-microsoft-graph`, which handles Graph REST API operations (users, groups, mail read, Intune, SharePoint, Defender, etc.). Operations that require Exchange Online PowerShell are handled here.

## Setup

### Prerequisites

- An Azure/Microsoft 365 tenant with Exchange Online
- Azure CLI (`az`) installed, or access to the Entra admin center
- Global Administrator or a combination of Application Administrator + Exchange Administrator roles

### Option A: Automated Setup (Azure CLI)

A setup script is included in `references/setup_exchange_bridge.sh`. Run it with your tenant domain:

```bash
chmod +x references/setup_exchange_bridge.sh
./references/setup_exchange_bridge.sh contoso.onmicrosoft.com
```

The script will:
1. Create an Entra app registration ("Tendril Exchange Bridge")
2. Generate a self-signed certificate (1-year validity)
3. Upload the certificate to the app registration
4. Create a service principal
5. Assign the Exchange Administrator directory role
6. Add the Exchange.ManageAsApp API permission with admin consent
7. Output the `.env` values and certificate files

### Option B: Manual Setup (Azure CLI, step-by-step)

```bash
# 1. Login to Azure
az login

# 2. Create the app registration
az ad app create \
  --display-name "Tendril Exchange Bridge" \
  --sign-in-audience AzureADMyOrg

# Save the appId from the output -- you'll need it for all subsequent steps.
# Example: "appId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# 3. Generate a self-signed certificate
mkdir -p certs
openssl req -x509 -newkey rsa:2048 \
  -keyout certs/exchange-bridge.key \
  -out certs/exchange-bridge.crt \
  -days 365 -nodes \
  -subj "/CN=Tendril Exchange Bridge"

# 4. Create PFX for the Docker container
openssl pkcs12 -export \
  -out certs/exchange-bridge.pfx \
  -inkey certs/exchange-bridge.key \
  -in certs/exchange-bridge.crt \
  -passout pass:

# 5. Get the certificate thumbprint
openssl x509 -in certs/exchange-bridge.crt -noout -fingerprint -sha1 \
  | sed 's/://g' | sed 's/sha1 Fingerprint=//i'

# 6. Upload the certificate to the app registration
az ad app credential reset \
  --id <your-app-id> \
  --cert @certs/exchange-bridge.crt \
  --append

# 7. Create the service principal
az ad sp create --id <your-app-id>

# Save the service principal "id" (object ID) from the output.

# 8. Assign Exchange Administrator role to the service principal
# Exchange Administrator role ID: 29232cdf-9323-42fd-ade2-1d097af3e4de
az rest --method POST \
  --url "https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignments" \
  --body "{
    \"principalId\": \"<sp-object-id>\",
    \"roleDefinitionId\": \"29232cdf-9323-42fd-ade2-1d097af3e4de\",
    \"directoryScopeId\": \"/\"
  }"

# 9. Add Exchange.ManageAsApp API permission
# Office 365 Exchange Online resource: 00000002-0000-0ff1-ce00-000000000000
# Exchange.ManageAsApp permission:     dc50a0fb-09a3-484d-be87-e023b12c6440
az ad app permission add \
  --id <your-app-id> \
  --api 00000002-0000-0ff1-ce00-000000000000 \
  --api-permissions dc50a0fb-09a3-484d-be87-e023b12c6440=Role

# 10. Grant admin consent
az ad app permission admin-consent --id <your-app-id>
```

### Option C: Manual Setup (Entra Admin Center)

1. **Create app registration**
   - Navigate to [Entra admin center](https://entra.microsoft.com) > Applications > App registrations > New registration
   - Name: "Tendril Exchange Bridge"
   - Supported account types: "Accounts in this organizational directory only"
   - Click Register

2. **Upload certificate**
   - Generate the certificate using the `openssl` commands in Option B (steps 3-4)
   - In the app registration > Certificates & secrets > Certificates > Upload certificate
   - Upload `exchange-bridge.crt`
   - Note the **Thumbprint** value

3. **Add API permission**
   - App registration > API permissions > Add a permission
   - Select "APIs my organization uses" > search for "Office 365 Exchange Online"
   - Select Application permissions > Exchange > `Exchange.ManageAsApp`
   - Click "Grant admin consent for [your org]"

4. **Assign Exchange Administrator role**
   - Entra admin center > Roles and administrators > Exchange Administrator
   - Add assignments > select the app's service principal ("Tendril Exchange Bridge")
   - Assign

5. **Configure .env**
   - Copy `.env.example` to `.env`
   - Fill in: `EXO_TENANT_ID`, `EXO_APP_ID` (from app registration), `EXO_CERT_THUMBPRINT`, `EXO_ORGANIZATION` (your `*.onmicrosoft.com` domain)
   - Place the `.pfx` file in the `certs/` directory

### Entra Permissions Required

| Permission / Role | Type | Purpose |
|-------------------|------|---------|
| `Exchange.ManageAsApp` | API permission (Office 365 Exchange Online, Role) | Allows app-only Exchange Online PowerShell connections |
| Exchange Administrator | Entra directory role (assigned to service principal) | Grants administrative access to all Exchange Online cmdlets |

## Authentication

Certificate-based app-only authentication via `Connect-ExchangeOnline`.

- Credential: Self-signed certificate (.pfx mounted as Docker volume at `/opt/bridge/certs/`)
- Module: ExchangeOnlineManagement v3+ (REST-based, runs on Linux)
- The certificate never leaves the container. All connections are outbound HTTPS.

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `exchange_client.py` | `/opt/bridge/data/tools/` | Core PowerShell wrapper: Connect-ExchangeOnline, cmdlet dispatch, session management |
| `exchange_check.py` | `/opt/bridge/data/tools/` | Healthcheck: validates env vars, certificate, and EXO connectivity |
| `exchange_bridge_tests.py` | `/opt/bridge/data/tools/` | Battery test: 10 tests across 6 categories |
| `quarantine_check.py` | `/opt/bridge/data/tools/` | List, search, preview, release, delete quarantined messages |
| `mail_flow.py` | `/opt/bridge/data/tools/` | Message trace, transport rules |
| `mailbox_permissions.py` | `/opt/bridge/data/tools/` | Full mailbox delegation: FullAccess, Send-As, Send-on-Behalf, folder permissions |
| `mailbox_convert.py` | `/opt/bridge/data/tools/` | Convert to shared mailbox, set/clear forwarding |

## Quick Start

```bash
# Verify bridge connectivity and certificate auth
python3 /opt/bridge/data/tools/exchange_check.py

# Run full battery test
python3 /opt/bridge/data/tools/exchange_bridge_tests.py

# List recent quarantined messages
python3 /opt/bridge/data/tools/quarantine_check.py list

# Quarantine summary (7-day stats)
python3 /opt/bridge/data/tools/quarantine_check.py summary
```

## Tool Reference

### quarantine_check.py -- Quarantine Management

```bash
python3 quarantine_check.py list                           # Recent quarantined messages (3 days)
python3 quarantine_check.py list --days 7                  # Last 7 days
python3 quarantine_check.py search user@external.com       # Search by sender
python3 quarantine_check.py search "invoice attached"      # Search by subject
python3 quarantine_check.py detail <identity>              # Full details for a message
python3 quarantine_check.py release <identity>             # Release from quarantine
python3 quarantine_check.py release-all --sender user@ext  # Release all from a sender
python3 quarantine_check.py delete <identity>              # Delete from quarantine
python3 quarantine_check.py summary                        # 7-day quarantine statistics
```

### mail_flow.py -- Message Trace and Transport Rules

```bash
python3 mail_flow.py trace --sender user@external.com      # Trace by sender (2 days)
python3 mail_flow.py trace --recipient user@example.com    # Trace by recipient
python3 mail_flow.py trace --sender user@ext --days 7      # Extended date range
python3 mail_flow.py trace --messageid <id>                # Trace specific message
python3 mail_flow.py rules                                  # List all transport rules
python3 mail_flow.py rule-detail "Rule Name"               # Transport rule details
```

### mailbox_permissions.py -- Full Mailbox Delegation

```bash
python3 mailbox_permissions.py check user@example.com                   # All permissions
python3 mailbox_permissions.py full-access user@example.com             # FullAccess delegates
python3 mailbox_permissions.py send-as user@example.com                 # Send-As permissions
python3 mailbox_permissions.py send-on-behalf user@example.com          # Send-on-Behalf
python3 mailbox_permissions.py folder user@example.com Inbox            # Folder-level permissions
python3 mailbox_permissions.py grant-full shared@example.com user@ex    # Grant FullAccess
python3 mailbox_permissions.py revoke-full shared@example.com user@ex   # Revoke FullAccess
python3 mailbox_permissions.py grant-sendas shared@example.com user@ex  # Grant Send-As
python3 mailbox_permissions.py revoke-sendas shared@example.com user@ex # Revoke Send-As
```

### mailbox_convert.py -- Shared Mailbox and Forwarding

```bash
python3 mailbox_convert.py info user@example.com                          # Mailbox type and properties
python3 mailbox_convert.py to-shared user@example.com                     # Convert to shared mailbox
python3 mailbox_convert.py to-user shared@example.com                     # Convert back to user
python3 mailbox_convert.py set-forwarding user@example.com target@ex.com  # Set forwarding
python3 mailbox_convert.py clear-forwarding user@example.com              # Remove forwarding
python3 mailbox_convert.py check-forwarding user@example.com              # Check forwarding status
```

## Common Patterns

### Quarantine Investigation
1. Check quarantine summary: `python3 quarantine_check.py summary`
2. Search for specific sender: `python3 quarantine_check.py search suspicious@external.com`
3. Preview the message: `python3 quarantine_check.py detail <identity>`
4. Release if legitimate: `python3 quarantine_check.py release <identity>`

### Email Delivery Troubleshooting
1. Trace the message: `python3 mail_flow.py trace --sender user@external.com --recipient user@example.com`
2. Check quarantine: `python3 quarantine_check.py search user@external.com`
3. Check transport rules: `python3 mail_flow.py rules`

### Offboarding (Shared Mailbox Conversion)
1. Check current state: `python3 mailbox_convert.py info user@example.com`
2. Convert to shared: `python3 mailbox_convert.py to-shared user@example.com`
3. Set forwarding: `python3 mailbox_convert.py set-forwarding user@example.com manager@example.com`
4. Grant access to manager: `python3 mailbox_permissions.py grant-full user@example.com manager@example.com`

### Shared Mailbox Delegation Audit
1. Check all permissions: `python3 mailbox_permissions.py check shared@example.com`
2. Review FullAccess: `python3 mailbox_permissions.py full-access shared@example.com`
3. Review Send-As: `python3 mailbox_permissions.py send-as shared@example.com`

## Cross-Bridge References

Operations that live on other bridges:

| Operation | Bridge | Reason |
|-----------|--------|--------|
| Read mail content, folder sizes, inbox rules | `bridge-microsoft-graph` | Available via Graph API (`Mail.ReadWrite`) |
| Calendar permissions, mailbox settings | `bridge-microsoft-graph` | Available via Graph API |
| User/group management, license assignment | `bridge-microsoft-graph` | Available via Graph API |
| eDiscovery, content search, DLP, retention | `bridge-microsoft-purview` (planned) | Security & Compliance PowerShell surface |
| Teams chat/channel messaging | `bridge-microsoft-teams-bot` (planned) | Bot Framework surface |

## API Quirks and Known Issues

- **Session duration:** Each tool invocation creates a new PowerShell session (connect, run, disconnect). Sessions are not pooled across calls. This adds ~5-10 seconds of overhead per invocation for authentication.
- **Certificate path:** The .pfx file is expected at `/opt/bridge/certs/exchange-bridge.pfx` (mounted read-only from the host). Override with `EXO_CERT_DIR` and `EXO_CERT_FILENAME` env vars.
- **Rate limits:** Exchange Online PowerShell has per-app throttling. Heavy batch operations (e.g., releasing hundreds of quarantine messages) may hit limits.
- **Quarantine identity:** The `Identity` field for quarantined messages is a long GUID-like string. Use `list` or `search` to discover identities before using `detail`, `release`, or `delete`.
- **Message trace lag:** Message trace data may have a 5-30 minute delay from the time of message delivery.
- **Shared mailbox detection:** `RecipientTypeDetails` is the authoritative field for identifying shared mailboxes (`SharedMailbox` vs `UserMailbox`).
- **Certificate expiry:** Self-signed certificates expire after 1 year. Regenerate and re-upload before expiry. The `setup_exchange_bridge.sh` script automates this.
- **PowerShell base image:** This bridge uses `mcr.microsoft.com/powershell:7.4-debian-bookworm` instead of `tendril-bridge-base`. The custom Dockerfile is preserved by `trellis build` (it does not contain the `# Generated by trellis` header).

## Battery Test

```bash
python3 /opt/bridge/data/tools/exchange_bridge_tests.py
```

Tests 10 operations across 6 categories: Connection, Quarantine, Mail Flow, Organization, Mailbox, and EOP.
