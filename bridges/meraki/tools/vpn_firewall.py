#!/usr/bin/env python3
"""
Meraki VPN and Firewall Tool

Provides visibility into VPN connectivity and firewall rules:
  - Site-to-site VPN status across the organization
  - L3 and L7 firewall rules per network
  - VPN peer details and connectivity

Usage:
  python3 vpn_firewall.py vpn-status               # All VPN site statuses
  python3 vpn_firewall.py vpn-detail <name>         # VPN config for a network
  python3 vpn_firewall.py firewall <name>           # L3 + L7 firewall rules
  python3 vpn_firewall.py firewall-audit            # Audit all network firewalls
"""

import sys
import json
from meraki_client import MerakiClient


def cmd_vpn_status(client):
    """Show site-to-site VPN statuses."""
    statuses = client.list_vpn_statuses()
    networks = {n["id"]: n["name"] for n in client.list_networks()}

    print(f"Site-to-Site VPN Statuses: {len(statuses)} sites\n")

    online = sum(1 for s in statuses if s.get("deviceStatus") == "online")
    offline = sum(1 for s in statuses if s.get("deviceStatus") != "online")
    print(f"  Online: {online}  |  Offline/Other: {offline}\n")

    for s in sorted(statuses, key=lambda x: x.get("networkName", "")):
        net_name = s.get("networkName") or networks.get(s.get("networkId", ""), "?")
        status = s.get("deviceStatus", "?")
        serial = s.get("deviceSerial", "?")
        peers = s.get("merakiVpnPeers", [])
        third_party = s.get("thirdPartyVpnPeers", [])

        marker = "●" if status == "online" else "○" if status == "dormant" else "✕"
        peer_str = f"{len(peers)} Meraki peers" if peers else "no peers"
        if third_party:
            peer_str += f", {len(third_party)} 3rd-party"

        print(f"  {marker} {net_name:45s}  {status:10s}  {peer_str}")

        if peers:
            for p in peers[:5]:
                p_name = p.get("networkName", "?")
                p_status = p.get("reachability", "?")
                p_marker = "●" if p_status == "reachable" else "✕"
                print(f"      {p_marker} → {p_name} ({p_status})")
            if len(peers) > 5:
                print(f"      ... and {len(peers) - 5} more peers")


def cmd_vpn_detail(client, name):
    """Show VPN configuration for a network."""
    net = client.find_network_by_name(name)
    if not net:
        print(f"No network matching '{name}'")
        sys.exit(1)

    if "appliance" not in net.get("productTypes", []):
        print(f"Network '{net['name']}' has no appliance -- VPN not available")
        return

    vpn = client.get_site_to_site_vpn(net["id"])
    if not vpn:
        print(f"No VPN config for '{net['name']}'")
        return

    print(f"VPN Configuration: {net['name']}\n")
    print(f"  Mode: {vpn.get('mode', 'none')}")

    hubs = vpn.get("hubs", [])
    if hubs:
        networks = {n["id"]: n["name"] for n in client.list_networks()}
        print(f"\n  Hubs ({len(hubs)}):")
        for h in hubs:
            hub_name = networks.get(h.get("hubId", ""), h.get("hubId", "?"))
            default = " (default route)" if h.get("useDefaultRoute") else ""
            print(f"    → {hub_name}{default}")

    subnets = vpn.get("subnets", [])
    if subnets:
        print(f"\n  Subnets ({len(subnets)}):")
        for s in subnets:
            use = "advertised" if s.get("useVpn") else "not advertised"
            print(f"    {s.get('localSubnet', '?'):20s}  {use}")


def cmd_firewall(client, name):
    """Show L3 and L7 firewall rules for a network."""
    net = client.find_network_by_name(name)
    if not net:
        print(f"No network matching '{name}'")
        sys.exit(1)

    if "appliance" not in net.get("productTypes", []):
        print(f"Network '{net['name']}' has no appliance -- firewall not available")
        return

    # L3 rules
    l3_rules = client.get_l3_firewall_rules(net["id"])
    print(f"L3 Firewall Rules: {net['name']} ({len(l3_rules)} rules)\n")
    if l3_rules:
        print(f"  {'#':3s}  {'Policy':8s}  {'Protocol':10s}  {'Source':22s}  {'Destination':22s}  {'Port':10s}  {'Comment'}")
        print(f"  {'─'*3}  {'─'*8}  {'─'*10}  {'─'*22}  {'─'*22}  {'─'*10}  {'─'*20}")
        for i, r in enumerate(l3_rules, 1):
            policy = r.get("policy", "?")
            proto = r.get("protocol", "?")
            src = r.get("srcCidr", "?")
            dst = r.get("destCidr", "?")
            port = r.get("destPort", "Any")
            comment = r.get("comment", "")
            print(f"  {i:3d}  {policy:8s}  {proto:10s}  {src:22s}  {dst:22s}  {str(port):10s}  {comment}")

    # L7 rules
    l7_rules = client.get_l7_firewall_rules(net["id"])
    if l7_rules:
        print(f"\nL7 Firewall Rules ({len(l7_rules)}):\n")
        print(f"  {'#':3s}  {'Policy':8s}  {'Type':20s}  {'Value'}")
        print(f"  {'─'*3}  {'─'*8}  {'─'*20}  {'─'*30}")
        for i, r in enumerate(l7_rules, 1):
            policy = r.get("policy", "?")
            rtype = r.get("type", "?")
            value = r.get("value", "?")
            print(f"  {i:3d}  {policy:8s}  {rtype:20s}  {value}")
    else:
        print("\nNo L7 firewall rules configured.")


def cmd_firewall_audit(client):
    """Audit firewall rules across all appliance networks."""
    networks = client.list_networks()
    appliance_nets = [n for n in networks if "appliance" in n.get("productTypes", [])]

    print(f"Firewall Audit: {len(appliance_nets)} appliance networks\n")

    for net in sorted(appliance_nets, key=lambda x: x.get("name", "")):
        l3 = client.get_l3_firewall_rules(net["id"])
        l7 = client.get_l7_firewall_rules(net["id"])

        # Count non-default rules (the default "allow any" rule is always present)
        custom_l3 = [r for r in l3 if r.get("comment") != "Default rule" and not (
            r.get("policy") == "allow" and r.get("srcCidr") == "Any" and r.get("destCidr") == "Any"
        )]

        status = "✓" if custom_l3 or l7 else "○"
        print(f"  {status} {net['name']:45s}  L3: {len(custom_l3)} custom rules  |  L7: {len(l7)} rules")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    action = sys.argv[1]
    client = MerakiClient()

    if action == "vpn-status":
        cmd_vpn_status(client)
    elif action == "vpn-detail" and len(sys.argv) >= 3:
        cmd_vpn_detail(client, " ".join(sys.argv[2:]))
    elif action == "firewall" and len(sys.argv) >= 3:
        cmd_firewall(client, " ".join(sys.argv[2:]))
    elif action == "firewall-audit":
        cmd_firewall_audit(client)
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
