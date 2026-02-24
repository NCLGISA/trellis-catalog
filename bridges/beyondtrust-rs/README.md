# BeyondTrust Remote Support Bridge

A Tendril bridge for [BeyondTrust Remote Support](https://www.beyondtrust.com/remote-support) (formerly Bomgar), providing programmatic access to appliance health, representative management, session lifecycle, Jump Items, reporting, Vault, and configuration backup via the Command, Reporting, and Configuration APIs.

## Prerequisites

- A BeyondTrust Remote Support B Series Appliance with **XML API enabled** (`/login > Management > API Configuration`)
- An **API account** with OAuth2 credentials and the desired permissions
- A running [Tendril Root](https://github.com/NCLGISA/trellis-catalog) server
- Docker on the bridge host

## Quick Start

### 1. Initialize from Catalog

```bash
trellis catalog init beyondtrust-rs
cd beyondtrust-rs
```

Or clone this directory manually if not using the Trellis CLI.

### 2. Build the Bridge

```bash
docker build --network=host -t bridge-beyondtrust-rs:latest .
```

> `--network=host` is required if your build environment uses an SSL inspection proxy.

### 3. Deploy

```bash
docker run -d \
  --name bridge-beyondtrust-rs \
  --hostname bridge-beyondtrust-rs \
  --restart unless-stopped \
  --network host \
  -v beyondtrust-rs-tendril:/opt/tendril \
  -v beyondtrust-rs-data:/opt/bridge/data \
  -e TZ=UTC \
  -e TENDRIL_INSTALL_KEY=<your-install-key> \
  -e TENDRIL_DOWNLOAD_URL=https://your-tendril-root/download/tendril?linux-amd64 \
  bridge-beyondtrust-rs:latest
```

### 4. Configure Credentials

Store your BeyondTrust API credentials in the Tendril credential vault:

```
bridge_credentials(action="set", bridge="beyondtrust-rs", key="api_host", value="support.example.com")
bridge_credentials(action="set", bridge="beyondtrust-rs", key="client_id", value="<your-oauth2-client-id>")
bridge_credentials(action="set", bridge="beyondtrust-rs", key="client_secret", value="<your-oauth2-client-secret>")
```

### 5. Verify

```bash
python3 /opt/bridge/data/tools/bt_check.py
python3 /opt/bridge/data/tools/bt.py health check
```

## BeyondTrust API Account Setup

1. Log in to your BeyondTrust appliance: `https://<host>/login`
2. Go to **Management > API Configuration**
3. Click **Add** to create a new API account
4. Configure permissions based on your needs:

| Permission | Enables |
|-----------|---------|
| **Command API** (Read-Only) | Health checks, rep/team listing, session queries |
| **Command API** (Full Access) | Session generation, rep status changes, session management |
| **Reporting** (Support Session) | Session history and detail reports |
| **Reporting** (License Usage) | License utilization reports |
| **Configuration API** | Jump Item CRUD, user/Jumpoint/Vault management |
| **Backup API** | Software configuration backups |

5. Save the account and note the **Client ID** and **Client Secret**

> The Client Secret cannot be changed, only regenerated. Regenerating immediately invalidates all tokens.

## API Coverage

This bridge covers three BeyondTrust API surfaces:

### Command API (`/api/command`)
XML-based API for real-time operations:
- Appliance health and failover status
- Logged-in representative listing and status management
- Support team and issue queue listing
- Session key generation with ticket integration
- Session lifecycle (join, leave, transfer, terminate)
- Connected client inventory (reps, customers, Jumpoints)

### Reporting API (`/api/reporting`)
XML-based API for historical data:
- Support session reports (full detail or listing summary)
- License usage reports
- Team activity reports

### Configuration API (`/api/config/v1/`)
JSON REST API for configuration management:
- Jump Items: Shell Jump, Remote RDP, Remote VNC, Local Jump, Protocol Tunnel, Web Jump
- Users and representatives
- Jumpoints
- Jump Groups
- Vault accounts and endpoints
- Group policies

### Backup API (`/api/backup`)
- Full software configuration backup download

## Rate Limits

BeyondTrust enforces per-API-account rate limits:
- **20 requests/second**
- **15,000 requests/hour**

Response headers include `X-RateLimit-Limit` and `X-RateLimit-Remaining`.

## File Structure

```
beyondtrust-rs/
├── bridge.yaml              # Trellis bridge manifest
├── Dockerfile               # Container build definition
├── docker-compose.yml       # Docker Compose deployment
├── .env.example             # Environment variable template
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── tools/
│   ├── bt_client.py         # Core API client (OAuth2, XML/JSON parsing)
│   ├── bt.py                # Unified CLI tool
│   └── bt_check.py          # Health check script
├── skills/
│   └── beyondtrust-rs/
│       └── SKILL.md         # Tendril skill definition with full CLI reference
└── references/
    └── api-overview.md       # BeyondTrust API reference notes
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BT_API_HOST` | Yes | B Series Appliance hostname (no `https://` prefix) |
| `BT_CLIENT_ID` | Yes | OAuth2 client ID |
| `BT_CLIENT_SECRET` | Yes | OAuth2 client secret |
| `TENDRIL_INSTALL_KEY` | Yes | Tendril agent install key |
| `TENDRIL_DOWNLOAD_URL` | No | Tendril agent download URL (defaults to standard) |

## Contributing

This bridge follows the [Trellis bridge authoring guide](https://github.com/NCLGISA/trellis-catalog/blob/main/docs/bridge-authoring-guide.md). To contribute:

1. Fork the repository
2. Create a feature branch
3. Test against a BeyondTrust appliance (or use the mock responses in `references/`)
4. Submit a pull request

## License

Apache-2.0
