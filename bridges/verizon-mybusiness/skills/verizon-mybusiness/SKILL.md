---
name: verizon-mybusiness
description: Manage a Verizon wireless fleet via the MyBusiness portal API -- device inventory with IMEI/SIM detail, billing summaries, upgrade eligibility, SIM protection status, and cross-bridge correlation to Sierra AirLink gateways and Intune iPads.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.03.07"
metadata:
  author: tendril-project
  version: "2026.03.07.1"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    department: ["it"]
    discovery:
      - verizon
      - mybusiness
      - wireless
      - cellular
      - fleet
      - billing
      - sim
      - firstnet
      - fleet-tracking
  references:
    - file: "ik-verizon-fleet.md"
      description: "Cost center to department mappings, device type categories, account numbers, fleet statistics"
credential_requirements:
  - key: VZ_USERNAME
    description: "Verizon MyBusiness portal username"
    required: true
  - key: VZ_PASSWORD
    description: "Verizon MyBusiness portal password"
    required: true
canopy_references:
  - organizational-glossary
  - fleet-correlation
---

# Verizon MyBusiness API Bridge

Programmatic access to the Verizon MyBusiness portal for managing a wireless fleet. Covers fleet inventory, per-line device detail with IMEI and SIM identifiers, billing account summaries, upgrade eligibility, SIM protection status, and device lock state.

## Authentication

- **Type:** REST-based ForgeRock Access Management SSO with programmatic SMS MFA code entry
- **Auth protocol:** ForgeRock authentication tree callbacks via REST API (no browser required)
- **Session mechanism:** HTTP session cookies (`b2bssoid`, `JSESSIONIDMBT`, `JSESSIONID`)
- **No API keys, no bearer tokens** -- the Verizon MyBusiness API uses pure session cookies
- **Credentials:** `VZ_USERNAME` and `VZ_PASSWORD` stored per-operator via `bridge_credentials`
- **MFA:** SMS one-time code submitted programmatically via the ForgeRock callback API
- **Session persistence:** Cookies stored in per-operator session file (`/opt/bridge/data/session/<operator>.json`)
- **Session lifetime:** 4+ hours with periodic keepalive pings (every 5 minutes)
- **Re-auth trigger:** When any API call returns HTTP 302 redirect to login page

### Credential Setup (per-operator)

Each operator who needs access must store their Verizon portal credentials in the Tendril credential vault:

```
bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_USERNAME", value="<your_username>")
bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_PASSWORD", value="<your_password>")
```

Credentials are encrypted at rest and injected as environment variables only for the duration of command execution. Values are never exposed via `bridge_credentials(action="list")`.

### MFA Workflow

The ForgeRock login is a multi-step REST callback flow. Username and password are submitted automatically using vault credentials. The SMS MFA step requires operator interaction:

**Two-phase authentication** (recommended for Tendril execute):
```bash
# Phase 1: Submit credentials, trigger SMS delivery
python3 auth_session.py initiate
# Output: "SMS code sent to (XXX) XXX-XXXX. Waiting for code..."
# Output: "Auth state saved. Run: auth_session.py complete --code <code>"

# Phase 2: Submit the SMS code received on your phone
python3 auth_session.py complete --code 123456
# Output: "Session established. N cookies saved."
```

**Single-command with known code:**
```bash
python3 auth_session.py login --mfa-code 123456
```

**Interactive mode** (reads code from stdin):
```bash
python3 auth_session.py login
# Prompts: "Enter SMS code: "
```

### Conditional Skill Access

The bridge exposes two tiers of functionality based on credential presence:

**Always available** (no credentials required):
- `verizon_check.py --quick` -- reports whether credentials are configured
- `auth_session.py status` -- session health and age

**Requires credentials in vault** (all fleet/billing/device operations):
- `fleet_check.py` -- fleet inventory, search, summary
- `device_check.py` -- IMEI, SIM, device detail
- `billing_check.py` -- invoices, account balances
- `correlate.py` -- cross-bridge correlation
- `auth_session.py login/initiate/complete` -- session management

