---
name: microsoft-purview
description: Microsoft Purview admin operations via Security & Compliance PowerShell (Connect-IPPSSession) -- DLP policies, retention policies/labels, sensitivity labels, alert policies, eDiscovery (read-only), and information barriers. Certificate-based authentication on Linux.
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
    - purview
    - dlp
    - retention
    - sensitivity-labels
    - ediscovery
    - alert-policies
    - information-barriers
    - compliance
---

# Microsoft Purview Bridge

Microsoft Purview admin operations via **Security & Compliance PowerShell** (`Connect-IPPSSession`). This bridge uses the ExchangeOnlineManagement module with certificate-based app-only authentication, running on Linux (PowerShell 7). All connections are outbound HTTPS to `compliance.protection.outlook.com`.

This bridge complements `bridge-microsoft-graph` (Graph REST API) and `bridge-microsoft-exchange` (Exchange Online PowerShell). Operations that require the Security & Compliance PowerShell endpoint are handled here.

## License Requirements

Features vary by Microsoft 365 license tier. This bridge documents minimum requirements per tool:

| Feature | E3 / G3 | E5 / G5 | Tool |
|---------|---------|---------|------|
| DLP policies (read/audit) | Core DLP (Exchange, SPO, OneDrive) | + Endpoint DLP (Windows/macOS) | `dlp_policy.py` |
| Sensitive information types | Built-in types | + Custom types, exact data match | `dlp_policy.py` |
| Retention policies (read) | Basic labels and policies | + Advanced auto-apply, ML classification | `retention_policy.py` |
| Retention labels | Manual application | + Auto-apply, disposition review | `retention_policy.py` |
| Sensitivity labels | Manual labeling only | + Auto-labeling, meeting labels | `sensitivity_labels.py` |
| Alert policies | System-generated alerts | + Custom alert categories | `alert_policy.py` |
| eDiscovery (read-only) | Standard eDiscovery | + Premium eDiscovery | `ediscovery_search.py` |
| Information barriers | Available | Available | (via `purview_client.py`) |
| Unified audit log | Standard (180 days) | Premium (1 year) | Use `bridge-microsoft-exchange` |

## Certificate Auth Limitations

Microsoft blocks certificate-based authentication (CBA) for specific cmdlets. These operations **must be performed via the Purview portal or interactive user authentication**:

| Blocked Operation | Cmdlets | Alternative |
|-------------------|---------|-------------|
| eDiscovery write | `New-ComplianceSearch`, `Start-ComplianceSearch`, `New-ComplianceSearchAction` | Purview portal |
| Case hold management | `New/Set/Remove-CaseHoldPolicy`, `New/Set/Remove-CaseHoldRule` | Purview portal |
| Retention policy write | `New/Set-RetentionCompliancePolicy`, `New/Set-RetentionComplianceRule` | Purview portal |
| Compliance security filters | `New/Set/Remove-ComplianceSecurityFilter` | Purview portal |
| Unified audit log | `Search-UnifiedAuditLog` | `bridge-microsoft-exchange` |

All **read operations** for these categories work normally with CBA. This bridge exposes 372 cmdlets via CBA -- more than user-context connections (328).

## Setup

### Prerequisites

- An Azure/Microsoft 365 tenant with Purview features
- Azure CLI (`az`) installed, or access to the Entra admin center
- Global Administrator or Application Administrator + Compliance Administrator roles

### Option A: Automated Setup (Azure CLI)

```bash
chmod +x references/setup_purview_bridge.sh
./references/setup_purview_bridge.sh contoso.onmicrosoft.com
```

The script will create the app registration, generate a certificate, assign the Compliance Administrator role, add the Exchange.ManageAsApp permission, and output `.env` values.

### Option B: Manual Setup (Azure CLI)

