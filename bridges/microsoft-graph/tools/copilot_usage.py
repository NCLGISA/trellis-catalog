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
Microsoft 365 Copilot Usage Reports Tool

Copilot adoption and usage analytics via beta Graph API reports endpoints.
Returns per-user activity detail and daily active/enabled user trends.

Usage:
    python3 copilot_usage.py user-detail                     # Per-user Copilot activity (D30)
    python3 copilot_usage.py user-detail --period D7         # Last 7 days
    python3 copilot_usage.py user-detail --period D90        # Last 90 days
    python3 copilot_usage.py trend                           # Daily active vs enabled (D30)
    python3 copilot_usage.py trend --period D7               # Last 7 days
    python3 copilot_usage.py summary                         # Adoption dashboard (D30)
    python3 copilot_usage.py summary --period D90            # Last 90 days
"""

import csv
import io
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from graph_client import GraphClient, BETA_BASE

VALID_PERIODS = {"D7", "D30", "D90", "D180"}
DEFAULT_PERIOD = "D30"


def _fetch_csv(client: GraphClient, endpoint: str) -> list:
    """Fetch a beta reports endpoint that returns CSV, parse into list of dicts."""
    resp = client.get(endpoint)
    if resp.status_code == 403:
        print("ERROR: Reports.Read.All permission required but access denied.")
        sys.exit(1)
    if resp.status_code == 404:
        print("ERROR: Copilot usage report endpoint not available.")
        print("This may indicate no M365 Copilot licenses are assigned in the tenant.")
        sys.exit(1)
    resp.raise_for_status()

    text = resp.text.strip()
    if not text:
        return []

    # Graph reports sometimes prepend a BOM or extra header line
    if text.startswith("\ufeff"):
        text = text[1:]

    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def _get_user_detail(client: GraphClient, period: str) -> list:
    """Fetch per-user Copilot usage detail."""
    url = f"{BETA_BASE}/reports/getMicrosoft365CopilotUsageUserDetail(period='{period}')"
    return _fetch_csv(client, url)


def _get_user_count_trend(client: GraphClient, period: str) -> list:
    """Fetch daily active/enabled user count trend."""
    url = f"{BETA_BASE}/reports/getMicrosoft365CopilotUserCountTrend(period='{period}')"
    return _fetch_csv(client, url)


def cmd_user_detail(client: GraphClient, period: str):
    """Show per-user Copilot activity."""
    rows = _get_user_detail(client, period)

    if not rows:
        print(f"No Copilot usage data available for period {period}.")
        print("Note: Requires M365 Copilot licenses assigned in the tenant.")
        return

    # Determine which columns exist (Microsoft may change schema)
    display_name_key = next((k for k in rows[0] if "Display Name" in k or "displayName" in k), None)
    upn_key = next((k for k in rows[0] if "Principal Name" in k or "userPrincipalName" in k), None)
    last_activity_key = next((k for k in rows[0] if "Last Activity" in k or "lastActivity" in k), None)

    name_col = display_name_key or "User"
    upn_col = upn_key or ""

    print(f"Copilot User Activity ({period}): {len(rows)} users")
    print()

    # Column headers vary; show what we have
    header_keys = list(rows[0].keys())
    if len(header_keys) <= 8:
        print(f"{'User':<35} ", end="")
        for k in header_keys:
            if k not in (name_col, upn_col, "Report Refresh Date"):
                print(f"{k:<20} ", end="")
        print()
        print("-" * 100)

        for row in rows:
            user = (row.get(name_col) or row.get(upn_col) or "?")[:34]
            print(f"{user:<35} ", end="")
            for k in header_keys:
                if k not in (name_col, upn_col, "Report Refresh Date"):
                    val = (row.get(k) or "")[:19]
                    print(f"{val:<20} ", end="")
            print()
    else:
        # Too many columns -- show as key-value per user
        for row in rows:
            user = row.get(name_col) or row.get(upn_col) or "?"
            print(f"User: {user}")
            for k, v in row.items():
                if k not in (name_col, upn_col, "Report Refresh Date") and v:
                    print(f"  {k}: {v}")
            print()


def cmd_trend(client: GraphClient, period: str):
    """Show daily active vs enabled user trend."""
    rows = _get_user_count_trend(client, period)

    if not rows:
        print(f"No Copilot trend data available for period {period}.")
        print("Note: Requires M365 Copilot licenses assigned in the tenant.")
        return

    date_key = next((k for k in rows[0] if "Date" in k and "Refresh" not in k), None)
    enabled_key = next((k for k in rows[0] if "Enabled" in k.lower() or "enabled" in k), None)
    active_key = next((k for k in rows[0] if "Active" in k.lower() or "active" in k), None)

    print(f"Copilot User Count Trend ({period}): {len(rows)} data points")
    print()
    print(f"{'Date':<14} {'Enabled':>10} {'Active':>10} {'Adoption':>10}")
    print("-" * 48)

    enabled_vals = []
    active_vals = []

    for row in sorted(rows, key=lambda r: r.get(date_key or "", ""), reverse=True):
        date = (row.get(date_key) or "?")[:13]
        enabled = row.get(enabled_key) or "0"
        active = row.get(active_key) or "0"

        try:
            e = int(enabled)
            a = int(active)
        except (ValueError, TypeError):
            e, a = 0, 0

        enabled_vals.append(e)
        active_vals.append(a)

        pct = f"{(a / e * 100):.0f}%" if e > 0 else "N/A"
        print(f"{date:<14} {enabled:>10} {active:>10} {pct:>10}")

    if enabled_vals:
        print()
        print(f"Enabled -- min: {min(enabled_vals)}, max: {max(enabled_vals)}, "
              f"avg: {sum(enabled_vals) / len(enabled_vals):.0f}")
        print(f"Active  -- min: {min(active_vals)}, max: {max(active_vals)}, "
              f"avg: {sum(active_vals) / len(active_vals):.0f}")


def cmd_summary(client: GraphClient, period: str):
    """High-level Copilot adoption dashboard."""
    print(f"Copilot Adoption Summary ({period})")
    print("=" * 60)

    # User detail for per-user stats
    detail_rows = _get_user_detail(client, period)

    if not detail_rows:
        print()
        print("No Copilot usage data available.")
        print("Note: Requires M365 Copilot licenses assigned in the tenant.")
        return

    print(f"\nTotal users in report: {len(detail_rows)}")

    # Try to find activity columns to identify active vs inactive users
    last_activity_key = next(
        (k for k in detail_rows[0] if "Last Activity" in k or "lastActivity" in k), None
    )

    if last_activity_key:
        active_users = [r for r in detail_rows if r.get(last_activity_key)]
        inactive_users = [r for r in detail_rows if not r.get(last_activity_key)]
        print(f"Active users:          {len(active_users)}")
        print(f"Inactive (licensed):   {len(inactive_users)}")
        if detail_rows:
            pct = len(active_users) / len(detail_rows) * 100
            print(f"Adoption rate:         {pct:.1f}%")

    # Column-level breakdown (apps that have data)
    app_columns = [
        k for k in detail_rows[0].keys()
        if k not in ("Report Refresh Date",) and ("Date" in k or "Count" in k or "Days" in k)
        and "Report" not in k
    ]

    if app_columns:
        print()
        print("Activity Columns Available:")
        for col in app_columns:
            non_empty = sum(1 for r in detail_rows if r.get(col) and r.get(col) != "0")
            print(f"  {col:<40} {non_empty:>5} users with activity")

    # Trend summary
    trend_rows = _get_user_count_trend(client, period)

    if trend_rows:
        date_key = next((k for k in trend_rows[0] if "Date" in k and "Refresh" not in k), None)
        active_key = next((k for k in trend_rows[0] if "Active" in k.lower() or "active" in k), None)
        enabled_key = next((k for k in trend_rows[0] if "Enabled" in k.lower() or "enabled" in k), None)

        if active_key:
            actives = []
            for r in trend_rows:
                try:
                    actives.append(int(r.get(active_key, 0)))
                except (ValueError, TypeError):
                    pass

            if actives:
                print()
                print("Trend Summary:")
                print(f"  Peak daily active:   {max(actives)}")
                print(f"  Lowest daily active: {min(actives)}")
                print(f"  Average daily active:{sum(actives) / len(actives):>5.0f}")

    # Show top users by display name
    display_name_key = next(
        (k for k in detail_rows[0] if "Display Name" in k or "displayName" in k), None
    )
    if display_name_key and last_activity_key:
        active_sorted = sorted(
            [r for r in detail_rows if r.get(last_activity_key)],
            key=lambda r: r.get(last_activity_key, ""),
            reverse=True,
        )
        if active_sorted:
            print()
            print("Most Recently Active Users:")
            for r in active_sorted[:10]:
                name = (r.get(display_name_key) or "?")[:35]
                last = (r.get(last_activity_key) or "?")[:10]
                print(f"  {name:<36} last active: {last}")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = GraphClient()
    command = sys.argv[1].lower()

    period = DEFAULT_PERIOD
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--period" and i + 1 < len(args):
            period = args[i + 1].upper()
            if period not in VALID_PERIODS:
                print(f"ERROR: Invalid period '{period}'. Must be one of: {', '.join(sorted(VALID_PERIODS))}")
                sys.exit(1)
            i += 2
        else:
            i += 1

    if command in ("user-detail", "userdetail"):
        cmd_user_detail(client, period)

    elif command == "trend":
        cmd_trend(client, period)

    elif command == "summary":
        cmd_summary(client, period)

    else:
        print(f"Unknown command: {command}")
        print("Commands: user-detail, trend, summary")
        sys.exit(1)


if __name__ == "__main__":
    main()
