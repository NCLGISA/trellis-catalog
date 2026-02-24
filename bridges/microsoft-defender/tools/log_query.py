#!/usr/bin/env python3
"""
Direct KQL queries against the Log Analytics workspace.

Use this for querying custom tables (TendrilLogs_CL, etc.) and workspace-
specific data that isn't available through the Defender XDR advanced hunting
schema.  For cross-schema hunting (MDE + Sentinel tables), use hunting.py.

Usage:
    python3 log_query.py query "<kql>" [timespan]     # Execute KQL
    python3 log_query.py tables                        # List workspace tables
    python3 log_query.py tendril [hours]               # Recent Tendril logs
    python3 log_query.py security [hours]              # Recent security events
    python3 log_query.py signin [hours]                # Recent sign-in logs
    python3 log_query.py file <path-to-kql> [timespan] # Run KQL from a file
"""

import sys
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from defender_client import DefenderClient


def format_log_results(data: dict) -> str:
    if "error" in data:
        return f"ERROR: {data.get('message', json.dumps(data))}"

    tables = data.get("tables", [])
    if not tables:
        return "No results."

    table = tables[0]
    columns = [c["name"] for c in table.get("columns", [])]
    rows = table.get("rows", [])

    if not rows:
        return "No results."

    lines = [f"Results: {len(rows)} rows\n"]

    col_widths = {c: len(c) for c in columns}
    for row in rows[:200]:
        for i, c in enumerate(columns):
            val = str(row[i]) if i < len(row) else ""
            col_widths[c] = min(max(col_widths[c], len(val)), 60)

    header = "  ".join(c.ljust(col_widths[c]) for c in columns)
    lines.append(header)
    lines.append("  ".join("─" * col_widths[c] for c in columns))

    for row in rows[:200]:
        line = "  ".join(
            str(row[i] if i < len(row) else "").ljust(col_widths[columns[i]])[:col_widths[columns[i]]]
            for i in range(len(columns))
        )
        lines.append(line)

    if len(rows) > 200:
        lines.append(f"\n... and {len(rows) - 200} more rows (truncated)")

    return "\n".join(lines)


def cmd_query(client: DefenderClient, kql: str, timespan: str = "P1D"):
    print(f"Querying Log Analytics workspace (timespan: {timespan})...\n")
    result = client.query_logs(kql, timespan=timespan)
    print(format_log_results(result))


def cmd_tables(client: DefenderClient):
    kql = (
        "search *\n"
        "| where TimeGenerated > ago(7d)\n"
        "| distinct $table\n"
        "| sort by $table asc"
    )
    result = client.query_logs(kql, timespan="P7D")
    tables_data = result.get("tables", [])
    if not tables_data:
        print("No tables found or query error.")
        if "error" in result:
            print(f"Error: {result.get('message', result)}")
        return

    rows = tables_data[0].get("rows", [])
    print(f"Workspace Tables (active in last 7d): {len(rows)}\n")
    for row in rows:
        print(f"  {row[0]}")


def cmd_tendril(client: DefenderClient, hours: int = 24):
    kql = (
        f"TendrilLogs_CL\n"
        f"| where TimeGenerated > ago({hours}h)\n"
        f"| sort by TimeGenerated desc\n"
        f"| take 100"
    )
    print(f"Tendril logs (last {hours}h)...\n")
    result = client.query_logs(kql, timespan=f"PT{hours}H")
    print(format_log_results(result))


def cmd_security(client: DefenderClient, hours: int = 24):
    kql = (
        f"SecurityEvent\n"
        f"| where TimeGenerated > ago({hours}h)\n"
        f"| summarize Count=count() by EventID, Activity\n"
        f"| sort by Count desc\n"
        f"| take 50"
    )
    print(f"Security event summary (last {hours}h)...\n")
    result = client.query_logs(kql, timespan=f"PT{hours}H")
    print(format_log_results(result))


def cmd_signin(client: DefenderClient, hours: int = 24):
    kql = (
        f"SigninLogs\n"
        f"| where TimeGenerated > ago({hours}h)\n"
        f"| where ResultType != '0'\n"
        f"| summarize FailCount=count() by UserPrincipalName, ResultType, ResultDescription, AppDisplayName\n"
        f"| sort by FailCount desc\n"
        f"| take 50"
    )
    print(f"Failed sign-ins (last {hours}h)...\n")
    result = client.query_logs(kql, timespan=f"PT{hours}H")
    print(format_log_results(result))


def cmd_file(client: DefenderClient, path: str, timespan: str = "P1D"):
    with open(path) as f:
        kql = f.read().strip()
    print(f"Executing KQL from {path} (timespan: {timespan})...\n")
    result = client.query_logs(kql, timespan=timespan)
    print(format_log_results(result))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = DefenderClient()
    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "query" and args:
        timespan = args[1] if len(args) > 1 else "P1D"
        cmd_query(client, args[0], timespan)
    elif cmd == "tables":
        cmd_tables(client)
    elif cmd == "tendril":
        hours = int(args[0]) if args else 24
        cmd_tendril(client, hours)
    elif cmd == "security":
        hours = int(args[0]) if args else 24
        cmd_security(client, hours)
    elif cmd == "signin":
        hours = int(args[0]) if args else 24
        cmd_signin(client, hours)
    elif cmd == "file" and args:
        timespan = args[1] if len(args) > 1 else "P1D"
        cmd_file(client, args[0], timespan)
    else:
        print(__doc__.strip())
        sys.exit(1)
