---
name: meraki-api
description: Full management of a Meraki organization via Dashboard API v1 -- networks, devices (wireless APs, switches, appliances, sensors, cameras, cellular gateways), SSIDs, VLANs, firewall rules, site-to-site VPN, switch ports, client visibility, firmware compliance, and uplink monitoring.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.16"
metadata:
  author: tendril-project
  version: "1.0.0"
  tendril-bridge: "true"
  tags:
    - meraki
    - cisco
    - networking
    - wireless
    - switches
    - appliances
    - firewall
    - vpn
    - firmware
    - clients
---

# Meraki Dashboard API Bridge

Full programmatic access to a Meraki organization via the Cisco Meraki Dashboard REST API v1. Covers all networks, devices, VLANs, VPN, firewall rules, and client visibility across the organization.

## Authentication

- **Type:** Static API key (Bearer token)
- **API Base:** `https://api.meraki.com/api/v1`
- **Auth header:** `Authorization: Bearer <MERAKI_API_KEY>`
- **Token lifetime:** Indefinite (until revoked)
- **Credentials:** `MERAKI_API_KEY` in container environment (account-level, not per-operator)

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `meraki_client.py` | `/opt/bridge/data/tools/` | Core REST API client with Bearer auth, Link-header pagination, rate limiting, org auto-discovery. All other tools depend on this. |
| `meraki_check.py` | `/opt/bridge/data/tools/` | Health check: validates API key, org access, reports network/device counts |
| `meraki_bridge_tests.py` | `/opt/bridge/data/tools/` | Comprehensive read-only battery test (23 tests across 8 categories) |
| `network_check.py` | `/opt/bridge/data/tools/` | Network inventory, clients, VLANs, SSIDs, firmware versions |
| `device_check.py` | `/opt/bridge/data/tools/` | Device inventory, status monitoring, uplinks, switch ports, device search |
| `vpn_firewall.py` | `/opt/bridge/data/tools/` | Site-to-site VPN status, L3/L7 firewall rules, firewall audit |

## Quick Start

```bash
# Verify bridge connectivity
python3 /opt/bridge/data/tools/meraki_check.py

# Test API access
python3 /opt/bridge/data/tools/meraki_client.py test

# Device status overview
python3 /opt/bridge/data/tools/device_check.py status

# VPN status
python3 /opt/bridge/data/tools/vpn_firewall.py vpn-status

# Run full battery test
python3 /opt/bridge/data/tools/meraki_bridge_tests.py
```

## Tool Reference

### meraki_client.py -- CLI Quick Access

```bash
python3 meraki_client.py test                    # Health check / connection test
python3 meraki_client.py networks                # List all networks
python3 meraki_client.py devices                 # Device count by type
python3 meraki_client.py status                  # Device status overview
python3 meraki_client.py admins                  # Organization admins
```

### network_check.py -- Network Inventory

```bash
python3 network_check.py list                    # List all networks
python3 network_check.py info "<network-name>"   # Network details + devices
python3 network_check.py clients "<network-name>" # Connected clients (24h)
python3 network_check.py vlans "<network-name>"  # VLAN inventory
python3 network_check.py ssids "<network-name>"  # Wireless SSID config
python3 network_check.py firmware "<network-name>" # Firmware versions
python3 network_check.py summary                 # Org-wide summary
```

### device_check.py -- Device Management

```bash
python3 device_check.py inventory                # Full inventory by type/model/network
python3 device_check.py status                   # Online/offline/alerting overview
python3 device_check.py offline                  # Offline devices with last seen
python3 device_check.py alerting                 # Alerting devices
python3 device_check.py uplinks                  # Appliance uplink status
python3 device_check.py search "<term>"          # Search by name/serial/model/MAC
python3 device_check.py info Q2AW-FMLQ-DRTN     # Device details by serial
python3 device_check.py ports Q2AW-FMLQ-DRTN    # Switch port configuration
python3 device_check.py port-status Q2AW-FMLQ-DRTN  # Live switch port status
python3 device_check.py clients Q2AW-FMLQ-DRTN  # Clients on a device
```

### vpn_firewall.py -- VPN and Firewall

```bash
python3 vpn_firewall.py vpn-status              # All site VPN statuses + peer reachability
python3 vpn_firewall.py vpn-detail "<network-name>" # VPN config, hubs, subnets
python3 vpn_firewall.py firewall "<network-name>"   # L3 + L7 firewall rules
python3 vpn_firewall.py firewall-audit           # Audit all network firewalls
```

## API Coverage

### Organization

```python
from meraki_client import MerakiClient
client = MerakiClient()

client.get_org()                          # Organization details
client.list_networks()                    # All networks
client.list_admins()                      # Organization admins
client.get_license_overview()             # License status
client.list_inventory()                   # All claimed devices
```

### Devices

```python
client.list_devices()                     # All devices
client.list_device_statuses()             # Status for every device
client.get_device_status_overview()       # Online/offline/alerting counts
client.get_device("Q2AW-FMLQ-DRTN")      # Single device by serial
client.get_device_clients("Q2AW-FMLQ-DRTN") # Clients on a device (24h)
client.find_device_by_name("<term>")     # Search by name
```

### Uplinks

```python
client.list_uplink_statuses()             # All appliance uplinks
```

### Networks

```python
client.get_network("L_569705352862367899") # Single network
client.list_network_devices("L_569705352862367899") # Devices in network
client.list_network_clients("L_569705352862367899") # Clients on network (24h)
client.find_network_by_name("<network-name>") # Search by name
```

### Wireless

