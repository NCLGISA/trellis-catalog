#!/usr/bin/env python3
"""
Advanced hunting via the unified Defender XDR API.

Executes KQL queries across both MDE endpoint tables (DeviceProcessEvents,
DeviceNetworkEvents, DeviceFileEvents, etc.) and Sentinel workspace tables
(SecurityEvent, Syslog, SigninLogs, custom tables) in a single query.

Usage:
    python3 hunting.py query "DeviceProcessEvents | take 10"
    python3 hunting.py query "SecurityEvent | where EventID == 4625 | take 20"
    python3 hunting.py tables                       # List available schema tables
    python3 hunting.py file <path-to-kql-file>      # Run KQL from a file
    python3 hunting.py presets                       # Show built-in query presets
    python3 hunting.py preset <name>                 # Run a preset query
"""

import sys
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from defender_client import DefenderClient

PRESETS = {
    "failed-logons": {
        "description": "Failed interactive sign-ins in the last 24h",
        "query": (
            "IdentityLogonEvents\n"
            "| where Timestamp > ago(24h)\n"
            "| where ActionType == 'LogonFailed'\n"
            "| where LogonType == 'Interactive'\n"
            "| summarize FailCount=count() by AccountUpn, DeviceName, FailureReason\n"
            "| sort by FailCount desc\n"
            "| take 50"
        ),
    },
    "suspicious-processes": {
        "description": "Unusual process execution from writable paths in the last 24h",
        "query": (
            "DeviceProcessEvents\n"
            "| where Timestamp > ago(24h)\n"
            "| where FolderPath matches regex @'(?i)(\\\\temp\\\\|\\\\appdata\\\\|\\\\downloads\\\\)'\n"
            "| where FileName !in~ ('chrome.exe','msedge.exe','firefox.exe','code.exe')\n"
            "| summarize Count=count() by FileName, FolderPath, DeviceName, AccountName\n"
            "| sort by Count desc\n"
            "| take 50"
        ),
    },
    "lateral-movement": {
        "description": "Remote logons (type 10 / RDP) in the last 7d",
        "query": (
            "IdentityLogonEvents\n"
            "| where Timestamp > ago(7d)\n"
            "| where LogonType == 'RemoteInteractive'\n"
            "| where ActionType == 'LogonSuccess'\n"
            "| summarize Count=count() by AccountUpn, DeviceName, DestinationDeviceName\n"
            "| sort by Count desc\n"
            "| take 50"
        ),
    },
    "new-local-admins": {
        "description": "Accounts added to local admin groups in the last 7d",
        "query": (
            "DeviceEvents\n"
            "| where Timestamp > ago(7d)\n"
            "| where ActionType == 'UserAccountAddedToLocalGroup'\n"
            "| extend GroupName = tostring(parse_json(AdditionalFields).GroupName)\n"
            "| where GroupName contains 'admin'\n"
            "| project Timestamp, DeviceName, AccountName, GroupName\n"
            "| sort by Timestamp desc"
        ),
    },
    "powershell-encoded": {
        "description": "Encoded PowerShell commands in the last 7d",
        "query": (
            "DeviceProcessEvents\n"
            "| where Timestamp > ago(7d)\n"
            "| where FileName =~ 'powershell.exe' or FileName =~ 'pwsh.exe'\n"
            "| where ProcessCommandLine contains '-enc' or ProcessCommandLine contains '-EncodedCommand'\n"
            "| project Timestamp, DeviceName, AccountName, ProcessCommandLine\n"
            "| sort by Timestamp desc\n"
            "| take 50"
        ),
    },
    "threat-indicators-hits": {
        "description": "Machines that matched threat indicators in the last 7d",
        "query": (
            "DeviceEvents\n"
            "| where Timestamp > ago(7d)\n"
            "| where ActionType == 'ConnectionToCustomIndicator' "
            "or ActionType == 'ProcessBlockedByCustomIndicator'\n"
            "| summarize Count=count() by DeviceName, ActionType, RemoteUrl, RemoteIP\n"
            "| sort by Count desc"
        ),
    },
    "tendril-logs": {
        "description": "Recent Tendril logs from the workspace (custom table)",
        "query": (
            "TendrilLogs_CL\n"
            "| where TimeGenerated > ago(24h)\n"
            "| sort by TimeGenerated desc\n"
            "| take 100"
        ),
    },
}


def format_results(data: dict) -> str:
    if "error" in data:
        return f"ERROR: {data.get('message', data)}"

    results = data.get("Results", [])
    schema = data.get("Schema", [])

    if not results:
        return "No results."

    if schema:
        cols = [s["Name"] for s in schema]
    else:
        cols = list(results[0].keys()) if results else []

    lines = [f"Results: {len(results)} rows\n"]

    col_widths = {c: len(c) for c in cols}
    for row in results[:200]:
        for c in cols:
            val = str(row.get(c, ""))
            col_widths[c] = min(max(col_widths[c], len(val)), 60)

    header = "  ".join(c.ljust(col_widths[c]) for c in cols)
    lines.append(header)
    lines.append("  ".join("─" * col_widths[c] for c in cols))

    for row in results[:200]:
        line = "  ".join(
            str(row.get(c, "")).ljust(col_widths[c])[:col_widths[c]]
            for c in cols
        )
        lines.append(line)

    if len(results) > 200:
        lines.append(f"\n... and {len(results) - 200} more rows (truncated)")

    return "\n".join(lines)


def cmd_query(client: DefenderClient, kql: str):
    print(f"Executing advanced hunting query...\n")
    result = client.advanced_hunt(kql)
    print(format_results(result))


def cmd_tables(client: DefenderClient):
    kql = (
        "search *\n"
        "| distinct $table\n"
        "| sort by $table asc"
    )
    print("Querying available schema tables...\n")
    result = client.advanced_hunt(kql)
    if "error" in result:
        print(f"ERROR: {result.get('message', result)}")
        return
    tables = [r.get("$table", "") for r in result.get("Results", [])]
    for t in tables:
        print(f"  {t}")
    print(f"\nTotal: {len(tables)} tables")


def cmd_presets():
    print("Available hunting presets:\n")
    for name, info in PRESETS.items():
        print(f"  {name:30s}  {info['description']}")


def cmd_preset(client: DefenderClient, name: str):
    if name not in PRESETS:
        print(f"Unknown preset: {name}")
        print(f"Available: {', '.join(PRESETS.keys())}")
        sys.exit(1)
    preset = PRESETS[name]
    print(f"Preset: {name} -- {preset['description']}\n")
    result = client.advanced_hunt(preset["query"])
    print(format_results(result))


def cmd_file(client: DefenderClient, path: str):
    with open(path) as f:
        kql = f.read().strip()
    print(f"Executing KQL from {path}...\n")
    result = client.advanced_hunt(kql)
    print(format_results(result))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = DefenderClient()
    cmd = sys.argv[1]

    if cmd == "query" and len(sys.argv) > 2:
        cmd_query(client, " ".join(sys.argv[2:]))
    elif cmd == "tables":
        cmd_tables(client)
    elif cmd == "presets":
        cmd_presets()
    elif cmd == "preset" and len(sys.argv) > 2:
        cmd_preset(client, sys.argv[2])
    elif cmd == "file" and len(sys.argv) > 2:
        cmd_file(client, sys.argv[2])
    else:
        print(__doc__.strip())
        sys.exit(1)
