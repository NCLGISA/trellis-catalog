#!/usr/bin/env python3
"""
Meraki Network Inventory and Configuration Tool

Provides network-level visibility into the Meraki organization:
  - Network inventory with product types
  - SSID configuration across networks
  - VLAN inventory per network
  - Client counts and usage
  - Firmware versions and compliance

Usage:
  python3 network_check.py list                    # List all networks
  python3 network_check.py info <name>             # Network details + devices
  python3 network_check.py clients <name>          # Network clients (24h)
  python3 network_check.py vlans <name>            # VLAN inventory
  python3 network_check.py ssids <name>            # Wireless SSIDs
  python3 network_check.py firmware <name>         # Firmware versions
  python3 network_check.py summary                 # Org-wide summary
"""

import sys
import json
from meraki_client import MerakiClient


def cmd_list(client):
    """List all networks with product types."""
    networks = client.list_networks()
    print(f"Networks: {len(networks)}\n")
    for n in sorted(networks, key=lambda x: x.get("name", "")):
        types = ", ".join(n.get("productTypes", []))
        tz = n.get("timeZone", "")
        print(f"  {n['name']:50s}  [{types}]")
    print(f"\nTotal: {len(networks)} networks")


def cmd_info(client, name):
    """Show details for a specific network."""
    net = client.find_network_by_name(name)
    if not net:
        print(f"No network matching '{name}'")
        sys.exit(1)

    print(f"Network: {net['name']}")
    print(f"  ID:            {net['id']}")
    print(f"  Org ID:        {net.get('organizationId')}")
    print(f"  Product types: {', '.join(net.get('productTypes', []))}")
    print(f"  Timezone:      {net.get('timeZone', '?')}")
    print(f"  Tags:          {', '.join(net.get('tags', [])) or 'none'}")
    print(f"  Notes:         {net.get('notes') or 'none'}")

    devices = client.list_network_devices(net["id"])
    print(f"\n  Devices ({len(devices)}):")
    for d in sorted(devices, key=lambda x: x.get("name") or ""):
        status_str = ""
        ip = d.get("lanIp", "")
        print(f"    {(d.get('name') or d['serial']):35s}  {d['model']:15s}  {ip:16s}  serial={d['serial']}")


def cmd_clients(client, name):
    """Show clients connected to a network (last 24h)."""
    net = client.find_network_by_name(name)
    if not net:
        print(f"No network matching '{name}'")
        sys.exit(1)

    clients = client.list_network_clients(net["id"])
    print(f"Clients on '{net['name']}' (last 24h): {len(clients)}\n")

    from collections import Counter
    vlan_counts = Counter(c.get("vlan") for c in clients)

    for c in sorted(clients, key=lambda x: x.get("description") or x.get("mac", "")):
        desc = c.get("description") or c.get("mac", "?")
        ip = c.get("ip") or "no-ip"
        vlan = c.get("vlan", "?")
        usage_sent = c.get("usage", {}).get("sent", 0)
        usage_recv = c.get("usage", {}).get("recv", 0)
        total_kb = (usage_sent + usage_recv) / 1024
        print(f"  {desc:40s}  ip={ip:16s}  vlan={str(vlan):5s}  usage={total_kb:,.0f} KB")

    print(f"\nTotal: {len(clients)} clients")
    print(f"\nClients by VLAN:")
    for vlan, count in vlan_counts.most_common():
        print(f"  VLAN {str(vlan):6s}  {count} clients")


def cmd_vlans(client, name):
    """Show VLAN inventory for a network."""
    net = client.find_network_by_name(name)
    if not net:
        print(f"No network matching '{name}'")
        sys.exit(1)

    if "appliance" not in net.get("productTypes", []):
        print(f"Network '{net['name']}' has no appliance -- VLANs not available")
        return

    vlans = client.get_vlans(net["id"])
    if not vlans:
        print(f"No VLANs configured on '{net['name']}'")
        return

    print(f"VLANs on '{net['name']}': {len(vlans)}\n")
    print(f"  {'ID':6s}  {'Name':25s}  {'Subnet':20s}  {'Gateway':16s}  {'DHCP':10s}")
    print(f"  {'─'*6}  {'─'*25}  {'─'*20}  {'─'*16}  {'─'*10}")
    for v in sorted(vlans, key=lambda x: x.get("id", 0)):
        vid = str(v.get("id", "?"))
        vname = v.get("name", "?")
        subnet = v.get("subnet", "?")
        gw = v.get("applianceIp", "?")
        dhcp = v.get("dhcpHandling", "?")
        print(f"  {vid:6s}  {vname:25s}  {subnet:20s}  {gw:16s}  {dhcp:10s}")


