#!/usr/bin/env python3
# Copyright 2026 The Tendril Project Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
MDE machine inventory and response actions.

Provides endpoint inventory, detailed machine info, and response actions
(isolate, scan, restrict, collect) via the MDE API.

Usage:
    python3 machines.py list                           # All machines
    python3 machines.py list --os windows              # Filter by OS
    python3 machines.py list --health atRisk           # Filter by health
    python3 machines.py detail <machine-id-or-name>    # Machine detail
    python3 machines.py search <query>                 # Search by name
    python3 machines.py isolate <machine-id> <comment> # Isolate machine
    python3 machines.py release <machine-id> <comment> # Release isolation
    python3 machines.py scan <machine-id> [quick|full] # Run AV scan
    python3 machines.py restrict <machine-id> <comment>        # Restrict code exec
    python3 machines.py unrestrict <machine-id> <comment>      # Remove restriction
    python3 machines.py collect <machine-id> <comment>         # Investigation pkg
    python3 machines.py actions <machine-id>                   # Recent actions
    python3 machines.py overview                               # Fleet summary
"""

import sys
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from defender_client import DefenderClient


def cmd_list(client: DefenderClient, os_filter: str = None, health: str = None):
    params = {}
    filters = []

    if os_filter:
        filters.append(f"osPlatform eq '{os_filter}'")
    if health:
        filters.append(f"healthStatus eq '{health}'")
    if filters:
        params["$filter"] = " and ".join(filters)

    machines = client.mde_get_all("/api/machines", params=params)

    if not machines:
        print("No machines found.")
        return

    print(f"Machines: {len(machines)}\n")
    print(f"  {'Name':30s}  {'OS':15s}  {'Health':12s}  {'Risk':10s}  {'Exposure':10s}  {'Last Seen'}")
    print(f"  {'─'*30}  {'─'*15}  {'─'*12}  {'─'*10}  {'─'*10}  {'─'*20}")

    machines.sort(key=lambda m: (m.get("computerDnsName") or ""))
    for m in machines:
        name = (m.get("computerDnsName") or "?")[:30]
        os_name = (m.get("osPlatform") or "?")[:15]
        hs = (m.get("healthStatus") or "?")[:12]
        risk = (m.get("riskScore") or "?")[:10]
        exposure = (m.get("exposureLevel") or "?")[:10]
        last_seen = (m.get("lastSeen") or "?")[:20]
        print(f"  {name:30s}  {os_name:15s}  {hs:12s}  {risk:10s}  {exposure:10s}  {last_seen}")


def cmd_detail(client: DefenderClient, identifier: str):
    if len(identifier) > 20:
        resp = client.mde_get(f"/api/machines/{identifier}")
    else:
        machines = client.mde_get_all(
            "/api/machines",
            params={"$filter": f"contains(computerDnsName,'{identifier}')"},
        )
        if not machines:
            print(f"No machine found matching '{identifier}'")
            return
        if len(machines) > 1:
            print(f"Multiple matches for '{identifier}':")
            for m in machines:
                print(f"  {m.get('id', '?')}  {m.get('computerDnsName', '?')}")
            return
        resp = client.mde_get(f"/api/machines/{machines[0]['id']}")

    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} {resp.text}")
        return

    m = resp.json()
    print(f"Machine: {m.get('computerDnsName', '?')}")
    print(f"  ID:              {m.get('id', '?')}")
    print(f"  OS:              {m.get('osPlatform', '?')} {m.get('osVersion', '')}")
    print(f"  Health:          {m.get('healthStatus', '?')}")
    print(f"  Risk Score:      {m.get('riskScore', '?')}")
    print(f"  Exposure Level:  {m.get('exposureLevel', '?')}")
    print(f"  Onboarding:      {m.get('onboardingStatus', '?')}")
    print(f"  First Seen:      {m.get('firstSeen', '?')}")
    print(f"  Last Seen:       {m.get('lastSeen', '?')}")
    print(f"  Last IP:         {m.get('lastIpAddress', '?')}")
    print(f"  Last External:   {m.get('lastExternalIpAddress', '?')}")
    print(f"  AAD Device ID:   {m.get('aadDeviceId', 'N/A')}")
    print(f"  Managed By:      {m.get('managedBy', 'N/A')}")

    tags = m.get("machineTags", [])
    if tags:
        print(f"  Tags:            {', '.join(tags)}")

    ips = m.get("ipAddresses", [])
    if ips:
        print(f"\n  IP Addresses:")
        for ip in ips[:10]:
            print(f"    {ip.get('ipAddress', '?'):20s}  {ip.get('type', '?'):8s}  MAC: {ip.get('macAddress', 'N/A')}")


def cmd_search(client: DefenderClient, query: str):
    machines = client.mde_get_all(
        "/api/machines",
        params={"$filter": f"contains(computerDnsName,'{query}')"},
    )
    if not machines:
        print(f"No machines matching '{query}'")
        return

    print(f"Machines matching '{query}': {len(machines)}\n")
    for m in machines:
        print(f"  {m.get('id', '?')}")
        print(f"    Name:   {m.get('computerDnsName', '?')}")
        print(f"    OS:     {m.get('osPlatform', '?')} {m.get('osVersion', '')}")
        print(f"    Health: {m.get('healthStatus', '?')}  Risk: {m.get('riskScore', '?')}")
        print()


def _machine_action(client: DefenderClient, machine_id: str, action: str, body: dict):
    resp = client.mde_post(f"/api/machines/{machine_id}/{action}", body)
    if resp.status_code in (200, 201):
        data = resp.json()
        print(f"Action '{action}' initiated on machine {machine_id}")
        print(f"  Action ID: {data.get('id', '?')}")
        print(f"  Status:    {data.get('status', '?')}")
        print(f"  Type:      {data.get('type', '?')}")
    else:
        print(f"ERROR: {resp.status_code} {resp.text}")


def cmd_isolate(client: DefenderClient, machine_id: str, comment: str):
    _machine_action(client, machine_id, "isolate", {
        "Comment": comment,
        "IsolationType": "Full",
    })


def cmd_release(client: DefenderClient, machine_id: str, comment: str):
    _machine_action(client, machine_id, "unisolate", {"Comment": comment})


def cmd_scan(client: DefenderClient, machine_id: str, scan_type: str = "Quick"):
    _machine_action(client, machine_id, "runAntiVirusScan", {
        "Comment": f"Initiated via Tendril bridge",
        "ScanType": scan_type.capitalize(),
    })


def cmd_restrict(client: DefenderClient, machine_id: str, comment: str):
    _machine_action(client, machine_id, "restrictCodeExecution", {"Comment": comment})


def cmd_unrestrict(client: DefenderClient, machine_id: str, comment: str):
    _machine_action(client, machine_id, "unrestrictCodeExecution", {"Comment": comment})


def cmd_collect(client: DefenderClient, machine_id: str, comment: str):
    _machine_action(client, machine_id, "collectInvestigationPackage", {"Comment": comment})


def cmd_actions(client: DefenderClient, machine_id: str):
    resp = client.mde_get(f"/api/machines/{machine_id}/machineactions")
    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} {resp.text}")
        return

    actions = resp.json().get("value", [])
    if not actions:
        print("No recent actions.")
        return

    print(f"Recent actions for machine {machine_id}: {len(actions)}\n")
    for a in actions[:20]:
        print(f"  [{a.get('status', '?'):12s}] {a.get('type', '?'):30s}  {a.get('creationDateTimeUtc', '?')[:19]}")
        if a.get("requestorComment"):
            print(f"    Comment: {a['requestorComment']}")


def cmd_overview(client: DefenderClient):
    machines = client.mde_get_all("/api/machines")

    by_os = {}
    by_health = {}
    by_risk = {}
    by_exposure = {}

    for m in machines:
        os_name = m.get("osPlatform") or "Unknown"
        by_os[os_name] = by_os.get(os_name, 0) + 1

        hs = m.get("healthStatus") or "Unknown"
        by_health[hs] = by_health.get(hs, 0) + 1

        risk = m.get("riskScore") or "Unknown"
        by_risk[risk] = by_risk.get(risk, 0) + 1

        exp = m.get("exposureLevel") or "Unknown"
        by_exposure[exp] = by_exposure.get(exp, 0) + 1

    print(f"MDE Fleet Overview: {len(machines)} endpoints\n")

    print("  By OS:")
    for os_name, count in sorted(by_os.items(), key=lambda x: -x[1]):
        print(f"    {os_name:20s}  {count}")

    print("\n  By Health Status:")
    for hs, count in sorted(by_health.items()):
        print(f"    {hs:20s}  {count}")

    print("\n  By Risk Score:")
    for risk, count in sorted(by_risk.items()):
        print(f"    {risk:20s}  {count}")

    print("\n  By Exposure Level:")
    for exp, count in sorted(by_exposure.items()):
        print(f"    {exp:20s}  {count}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = DefenderClient()
    cmd = sys.argv[1]

    os_filter = None
    health = None
    args = sys.argv[2:]
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] == "--os" and i + 1 < len(args):
            os_filter = args[i + 1]
            i += 2
        elif args[i] == "--health" and i + 1 < len(args):
            health = args[i + 1]
            i += 2
        else:
            filtered_args.append(args[i])
            i += 1

    if cmd == "list":
        cmd_list(client, os_filter=os_filter, health=health)
    elif cmd == "detail" and filtered_args:
        cmd_detail(client, filtered_args[0])
    elif cmd == "search" and filtered_args:
        cmd_search(client, filtered_args[0])
    elif cmd == "isolate" and len(filtered_args) >= 2:
        cmd_isolate(client, filtered_args[0], " ".join(filtered_args[1:]))
    elif cmd == "release" and len(filtered_args) >= 2:
        cmd_release(client, filtered_args[0], " ".join(filtered_args[1:]))
    elif cmd == "scan" and filtered_args:
        scan_type = filtered_args[1] if len(filtered_args) > 1 else "Quick"
        cmd_scan(client, filtered_args[0], scan_type)
    elif cmd == "restrict" and len(filtered_args) >= 2:
        cmd_restrict(client, filtered_args[0], " ".join(filtered_args[1:]))
    elif cmd == "unrestrict" and len(filtered_args) >= 2:
        cmd_unrestrict(client, filtered_args[0], " ".join(filtered_args[1:]))
    elif cmd == "collect" and len(filtered_args) >= 2:
        cmd_collect(client, filtered_args[0], " ".join(filtered_args[1:]))
    elif cmd == "actions" and filtered_args:
        cmd_actions(client, filtered_args[0])
    elif cmd == "overview":
        cmd_overview(client)
    else:
        print(__doc__.strip())
        sys.exit(1)