```bash
az login

# Create app registration
az ad app create --display-name "Tendril Purview Bridge" --sign-in-audience AzureADMyOrg
# Note the appId from output

# Generate certificate
mkdir -p certs
openssl req -x509 -newkey rsa:2048 \
  -keyout certs/purview-bridge.key -out certs/purview-bridge.crt \
  -days 365 -nodes -subj "/CN=Tendril Purview Bridge"
openssl pkcs12 -export -out certs/purview-bridge.pfx \
  -inkey certs/purview-bridge.key -in certs/purview-bridge.crt -passout pass:

# Get thumbprint
openssl x509 -in certs/purview-bridge.crt -noout -fingerprint -sha1 \
  | sed 's/://g' | sed 's/sha1 Fingerprint=//i'

# Upload certificate
az ad app credential reset --id <app-id> --cert @certs/purview-bridge.crt --append

# Create service principal
az ad sp create --id <app-id>
# Note the SP object id

# Assign Compliance Administrator role (17315797-102d-40b4-93e0-432062caca18)
az rest --method POST \
  --url "https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignments" \
  --body "{
    \"principalId\": \"<sp-object-id>\",
    \"roleDefinitionId\": \"17315797-102d-40b4-93e0-432062caca18\",
    \"directoryScopeId\": \"/\"
  }"

# Add Exchange.ManageAsApp permission (required for Connect-IPPSSession)
az ad app permission add --id <app-id> \
  --api 00000002-0000-0ff1-ce00-000000000000 \
  --api-permissions dc50a0fb-09a3-484d-be87-e023b12c6440=Role
sleep 5
az ad app permission admin-consent --id <app-id>
```

### Option C: Manual Setup (Entra Admin Center)

1. **Create app registration**: Entra admin center > Applications > App registrations > New registration. Name: "Tendril Purview Bridge", single tenant.
2. **Upload certificate**: App registration > Certificates & secrets > Upload `purview-bridge.crt`. Note the thumbprint.
3. **Add API permission**: API permissions > Add a permission > APIs my organization uses > "Office 365 Exchange Online" > Application permissions > `Exchange.ManageAsApp`. Grant admin consent.
4. **Assign Compliance Administrator role**: Entra admin center > Roles and administrators > Compliance Administrator > Add assignments > select the service principal.
5. **Configure .env**: Copy `.env.example`, fill in values, place `.pfx` in `certs/`.

### Entra Permissions Required

| Permission / Role | Type | Purpose |
|-------------------|------|---------|
| `Exchange.ManageAsApp` | API permission (Office 365 Exchange Online, Role) | Required for Connect-IPPSSession app-only auth |
| Compliance Administrator | Entra directory role (assigned to service principal) | Grants access to all Security & Compliance cmdlets |

## Authentication

Certificate-based app-only authentication via `Connect-IPPSSession`.

- Credential: Self-signed certificate (.pfx mounted at `/opt/bridge/certs/`)
- Module: ExchangeOnlineManagement v3+ (REST-based, runs on Linux)
- Endpoint: `compliance.protection.outlook.com` (outbound HTTPS only)

## Tools

| Script | Purpose |
|--------|---------|
| `purview_client.py` | Core: Connect-IPPSSession wrapper, cmdlet dispatch, session management |
| `purview_check.py` | Core: Healthcheck (env vars, certificate, SCC connectivity) |
| `purview_bridge_tests.py` | Core: 10-test battery across 7 categories |
| `dlp_policy.py` | DLP policy/rule list, detail, sensitive info types, summary |
| `retention_policy.py` | Retention policy/rule/label list and detail (read-only) |
| `sensitivity_labels.py` | Sensitivity label inventory, label policies, auto-labeling |
| `alert_policy.py` | Alert policy list, detail, category grouping |
| `ediscovery_search.py` | eDiscovery case list, compliance search list (read-only) |

## Quick Start

```bash
python3 /opt/bridge/data/tools/purview_check.py
python3 /opt/bridge/data/tools/purview_bridge_tests.py

python3 /opt/bridge/data/tools/dlp_policy.py summary
python3 /opt/bridge/data/tools/sensitivity_labels.py summary
python3 /opt/bridge/data/tools/retention_policy.py summary
python3 /opt/bridge/data/tools/alert_policy.py summary
```

## Tool Reference

### dlp_policy.py -- Data Loss Prevention

```bash
python3 dlp_policy.py list                           # All DLP policies
python3 dlp_policy.py detail "U.S. Health Insurance Act (HIPAA)"  # Policy details
python3 dlp_policy.py rules                          # All DLP rules
python3 dlp_policy.py rules "U.S. PII Data"         # Rules for specific policy
python3 dlp_policy.py rule-detail "Rule Name"        # Detailed rule config
python3 dlp_policy.py sensitive-types                # Sensitive information types
python3 dlp_policy.py summary                        # DLP summary
```

### retention_policy.py -- Retention (Read-Only)