```python
client.get_ssids("L_569705352862367899")  # SSIDs for a network
client.get_ssid("L_569705352862367899", 0) # Single SSID detail
```

### Appliance (VLANs)

```python
client.get_vlans("L_569705352862367899")  # VLANs for a network
client.get_vlan("L_569705352862367899", 14) # Single VLAN
```

### Firewall

```python
client.get_l3_firewall_rules("L_569705352862367899") # L3 firewall rules
client.get_l7_firewall_rules("L_569705352862367899") # L7 firewall rules
```

### VPN

```python
client.list_vpn_statuses()                # Site-to-site VPN statuses
client.get_site_to_site_vpn("L_569705352862367899") # VPN config for a network
```

### Switch

```python
client.get_switch_ports("Q2AW-FMLQ-DRTN")       # Port configuration
client.get_switch_port_statuses("Q2AW-FMLQ-DRTN") # Live port statuses
```

### Firmware

```python
client.get_firmware_upgrades("L_569705352862367899") # Firmware per network
client.list_firmware_upgrades()           # Firmware upgrade history
```

## Common Patterns

### Network Troubleshooting
1. Check device status: `python3 device_check.py status` to see if anything is offline
2. Check alerting devices: `python3 device_check.py alerting` for active alerts
3. Check uplinks: `python3 device_check.py uplinks` for WAN connectivity
4. Check VPN: `python3 vpn_firewall.py vpn-status` for site connectivity

### Device Audit
1. Full inventory: `python3 device_check.py inventory`
2. Find specific device: `python3 device_check.py search "Admin"` or by serial
3. Check switch ports: `python3 device_check.py port-status <serial>`
4. See connected clients: `python3 device_check.py clients <serial>`

### Firmware Compliance
1. Check firmware per network: `python3 network_check.py firmware "<network-name>"`
2. Products use version prefixes: MR (wireless), MS (switch), MX (appliance), MV (camera), MT (sensor)

### VPN Health Check
1. Overview: `python3 vpn_firewall.py vpn-status` -- shows all VPN sites with peer reachability
2. Detail: `python3 vpn_firewall.py vpn-detail "<network-name>"` for subnets and hub config

### Firewall Audit
1. Single network: `python3 vpn_firewall.py firewall "<network-name>"` for L3+L7 rules
2. Org-wide: `python3 vpn_firewall.py firewall-audit` to audit all appliance networks

### Client Investigation
1. By network: `python3 network_check.py clients "<network-name>"` (shows VLAN, IP, usage)
2. By device: `python3 device_check.py clients <serial>` (clients on a specific switch/AP)

## Tenant Context

- **Organization:** Discovered automatically from API key
- **Cloud region:** North America (n12.dashboard.meraki.com)
- **Networks, devices, admins:** Discovered via API (use `meraki_check.py` for counts)
- **VPN topology:** Hub-and-spoke is common; use `vpn_firewall.py vpn-status` to discover your topology
- **Licensing:** Subscription model

## Network Naming Convention

Organizations may use different naming schemes (e.g., numeric prefixes, site codes, facility names). Use `network_check.py list` and `network_check.py info "<network-name>"` to explore your organization's structure.

## Rate Limiting

- **Limit:** ~10 requests/second (varies by endpoint and org size)
- **Response:** HTTP 429 with `Retry-After` header (seconds)
- **Strategy:** Sleep for `Retry-After`, then retry (max 3 attempts)

## Pagination

Meraki uses cursor-based pagination via the `Link` HTTP header with `rel=next`. The `get_all()` helper follows `Link` headers automatically. Default `perPage` is 1000 (max varies by endpoint).

## API Quirks and Known Issues

1. **Pagination is in the Link header.** Unlike Graph or Zoom, Meraki puts the next page URL in the HTTP `Link` header (`<url>; rel=next`), not in the response body.
2. **perPage limits vary.** Most endpoints accept 1000, but some (VPN statuses) require 3-300. The client handles this per-endpoint.
3. **Device serial is the primary ID.** All device-level operations use the serial number (e.g., `Q2AW-FMLQ-DRTN`), not a UUID or numeric ID.
4. **Network ID format.** Combined networks use `L_` prefix, standalone networks use `N_` prefix.
5. **Product type gating.** Endpoints return 400 if the network doesn't have the relevant product type (e.g., requesting VLANs on a wireless-only network). The client returns empty lists for these.
6. **Client descriptions can be null.** Use MAC address as fallback when `description` is null.
7. **Switch port VLANs can be null.** Trunk ports don't have a single VLAN assignment.
8. **Firmware version prefixes.** Versions use product-specific prefixes: MR (wireless), MS (switch), MX (appliance), MV (camera), MT (sensor).
9. **Uplink statuses are org-level only.** There is no per-device uplink status endpoint -- use the org-level endpoint and filter client-side.
10. **VPN statuses include peer reachability.** The `merakiVpnPeers` array shows reachability to each peer, useful for troubleshooting site connectivity.
11. **License status.** Check your organization's license status. Some orgs may show expired licenses while API access continues to function.
12. **Inventory vs devices.** `list_inventory()` returns all claimed devices including unconfigured ones. `list_devices()` returns only network-assigned devices.
13. **SSID slots.** Every wireless network has 15 SSID slots (0-14). Unconfigured slots show as "Unconfigured SSID" with `enabled=false`.

## Battery Test

Run the comprehensive read-only battery test to verify all API connectivity:

```bash
python3 /opt/bridge/data/tools/meraki_bridge_tests.py
```

The test covers 23 tests across 8 categories: Organization, Networks, Devices, Uplinks, Wireless, Appliance (VLANs + Firewall), VPN, and Switch.
