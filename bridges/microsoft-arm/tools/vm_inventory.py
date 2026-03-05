#!/usr/bin/env python3
"""
Azure VM inventory and status tool via ARM API.

Lists VMs with power state, size, OS, and resource group. Provides
detailed views of individual VMs including network interfaces and disks.

Usage:
    python3 vm_inventory.py list                   # All VMs with power state
    python3 vm_inventory.py list --rg <rg-name>    # VMs in a resource group
    python3 vm_inventory.py detail <rg> <vm-name>  # Detailed VM info
    python3 vm_inventory.py status                  # Summary by power state
"""

import sys
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from arm_client import ArmClient


def cmd_list(client: ArmClient, resource_group: str = None):
    """List all VMs with power state."""
    statuses = client.list_vm_statuses(resource_group)
    statuses.sort(key=lambda v: (v["resourceGroup"], v["name"]))

    print(f"Azure VMs ({len(statuses)}):\n")
    print(f"  {'Name':30s}  {'Resource Group':30s}  {'Size':20s}  {'OS':8s}  {'Power State':12s}")
    print(f"  {'─' * 30}  {'─' * 30}  {'─' * 20}  {'─' * 8}  {'─' * 12}")

    for vm in statuses:
        print(
            f"  {vm['name']:30s}  {vm['resourceGroup']:30s}  "
            f"{vm.get('vmSize', '?'):20s}  {vm.get('osType', '?'):8s}  {vm['powerState']:12s}"
        )

    # Summary
    running = sum(1 for v in statuses if v["powerState"] == "running")
    deallocated = sum(1 for v in statuses if v["powerState"] == "deallocated")
    other = len(statuses) - running - deallocated
    print(f"\n  Summary: {running} running, {deallocated} deallocated, {other} other")


def cmd_detail(client: ArmClient, resource_group: str, vm_name: str):
    """Get detailed info for a single VM."""
    vm = client.get_vm(resource_group, vm_name, instance_view=True)
    print(json.dumps(vm, indent=2))


def cmd_status(client: ArmClient):
    """Power state summary across all VMs."""
    statuses = client.list_vm_statuses()

    by_state = {}
    for vm in statuses:
        state = vm["powerState"]
        by_state.setdefault(state, []).append(vm)

    print(f"VM Power State Summary ({len(statuses)} total):\n")
    for state, vms in sorted(by_state.items()):
        print(f"  {state}: {len(vms)}")
        for vm in vms:
            print(f"    {vm['name']:30s}  ({vm['resourceGroup']})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 vm_inventory.py <command> [args]")
        print()
        print("Commands:")
        print("  list [--rg <rg-name>]    List all VMs with power state")
        print("  detail <rg> <vm-name>    Detailed VM info (JSON)")
        print("  status                   Summary by power state")
        sys.exit(1)

    client = ArmClient()
    command = sys.argv[1]

    if command == "list":
        rg = None
        if "--rg" in sys.argv:
            idx = sys.argv.index("--rg")
            if idx + 1 < len(sys.argv):
                rg = sys.argv[idx + 1]
        cmd_list(client, rg)
    elif command == "detail" and len(sys.argv) > 3:
        cmd_detail(client, sys.argv[2], sys.argv[3])
    elif command == "status":
        cmd_status(client)
    else:
        print(f"Unknown command or missing argument: {command}")
        sys.exit(1)
