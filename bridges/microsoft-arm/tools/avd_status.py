#!/usr/bin/env python3
"""
Azure Virtual Desktop (AVD) status tool via ARM API.

Lists host pools, session hosts, active user sessions, and application
groups for AVD infrastructure monitoring.

Usage:
    python3 avd_status.py pools                         # List host pools
    python3 avd_status.py hosts <rg> <pool-name>        # List session hosts
    python3 avd_status.py sessions <rg> <pool> <host>   # Active user sessions
    python3 avd_status.py apps                           # Application groups
    python3 avd_status.py overview                       # Full AVD overview
"""

import sys
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from arm_client import ArmClient


def cmd_pools(client: ArmClient):
    """List all AVD host pools."""
    pools = client.list_host_pools()
    print(f"AVD Host Pools ({len(pools)}):\n")

    if not pools:
        print("  No host pools found.")
        return

    print(f"  {'Name':30s}  {'Type':15s}  {'Load Balancer':15s}  {'Max Sessions':>12s}  {'Location':15s}")
    print(f"  {'─' * 30}  {'─' * 15}  {'─' * 15}  {'─' * 12}  {'─' * 15}")

    for p in pools:
        props = p.get("properties", {})
        print(
            f"  {p['name']:30s}  "
            f"{props.get('hostPoolType', '?'):15s}  "
            f"{props.get('loadBalancerType', '?'):15s}  "
            f"{props.get('maxSessionLimit', '?'):>12}  "
            f"{p.get('location', '?'):15s}"
        )


def cmd_hosts(client: ArmClient, resource_group: str, pool_name: str):
    """List session hosts in a host pool."""
    hosts = client.list_session_hosts(resource_group, pool_name)
    print(f"Session Hosts in '{pool_name}' ({len(hosts)}):\n")

    if not hosts:
        print("  No session hosts found.")
        return

    print(f"  {'Name':40s}  {'Status':15s}  {'Sessions':>10s}  {'Allow New':>10s}  {'Drain Mode':>10s}")
    print(f"  {'─' * 40}  {'─' * 15}  {'─' * 10}  {'─' * 10}  {'─' * 10}")

    for h in hosts:
        props = h.get("properties", {})
        name = h.get("name", "?").split("/")[-1]
        print(
            f"  {name:40s}  "
            f"{props.get('status', '?'):15s}  "
            f"{props.get('sessions', 0):>10}  "
            f"{'yes' if props.get('allowNewSession') else 'no':>10s}  "
            f"{'ON' if props.get('updateState') == 'drainMode' else 'off':>10s}"
        )


def cmd_sessions(client: ArmClient, resource_group: str, pool_name: str, session_host: str):
    """List active user sessions on a session host."""
    sessions = client.list_user_sessions(resource_group, pool_name, session_host)
    print(f"User Sessions on '{session_host}' ({len(sessions)}):\n")

    if not sessions:
        print("  No active sessions.")
        return

    for s in sessions:
        props = s.get("properties", {})
        session_id = s.get("name", "?").split("/")[-1]
        print(f"  Session {session_id}:")
        print(f"    User:        {props.get('userPrincipalName', '?')}")
        print(f"    State:       {props.get('sessionState', '?')}")
        print(f"    App Type:    {props.get('applicationType', '?')}")
        print(f"    Created:     {props.get('createTime', '?')}")


def cmd_apps(client: ArmClient):
    """List AVD application groups."""
    groups = client.list_app_groups()
    print(f"AVD Application Groups ({len(groups)}):\n")

    if not groups:
        print("  No application groups found.")
        return

    for g in groups:
        props = g.get("properties", {})
        print(f"  {g['name']}")
        print(f"    Type:      {props.get('applicationGroupType', '?')}")
        print(f"    Host Pool: {props.get('hostPoolArmPath', '?').split('/')[-1]}")
        print(f"    Location:  {g.get('location', '?')}")
        print()


def cmd_overview(client: ArmClient):
    """Full AVD infrastructure overview."""
    pools = client.list_host_pools()
    app_groups = client.list_app_groups()

    print(f"=== AVD Infrastructure Overview ===\n")
    print(f"Host Pools: {len(pools)}")
    print(f"Application Groups: {len(app_groups)}")

    for p in pools:
        props = p.get("properties", {})
        pool_name = p["name"]
        rg = p["id"].split("/resourceGroups/")[1].split("/")[0]

        print(f"\n── {pool_name} ({rg}) ──")
        print(f"  Type: {props.get('hostPoolType', '?')}, LB: {props.get('loadBalancerType', '?')}, Max Sessions: {props.get('maxSessionLimit', '?')}")

        hosts = client.list_session_hosts(rg, pool_name)
        total_sessions = 0
        for h in hosts:
            h_props = h.get("properties", {})
            h_name = h.get("name", "?").split("/")[-1]
            sessions = h_props.get("sessions", 0)
            total_sessions += sessions
            status = h_props.get("status", "?")
            print(f"    {h_name:35s}  status={status:12s}  sessions={sessions}")

        print(f"  Total sessions: {total_sessions}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 avd_status.py <command> [args]")
        print()
        print("Commands:")
        print("  pools                           List host pools")
        print("  hosts <rg> <pool-name>          List session hosts")
        print("  sessions <rg> <pool> <host>     Active user sessions")
        print("  apps                            Application groups")
        print("  overview                        Full AVD overview")
        sys.exit(1)

    client = ArmClient()
    command = sys.argv[1]

    if command == "pools":
        cmd_pools(client)
    elif command == "hosts" and len(sys.argv) > 3:
        cmd_hosts(client, sys.argv[2], sys.argv[3])
    elif command == "sessions" and len(sys.argv) > 4:
        cmd_sessions(client, sys.argv[2], sys.argv[3], sys.argv[4])
    elif command == "apps":
        cmd_apps(client)
    elif command == "overview":
        cmd_overview(client)
    else:
        print(f"Unknown command or missing argument: {command}")
        sys.exit(1)