```bash
python3 retention_policy.py policies                 # All retention policies
python3 retention_policy.py policy-detail "Policy"   # Policy details
python3 retention_policy.py rules                    # All retention rules
python3 retention_policy.py labels                   # Retention labels (compliance tags)
python3 retention_policy.py label-detail "Label"     # Label details
python3 retention_policy.py summary                  # Retention summary
```

### sensitivity_labels.py -- Sensitivity Labels

```bash
python3 sensitivity_labels.py list                   # All sensitivity labels
python3 sensitivity_labels.py detail "Confidential"  # Label details
python3 sensitivity_labels.py policies               # Label policies
python3 sensitivity_labels.py policy-detail "Policy"  # Policy details
python3 sensitivity_labels.py auto-labeling          # Auto-labeling policies (E5)
python3 sensitivity_labels.py summary                # Label inventory summary
```

### alert_policy.py -- Alert Policies

```bash
python3 alert_policy.py list                         # All alert policies
python3 alert_policy.py detail "Alert Name"          # Policy details
python3 alert_policy.py by-category                  # Group by category
python3 alert_policy.py summary                      # Alert summary
```

### ediscovery_search.py -- eDiscovery (Read-Only)

```bash
python3 ediscovery_search.py cases                   # List eDiscovery cases
python3 ediscovery_search.py case-detail "Case"      # Case details
python3 ediscovery_search.py searches                # List compliance searches
python3 ediscovery_search.py search-detail "Search"  # Search details
python3 ediscovery_search.py case-members "Case"     # Case members
python3 ediscovery_search.py summary                 # eDiscovery summary
```

## Common Patterns

### DLP Policy Audit
1. Get overview: `python3 dlp_policy.py summary`
2. List all policies: `python3 dlp_policy.py list`
3. Inspect a specific policy: `python3 dlp_policy.py detail "U.S. PII Data"`
4. Review rules: `python3 dlp_policy.py rules "U.S. PII Data"`

### Compliance Posture Review
1. DLP: `python3 dlp_policy.py summary`
2. Retention: `python3 retention_policy.py summary`
3. Labels: `python3 sensitivity_labels.py summary`
4. Alerts: `python3 alert_policy.py summary`
5. eDiscovery: `python3 ediscovery_search.py summary`

### Retention Label Inventory
1. List all labels: `python3 retention_policy.py labels`
2. Detail on a label: `python3 retention_policy.py label-detail "Records_Retention_7yr"`
3. Cross-reference with policies: `python3 retention_policy.py policies`

## Cross-Bridge References

| Operation | Bridge | Reason |
|-----------|--------|--------|
| Unified audit log (`Search-UnifiedAuditLog`) | `bridge-microsoft-exchange` | Available via Connect-ExchangeOnline, not Connect-IPPSSession |
| Quarantine, message trace, transport rules | `bridge-microsoft-exchange` | Exchange Online PowerShell surface |
| Mail read, user/group management, Intune | `bridge-microsoft-graph` | Microsoft Graph REST API surface |
| Teams chat/messaging | `bridge-microsoft-teams-bot` (planned) | Bot Framework surface |

## API Quirks and Known Issues

- **Session overhead:** Each tool invocation creates a new PowerShell session (~8-15 seconds). Sessions are not pooled.
- **CBA cmdlet count:** CBA exposes 372 cmdlets vs 328 for user-context -- some specialized DLP cmdlets are only available via CBA.
- **Search-UnifiedAuditLog:** Not available via Connect-IPPSSession. Use the Exchange bridge.
- **Retention write operations:** `New/Set-RetentionCompliancePolicy` and `New/Set-RetentionComplianceRule` are blocked by Microsoft for CBA as of January 2026.
- **eDiscovery write operations:** `New/Start-ComplianceSearch` and related cmdlets blocked by Microsoft for CBA.
- **Auto-labeling:** `Get-AutoSensitivityLabelPolicy` requires E5 licensing. Returns a "not recognized" error on E3-only tenants.
- **Certificate expiry:** Self-signed certificates expire after 1 year. Regenerate before expiry.
- **PowerShell base image:** Uses `mcr.microsoft.com/powershell:7.4-debian-bookworm`. The custom Dockerfile is preserved by `trellis build`.

## Battery Test

```bash
python3 /opt/bridge/data/tools/purview_bridge_tests.py
```

Tests 10 operations across 7 categories: Connection, DLP, Retention, Sensitivity Labels, Alert Policies, eDiscovery, and Information Barriers.
