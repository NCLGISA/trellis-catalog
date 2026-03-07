# bridge-verizon-mybusiness

Tendril bridge for managing Verizon Business wireless fleets through the MyBusiness portal API.

## What It Does

This bridge provides programmatic access to the Verizon MyBusiness portal, exposing fleet management capabilities as Tendril tools:

- **Fleet inventory** -- list, search, filter, and summarize all wireless lines
- **Device detail** -- IMEI, SIM ID, equipment model, SIM type, lock status, upgrade eligibility
- **Billing** -- account summaries, invoice amounts, payment status
- **Cross-bridge correlation** -- match Verizon lines to Sierra AirLink gateways (by IMEI) and Intune iPads (by phone number)
- **Session management** -- REST-based ForgeRock authentication with programmatic SMS MFA

## Architecture

```
┌──────────────────────────────────────────┐
│  Tendril Root                            │
│  ┌────────────────────────────────────┐  │
│  │  bridge-verizon-mybusiness         │  │
│  │  ┌──────────┐  ┌───────────────┐  │  │
│  │  │ Tendril  │  │ Python Tools  │  │  │
│  │  │ Agent    │  │               │  │  │
│  │  │          │  │ fleet_check   │  │  │
│  │  │ execute ─┼──┤ device_check  │  │  │
│  │  │          │  │ billing_check │  │  │
│  │  │          │  │ auth_session  │  │  │
│  │  │          │  │ correlate     │  │  │
│  │  └──────────┘  └───────┬───────┘  │  │
│  └────────────────────────┼──────────┘  │
│                           │              │
└───────────────────────────┼──────────────┘
                            │ httpx (REST)
                            ▼
              ┌─────────────────────────┐
              │ Verizon MyBusiness API  │
              │ mb.verizonwireless.com  │
              │                         │
              │ ForgeRock SSO           │
              │ Akamai CDN             │
              └─────────────────────────┘
```

All API access uses pure REST over HTTPS with session cookies. No browser, WebSocket, or API keys required.

## Prerequisites

- A Tendril Root with bridge support
- A Verizon MyBusiness portal account with admin or fleet-level access
- SMS-capable phone for MFA during initial login

## Quick Start

### 1. Deploy

```bash
# Set your Tendril install key and download URL
export TENDRIL_INSTALL_KEY="<your_install_key>"
export TENDRIL_DOWNLOAD_URL="<your_tendril_download_url>"

# Build and start
docker compose up -d
```

### 2. Store Credentials

Each operator stores their own Verizon credentials in the Tendril vault:

```
bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_USERNAME", value="<username>")
bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_PASSWORD", value="<password>")
```

### 3. Authenticate

```bash
# Phase 1: triggers SMS to your phone
execute(bridge="bridge-verizon-mybusiness", command="python3 auth_session.py initiate")

# Phase 2: submit the SMS code
execute(bridge="bridge-verizon-mybusiness", command="python3 auth_session.py complete --code 123456")
```

### 4. Use

```bash
execute(bridge="bridge-verizon-mybusiness", command="python3 fleet_check.py summary")
execute(bridge="bridge-verizon-mybusiness", command="python3 fleet_check.py list")
execute(bridge="bridge-verizon-mybusiness", command="python3 device_check.py info <phone_number>")
execute(bridge="bridge-verizon-mybusiness", command="python3 billing_check.py summary")
```

## Customization

### Organization-Specific Configuration

After deploying, customize these files for your organization:

1. **`references/ik-verizon-fleet.md`** -- Fill in your account numbers, department mappings, fleet statistics, and cross-bridge correlation notes. This institutional knowledge document is used by operators for context.

2. **`tools/fleet_check.py`** -- Update the `DEPT_LABELS` dictionary at the top of the file with your organization's cost center prefix to department name mappings.

### Credential Isolation

Credentials are per-operator. Each person who needs access stores their own Verizon MyBusiness username and password in the Tendril credential vault. The bridge never sees credentials from other operators, and credentials are injected as environment variables only during command execution.

### Conditional Skill Exposure

Tools that require credentials will exit with a setup message if credentials are not configured. The health check (`verizon_check.py --quick`) and session status (`auth_session.py status`) are always available regardless of credential state.

## File Structure

```
bridge-catalog/
├── Dockerfile              # Python 3.11 slim + httpx
├── docker-compose.yml      # Service definition with env vars
├── entrypoint.sh           # Seed directories + download Tendril agent
├── tools/
│   ├── verizon_client.py   # Core HTTP client (session cookies, keepalive)
│   ├── forgerock_auth.py   # REST authentication (ForgeRock callback tree)
│   ├── auth_session.py     # Session management (login, MFA, status)
│   ├── verizon_check.py    # Health check
│   ├── fleet_check.py      # Fleet inventory (list, search, filter)
│   ├── device_check.py     # Per-line device detail (IMEI, SIM)
│   └── billing_check.py    # Billing summaries
├── skills/
│   └── verizon-mybusiness/
│       └── SKILL.md        # Trellis skill manifest
└── references/
    └── ik-verizon-fleet.md # Institutional knowledge template
```

## Authentication Details

The Verizon MyBusiness portal uses ForgeRock Access Management for SSO. This bridge implements the full authentication flow as a pure REST client:

1. **Akamai cookie acquisition** -- visit login page to get bot-detection cookies
2. **Username validation** -- ForgeRock `VBGUserValidateService` callback tree
3. **Device fingerprint** -- browser-equivalent device profile submission
4. **Password submission** -- ForgeRock `VBGUserLoginService` callback tree
5. **SMS MFA** -- one-time code submitted via ForgeRock callback
6. **Session finalization** -- collect all portal session cookies

Sessions last 4+ hours with automatic keepalive pings. When a session expires (detected by HTTP 302 redirect), re-authentication is needed.

## Trellis Compliance

- Per-operator credential vault (`bridge_credentials`)
- Conditional skill exposure based on credential presence
- No hardcoded credentials or PII in the image
- Parameterized `TENDRIL_DOWNLOAD_URL` (no hardcoded endpoints)
- Versioned seed directory with `BRIDGE_SEED_VERSION`
- Standard Tendril bridge directory layout (`/opt/bridge/`, `/opt/tendril/`)

## License

See your Tendril Root license agreement for usage terms.
