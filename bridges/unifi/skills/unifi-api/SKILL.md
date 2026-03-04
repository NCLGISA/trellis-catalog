---
name: unifi-api
description: "UniFi Network Controller bridge -- manage sites, devices (APs, switches, gateways), clients, WLANs, networks/VLANs, DPI stats, firmware, firewall rules, and configuration compliance via the UniFi REST API. Use when managing wireless infrastructure, checking device status, viewing connected clients, configuring networks, auditing security posture, or any UniFi / Ubiquiti operations."
metadata:
  author: rowan-county-it
  version: "1.0"
  tendril-bridge: "true"
  skill_scope: "bridge"
credentials:
  - key: unifi_username
    env: UNIFI_USERNAME
    description: UniFi controller admin username
  - key: unifi_password
    env: UNIFI_PASSWORD
    description: UniFi controller admin password
---

# UniFi Network Controller Bridge

Manage Ubiquiti UniFi network infrastructure through the UniFi REST API via Tendril. Covers sites, devices (access points, switches, gateways), clients, wireless networks, VLANs, DPI statistics, firmware management, firewall rules, and configuration compliance auditing.

## Quick Start

Use the Tendril MCP to execute UniFi API commands:

```
MCP Server: user-tendril
Tool: execute
Agent: bridge-unifi
Shell: bash
```

## Environment

| Setting | Value |
|---------|-------|
| Product | Ubiquiti UniFi Network Controller |
| Protocol | HTTPS REST API |
| Container | bridge-unifi |
| OS | Debian (python:3.11-slim) |
| Auth | Session-based (cookie) with auto-login |
| Controller Types | Standard (port 8443) and UniFi OS (UDM/UCG) -- auto-detected |

## Tools

### Core Triad

| Script | Location | Purpose |
|--------|----------|---------|
| `unifi_client.py` | `/opt/bridge/data/tools/` | REST API client with session auth, controller-type detection, site discovery |
| `unifi_check.py` | `/opt/bridge/data/tools/` | Health check: validates env vars, API access, device visibility |
| `unifi_bridge_tests.py` | `/opt/bridge/data/tools/` | Read-only 18-test battery covering all API categories |

### Domain Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `unifi_devices.py` | `/opt/bridge/data/tools/` | Device inventory, status, firmware, adopt/restart/upgrade/provision |
| `unifi_clients.py` | `/opt/bridge/data/tools/` | Connected/historical clients, block/unblock/reconnect |
| `unifi_wlans.py` | `/opt/bridge/data/tools/` | WLAN listing, enable/disable, password management |
| `unifi_networks.py` | `/opt/bridge/data/tools/` | Network/VLAN config, firewall rules, port forwards, routes |
| `unifi_stats.py` | `/opt/bridge/data/tools/` | Site health, DPI, events, alarms, rogue APs, traffic, dashboard |
| `unifi_audit.py` | `/opt/bridge/data/tools/` | Configuration compliance: firmware, WLAN security, network, security posture |

## Client Script (CLI)

All operations go through the client script which handles session auth, controller-type detection, and JSON output:

```bash
python3 /opt/bridge/data/tools/unifi_client.py <action> [--site SITE]
```

### Client Actions

| Action | Description |
|--------|-------------|
| `test` | Validate credentials and list sites |
| `sites` | List all sites |
| `devices` | List all adopted devices |
| `clients` | List connected clients |
| `wlans` | List wireless networks |
| `networks` | List network configurations |
| `health` | Site health summary |
| `sysinfo` | Controller system information |
| `events` | Recent events (`--limit N`) |
| `alarms` | Active alarms |
| `status` | Server status (no auth required) |

## Device Management

```bash
python3 /opt/bridge/data/tools/unifi_devices.py <command> [mac] [--site SITE]
```

| Command | Description | Args |
|---------|-------------|------|
| `list` | All devices with status, firmware, client count | |
| `detail` | Full device info (radio, ports, CPU/mem) | `<mac>` |
| `summary` | Count by type and status | |
| `firmware` | Firmware currency report | |
| `restart` | Reboot a device | `<mac>` |
| `adopt` | Adopt a new device | `<mac>` |
| `upgrade` | Trigger firmware upgrade | `<mac>` |
| `provision` | Force re-provision | `<mac>` |

## Client Management

```bash
python3 /opt/bridge/data/tools/unifi_clients.py <command> [mac] [--site SITE]
```

| Command | Description | Args |
|---------|-------------|------|
| `list` | Connected clients (hostname, IP, signal, traffic) | |
| `detail` | Full client details (radio, rates, VLAN, switch port) | `<mac>` |
| `summary` | Client counts by type, network, SSID | |
| `history` | All known users (historical) | |
| `block` | Block a client | `<mac>` |
| `unblock` | Unblock a client | `<mac>` |
| `reconnect` | Force reconnect (kick) | `<mac>` |

## WLAN Management

```bash
python3 /opt/bridge/data/tools/unifi_wlans.py <command> [wlan_id] [--site SITE]
```

| Command | Description | Args |
|---------|-------------|------|
| `list` | All WLANs with security, VLAN, band, guest status | |
| `detail` | Full WLAN configuration | `<wlan_id>` |
| `summary` | WLAN counts by security type and status | |
| `enable` | Enable a WLAN | `<wlan_id>` |
| `disable` | Disable a WLAN | `<wlan_id>` |
| `set-password` | Update WPA passphrase | `<wlan_id> <password>` |