def cmd_ssids(client, name):
    """Show wireless SSIDs for a network."""
    net = client.find_network_by_name(name)
    if not net:
        print(f"No network matching '{name}'")
        sys.exit(1)

    if "wireless" not in net.get("productTypes", []):
        print(f"Network '{net['name']}' has no wireless -- SSIDs not available")
        return

    ssids = client.get_ssids(net["id"])
    if not ssids:
        print(f"No SSIDs on '{net['name']}'")
        return

    print(f"SSIDs on '{net['name']}':\n")
    print(f"  {'#':3s}  {'Name':30s}  {'Enabled':8s}  {'Auth':20s}  {'VLAN':6s}  {'Band':10s}")
    print(f"  {'─'*3}  {'─'*30}  {'─'*8}  {'─'*20}  {'─'*6}  {'─'*10}")
    for s in ssids:
        num = str(s.get("number", "?"))
        sname = s.get("name", "?")
        enabled = "Yes" if s.get("enabled") else "No"
        auth = s.get("authMode", "?")
        vlan = str(s.get("defaultVlanId", "")) or "-"
        band = s.get("bandSelection", "?")
        if s.get("enabled") or sname != "Unconfigured SSID":
            print(f"  {num:3s}  {sname:30s}  {enabled:8s}  {auth:20s}  {vlan:6s}  {band:10s}")


def cmd_firmware(client, name):
    """Show firmware versions for a network."""
    net = client.find_network_by_name(name)
    if not net:
        print(f"No network matching '{name}'")
        sys.exit(1)

    fw = client.get_firmware_upgrades(net["id"])
    if not fw:
        print(f"No firmware info for '{net['name']}'")
        return

    products = fw.get("products", {})
    print(f"Firmware on '{net['name']}':\n")
    print(f"  {'Product':15s}  {'Current Version':25s}  {'Latest Available':25s}")
    print(f"  {'─'*15}  {'─'*25}  {'─'*25}")
    for product, info in sorted(products.items()):
        current = info.get("currentVersion", {}).get("shortName", "?")
        available_versions = info.get("availableVersions", [])
        latest = available_versions[-1].get("shortName", "?") if available_versions else current
        behind = " (update available)" if latest != current and latest != "?" else ""
        print(f"  {product:15s}  {current:25s}  {latest:25s}{behind}")


def cmd_summary(client):
    """Organization-wide summary."""
    org = client.get_org()
    networks = client.list_networks()
    overview = client.get_device_status_overview()
    admins = client.list_admins()

    print(f"Organization: {org.get('name')}")
    print(f"  Org ID:    {org.get('id')}")
    print(f"  Licensing: {org.get('licensing', {}).get('model', 'unknown')}")
    print(f"  Region:    {org.get('cloud', {}).get('region', {}).get('name', 'unknown')}")

    counts = overview.get("counts", {}).get("byStatus", {})
    total = sum(counts.values())
    print(f"\nDevices: {total}")
    for status, count in sorted(counts.items()):
        print(f"  {status:12s}  {count}")

    print(f"\nNetworks: {len(networks)}")
    from collections import Counter
    type_counts = Counter()
    for n in networks:
        for pt in n.get("productTypes", []):
            type_counts[pt] += 1
    for pt, count in type_counts.most_common():
        print(f"  {pt:20s}  {count} networks")

    print(f"\nAdmins: {len(admins)}")
    for a in admins:
        mfa = "MFA" if a.get("twoFactorAuthEnabled") else "no-MFA"
        print(f"  {a.get('name', '?'):25s}  {a.get('orgAccess', '?'):6s}  {mfa}")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    action = sys.argv[1]
    client = MerakiClient()

    if action == "list":
        cmd_list(client)
    elif action == "info" and len(sys.argv) >= 3:
        cmd_info(client, " ".join(sys.argv[2:]))
    elif action == "clients" and len(sys.argv) >= 3:
        cmd_clients(client, " ".join(sys.argv[2:]))
    elif action == "vlans" and len(sys.argv) >= 3:
        cmd_vlans(client, " ".join(sys.argv[2:]))
    elif action == "ssids" and len(sys.argv) >= 3:
        cmd_ssids(client, " ".join(sys.argv[2:]))
    elif action == "firmware" and len(sys.argv) >= 3:
        cmd_firmware(client, " ".join(sys.argv[2:]))
    elif action == "summary":
        cmd_summary(client)
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
