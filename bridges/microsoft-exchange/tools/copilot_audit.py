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
Microsoft 365 Copilot Audit Log Tool

Search and analyze Copilot AI interaction audit records from the
unified audit log via Search-UnifiedAuditLog (RecordType CopilotInteraction).

Usage:
    python3 copilot_audit.py recent                          # Last 7 days of Copilot activity
    python3 copilot_audit.py recent --days 30                # Last 30 days
    python3 copilot_audit.py user user@example.com           # Activity for one user
    python3 copilot_audit.py user user@example.com --days 14 # With date range
    python3 copilot_audit.py search --days 7 --user a@b.com  # Flexible search
    python3 copilot_audit.py summary                         # Aggregate stats (7 days)
    python3 copilot_audit.py summary --days 30               # Aggregate stats (30 days)
"""

import sys
import json
from collections import Counter
from datetime import datetime, timedelta

sys.path.insert(0, "/opt/bridge/data/tools")
from exchange_client import ExchangeClient

RECORD_TYPE = "CopilotInteraction"
DEFAULT_DAYS = 7
MAX_RESULTS = 5000


def _search_copilot(client: ExchangeClient, days: int = DEFAULT_DAYS,
                    user: str = None, result_size: int = MAX_RESULTS) -> list:
    """Run Search-UnifiedAuditLog for CopilotInteraction records."""
    start = (datetime.utcnow() - timedelta(days=days)).strftime("%m/%d/%Y")
    end = (datetime.utcnow() + timedelta(days=1)).strftime("%m/%d/%Y")

    params = {
        "RecordType": RECORD_TYPE,
        "StartDate": start,
        "EndDate": end,
        "ResultSize": str(result_size),
    }
    if user:
        params["UserIds"] = user

    result = client.run_cmdlet("Search-UnifiedAuditLog", params)

    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    records = result["data"] if isinstance(result["data"], list) else []
    return records


def _parse_audit_data(record: dict) -> dict:
    """Extract key fields from AuditData JSON embedded in each record."""
    raw = record.get("AuditData", "")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _extract_app(audit: dict) -> str:
    """Determine which M365 app hosted the Copilot interaction."""
    app = audit.get("AppHost") or audit.get("Workload") or "Unknown"
    return app


def recent(client: ExchangeClient, days: int = DEFAULT_DAYS):
    """List recent Copilot interactions."""
    records = _search_copilot(client, days=days)

    print(f"Copilot Interactions (last {days} days): {len(records)}")
    print()
    print(f"{'Date':<20} {'User':<35} {'App':<15} {'Operation'}")
    print("-" * 90)

    for r in records:
        audit = _parse_audit_data(r)
        date = (r.get("CreationDate") or audit.get("CreationTime") or "?")[:19]
        user = (r.get("UserIds") or audit.get("UserId") or "?")[:34]
        app = _extract_app(audit)[:14]
        operation = (r.get("Operations") or audit.get("Operation") or "?")[:30]
        print(f"{date:<20} {user:<35} {app:<15} {operation}")

    if not records:
        print("No Copilot interactions found.")
        print("Note: Requires M365 Copilot licenses to be assigned in the tenant.")


def user_activity(client: ExchangeClient, email: str, days: int = DEFAULT_DAYS):
    """Show Copilot activity for a specific user."""
    records = _search_copilot(client, days=days, user=email)

    print(f"Copilot Activity for {email} (last {days} days): {len(records)}")
    print()

    if not records:
        print("No Copilot interactions found for this user.")
        return

    apps = Counter()
    operations = Counter()

    print(f"{'Date':<20} {'App':<15} {'Operation'}")
    print("-" * 55)

    for r in records:
        audit = _parse_audit_data(r)
        date = (r.get("CreationDate") or audit.get("CreationTime") or "?")[:19]
        app = _extract_app(audit)
        operation = (r.get("Operations") or audit.get("Operation") or "?")
        apps[app] += 1
        operations[operation] += 1
        print(f"{date:<20} {app:<15} {operation}")

    print()
    print("App Breakdown:")
    for app, count in apps.most_common():
        print(f"  {app:<25} {count:>5}")

    print()
    print("Operation Breakdown:")
    for op, count in operations.most_common():
        print(f"  {op:<35} {count:>5}")


def search(client: ExchangeClient, days: int = DEFAULT_DAYS, user: str = None):
    """Flexible search with all filters."""
    records = _search_copilot(client, days=days, user=user)

    filters = [f"last {days} days"]
    if user:
        filters.append(f"user={user}")

    print(f"Copilot Search ({', '.join(filters)}): {len(records)}")
    print()

    if not records:
        print("No matching records found.")
        return

    print(f"{'Date':<20} {'User':<35} {'App':<15} {'Operation'}")
    print("-" * 90)

    for r in records:
        audit = _parse_audit_data(r)
        date = (r.get("CreationDate") or audit.get("CreationTime") or "?")[:19]
        usr = (r.get("UserIds") or audit.get("UserId") or "?")[:34]
        app = _extract_app(audit)[:14]
        operation = (r.get("Operations") or audit.get("Operation") or "?")[:30]
        print(f"{date:<20} {usr:<35} {app:<15} {operation}")


def summary(client: ExchangeClient, days: int = DEFAULT_DAYS):
    """Aggregate Copilot usage summary."""
    records = _search_copilot(client, days=days)

    print(f"Copilot Usage Summary (last {days} days)")
    print("=" * 60)

    if not records:
        print()
        print("Total interactions: 0")
        print()
        print("No Copilot interactions found in this period.")
        print("Note: Requires M365 Copilot licenses to be assigned in the tenant.")
        return

    users = Counter()
    apps = Counter()
    operations = Counter()
    daily = Counter()

    for r in records:
        audit = _parse_audit_data(r)
        user = (r.get("UserIds") or audit.get("UserId") or "unknown")
        app = _extract_app(audit)
        operation = (r.get("Operations") or audit.get("Operation") or "unknown")
        date = (r.get("CreationDate") or audit.get("CreationTime") or "")[:10]

        users[user] += 1
        apps[app] += 1
        operations[operation] += 1
        if date:
            daily[date] += 1

    print()
    print(f"Total interactions:   {len(records)}")
    print(f"Unique users:         {len(users)}")
    print(f"Active days:          {len(daily)}")
    if daily:
        avg_daily = len(records) / len(daily)
        print(f"Avg interactions/day: {avg_daily:.1f}")

    print()
    print("By Application:")
    for app, count in apps.most_common():
        pct = (count / len(records)) * 100
        print(f"  {app:<25} {count:>5} ({pct:>5.1f}%)")

    print()
    print("Top Users:")
    for user, count in users.most_common(10):
        print(f"  {user:<40} {count:>5}")

    print()
    print("By Operation:")
    for op, count in operations.most_common(10):
        print(f"  {op:<35} {count:>5}")

    if daily:
        print()
        print("Daily Activity (last 7 shown):")
        for date, count in sorted(daily.items(), reverse=True)[:7]:
            bar = "#" * min(count, 50)
            print(f"  {date}  {count:>4}  {bar}")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = ExchangeClient()
    command = sys.argv[1].lower()

    args = sys.argv[2:]
    days = DEFAULT_DAYS
    user = None

    i = 0
    positional = []
    while i < len(args):
        if args[i] == "--days" and i + 1 < len(args):
            days = int(args[i + 1])
            i += 2
        elif args[i] == "--user" and i + 1 < len(args):
            user = args[i + 1]
            i += 2
        else:
            positional.append(args[i])
            i += 1

    if command == "recent":
        recent(client, days=days)

    elif command == "user":
        email = positional[0] if positional else user
        if not email:
            print("Usage: copilot_audit.py user <email> [--days N]")
            sys.exit(1)
        user_activity(client, email, days=days)

    elif command == "search":
        search(client, days=days, user=user)

    elif command == "summary":
        summary(client, days=days)

    else:
        print(f"Unknown command: {command}")
        print("Commands: recent, user, search, summary")
        sys.exit(1)


if __name__ == "__main__":
    main()