## Network / VLAN Management

```bash
python3 /opt/bridge/data/tools/unifi_networks.py <command> [--site SITE]
```

| Command | Description | Args |
|---------|-------------|------|
| `networks` | All network configs (VLAN, subnet, DHCP) | |
| `network-detail` | Full network configuration | `<network_id>` |
| `vlans` | VLAN-focused view (ID, subnet, purpose) | |
| `firewall` | Firewall rules | |
| `port-forwards` | Port forwarding rules | |
| `routes` | Static routes | |
| `summary` | Overall network topology summary | |

## Statistics and Monitoring

```bash
python3 /opt/bridge/data/tools/unifi_stats.py <command> [--site SITE]
```

| Command | Description | Args |
|---------|-------------|------|
| `health` | Site health by subsystem (wan, wlan, lan, vpn) | |
| `dpi` | Deep Packet Inspection statistics | |
| `events` | Recent events | `[--limit N]` |
| `alarms` | Active alarms | |
| `rogues` | Detected rogue access points | |
| `traffic` | Site traffic statistics | `[--interval 5minutes\|hourly\|daily]` |
| `dashboard` | Combined view: health + devices + clients + events | |

## Configuration Audit

```bash
python3 /opt/bridge/data/tools/unifi_audit.py <command> [--site SITE]
```

| Command | Description |
|---------|-------------|
| `full` | Complete audit (firmware + WLANs + networks + security) |
| `firmware` | Firmware currency and device status |
| `wlans` | WLAN security configuration (encryption, passphrase strength) |
| `networks` | Network/VLAN configuration (duplicates, DNS) |
| `security` | Security posture (rogue APs, port forwards, blocked clients) |

Findings are categorized by severity: `CRITICAL`, `WARNING`, `INFO`, `PASS`.

## Common Examples

### Quick status check

```bash
python3 /opt/bridge/data/tools/unifi_stats.py dashboard
```

### List all devices with firmware status

```bash
python3 /opt/bridge/data/tools/unifi_devices.py firmware
```

### Find who is connected to a specific SSID

```bash
python3 /opt/bridge/data/tools/unifi_clients.py list | python3 -c "
import json, sys
clients = json.load(sys.stdin)
for c in clients:
    if c.get('essid') == 'CorpWiFi':
        print(f\"{c['hostname']:30} {c['ip']:15} signal={c.get('signal','?')}\")
"
```

### Full compliance audit

```bash
python3 /opt/bridge/data/tools/unifi_audit.py full
```

### Restart an access point

```bash
python3 /opt/bridge/data/tools/unifi_devices.py restart aa:bb:cc:dd:ee:ff
```

### Check for rogue APs

```bash
python3 /opt/bridge/data/tools/unifi_stats.py rogues
```

## Workflow Patterns

### Network Troubleshooting

```bash
# 1. Check overall site health
python3 /opt/bridge/data/tools/unifi_stats.py health

# 2. Check if the user's device is connected
python3 /opt/bridge/data/tools/unifi_clients.py detail aa:bb:cc:dd:ee:ff

# 3. Check the AP the client is connected to
python3 /opt/bridge/data/tools/unifi_devices.py detail 11:22:33:44:55:66

# 4. Review recent events for anomalies
python3 /opt/bridge/data/tools/unifi_stats.py events --limit 25
```

### Firmware Upgrade Cycle

```bash
# 1. Check what needs updating
python3 /opt/bridge/data/tools/unifi_devices.py firmware

# 2. Upgrade a specific device
python3 /opt/bridge/data/tools/unifi_devices.py upgrade aa:bb:cc:dd:ee:ff

# 3. Monitor events during upgrade
python3 /opt/bridge/data/tools/unifi_stats.py events --limit 10
```

### Security Review

```bash
# 1. Run full audit
python3 /opt/bridge/data/tools/unifi_audit.py full

# 2. Check for rogue APs in detail
python3 /opt/bridge/data/tools/unifi_stats.py rogues

# 3. Review port forwards
python3 /opt/bridge/data/tools/unifi_networks.py port-forwards
```

## Authentication

The bridge uses session-based authentication (cookie). Credentials are resolved from environment variables injected by Tendril Root from the operator vault.

### Credential Setup

```
bridge_credentials(action="set", bridge="unifi", key="unifi_username", value="<admin-user>")
bridge_credentials(action="set", bridge="unifi", key="unifi_password", value="<password>")
```

## API Quirks and Known Issues

- **Self-signed certificates**: Most UniFi controllers use self-signed TLS certs. The client disables certificate verification by default.
- **UniFi OS vs Standard**: UDM Pro, UCG Max, and similar devices use `/api/auth/login` and prefix all API paths with `/proxy/network/`. Standard controllers (software-only) use `/api/login` with no prefix. The client auto-detects the controller type.
- **Session expiry**: Sessions expire after ~30 minutes of inactivity. The client automatically re-authenticates on 401 responses.
- **Rate limiting**: The UniFi API does not enforce strict rate limits, but rapid successive calls may cause temporary lockouts on some firmware versions.
- **Site name**: Most single-site controllers use `default` as the site name. Multi-site controllers use site-specific names visible in `list_sites`.
- **MAC format**: All MAC addresses should be lowercase with colons (e.g. `aa:bb:cc:dd:ee:ff`).
