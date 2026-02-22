---
name: sierra-airlink-api
description: Manage Sierra Wireless AirLink cellular gateways via the AirVantage REST API -- system inventory, gateway hardware, signal quality, GPS location, cellular stats, firmware versions, alert monitoring, and fleet communication status.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.21"
metadata:
  author: tendril-project
  version: "1.0.0"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - sierra-wireless
    - airlink
    - airvantage
    - cellular
    - lte
    - gateways
    - iot
    - fleet
---

# Sierra AirLink (AirVantage) API Bridge

Full programmatic access to the Sierra Wireless AirVantage management platform for AirLink cellular gateway fleets. Covers system inventory, gateway hardware details, signal quality monitoring, GPS tracking, cellular statistics, firmware management, and alert monitoring.

## Authentication

- **Type:** OAuth2 Client Credentials (RFC 6749)
- **Token endpoint:** `POST https://na.airvantage.net/api/oauth/token`
- **Auth method:** HTTP Basic (base64-encoded client_id:client_secret)
- **Token lifetime:** 24 hours (auto-renewed 5 minutes before expiry)
- **Credentials:** `AIRLINK_CLIENT_ID` and `AIRLINK_CLIENT_SECRET` in container environment
- **Region:** `na` (North America) -- `na.airvantage.net`

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `airlink_client.py` | `/opt/bridge/data/tools/` | Core REST API client with OAuth2 token lifecycle, pagination (offset/size), rate limiting. All other tools depend on this. |
| `airlink_check.py` | `/opt/bridge/data/tools/` | Health check: validates env vars, acquires token, reports system/gateway counts, alert status |
| `system_check.py` | `/opt/bridge/data/tools/` | System inventory, search, details, communication status summary, offline detection |
| `gateway_check.py` | `/opt/bridge/data/tools/` | Gateway inventory, IMEI/serial/MAC lookup, hardware details |
| `alert_check.py` | `/opt/bridge/data/tools/` | Alert rules listing, active alert states, alert event history |
| `data_check.py` | `/opt/bridge/data/tools/` | Device telemetry: signal quality, GPS location, cellular stats, firmware, combined summary |

## Quick Start

```bash
# Verify bridge connectivity
python3 /opt/bridge/data/tools/airlink_check.py

# Test API access
python3 /opt/bridge/data/tools/airlink_client.py test

# System status overview
python3 /opt/bridge/data/tools/system_check.py status

# List all gateways
python3 /opt/bridge/data/tools/gateway_check.py list

# Check signal quality for a system
python3 /opt/bridge/data/tools/data_check.py signal <system_uid>
```

## Tool Reference

### airlink_client.py -- Core API Client

```bash
python3 airlink_client.py test            # Health check: acquire token, count systems/gateways
python3 airlink_client.py systems         # List all systems with name, comm status, lifecycle state
python3 airlink_client.py gateways        # List all gateways with IMEI, serial, type
python3 airlink_client.py token           # Acquire and confirm OAuth2 token
```

### airlink_check.py -- Health Check

```bash
python3 airlink_check.py                # Full health check (5 steps)
python3 airlink_check.py --quick        # Token-only check (no API calls)
python3 airlink_check.py --verbose      # Detailed JSON output
```

### system_check.py -- System Inventory

```bash
python3 system_check.py list            # All systems with name, comm status, last comm, IMEI
python3 system_check.py search "RV50"   # Find by name, IMEI, or serial number
python3 system_check.py info <uid>      # Full details: gateway, subscription, apps, data
python3 system_check.py status          # Comm status breakdown (OK/ERROR/WARNING/UNDEFINED)
python3 system_check.py offline         # Systems with commStatus=ERROR
```

### gateway_check.py -- Gateway Hardware

```bash
python3 gateway_check.py list           # All gateways with IMEI, serial, MAC, type
python3 gateway_check.py info <uid>     # Gateway details including labels and metadata
python3 gateway_check.py search "353"   # Find by IMEI, serial number, or MAC address
```

### alert_check.py -- Alert Monitoring

```bash
python3 alert_check.py rules           # All alert rules with active/stateful status
python3 alert_check.py active          # Systems currently in alert state
python3 alert_check.py history         # Alert events (last 7 days)
python3 alert_check.py history --days 30  # Alert events for custom period
```

### data_check.py -- Device Telemetry

```bash
python3 data_check.py signal <uid>     # RSSI, RSRP, RSRQ, signal bars, network type
python3 data_check.py location <uid>   # GPS latitude/longitude with Google Maps link
python3 data_check.py cellular <uid>   # APN, cell ID, operator, roaming, data usage
python3 data_check.py firmware <uid>   # Firmware version and components
python3 data_check.py summary <uid>    # Combined overview of all telemetry data
```

## API Coverage

### Systems (v1)

