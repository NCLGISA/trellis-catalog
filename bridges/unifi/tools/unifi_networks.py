#!/usr/bin/env python3
"""
UniFi Network / VLAN Configuration Tool

Network segment and VLAN management, firewall rules, port forwarding,
and routing for UniFi controllers.

Usage:
    python3 unifi_networks.py networks [--site SITE]
    python3 unifi_networks.py network-detail <network_id> [--site SITE]
    python3 unifi_networks.py vlans [--site SITE]
    python3 unifi_networks.py firewall [--site SITE]
    python3 unifi_networks.py port-forwards [--site SITE]
    python3 unifi_networks.py routes [--site SITE]
    python3 unifi_networks.py summary [--site SITE]

All operations are read-only.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unifi_client import UniFiClient


def cmd_networks(client, args):
    """List all network configurations."""
    nets = client.list_networks(site=args.site)
    rows = []
    for n in nets:
        rows.append({
            "name": n.get("name", "?"),
            "id": n.get("_id", ""),
            "purpose": n.get("purpose", "?"),
            "vlan": n.get("vlan"),
            "vlan_enabled": n.get("vlan_enabled", False),
            "subnet": n.get("ip_subnet", ""),
            "domain_name": n.get("domain_name", ""),
            "dhcpd_enabled": n.get("dhcpd_enabled", False),
            "dhcp_start": n.get("dhcpd_start", ""),
            "dhcp_stop": n.get("dhcpd_stop", ""),
            "dhcp_dns": n.get("dhcpd_dns_1", ""),
            "igmp_snooping": n.get("igmp_snooping", False),
            "networkgroup": n.get("networkgroup", ""),
        })
    print(json.dumps(rows, indent=2))


def cmd_network_detail(client, args):
    """Get full details for a single network."""
    net = client.get_network(args.network_id, site=args.site)
    if not net:
        print(json.dumps({"error": f"Network {args.network_id} not found"}))
        sys.exit(1)
    print(json.dumps(net, indent=2, default=str))


def cmd_vlans(client, args):
    """List networks with VLAN focus -- VLAN IDs, subnets, DHCP status."""
    nets = client.list_networks(site=args.site)
    rows = []
    for n in nets:
        rows.append({
            "name": n.get("name", "?"),
            "vlan": n.get("vlan", "untagged"),
            "subnet": n.get("ip_subnet", ""),
            "purpose": n.get("purpose", "?"),
            "dhcp": n.get("dhcpd_enabled", False),
            "igmp_snooping": n.get("igmp_snooping", False),
        })
    rows.sort(key=lambda r: (r["vlan"] if isinstance(r["vlan"], int) else 0))
    print(json.dumps(rows, indent=2))


def cmd_firewall(client, args):
    """List firewall rules."""
    rules = client.list_firewall_rules(site=args.site)
    rows = []
    for r in rules:
        rows.append({
            "name": r.get("name", "?"),
            "id": r.get("_id", ""),
            "enabled": r.get("enabled", True),
            "ruleset": r.get("ruleset", "?"),
            "action": r.get("action", "?"),
            "protocol": r.get("protocol", "all"),
            "src": r.get("src_firewallgroup_ids", []),
            "dst": r.get("dst_firewallgroup_ids", []),
            "rule_index": r.get("rule_index"),
        })
    print(json.dumps(rows, indent=2))


def cmd_port_forwards(client, args):
    """List port forwarding rules."""
    fwds = client.list_port_forwards(site=args.site)
    rows = []
    for f in fwds:
        rows.append({
            "name": f.get("name", "?"),
            "id": f.get("_id", ""),
            "enabled": f.get("enabled", True),
            "proto": f.get("proto", "?"),
            "src": f.get("src", "any"),
            "dst_port": f.get("dst_port", "?"),
            "fwd": f.get("fwd", "?"),
            "fwd_port": f.get("fwd_port", "?"),
        })
    print(json.dumps(rows, indent=2))


def cmd_routes(client, args):
    """List static routes."""
    routes = client.list_routes(site=args.site)
    rows = []
    for r in routes:
        rows.append({
            "name": r.get("name", "?"),
            "id": r.get("_id", ""),
            "enabled": r.get("enabled", True),
            "type": r.get("type", "?"),
            "network": r.get("static-route_network", ""),
            "nexthop": r.get("static-route_nexthop", ""),
            "distance": r.get("static-route_distance", ""),
            "interface": r.get("static-route_interface", ""),
        })
    print(json.dumps(rows, indent=2))


def cmd_summary(client, args):
    """Overall network topology summary."""
    nets = client.list_networks(site=args.site)
    rules = client.list_firewall_rules(site=args.site)
    fwds = client.list_port_forwards(site=args.site)
    routes = client.list_routes(site=args.site)

    vlans = [n.get("vlan") for n in nets if n.get("vlan")]

    summary = {
        "total_networks": len(nets),
        "vlans": sorted(set(v for v in vlans if isinstance(v, int))),
        "firewall_rules": len(rules),
        "port_forwards": len(fwds),
        "static_routes": len(routes),
        "networks": [
            {
                "name": n.get("name", "?"),
                "vlan": n.get("vlan", "untagged"),
                "subnet": n.get("ip_subnet", ""),
                "purpose": n.get("purpose", "?"),
            }
            for n in nets
        ],
    }
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description="UniFi Network/VLAN Management")
    parser.add_argument("command", choices=["networks", "network-detail", "vlans",
                                            "firewall", "port-forwards", "routes",
                                            "summary"])
    parser.add_argument("network_id", nargs="?", help="Network ID (for network-detail)")
    parser.add_argument("--site", default=None, help="Site name")
    args = parser.parse_args()

    if args.command == "network-detail" and not args.network_id:
        parser.error("network-detail requires a network ID argument")

    client = UniFiClient()
    try:
        {
            "networks": cmd_networks,
            "network-detail": cmd_network_detail,
            "vlans": cmd_vlans,
            "firewall": cmd_firewall,
            "port-forwards": cmd_port_forwards,
            "routes": cmd_routes,
            "summary": cmd_summary,
        }[args.command](client, args)
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)
    finally:
        client.logout()


if __name__ == "__main__":
    main()