If an operator runs a credentialed command without vault credentials, the tool exits with a clear setup message:
```
ERROR: Verizon credentials not configured for this operator.
Set up credentials via:
  bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_USERNAME", value="...")
  bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_PASSWORD", value="...")
```

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `verizon_client.py` | `/opt/bridge/data/tools/` | Core HTTP client with session cookie management, keepalive, auto-detect session expiry. All other tools depend on this. |
| `forgerock_auth.py` | `/opt/bridge/data/tools/` | Pure REST client for ForgeRock authentication tree -- drives username, password, device profile, and MFA callbacks without a browser. |
| `verizon_check.py` | `/opt/bridge/data/tools/` | Health check: validates credentials, session cookies, fleet line counts, billing status |
| `fleet_check.py` | `/opt/bridge/data/tools/` | Fleet inventory: list all lines, search by MTN/user/department, filter by device type and status |
| `device_check.py` | `/opt/bridge/data/tools/` | Per-line device detail: IMEI, SIM ID, equipment model, SIM type, device lock status, upgrade eligibility |
| `billing_check.py` | `/opt/bridge/data/tools/` | Billing: account summaries, invoice amounts, payment due dates, autopay/paperless status |
| `correlate.py` | `/opt/bridge/data/tools/` | Cross-bridge correlation: match Verizon MTNs to AirLink gateways (by IMEI) and Intune iPads (by phone number) |
| `auth_session.py` | `/opt/bridge/data/tools/` | Session management: REST-based login with MFA, two-phase auth, session status, keepalive |
| `verizon_bridge_tests.py` | `/opt/bridge/data/tools/` | Integration test battery: read-only tests across credentials, auth endpoints, session, fleet, billing, device, and dashboard |

## Quick Start

```bash
# Step 0: Verify credentials are configured
python3 /opt/bridge/data/tools/verizon_check.py --quick

# Step 1: Authenticate (triggers SMS, then complete with code)
python3 /opt/bridge/data/tools/auth_session.py initiate
python3 /opt/bridge/data/tools/auth_session.py complete --code <sms_code>

# Step 2: Verify session
python3 /opt/bridge/data/tools/verizon_check.py

# Step 3: Use the fleet tools
python3 /opt/bridge/data/tools/fleet_check.py list
python3 /opt/bridge/data/tools/fleet_check.py search "<phone_number>"
python3 /opt/bridge/data/tools/device_check.py info <phone_number>
python3 /opt/bridge/data/tools/fleet_check.py summary
python3 /opt/bridge/data/tools/billing_check.py summary
python3 /opt/bridge/data/tools/correlate.py match-airlink
```

## Tool Reference

### auth_session.py -- Session Management

```bash
python3 auth_session.py initiate                   # Phase 1: submit credentials, trigger SMS
python3 auth_session.py complete --code 123456     # Phase 2: submit SMS code, establish session
python3 auth_session.py login                      # Interactive: prompts for SMS code on stdin
python3 auth_session.py login --mfa-code 123456    # Single-command with known code
python3 auth_session.py status                     # Check session validity, credential config, age
python3 auth_session.py refresh                    # Keepalive ping
python3 auth_session.py keepalive                  # Start keepalive daemon (pings every 5 min)
```

### verizon_client.py -- Core API Client

```bash
python3 verizon_client.py test              # Session check: verify cookies are valid
python3 verizon_client.py fleet             # Quick fleet count (total/active/suspended)
python3 verizon_client.py keepalive         # Start keepalive daemon (pings every 5 min)
```

**Python API:**

