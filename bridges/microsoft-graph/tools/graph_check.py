#!/usr/bin/env python3
"""
Health check for the Microsoft Graph bridge.

Validates environment variables are set and tests API connectivity.

Usage:
    python3 graph_check.py
"""

import os
import sys
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from graph_client import GraphClient


def check():
    """Run health checks and report status."""
    checks = {}

    # Check environment variables
    required_vars = ["AZURE_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET"]
    env_status = {}
    all_set = True
    for var in required_vars:
        val = os.getenv(var, "")
        if val:
            env_status[var] = "set"
        else:
            env_status[var] = "MISSING"
            all_set = False
    checks["environment"] = env_status

    if not all_set:
        checks["api_connection"] = {"ok": False, "error": "Missing environment variables"}
        print(json.dumps(checks, indent=2))
        sys.exit(1)

    # Test API connection (use /users endpoint which is covered by User.ReadWrite.All;
    # /organization requires Organization.Read.All which may not be granted yet)
    try:
        client = GraphClient()
        result = client.test_connection()
        checks["api_connection"] = result
    except Exception as e:
        checks["api_connection"] = {"ok": False, "error": str(e)}

    # Test user listing (basic permission check)
    if checks["api_connection"].get("ok"):
        try:
            users = client.list_users(select="id", top=1)
            checks["permission_test"] = {
                "ok": True,
                "test": "User.Read.All",
                "result": f"Successfully queried users (found at least {len(users)})",
            }
        except Exception as e:
            checks["permission_test"] = {
                "ok": False,
                "test": "User.Read.All",
                "error": str(e),
            }

    print(json.dumps(checks, indent=2))

    if checks["api_connection"].get("ok"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    check()
