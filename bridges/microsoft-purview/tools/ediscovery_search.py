"""
Microsoft Purview eDiscovery Tool (Read-Only)

List and inspect eDiscovery cases and compliance searches.

IMPORTANT: Certificate-based authentication (CBA) does NOT support write
operations for eDiscovery. The following cmdlets are blocked by Microsoft:
  - New-ComplianceSearch, Start-ComplianceSearch
  - New-ComplianceSearchAction, Get-ComplianceSearchAction
  - New/Set/Remove-CaseHoldPolicy, New/Set/Remove-CaseHoldRule

Write operations must be performed via the Microsoft Purview portal or
interactive user authentication.

License requirements:
  E3: Standard eDiscovery (basic case management)
  E5: Premium eDiscovery (advanced analytics, review sets, custodian management)

Usage:
    python3 ediscovery_search.py cases                       # List eDiscovery cases
    python3 ediscovery_search.py case-detail <name>          # Case details
    python3 ediscovery_search.py searches                    # List compliance searches
    python3 ediscovery_search.py search-detail <name>        # Search details
    python3 ediscovery_search.py case-members <name>         # Case role group members
    python3 ediscovery_search.py summary                     # eDiscovery summary
"""

import sys
import json
from collections import Counter

sys.path.insert(0, "/opt/bridge/data/tools")
from purview_client import PurviewClient


def list_cases(client: PurviewClient):
    result = client.run_cmdlet("Get-ComplianceCase")
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    cases = result["data"] if isinstance(result["data"], list) else []
    if not cases:
        print("No eDiscovery cases found.")
        return

    print(f"eDiscovery Cases: {len(cases)}")
    print()
    print(f"{'Status':<12} {'Type':<20} {'Name':<45} {'Created'}")
    print("-" * 95)

    for c in cases:
        status = (c.get("Status") or "?")[:11]
        case_type = (c.get("CaseType") or "?")[:19]
        name = (c.get("Name") or "?")[:44]
        created = (str(c.get("CreatedDateTime") or "?"))[:19]
        print(f"{status:<12} {case_type:<20} {name:<45} {created}")


def case_detail(client: PurviewClient, name: str):
    result = client.run_cmdlet("Get-ComplianceCase", {"Identity": name})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]
    print(json.dumps(data, indent=2, default=str))


def list_searches(client: PurviewClient):
    result = client.run_cmdlet("Get-ComplianceSearch")
    if not result["ok"]:
        if "not recognized" in result.get("error", "").lower():
            print("Get-ComplianceSearch may not be available via CBA.")
            print("Check Microsoft documentation for current CBA cmdlet support.")
            return
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    searches = result["data"] if isinstance(result["data"], list) else []
    if not searches:
        print("No compliance searches found.")
        return

    print(f"Compliance Searches: {len(searches)}")
    print()
    print(f"{'Status':<12} {'Name':<45} {'Items':>10} {'Size':>12}")
    print("-" * 85)

    for s in searches:
        status = (s.get("Status") or "?")[:11]
        name = (s.get("Name") or "?")[:44]
        items = s.get("Items", "?")
        size = s.get("Size", "?")
        print(f"{status:<12} {name:<45} {items:>10} {size:>12}")


def search_detail(client: PurviewClient, name: str):
    result = client.run_cmdlet("Get-ComplianceSearch", {"Identity": name})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]
    print(json.dumps(data, indent=2, default=str))


def case_members(client: PurviewClient, name: str):
    result = client.run_cmdlet("Get-ComplianceCaseMember", {"Case": name})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    members = result["data"] if isinstance(result["data"], list) else []
    if not members:
        print(f"No members found for case: {name}")
        return

    print(f"Members of eDiscovery case '{name}': {len(members)}")
    print()
    for m in members:
        if isinstance(m, dict):
            name_val = m.get("Name") or m.get("DisplayName") or "?"
            role = m.get("Role") or ""
            print(f"  {name_val:<40} {role}")
        else:
            print(f"  {m}")


def summary(client: PurviewClient):
    cases = client.run_cmdlet("Get-ComplianceCase")

    c_list = cases["data"] if cases["ok"] and isinstance(cases["data"], list) else []

    print(f"eDiscovery Summary")
    print(f"=" * 60)
    print(f"Total cases: {len(c_list)}")

    if c_list:
        statuses = Counter(c.get("Status", "Unknown") for c in c_list)
        print()
        print("By status:")
        for s, count in statuses.most_common():
            print(f"  {s:<20} {count}")

        types = Counter(c.get("CaseType", "Unknown") for c in c_list)
        print()
        print("By type:")
        for t, count in types.most_common():
            print(f"  {t:<20} {count}")

    print()
    print("NOTE: Write operations (create search, start search, manage holds)")
    print("are NOT available via certificate-based authentication.")
    print("Use the Microsoft Purview portal for these operations.")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = PurviewClient()
    command = sys.argv[1].lower()

    if command == "cases":
        list_cases(client)
    elif command in ("case-detail", "casedetail"):
        if len(sys.argv) < 3:
            print("Usage: ediscovery_search.py case-detail <name>")
            sys.exit(1)
        case_detail(client, " ".join(sys.argv[2:]))
    elif command == "searches":
        list_searches(client)
    elif command in ("search-detail", "searchdetail"):
        if len(sys.argv) < 3:
            print("Usage: ediscovery_search.py search-detail <name>")
            sys.exit(1)
        search_detail(client, " ".join(sys.argv[2:]))
    elif command in ("case-members", "casemembers"):
        if len(sys.argv) < 3:
            print("Usage: ediscovery_search.py case-members <case-name>")
            sys.exit(1)
        case_members(client, " ".join(sys.argv[2:]))
    elif command == "summary":
        summary(client)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
