#!/usr/bin/env python3
"""
Meraki Device Inventory and Status Tool

Provides device-level visibility into the Meraki organization:
  - Device inventory by type, model, and network
  - Online/offline/alerting status monitoring
  - Uplink status for appliances
  - Switch port configuration and status
  - Device search by name or serial

Usage:
  python3 device_check.py inventory                # Full device inventory
  python3 device_check.py status                   # Device status overview
  python3 device_check.py offline                  # Offline devices
  python3 device_check.py alerting                 # Alerting devices
  python3 device_check.py uplinks                  # Appliance uplink status
  python3 device_check.py search <query>           # Search by name/serial/model
  python3 device_check.py info <serial>            # Device details
  python3 device_check.py ports <serial>           # Switch port config
  python3 device_check.py port-status <serial>     # Switch port live status
  python3 device_check.py clients <serial>         # Clients on a device
"""

import sys
import json
from collections import Counter
from meraki_client import MerakiClient


def cmd_inventory(client):
    """Full device inventory breakdown."""
    devices = client.list_devices()
    print(f"Total devices: {len(devices)}\n")

    types = Counter(d.get("productType", "unknown") for d in devices)
    print("By product type:")
    for t, c in types.most_common():
        print(f"  {t:20s}  {c}")

    models = Counter(d.get("model", "unknown") for d in devices)
    print(f"\nBy model:")
    for m, c in models.most_common():
        print(f"  {m:20s}  {c}")

    # Group by network
    net_counts = Counter(d.get("networkId", "unassigned") for d in devices)
    networks = {n["id"]: n["name"] for n in client.list_networks()}
    print(f"\nBy network (top 20):")
    for net_id, count in net_counts.most_common(20):
        net_name = networks.get(net_id, net_id)
        print(f"  {net_name:50s}  {count}")


def cmd_status(client):
    """Device status overview with details for non-online."""
    overview = client.get_device_status_overview()
    counts = overview.get("counts", {}).get("byStatus", {})
    total = sum(counts.values())
    print(f"Device Status Overview ({total} total):\n")
    for status, count in sorted(counts.items()):
        pct = (count / total * 100) if total else 0
        bar = "█" * int(pct / 2)
        print(f"  {status:12s}  {count:4d}  ({pct:5.1f}%)  {bar}")


def cmd_offline(client):
    """Show offline devices."""
    statuses = client.list_device_statuses()
    offline = [d for d in statuses if d.get("status") == "offline"]
    print(f"Offline devices: {len(offline)}\n")
    if not offline:
        print("  All devices are online or dormant.")
        return
    for d in sorted(offline, key=lambda x: x.get("name") or ""):
        name = d.get("name") or d.get("serial", "?")
        model = d.get("model", "?")
        last_seen = d.get("lastReportedAt", "never")
        ip = d.get("lanIp") or d.get("publicIp") or "no-ip"
        print(f"  {name:40s}  {model:15s}  {ip:16s}  last={last_seen}")


def cmd_alerting(client):
    """Show alerting devices."""
    statuses = client.list_device_statuses()
    alerting = [d for d in statuses if d.get("status") == "alerting"]
    print(f"Alerting devices: {len(alerting)}\n")
    if not alerting:
        print("  No devices are alerting.")
        return
    for d in sorted(alerting, key=lambda x: x.get("name") or ""):
        name = d.get("name") or d.get("serial", "?")
        model = d.get("model", "?")
        ip = d.get("lanIp") or d.get("publicIp") or "no-ip"
        last_seen = d.get("lastReportedAt", "?")
        print(f"  {name:40s}  {model:15s}  {ip:16s}  last={last_seen}")


def cmd_uplinks(client):
    """Show appliance uplink statuses."""
    uplinks = client.list_uplink_statuses()
    networks = {n["id"]: n["name"] for n in client.list_networks()}
    print(f"Appliance uplinks: {len(uplinks)}\n")

    for u in sorted(uplinks, key=lambda x: networks.get(x.get("networkId", ""), "")):
        net_name = networks.get(u.get("networkId", ""), "?")
        model = u.get("model", "?")
        ha = u.get("highAvailability", {})
        ha_str = f" ({ha.get('role', '?')})" if ha.get("enabled") else ""

        print(f"  {net_name:45s}  {model}{ha_str}")
        for link in u.get("uplinks", []):
            iface = link.get("interface") or "?"
            status = link.get("status") or "?"
            ip = link.get("ip") or "no-ip"
            public = link.get("publicIp") or "no-ip"
            assign = link.get("ipAssignedBy") or "?"
            marker = "●" if status == "active" else "○" if status == "ready" else "✕"
            print(f"    {marker} {iface:6s}  {status:10s}  ip={ip:16s}  public={public:16s}  {assign}")


def cmd_search(client, query):
    """Search devices by name, serial, or model."""
    devices = client.list_devices()
    query_lower = query.lower()
    matches = [
        d for d in devices
        if query_lower in (d.get("name") or "").lower()
        or query_lower in d.get("serial", "").lower()
        or query_lower in d.get("model", "").lower()
        or query_lower in (d.get("mac") or "").lower()
    ]
    print(f"Search '{query}': {len(matches)} matches\n")
    for d in sorted(matches, key=lambda x: x.get("name") or ""):
        name = d.get("name") or "(unnamed)"
        ip = d.get("lanIp") or "no-ip"
        print(f"  {name:40s}  {d['model']:15s}  {ip:16s}  serial={d['serial']}")


