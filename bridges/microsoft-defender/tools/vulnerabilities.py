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
MDE Threat and Vulnerability Management (TVM).

Provides CVE exposure analysis, software inventory, and security
recommendations from the Defender for Endpoint vulnerability management API.

Usage:
    python3 vulnerabilities.py dashboard                 # TVM summary
    python3 vulnerabilities.py cves                      # CVE exposure list
    python3 vulnerabilities.py cves --severity critical  # Filter by severity
    python3 vulnerabilities.py cve <cve-id>              # CVE detail + affected machines
    python3 vulnerabilities.py software                  # Software inventory
    python3 vulnerabilities.py software <name>           # Search software
    python3 vulnerabilities.py recommendations           # Security recommendations
    python3 vulnerabilities.py machine <machine-id>      # Vulns for a machine
"""

import sys
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from defender_client import DefenderClient


def cmd_dashboard(client: DefenderClient):
    vulns = client.mde_get_all("/api/vulnerabilities")
    recs = client.mde_get_all("/api/recommendations")

    by_severity = {}
    exploitable = 0
    for v in vulns:
        sev = v.get("severity", "unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        if v.get("exploitVerified") or v.get("publicExploit"):
            exploitable += 1

    print(f"Threat & Vulnerability Management Dashboard\n")
    print(f"  Total CVEs exposed:      {len(vulns)}")
    print(f"  Publicly exploitable:    {exploitable}")
    print(f"  Security recommendations: {len(recs)}\n")

    print("  CVEs by Severity:")
    for sev in ["Critical", "High", "Medium", "Low"]:
        count = by_severity.get(sev, 0)
        if count:
            print(f"    {sev:12s}  {count}")

    active_recs = [r for r in recs if r.get("status") != "Completed"]
    if active_recs:
        print(f"\n  Top Recommendations ({len(active_recs)} active):")
        for r in active_recs[:10]:
            print(f"    [{r.get('severityScore', '?'):>5}] {r.get('recommendationName', '?')[:60]}")
            print(f"           Exposed: {r.get('exposedMachinesCount', 0)} machines  |  Category: {r.get('recommendationCategory', '?')}")


def cmd_cves(client: DefenderClient, severity: str = None):
    vulns = client.mde_get_all("/api/vulnerabilities")

    if severity:
        vulns = [v for v in vulns if v.get("severity", "").lower() == severity.lower()]

    vulns.sort(key=lambda v: v.get("cvssV3", 0), reverse=True)

    if not vulns:
        print("No CVEs found.")
        return

    print(f"CVE Exposure: {len(vulns)} vulnerabilities\n")
    print(f"  {'CVE ID':20s}  {'Severity':10s}  {'CVSS':>5s}  {'Exploit':>8s}  {'Machines':>8s}  {'Description'}")
    print(f"  {'─'*20}  {'─'*10}  {'─'*5}  {'─'*8}  {'─'*8}  {'─'*40}")

    for v in vulns[:100]:
        cve_id = (v.get("id") or "?")[:20]
        sev = (v.get("severity") or "?")[:10]
        cvss = str(v.get("cvssV3") or "?")[:5]
        exploit = "Yes" if v.get("publicExploit") or v.get("exploitVerified") else "No"
        machines = str(v.get("exposedMachines") or 0)
        desc = (v.get("description") or "?")[:40]
        print(f"  {cve_id:20s}  {sev:10s}  {cvss:>5s}  {exploit:>8s}  {machines:>8s}  {desc}")

    if len(vulns) > 100:
        print(f"\n  ... and {len(vulns) - 100} more (truncated)")


def cmd_cve_detail(client: DefenderClient, cve_id: str):
    resp = client.mde_get(f"/api/vulnerabilities/{cve_id}")
    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} {resp.text}")
        return

    v = resp.json()
    print(f"CVE: {v.get('id', '?')}")
    print(f"  Severity:     {v.get('severity', '?')}")
    print(f"  CVSS v3:      {v.get('cvssV3', '?')}")
    print(f"  Description:  {v.get('description', '?')}")
    print(f"  Published:    {v.get('publishedOn', '?')}")
    print(f"  Updated:      {v.get('updatedOn', '?')}")
    print(f"  Exploit:      Public={v.get('publicExploit', False)}, Verified={v.get('exploitVerified', False)}")
    print(f"  Exposed:      {v.get('exposedMachines', 0)} machines")

    machines_resp = client.mde_get(f"/api/vulnerabilities/{cve_id}/machineReferences")
    if machines_resp.status_code == 200:
        machines = machines_resp.json().get("value", [])
        if machines:
            print(f"\n  Affected Machines ({len(machines)}):")
            for m in machines[:25]:
                print(f"    {m.get('computerDnsName', '?'):30s}  OS: {m.get('osPlatform', '?')}")


def cmd_software(client: DefenderClient, name: str = None):
    software = client.mde_get_all("/api/Software")

    if name:
        software = [
            s for s in software
            if name.lower() in s.get("name", "").lower()
            or name.lower() in s.get("vendor", "").lower()
        ]

    software.sort(key=lambda s: s.get("exposedMachines", 0), reverse=True)

    if not software:
        print("No software found.")
        return

    print(f"Software Inventory: {len(software)} products\n")
    print(f"  {'Vendor':20s}  {'Product':30s}  {'Machines':>8s}  {'Vulns':>6s}  {'Exposed':>8s}")
    print(f"  {'─'*20}  {'─'*30}  {'─'*8}  {'─'*6}  {'─'*8}")

    for s in software[:50]:
        vendor = (s.get("vendor") or "?")[:20]
        product = (s.get("name") or "?")[:30]
        machines = str(s.get("installedMachines") or 0)
        vulns = str(s.get("vulnerabilities") or 0)
        exposed = str(s.get("exposedMachines") or 0)
        print(f"  {vendor:20s}  {product:30s}  {machines:>8s}  {vulns:>6s}  {exposed:>8s}")


def cmd_recommendations(client: DefenderClient):
    recs = client.mde_get_all("/api/recommendations")
    recs.sort(key=lambda r: r.get("severityScore", 0), reverse=True)

    if not recs:
        print("No recommendations.")
        return

    active = [r for r in recs if r.get("status") != "Completed"]
    print(f"Security Recommendations: {len(active)} active ({len(recs)} total)\n")

    for r in active[:30]:
        print(f"  [{r.get('severityScore', '?'):>5}] {r.get('recommendationName', '?')}")
        print(f"    Category: {r.get('recommendationCategory', '?')}  |  "
              f"Exposed: {r.get('exposedMachinesCount', 0)} machines  |  "
              f"Related CVEs: {r.get('activeAlert', False)}")
        remediation = r.get("remediationType", "")
        if remediation:
            print(f"    Remediation: {remediation}")
        print()


def cmd_machine_vulns(client: DefenderClient, machine_id: str):
    resp = client.mde_get(f"/api/machines/{machine_id}/vulnerabilities")
    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} {resp.text}")
        return

    vulns = resp.json().get("value", [])
    vulns.sort(key=lambda v: v.get("cvssV3", 0), reverse=True)

    if not vulns:
        print("No vulnerabilities for this machine.")
        return

    print(f"Vulnerabilities for machine {machine_id}: {len(vulns)}\n")
    print(f"  {'CVE ID':20s}  {'Severity':10s}  {'CVSS':>5s}  {'Exploit':>8s}")
    print(f"  {'─'*20}  {'─'*10}  {'─'*5}  {'─'*8}")

    for v in vulns[:50]:
        cve_id = v.get("id", "?")[:20]
        sev = v.get("severity", "?")[:10]
        cvss = str(v.get("cvssV3", "?"))[:5]
        exploit = "Yes" if v.get("publicExploit") or v.get("exploitVerified") else "No"
        print(f"  {cve_id:20s}  {sev:10s}  {cvss:>5s}  {exploit:>8s}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = DefenderClient()
    cmd = sys.argv[1]

    severity = None
    args = sys.argv[2:]
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] == "--severity" and i + 1 < len(args):
            severity = args[i + 1]
            i += 2
        else:
            filtered_args.append(args[i])
            i += 1

    if cmd == "dashboard":
        cmd_dashboard(client)
    elif cmd == "cves":
        cmd_cves(client, severity=severity)
    elif cmd == "cve" and filtered_args:
        cmd_cve_detail(client, filtered_args[0])
    elif cmd == "software":
        cmd_software(client, filtered_args[0] if filtered_args else None)
    elif cmd == "recommendations":
        cmd_recommendations(client)
    elif cmd == "machine" and filtered_args:
        cmd_machine_vulns(client, filtered_args[0])
    else:
        print(__doc__.strip())
        sys.exit(1)
