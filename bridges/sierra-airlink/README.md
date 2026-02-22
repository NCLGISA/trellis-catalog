# Sierra AirLink Bridge (AirVantage)

Tendril bridge for managing Sierra Wireless AirLink cellular gateways via the AirVantage REST API. Provides system inventory, gateway hardware management, signal quality monitoring, GPS location tracking, cellular statistics, firmware oversight, and alert monitoring.

## Prerequisites

- **AirVantage account** with API access at [na.airvantage.net](https://na.airvantage.net)
- **API Client** configured for **Client Credentials** flow
- **Docker** and **docker-compose** (for container deployment)
- **Tendril install key** from the Tendril admin panel

## API Client Setup

1. Log in to [AirVantage](https://na.airvantage.net)
2. Navigate to **Develop > API Clients**
3. Click **New** to create a new API client
4. Set the flow type to **Client Credentials**
5. Note the **Client ID** and **Secret Key**

## Quick Start (Local Testing)

```bash
cd bridges/sierra-airlink

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set credentials
export AIRLINK_CLIENT_ID="your_client_id"
export AIRLINK_CLIENT_SECRET="your_client_secret"
export AIRLINK_REGION="na"

# Run health check
python3 tools/airlink_check.py

# List systems
python3 tools/system_check.py list

# List gateways
python3 tools/gateway_check.py list
```

## Container Deployment

```bash
cd bridges/sierra-airlink

# Create .env from template
cp .env.example .env
# Edit .env with your credentials

# Build and run
docker-compose up -d --build

# Check logs
docker-compose logs -f
```

For production deployment, use the standard bridge deployment process via `deploy-to-portainer.sh`.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TENDRIL_INSTALL_KEY` | Yes (first run) | One-time Tendril registration key |
| `TENDRIL_DOWNLOAD_URL` | No | Agent download URL (default: Tendril Root server) |
| `AIRLINK_CLIENT_ID` | Yes | OAuth2 client ID from AirVantage |
| `AIRLINK_CLIENT_SECRET` | Yes | OAuth2 client secret |
| `AIRLINK_REGION` | No | `na` (default) or `eu` |
| `BRIDGE_SEED_VERSION` | No | Bump to re-seed tools/skills on rebuild |

## Tools

| Tool | Description |
|------|-------------|
| `airlink_client.py` | Core API client with OAuth2 token management, pagination, rate limiting |
| `airlink_check.py` | Health check: env vars, token, system/gateway/alert counts |
| `system_check.py` | System inventory: list, search, info, status, offline |
| `gateway_check.py` | Gateway inventory: list, info, search by IMEI/serial/MAC |
| `alert_check.py` | Alert monitoring: rules, active alerts, event history |
| `data_check.py` | Device telemetry: signal, location, cellular, firmware, summary |

## Authentication

The bridge uses OAuth2 **Client Credentials** flow:

1. Client sends `POST /api/oauth/token` with HTTP Basic auth (client_id:secret base64-encoded) and `grant_type=client_credentials`
2. AirVantage returns an `access_token` valid for 24 hours
3. All API calls use `Authorization: Bearer <token>`
4. Token is auto-renewed 5 minutes before expiry

No refresh tokens are issued in this flow -- the client simply re-acquires using the same credentials.

## API Endpoints

| Endpoint | Version | Description |
|----------|---------|-------------|
| `/api/v1/systems` | v1 | System inventory and details |
| `/api/v1/systems/{uid}/data` | v1 | Last-known device telemetry |
| `/api/v1/gateways` | v1 | Gateway hardware inventory |
| `/api/v2/alertrules` | v2 | Alert rule definitions |
| `/api/v3/alerts/current` | v3 | Current alert states |
| `/api/v3/alerts/history` | v3 | Alert event history |

## Directory Structure

```
bridges/sierra-airlink/
  .env.example           # Environment variable template
  Dockerfile             # Container image definition
  docker-compose.yml     # Service definition with volumes
  entrypoint.sh          # Seed tools/skills, download agent, launch
  requirements.txt       # Python dependencies
  README.md              # This file
  tools/
    airlink_client.py    # Core API client
    airlink_check.py     # Health check
    system_check.py      # System inventory
    gateway_check.py     # Gateway inventory
    alert_check.py       # Alert monitoring
    data_check.py        # Device telemetry
  skills/
    sierra-airlink-api/
      SKILL.md           # Agent skill definition
```