```python
from verizon_client import VerizonClient

client = VerizonClient()  # Loads session from cookie store
client.is_session_alive()  # True/False

# Fleet endpoints
client.retrieve_entitled_mtn()  # All lines
client.retrieve_line_summary_count()  # Counts by category

# Per-line detail
client.retrieve_mtn_device_info(mtn="<phone_number>", account="<account_number>")
client.retrieve_user_info(mtn="<phone_number>", account="<account_number>")
client.retrieve_device_lock(mtn="<phone_number>", account="<account_number>", device_id="<imei>")

# Billing
client.get_billing_accounts()  # Invoice amounts, due dates per account

# Dashboard
client.get_mbt_data()  # Dashboard summary
client.get_line_upgrade_eligible()  # Total lines and upgrade-eligible count
```

### verizon_check.py -- Health Check

```bash
python3 verizon_check.py              # Full health check (session + API + fleet count)
python3 verizon_check.py --quick      # Credential + session check only (no API calls)
```

### fleet_check.py -- Fleet Inventory

```bash
python3 fleet_check.py list                        # All lines (name, MTN, status, device type, cost center)
python3 fleet_check.py list --type ODI             # Only ODI devices (gateways)
python3 fleet_check.py list --type Tablet          # Only tablets (iPads)
python3 fleet_check.py list --type Smartphone      # Only smartphones
python3 fleet_check.py list --type MIFI            # Only MiFi hotspots
python3 fleet_check.py list --dept <prefix>        # Filter by cost center department prefix
python3 fleet_check.py list --status suspended     # Only suspended lines
python3 fleet_check.py search "<phone_number>"     # Search by MTN
python3 fleet_check.py search "<user_name>"        # Search by user name
python3 fleet_check.py summary                     # Fleet counts: total, active, suspended, 5G, 4G, upgrade eligible
python3 fleet_check.py by-department               # Line count breakdown by department
python3 fleet_check.py by-device-type              # Line count breakdown by device type
python3 fleet_check.py upgrade-eligible            # Lines eligible for device upgrade
```

### device_check.py -- Per-Line Device Detail

```bash
python3 device_check.py info <phone_number>        # Full device info (IMEI, SIM, model, SIM type, lock status)
python3 device_check.py batch-imei --type ODI      # Fetch IMEI for all ODI devices (for AirLink correlation)
python3 device_check.py batch-imei --type Tablet   # Fetch IMEI for all tablets
python3 device_check.py sim-status <phone_number>  # SIM freeze/protection status
```

### billing_check.py -- Billing

```bash
python3 billing_check.py summary                   # All accounts: balance, due date, autopay
python3 billing_check.py account <account_number>  # Single account detail
python3 billing_check.py invoices                  # Invoice listing with amounts
```

### correlate.py -- Cross-Bridge Correlation

```bash
python3 correlate.py match-airlink                 # Match ODI/MiFi lines to AirLink gateways by IMEI
python3 correlate.py match-intune                  # Match tablet lines to Intune iPads by phone number
python3 correlate.py full                          # Full correlation report (AirLink + Intune + department)
python3 correlate.py vehicle <vehicle_id>          # Look up everything for a specific vehicle
```

## API Coverage

### Fleet Inventory

| Endpoint | Method | Body | Returns |
|----------|--------|------|---------|
| `/mbt/secure/accountandlinesvc/mbt/wno/retrieveEntitledMtn` | POST | `{}` | All lines with 39 fields per record |
| `/mbt/secure/accountandlinesvc/mbt/wno/retrieveLineSummaryCount` | POST | `{ecpdId, clientId, gon, pageInfo, lineCounts[...]}` | Counts: total, active, suspended, upgradeEligible, 5G, 4G |

### Per-Line Detail (WNC)