def cmd_info(client, serial):
    """Show detailed info for a single device."""
    try:
        d = client.get_device(serial)
    except Exception:
        print(f"Device not found: {serial}")
        sys.exit(1)

    print(f"Device: {d.get('name') or '(unnamed)'}")
    print(f"  Serial:        {d.get('serial')}")
    print(f"  Model:         {d.get('model')}")
    print(f"  MAC:           {d.get('mac')}")
    print(f"  LAN IP:        {d.get('lanIp', 'n/a')}")
    print(f"  Firmware:      {d.get('firmware', 'n/a')}")
    print(f"  Network ID:    {d.get('networkId')}")
    print(f"  Tags:          {', '.join(d.get('tags', [])) or 'none'}")
    print(f"  Notes:         {d.get('notes') or 'none'}")
    print(f"  Address:       {d.get('address') or 'n/a'}")
    print(f"  Lat/Lng:       {d.get('lat')}, {d.get('lng')}")


def cmd_ports(client, serial):
    """Show switch port configuration."""
    ports = client.get_switch_ports(serial)
    if not ports:
        print(f"No switch ports for {serial} (not a switch or not accessible)")
        return

    print(f"Switch ports for {serial}: {len(ports)}\n")
    print(f"  {'Port':5s}  {'Type':8s}  {'VLAN':6s}  {'Voice':6s}  {'Enabled':8s}  {'PoE':4s}  {'Name'}")
    print(f"  {'─'*5}  {'─'*8}  {'─'*6}  {'─'*6}  {'─'*8}  {'─'*4}  {'─'*20}")
    for p in ports:
        pid = str(p.get("portId", "?"))
        ptype = p.get("type", "?")
        vlan = str(p.get("vlan") or "-")
        voice = str(p.get("voiceVlan") or "-")
        enabled = "Yes" if p.get("enabled") else "No"
        poe = "Yes" if p.get("poeEnabled") else "No"
        name = p.get("name") or ""
        print(f"  {pid:5s}  {ptype:8s}  {vlan:6s}  {voice:6s}  {enabled:8s}  {poe:4s}  {name}")


def cmd_port_status(client, serial):
    """Show live switch port statuses."""
    statuses = client.get_switch_port_statuses(serial)
    if not statuses:
        print(f"No port statuses for {serial}")
        return

    active = sum(1 for p in statuses if p.get("status") == "Connected")
    print(f"Switch port statuses for {serial}: {len(statuses)} ports, {active} connected\n")
    print(f"  {'Port':5s}  {'Status':12s}  {'Speed':12s}  {'Duplex':8s}  {'PoE (W)':8s}  {'Clients':8s}  {'LLDP/CDP'}")
    print(f"  {'─'*5}  {'─'*12}  {'─'*12}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*25}")
    for p in statuses:
        pid = str(p.get("portId", "?"))
        status = p.get("status", "?")
        speed = p.get("speed") or "-"
        duplex = p.get("duplex") or "-"
        poe_w = str(p.get("powerUsageInWh") or "-")
        clients = str(p.get("clientCount", 0))
        # LLDP/CDP neighbor info
        lldp = p.get("lldp", {})
        cdp = p.get("cdp", {})
        neighbor = lldp.get("systemName") or cdp.get("deviceId") or ""
        if status != "Disconnected" or neighbor:
            print(f"  {pid:5s}  {status:12s}  {speed:12s}  {duplex:8s}  {poe_w:8s}  {clients:8s}  {neighbor}")


def cmd_clients(client, serial):
    """Show clients connected to a specific device."""
    clients = client.get_device_clients(serial)
    print(f"Clients on {serial} (last 24h): {len(clients)}\n")
    for c in sorted(clients, key=lambda x: x.get("description") or x.get("mac", "")):
        desc = c.get("description") or c.get("mac", "?")
        ip = c.get("ip") or "no-ip"
        vlan = str(c.get("vlan") or "?")
        usage_sent = c.get("usage", {}).get("sent", 0)
        usage_recv = c.get("usage", {}).get("recv", 0)
        total_kb = (usage_sent + usage_recv) / 1024
        print(f"  {desc:40s}  ip={ip:16s}  vlan={vlan:5s}  {total_kb:,.0f} KB")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    action = sys.argv[1]
    client = MerakiClient()

    if action == "inventory":
        cmd_inventory(client)
    elif action == "status":
        cmd_status(client)
    elif action == "offline":
        cmd_offline(client)
    elif action == "alerting":
        cmd_alerting(client)
    elif action == "uplinks":
        cmd_uplinks(client)
    elif action == "search" and len(sys.argv) >= 3:
        cmd_search(client, " ".join(sys.argv[2:]))
    elif action == "info" and len(sys.argv) >= 3:
        cmd_info(client, sys.argv[2])
    elif action == "ports" and len(sys.argv) >= 3:
        cmd_ports(client, sys.argv[2])
    elif action == "port-status" and len(sys.argv) >= 3:
        cmd_port_status(client, sys.argv[2])
    elif action == "clients" and len(sys.argv) >= 3:
        cmd_clients(client, sys.argv[2])
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
