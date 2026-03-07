"""
Verizon MyBusiness Bridge -- Health Check

Validates credentials, session cookies, API connectivity, and fleet counts.
The --quick flag checks credentials and session only (no API calls).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from verizon_client import VerizonClient, SessionExpiredError, credentials_available


def main():
    quick = "--quick" in sys.argv

    print("Verizon MyBusiness Bridge -- Health Check")
    print("=" * 50)

    # Step 0: Credential check (always available, no credentials required to run)
    print("\n[0] Credential configuration...")
    has_creds = credentials_available()
    username = os.getenv("VZ_USERNAME", "").strip()
    if has_creds:
        print(f"    OK -- VZ_USERNAME={username}")
        print(f"    OK -- VZ_PASSWORD=****")
    else:
        print("    MISSING -- Verizon credentials not configured")
        print('    Set: bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_USERNAME", value="...")')
        print('    Set: bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_PASSWORD", value="...")')
        if quick:
            print("\nQuick check: credentials not configured.")
            sys.exit(1)

    # Step 1: Session check
    print("\n[1] Session validity...")
    try:
        client = VerizonClient()
    except FileNotFoundError as e:
        print(f"    NO SESSION -- {e}")
        if quick:
            print("\nQuick check: no session.")
            sys.exit(1)
        print("    Run: python3 auth_session.py initiate")
        sys.exit(1)

    try:
        alive = client.is_session_alive()
        if alive:
            print("    OK -- session is active")
        else:
            print("    EXPIRED -- session expired")
            print("    Run: python3 auth_session.py initiate")
            sys.exit(1)
    except Exception as e:
        print(f"    FAIL -- {e}")
        sys.exit(1)

    if quick:
        print("\nQuick check passed.")
        return

    # Step 2: Fleet summary (requires credentials)
    if not has_creds:
        print("\n[2-4] Skipping API checks (no credentials)")
        print("\nHealth check: partial (credential-limited).")
        return

    print("\n[2] Fleet summary...")
    try:
        counts = client.retrieve_line_summary_count()
        lc = counts.get("lineCounts", {})
        print(f"    Total lines: {lc.get('total', '?')}")
        print(f"    Active: {lc.get('active', '?')}")
        print(f"    Suspended: {lc.get('suspended', '?')}")
        print(f"    5G: {lc.get('5G', '?')}")
        print(f"    4G: {lc.get('4G', '?')}")
        print(f"    Upgrade eligible: {lc.get('upgradeEligible', '?')}")
    except SessionExpiredError:
        print("    FAIL -- session expired during fleet query")
        sys.exit(1)
    except Exception as e:
        print(f"    WARN -- fleet query failed: {e}")

    # Step 3: Billing check
    print("\n[3] Billing accounts...")
    try:
        billing = client.get_billing_accounts()
        accounts = billing.get("accountInfo", [])
        for acct in accounts:
            print(f"    {acct['accountNumber']}: ${acct['totalBalanceDue']:,.2f} "
                  f"due {acct['paymentDueDate']}")
    except Exception as e:
        print(f"    WARN -- billing query failed: {e}")

    # Step 4: Dashboard
    print("\n[4] Dashboard summary...")
    try:
        upgrade = client.get_line_upgrade_eligible()
        print(f"    Total lines: {upgrade.get('totalLines', '?')}")
        print(f"    Upgrade eligible: {upgrade.get('totalUpgradeLines', '?')}")
        orders = client.get_total_orders()
        print(f"    Pending orders: {orders.get('totalOrderCount', '?')}")
    except Exception as e:
        print(f"    WARN -- dashboard query failed: {e}")

    print("\nHealth check passed.")


if __name__ == "__main__":
    main()