| Endpoint | Method | Body | Returns |
|----------|--------|------|---------|
| `/mbt/secure/accountandlinedetails/mbt/wnc/retrieveMtnDeviceInfo` | POST | `{accountNumber, mtn, clientId, ecpdId, gon, loadSection}` | **IMEI (deviceId)**, SIM ID, equipment model, SIM type (eSIM/pSIM, 4G/5G), category |
| `/mbt/secure/accountandlinedetails/mbt/wnc/retrieveUserInfoForSelectedMtn` | POST | `{mtn, gon, clientId, accountNumber, ecpdId, loadSection}` | User name, wireless user ID, alternate contact numbers |
| `/mbt/secure/smmanagetransactionsvc/mbt/sm/manage/deviceLock/retreive` | POST | `{mtn, accountNumber, deviceId, clientId, ecpdId, gon}` | Device lock/unlock status, IMEI, eligible unlock date |
| `/mbt/secure/aecompositesvc/mbt/ae/checkUpgradeActivationEligibility` | POST | `{mtn, accountNumber, ecpdId, gon, ...}` | Upgrade eligibility, activation eligibility |

### Billing

| Endpoint | Method | Body | Returns |
|----------|--------|------|---------|
| `/mbt/secure/invoiceusagecompositesvc/mbt/invoice-usage/v1/invoice/billing/accounts/get` | POST | `{billPeriod, page, limit, searchField, searchValue, ecpdId, userId}` | Account info: invoice number, date, balance, due date, autopay, paperless |
| `/mbt/secure/mbpaymentsvc/mbt/smpayments/get/PageLevelBillingAccess` | POST | `{ecpdId, userId}` | Billing page access permissions |

### Dashboard / Summary

| Endpoint | Method | Body | Returns |
|----------|--------|------|---------|
| `/mbt/secure/esmcompositesvc/mbt/esmhome/getMbtData` | POST | `{}` | Dashboard business data |
| `/mbt/secure/esmcompositesvc/mbt/esmhome/summary/lineAndUpgrdEligible/get` | POST | `{ecpdId, userId}` | Total lines and upgrade-eligible count |
| `/mbt/secure/esmcompositesvc/mbt/esmhome/summary/totalOrders/get` | POST | `{ecpdId, userId}` | Total pending orders |
| `/mbt/secure/esmcompositesvc/mbt/esmhome/getBillingCards` | POST | `{ecpdId, ...}` | Billing card summaries for dashboard |

### ForgeRock Authentication (REST callbacks)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/vzauth/json/realms/root/realms/vzwmb/authenticate?authIndexType=service&authIndexValue=VBGUserValidateService` | POST | Step 1-2: Username validation + device profile |
| `/vzauth/json/realms/root/realms/vzwmb/authenticate?authIndexType=service&authIndexValue=VBGUserLoginService` | POST | Step 3-4: Password + SMS MFA code |
| `POST sso.verizonenterprise.com/account/business/addsession` | POST | SSO session creation after auth |

## Session Parameters

All API calls require these context values (extracted from session cookies at login):

| Parameter | Source | Description |
|-----------|--------|-------------|
| `ecpdId` | `profileId` cookie | Enterprise customer profile identifier |
| `userId` | `VZ_USERNAME` credential | Portal login username |
| `gon` | `GROUP_ORDER_NUMBER` cookie | Group order number for the account |
| `clientId` | Varies by endpoint | Service identifier (`MBT_WNO`, `MBT_ANC`, `MBT_WNC`) |

## Device Type Categories

Verizon classifies wireless lines by device type. Common categories relevant for fleet management:

| Category Pattern | Description | Bridge Correlation |
|-----------------|-------------|-------------------|
| `5GSmartphone` / `4GSmartphone` | Employee smartphones | Match to Intune by user name |
| `5GTablet` / `4GTablet` | Tablets (iPads) with cellular | Match to Intune by phone number |
| `4GODINonStationary` / `4GODI_Data` / `4GODI_D_V` | Gateway/modem devices | **AirLink gateways** -- match by IMEI |
| `4GMIFI DEVICE` / `5GMIFI DEVICE` | MiFi hotspot devices | Some may be AirLink gateways |
| Other (FeaturePhone, Hotspot, USB, Connected) | Specialty devices | Case-by-case |

