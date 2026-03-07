"""
Verizon MyBusiness Bridge -- Fleet Inventory

List, search, filter, and summarize wireless lines.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from verizon_client import VerizonClient, require_credentials

DEPT_LABELS = {
    # Map cost center prefixes to department names.
    # Customize this for your organization's cost center structure.
    # Example:
    #   "IT": "Information Technology",
    #   "FIN": "Finance",
    #   "OPS": "Operations",
}


def normalize_mtn(mtn: str) -> str:
    return "".join(c for c in mtn if c.isdigit())


def get_dept_prefix(cost_center: str) -> str:
    return cost_center.split("-")[0].split(" ")[0] if cost_center else "?"


def main():
    if len(sys.argv) < 2:
        print("Usage: fleet_check.py <command> [options]")
        print("Commands: list, search, summary, by-department, by-device-type, upgrade-eligible")
        sys.exit(1)

    require_credentials()
    cmd = sys.argv[1]
    client = VerizonClient()
    fleet = client.retrieve_entitled_mtn()
    lines = fleet.get("mtnDetails", [])

    opts = {}
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--type" and i + 1 < len(sys.argv):
            opts["type"] = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--dept" and i + 1 < len(sys.argv):
            opts["dept"] = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--status" and i + 1 < len(sys.argv):
            opts["status"] = sys.argv[i + 1]
            i += 2
        else:
            opts["query"] = sys.argv[i]
            i += 1

    def apply_filters(records):
        result = records
        if "type" in opts:
            t = opts["type"].upper()
            result = [r for r in result if t in r.get("deviceType", "").upper()]
        if "dept" in opts:
            d = opts["dept"].upper()
            result = [r for r in result if get_dept_prefix(r.get("costCenter", "")).upper() == d]
        if "status" in opts:
            s = opts["status"].lower()
            result = [r for r in result if r.get("status", "").lower() == s]
        return result

    if cmd == "list":
        filtered = apply_filters(lines)
        print(f"{'MTN':<15} {'User':<25} {'Status':<10} {'Device Type':<22} {'Dept':<5} {'Cost Center'}")
        print("─" * 100)
        for r in filtered:
            dept = get_dept_prefix(r.get("costCenter", ""))
            print(f"{r.get('mtn',''):<15} {r.get('userName',''):<25} {r.get('status',''):<10} "
                  f"{r.get('deviceType',''):<22} {dept:<5} {r.get('costCenter','')}")
        print(f"\nTotal: {len(filtered)} lines")

    elif cmd == "search":
        query = opts.get("query", "").upper()
        if not query:
            print("Usage: fleet_check.py search <mtn|name|keyword>")
            sys.exit(1)
        matches = [r for r in lines if
                   query in normalize_mtn(r.get("mtn", "")) or
                   query in r.get("mtn", "").upper() or
                   query in r.get("userName", "").upper() or
                   query in r.get("firstName", "").upper() or
                   query in r.get("lastName", "").upper() or
                   query in r.get("emailAddress", "").upper() or
                   query in r.get("costCenter", "").upper()]
        for r in matches:
            print(json.dumps({
                "mtn": r.get("mtn"),
                "userName": r.get("userName"),
                "status": r.get("status"),
                "deviceType": r.get("deviceType"),
                "costCenter": r.get("costCenter"),
                "accountNumber": r.get("accountNumber"),
                "planName": r.get("planName"),
                "upgradeDate": r.get("upgradeDate"),
            }, indent=2))
        print(f"\n{len(matches)} match(es)")

    elif cmd == "summary":
        counts = client.retrieve_line_summary_count()
        lc = counts.get("lineCounts", {})
        print(f"Total: {lc.get('total', '?')}")
        print(f"Active: {lc.get('active', '?')}")
        print(f"Suspended: {lc.get('suspended', '?')}")
        print(f"5G: {lc.get('5G', '?')}")
        print(f"4G: {lc.get('4G', '?')}")
        print(f"Upgrade eligible: {lc.get('upgradeEligible', '?')}")

    elif cmd == "by-department":
        dept_counts = {}
        for r in lines:
            prefix = get_dept_prefix(r.get("costCenter", ""))
            dept_counts[prefix] = dept_counts.get(prefix, 0) + 1
        print(f"{'Dept':<6} {'Name':<30} {'Lines':>5}")
        print("─" * 45)
        for prefix in sorted(dept_counts, key=lambda x: -dept_counts[x]):
            label = DEPT_LABELS.get(prefix, "Unknown")
            print(f"{prefix:<6} {label:<30} {dept_counts[prefix]:>5}")

    elif cmd == "by-device-type":
        type_counts = {}
        for r in lines:
            dt = r.get("deviceType", "unknown")
            type_counts[dt] = type_counts.get(dt, 0) + 1
        print(f"{'Device Type':<25} {'Count':>5}")
        print("─" * 32)
        for dt in sorted(type_counts, key=lambda x: -type_counts[x]):
            print(f"{dt:<25} {type_counts[dt]:>5}")

    elif cmd == "upgrade-eligible":
        eligible = [r for r in lines if r.get("upgradeDevice")]
        eligible = apply_filters(eligible)
        print(f"{'MTN':<15} {'User':<25} {'Upgrade Date':<25} {'Device Type'}")
        print("─" * 85)
        for r in eligible:
            print(f"{r.get('mtn',''):<15} {r.get('userName',''):<25} "
                  f"{r.get('upgradeDate',''):<25} {r.get('deviceType','')}")
        print(f"\nTotal: {len(eligible)} lines eligible for upgrade")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
