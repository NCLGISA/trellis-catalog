#!/usr/bin/env python3
"""
NSG (Network Security Group) inspection tool via ARM API.

Lists NSGs, their rules, and provides filtering by port, protocol,
and direction for segmentation analysis.

Usage:
    python3 nsg_query.py list                          # All NSGs
    python3 nsg_query.py rules <rg> <nsg-name>         # Rules for an NSG
    python3 nsg_query.py find-port <port>              # Find rules affecting a port
    python3 nsg_query.py summary                       # Rule count summary
"""

import sys
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from arm_client import ArmClient


def cmd_list(client: ArmClient):
    """List all NSGs with rule counts."""
    nsgs = client.list_nsgs()
    nsgs.sort(key=lambda n: n["name"])

    print(f"Network Security Groups ({len(nsgs)}):\n")
    print(f"  {'Name':40s}  {'Resource Group':30s}  {'Custom Rules':>12s}  {'Location':15s}")
    print(f"  {'─' * 40}  {'─' * 30}  {'─' * 12}  {'─' * 15}")

    for nsg in nsgs:
        rg = nsg["id"].split("/resourceGroups/")[1].split("/")[0]
        rule_count = len(nsg.get("properties", {}).get("securityRules", []))
        print(f"  {nsg['name']:40s}  {rg:30s}  {rule_count:12d}  {nsg.get('location', '?')}")


def cmd_rules(client: ArmClient, resource_group: str, nsg_name: str):
    """List all rules for a specific NSG."""
    rules = client.list_nsg_rules(resource_group, nsg_name)

    for category in ["custom", "default"]:
        rule_list = rules.get(category, [])
        print(f"\n{category.upper()} Rules ({len(rule_list)}):")
        print(f"  {'Priority':>8s}  {'Direction':10s}  {'Access':8s}  {'Protocol':10s}  "
              f"{'Src Ports':15s}  {'Dst Ports':15s}  {'Name'}")
        print(f"  {'─' * 8}  {'─' * 10}  {'─' * 8}  {'─' * 10}  {'─' * 15}  {'─' * 15}  {'─' * 30}")

        for r in sorted(rule_list, key=lambda x: x.get("properties", {}).get("priority", 9999)):
            props = r.get("properties", {})
            print(
                f"  {props.get('priority', '?'):>8}  "
                f"{props.get('direction', '?'):10s}  "
                f"{props.get('access', '?'):8s}  "
                f"{props.get('protocol', '?'):10s}  "
                f"{props.get('sourcePortRange', props.get('sourcePortRanges', '?')):15}  "
                f"{props.get('destinationPortRange', props.get('destinationPortRanges', '?')):15}  "
                f"{r.get('name', '?')}"
            )


def cmd_find_port(client: ArmClient, target_port: str):
    """Find all NSG rules that reference a specific port."""
    nsgs = client.list_nsgs()
    matches = []

    for nsg in nsgs:
        rg = nsg["id"].split("/resourceGroups/")[1].split("/")[0]
        for rule in nsg.get("properties", {}).get("securityRules", []):
            props = rule.get("properties", {})
            dst_port = str(props.get("destinationPortRange", ""))
            dst_ranges = props.get("destinationPortRanges", [])

            port_match = False
            if dst_port == target_port or dst_port == "*":
                port_match = True
            for pr in dst_ranges:
                if pr == target_port or pr == "*":
                    port_match = True
                elif "-" in pr:
                    low, high = pr.split("-")
                    if int(low) <= int(target_port) <= int(high):
                        port_match = True

            if port_match:
                matches.append({
                    "nsg": nsg["name"],
                    "resourceGroup": rg,
                    "rule": rule.get("name"),
                    "priority": props.get("priority"),
                    "direction": props.get("direction"),
                    "access": props.get("access"),
                    "protocol": props.get("protocol"),
                    "srcAddress": props.get("sourceAddressPrefix", props.get("sourceAddressPrefixes")),
                    "dstAddress": props.get("destinationAddressPrefix", props.get("destinationAddressPrefixes")),
                    "dstPort": dst_port or dst_ranges,
                })

    print(f"Rules referencing port {target_port} ({len(matches)} found):\n")
    for m in matches:
        access_marker = "ALLOW" if m["access"] == "Allow" else "DENY"
        print(
            f"  [{access_marker:5s}]  {m['nsg']:30s}  {m['rule']:30s}  "
            f"{m['direction']:10s}  pri={m['priority']}"
        )
        print(f"           src={m['srcAddress']}  dst={m['dstAddress']}")


def cmd_summary(client: ArmClient):
    """Summary of NSGs and rule counts."""
    nsgs = client.list_nsgs()
    total_custom = 0
    print(f"NSG Summary ({len(nsgs)} groups):\n")
    for nsg in sorted(nsgs, key=lambda n: n["name"]):
        rules = nsg.get("properties", {}).get("securityRules", [])
        allow_count = sum(1 for r in rules if r.get("properties", {}).get("access") == "Allow")
        deny_count = sum(1 for r in rules if r.get("properties", {}).get("access") == "Deny")
        total_custom += len(rules)
        print(f"  {nsg['name']:40s}  {len(rules):3d} rules  ({allow_count} allow, {deny_count} deny)")

    print(f"\n  Total custom rules across all NSGs: {total_custom}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 nsg_query.py <command> [args]")
        print()
        print("Commands:")
        print("  list                          List all NSGs")
        print("  rules <rg> <nsg-name>         Show rules for an NSG")
        print("  find-port <port>              Find rules affecting a port")
        print("  summary                       Rule count summary")
        sys.exit(1)

    client = ArmClient()
    command = sys.argv[1]

    if command == "list":
        cmd_list(client)
    elif command == "rules" and len(sys.argv) > 3:
        cmd_rules(client, sys.argv[2], sys.argv[3])
    elif command in ("find-port", "find_port") and len(sys.argv) > 2:
        cmd_find_port(client, sys.argv[2])
    elif command == "summary":
        cmd_summary(client)
    else:
        print(f"Unknown command or missing argument: {command}")
        sys.exit(1)
