#!/usr/bin/env python3
"""
Adobe Sign Bridge - Health Check

Validates:
  1. ADOBE_SIGN_INTEGRATION_KEY environment variable is set
  2. Base URI discovery succeeds (network + auth validation)
  3. API access to agreements, templates, and users
  4. Reports account summary

Usage:
    python3 /opt/bridge/data/tools/adobe_sign_check.py
    python3 /opt/bridge/data/tools/adobe_sign_check.py --quick
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    quick = "--quick" in sys.argv

    print("=" * 60)
    print("Adobe Sign Bridge Health Check")
    print("=" * 60)

    # ── Step 1: Environment ──────────────────────────────────────────
    key = os.getenv("ADOBE_SIGN_INTEGRATION_KEY", "")
    print(f"\n[1/4] ADOBE_SIGN_INTEGRATION_KEY: {'set (' + key[:8] + '...)' if key else 'NOT SET'}")
    if not key:
        print("  FAIL: Set ADOBE_SIGN_INTEGRATION_KEY in docker-compose.yml or .env")
        sys.exit(1)
    print("  PASS")

    if quick:
        print("\n" + "=" * 60)
        print("Quick check passed (env only). Use full check for API validation.")
        print("=" * 60)
        return

    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()

    # ── Step 2: Base URI Discovery ───────────────────────────────────
    print("\n[2/4] Base URI discovery:")
    try:
        api_base = client.api_base
        print(f"  API base: {api_base}")
        print(f"  Web base: {client.web_base}")
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # ── Step 3: Account Access ───────────────────────────────────────
    print("\n[3/4] Account access:")
    try:
        users = client.list_users(page_size=50, max_pages=1)
        print(f"  Users accessible: {len(users)} found")
        for u in users[:5]:
            email = u.get("email", "?")
            name = f"{u.get('firstName', '')} {u.get('lastName', '')}".strip() or "?"
            status = u.get("userStatus", u.get("status", "?"))
            print(f"    {name:30s}  {email:40s}  {status}")
        if len(users) > 5:
            print(f"    ... and {len(users) - 5} more")
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # ── Step 4: API Coverage ─────────────────────────────────────────
    print("\n[4/4] API endpoint access:")
    checks = []

    try:
        agreements = client.list_agreements(page_size=5, max_pages=1)
        checks.append(("Agreements", True, f"{len(agreements)} recent"))
    except Exception as e:
        checks.append(("Agreements", False, str(e)))

    try:
        templates = client.list_library_documents(page_size=5, max_pages=1)
        checks.append(("Library Documents", True, f"{len(templates)} found"))
    except Exception as e:
        checks.append(("Library Documents", False, str(e)))

    try:
        widgets = client.list_widgets(page_size=5, max_pages=1)
        checks.append(("Web Forms", True, f"{len(widgets)} found"))
    except Exception as e:
        checks.append(("Web Forms", False, str(e)))

    try:
        webhooks = client.list_webhooks(page_size=5, max_pages=1)
        checks.append(("Webhooks", True, f"{len(webhooks)} found"))
    except Exception as e:
        checks.append(("Webhooks", False, str(e)))

    try:
        workflows = client.list_workflows()
        checks.append(("Workflows", True, f"{len(workflows)} found"))
    except Exception as e:
        checks.append(("Workflows", False, str(e)))

    all_passed = True
    for name, passed, detail in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  {name:20s}  {status}  ({detail})")

    if not all_passed:
        print("\n  Some endpoint checks failed. Verify Integration Key scopes.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("All checks passed. Adobe Sign bridge is operational.")
    print("=" * 60)


if __name__ == "__main__":
    main()