```python
from airlink_client import AirLinkClient
client = AirLinkClient()

client.list_systems(fields="uid,name,commStatus")     # All systems (paginated)
client.get_system("abc123")                             # Full system details
client.get_system_data("abc123")                                  # Last datapoints (all)
client.get_system_data("abc123", ids="_RSSI,_LATITUDE")           # Specific data IDs
```

### Gateways (v1)

```python
client.list_gateways(fields="uid,imei,type")   # All gateways (paginated)
client.get_gateway("abc123")                     # Gateway details
```

### Alerts (v2/v3)

```python
client.list_alert_rules()                        # All alert rules
client.get_alert_rule("abc123")                  # Rule details
client.list_current_alerts()                     # Active alert states
client.list_alert_history(from_ts, to_ts)        # Alert event log
```

## Common Patterns

### Fleet Health Check
1. Run health check: `python3 airlink_check.py` to verify connectivity
2. Check system status: `python3 system_check.py status` for comm status breakdown
3. Find offline systems: `python3 system_check.py offline` for ERROR status systems
4. Check active alerts: `python3 alert_check.py active` for systems in alert

### Device Troubleshooting
1. Find the system: `python3 system_check.py search "unit_name"`
2. Get full details: `python3 system_check.py info <uid>`
3. Check signal: `python3 data_check.py signal <uid>`
4. Check location: `python3 data_check.py location <uid>`
5. Full summary: `python3 data_check.py summary <uid>`

### Signal Quality Assessment
1. Get signal data: `python3 data_check.py signal <uid>`
2. Interpret levels:
   - **RSSI:** POOR (<-100), FAIR (-100 to -85), GOOD (-85 to -70), EXCELLENT (>-70)
   - **RSRP (LTE):** POOR (<-120), FAIR (-120 to -105), GOOD (-105 to -90), EXCELLENT (>-90)
   - **RSRQ (LTE):** FAIR_TO_POOR (<-12), GOOD (-12 to -9), EXCELLENT (>-9)
   - **Signal bars:** 0=NO_SIGNAL, 1=VERY_LOW, 2=LOW, 3=GOOD, 4=VERY_GOOD, 5=EXCELLENT

### Gateway Inventory
1. List all hardware: `python3 gateway_check.py list`
2. Search by IMEI: `python3 gateway_check.py search "353270"`
3. Get details: `python3 gateway_check.py info <uid>`

## Domain Knowledge

### System States (lifeCycleState)
- **INVENTORY** -- Registered but not activated
- **ACTIVE** -- Activated and operational
- **TEST_READY** -- Ready for testing
- **SUSPENDED** -- Temporarily suspended
- **RETIRED** -- Decommissioned

### Communication Status (commStatus)
- **OK** -- Communicating normally
- **WARNING** -- Communication degraded (heartbeat SLA warning threshold)
- **ERROR** -- Communication lost (heartbeat SLA error threshold)
- **UNDEFINED** -- No heartbeat configured or no communication yet

### AirLink Device Types
Common Sierra Wireless AirLink models:
- **RV50/RV50X** -- Rugged LTE gateway for vehicles and fixed sites
- **RV55** -- Next-gen rugged LTE gateway with FirstNet support
- **GX450** -- High-performance LTE gateway for mission-critical applications
- **MP70** -- Mobile LTE gateway for fleet and public safety vehicles
- **ES450** -- Enterprise LTE gateway for branch offices

### AirVantage Timestamps
All timestamps in the API are Unix milliseconds (ms since epoch). The tools convert these to human-readable UTC format.

## Pagination

AirVantage uses offset/size pagination:
- **size:** Items per page (0-500, default 100)
- **offset:** Starting row
- **Response:** `{ "items": [...], "count": N, "size": M, "offset": O }`

The `get_all()` helper in `airlink_client.py` handles pagination automatically.

## Rate Limiting

- **Response:** HTTP 429 with `Retry-After` header
- **Strategy:** Sleep for `Retry-After` seconds, then retry (max 3 attempts)
- On 401 responses, the client automatically re-acquires the OAuth2 token

## API Quirks

1. **Timestamps are milliseconds.** All dates are Unix milliseconds, not seconds.
2. **Fields parameter is additive.** Requesting `fields=uid,name` returns only those fields plus uid.
3. **Gateway search uses exact filter params.** IMEI, serial, and MAC are passed as exact-match query params; partial matches depend on AirVantage API behavior.
4. **System search combines multiple filters.** Use `gateway=imei:xxx` syntax for nested object filters.
5. **Data IDs use uppercase underscore-prefixed format.** Use exact names: `_RSSI`, `_LATITUDE`, `_FIRMWARE_VERSION`.
6. **Alert rules use v2, alert states use v3.** Different API versions for rules vs. current/history.
7. **Client Credentials tokens have no refresh token.** Re-acquire using the same client credentials.
8. **Empty data fields return empty arrays.** `{"_RSSI": []}` means no data available for that metric.
