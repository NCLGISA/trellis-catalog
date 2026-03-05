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
Unified incident management via the Defender XDR API.

Lists, inspects, and manages security incidents from all Defender sources
(MDE, MDI, MDCA, Sentinel analytics rules) through the unified portal API.

Usage:
    python3 incidents.py list                          # Active incidents
    python3 incidents.py list --severity high          # Filter by severity
    python3 incidents.py list --status active           # Filter by status
    python3 incidents.py detail <incident-id>          # Full incident detail
    python3 incidents.py alerts <incident-id>          # Alerts in an incident
    python3 incidents.py assign <incident-id> <email>  # Assign to analyst
    python3 incidents.py resolve <incident-id> <classification>
    python3 incidents.py dashboard                     # Summary counts
"""

import sys
import json
from datetime import datetime, timedelta, timezone

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from defender_client import DefenderClient

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "informational": 3}


def cmd_list(client: DefenderClient, severity: str = None, status: str = None):
    params = {"$top": 100}
    filters = []

    if status:
        filters.append(f"status eq '{status}'")
    else:
        filters.append("status ne 'resolved'")

    if severity:
        filters.append(f"severity eq '{severity}'")

    if filters:
        params["$filter"] = " and ".join(filters)

    params["$orderby"] = "lastUpdateDateTime desc"

    incidents = client.security_get_all("/api/incidents", params=params)

    if not incidents:
        print("No incidents found matching criteria.")
        return

    print(f"Incidents: {len(incidents)}\n")
    print(f"  {'ID':>10s}  {'Severity':12s}  {'Status':12s}  {'Alerts':>6s}  {'Title'}")
    print(f"  {'─'*10}  {'─'*12}  {'─'*12}  {'─'*6}  {'─'*50}")

    for inc in incidents:
        inc_id = str(inc.get("incidentId", ""))
        sev = inc.get("severity", "?")
        st = inc.get("status", "?")
        alert_count = len(inc.get("alerts", []))
        title = inc.get("incidentName", inc.get("title", "?"))[:50]
        print(f"  {inc_id:>10s}  {sev:12s}  {st:12s}  {alert_count:6d}  {title}")


def cmd_detail(client: DefenderClient, incident_id: str):
    resp = client.security_get(f"/api/incidents/{incident_id}")
    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} {resp.text}")
        return

    inc = resp.json()
    print(f"Incident #{inc.get('incidentId')}")
    print(f"  Title:       {inc.get('incidentName', inc.get('title', '?'))}")
    print(f"  Severity:    {inc.get('severity')}")
    print(f"  Status:      {inc.get('status')}")
    print(f"  Assigned To: {inc.get('assignedTo', 'Unassigned')}")
    print(f"  Created:     {inc.get('createdDateTime', '?')}")
    print(f"  Updated:     {inc.get('lastUpdateDateTime', '?')}")
    print(f"  Classification: {inc.get('classification', 'None')}")
    print(f"  Determination:  {inc.get('determination', 'None')}")

    tags = inc.get("tags", [])
    if tags:
        print(f"  Tags:        {', '.join(tags)}")

    alerts = inc.get("alerts", [])
    if alerts:
        print(f"\n  Alerts ({len(alerts)}):")
        for a in alerts:
            print(f"    [{a.get('severity', '?'):12s}] {a.get('title', '?')}")
            print(f"      Source: {a.get('serviceSource', '?')}  |  Category: {a.get('category', '?')}")

    devices = inc.get("devices", [])
    if devices:
        print(f"\n  Devices ({len(devices)}):")
        for d in devices:
            print(f"    {d.get('deviceDnsName', '?')} (OS: {d.get('osPlatform', '?')}, Risk: {d.get('riskScore', '?')})")


def cmd_alerts(client: DefenderClient, incident_id: str):
    resp = client.security_get(f"/api/incidents/{incident_id}")
    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} {resp.text}")
        return

    alerts = resp.json().get("alerts", [])
    if not alerts:
        print("No alerts for this incident.")
        return

    print(f"Alerts for incident #{incident_id}: {len(alerts)}\n")
    for a in alerts:
        print(f"  Alert: {a.get('alertId', '?')}")
        print(f"    Title:      {a.get('title', '?')}")
        print(f"    Severity:   {a.get('severity', '?')}")
        print(f"    Status:     {a.get('status', '?')}")
        print(f"    Source:     {a.get('serviceSource', '?')}")
        print(f"    Category:   {a.get('category', '?')}")
        print(f"    Created:    {a.get('createdDateTime', '?')}")
        devices = a.get("devices", [])
        if devices:
            names = [d.get("deviceDnsName", "?") for d in devices]
            print(f"    Devices:    {', '.join(names)}")
        print()


def cmd_assign(client: DefenderClient, incident_id: str, email: str):
    resp = client.security_patch(
        f"/api/incidents/{incident_id}",
        {"assignedTo": email, "status": "active"},
    )
    if resp.status_code == 200:
        print(f"Incident #{incident_id} assigned to {email}")
    else:
        print(f"ERROR: {resp.status_code} {resp.text}")


def cmd_resolve(client: DefenderClient, incident_id: str, classification: str):
    valid = ["truePositive", "falsePositive", "informationalExpectedActivity"]
    if classification not in valid:
        print(f"Classification must be one of: {', '.join(valid)}")
        sys.exit(1)

    resp = client.security_patch(
        f"/api/incidents/{incident_id}",
        {"status": "resolved", "classification": classification},
    )
    if resp.status_code == 200:
        print(f"Incident #{incident_id} resolved as {classification}")
    else:
        print(f"ERROR: {resp.status_code} {resp.text}")


def cmd_dashboard(client: DefenderClient):
    incidents = client.security_get_all(
        "/api/incidents",
        params={"$filter": "status ne 'resolved'", "$top": 200},
    )

    by_severity = {}
    by_status = {}
    by_source = {}

    for inc in incidents:
        sev = inc.get("severity", "unknown")
        st = inc.get("status", "unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_status[st] = by_status.get(st, 0) + 1

        for alert in inc.get("alerts", []):
            src = alert.get("serviceSource", "unknown")
            by_source[src] = by_source.get(src, 0) + 1

    print(f"Defender XDR Incident Dashboard\n")
    print(f"  Open Incidents: {len(incidents)}\n")

    print("  By Severity:")
    for sev in sorted(by_severity, key=lambda s: SEVERITY_ORDER.get(s, 99)):
        print(f"    {sev:20s}  {by_severity[sev]}")

    print("\n  By Status:")
    for st, count in sorted(by_status.items()):
        print(f"    {st:20s}  {count}")

    if by_source:
        print("\n  Alert Sources:")
        for src, count in sorted(by_source.items(), key=lambda x: -x[1]):
            print(f"    {src:30s}  {count}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = DefenderClient()
    cmd = sys.argv[1]

    severity = None
    status = None
    args = sys.argv[2:]
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] == "--severity" and i + 1 < len(args):
            severity = args[i + 1]
            i += 2
        elif args[i] == "--status" and i + 1 < len(args):
            status = args[i + 1]
            i += 2
        else:
            filtered_args.append(args[i])
            i += 1

    if cmd == "list":
        cmd_list(client, severity=severity, status=status)
    elif cmd == "detail" and filtered_args:
        cmd_detail(client, filtered_args[0])
    elif cmd == "alerts" and filtered_args:
        cmd_alerts(client, filtered_args[0])
    elif cmd == "assign" and len(filtered_args) >= 2:
        cmd_assign(client, filtered_args[0], filtered_args[1])
    elif cmd == "resolve" and len(filtered_args) >= 2:
        cmd_resolve(client, filtered_args[0], filtered_args[1])
    elif cmd == "dashboard":
        cmd_dashboard(client)
    else:
        print(__doc__.strip())
        sys.exit(1)