## Cross-Bridge Correlation Strategy

**Verizon to Sierra AirLink (IMEI match):**
1. Filter fleet for ODI + MiFi device types
2. Call `retrieveMtnDeviceInfo` for each to get IMEI
3. Match IMEI against AirLink gateway inventory
4. Result: vehicle <-> Verizon MTN <-> AirLink gateway

**Verizon to Intune iPad (phone number match):**
1. Filter fleet for Tablet device types
2. Match Verizon MTN digits against Intune `phoneNumber` field
3. Result: iPad serial <-> Verizon MTN <-> Intune user assignment

## Common Patterns

### First-Time Setup
1. Store credentials: `bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_USERNAME", value="<username>")`
2. Store password: `bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_PASSWORD", value="<password>")`
3. Initiate auth: `python3 auth_session.py initiate` (triggers SMS)
4. Complete auth: `python3 auth_session.py complete --code <sms_code>`
5. Verify: `python3 verizon_check.py`

### Session Renewal (when expired)
1. Run any command -- if it reports "Session expired", proceed:
2. `python3 auth_session.py initiate` (triggers SMS)
3. `python3 auth_session.py complete --code <sms_code>`
4. Retry the original command

### Fleet Inventory Check
1. Verify session: `python3 verizon_check.py`
2. Get summary counts: `python3 fleet_check.py summary`
3. List all lines: `python3 fleet_check.py list`
4. Filter by department: `python3 fleet_check.py list --dept <prefix>`

### Device Troubleshooting
1. Search for the line: `python3 fleet_check.py search "<phone_number>"`
2. Get device detail: `python3 device_check.py info <phone_number>`
3. Check SIM status: `python3 device_check.py sim-status <phone_number>`

### Vehicle Gateway Lookup
1. Get vehicle's AirLink IMEI: query `bridge-sierra-airlink` -> `python3 gateway_check.py search "<vehicle_name>"`
2. Look up the IMEI in Verizon: `python3 device_check.py batch-imei --type ODI` -> find matching IMEI
3. Or: `python3 correlate.py vehicle <vehicle_id>`

## API Quirks and Known Issues

1. **Session cookies, not API tokens.** The portal uses ForgeRock SSO session cookies. Sessions expire after 4+ hours with keepalive pings.
2. **SMS MFA required.** Every new session requires an SMS verification code. The `forgerock_auth.py` module automates everything except the SMS code entry itself.
3. **Akamai bot protection.** The portal is behind Akamai CDN with bot detection (`ak_bmsc`, `bm_sv` cookies). The auth module includes browser-equivalent headers and device fingerprinting to avoid detection.
4. **POST bodies vary by endpoint.** Some endpoints accept `{}`, others require `ecpdId`, `gon`, `clientId`, and other session context.
5. **IMEI is padded.** `deviceId` values are right-padded with spaces. Strip whitespace before matching.
6. **MTN format varies.** Phone numbers appear in dotted format (e.g., `555.123.4567`) in the fleet list but digits only in per-line detail. Normalize before comparison.
7. **Cost center format inconsistency.** Some departments use space delimiters (`XX 1234567`) and others use dashes (`XX-1234567`). Parse the prefix only.
8. **302 redirect = session expired.** Any API call returning HTTP 302 means re-authentication is needed.
9. **Citrix NetScaler load balancer.** `NSC_*` cookies rotate on each request and must be preserved in the cookie jar.

## Institutional Knowledge

Organization-specific context belongs in `references/`:

- `ik-verizon-fleet.md` -- Cost center mappings, device type categories, account numbers, fleet statistics, correlation fields

Customize the reference document with your organization's account numbers, department mappings, and fleet specifics.

Pull with: `transfer_file(source="bridge-verizon-mybusiness", source_path="/opt/bridge/data/references/ik-verizon-fleet.md", destination="local")`
