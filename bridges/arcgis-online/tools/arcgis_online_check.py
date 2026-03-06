#!/usr/bin/env python3
"""
ArcGIS Online Bridge - Health Check

Verifies environment variables, OAuth2 token acquisition, and basic
API connectivity. Used as the Docker HEALTHCHECK and for manual validation.

Usage:
    python3 /opt/bridge/data/tools/arcgis_online_check.py           # full check
    python3 /opt/bridge/data/tools/arcgis_online_check.py --quick   # env vars only
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import os


def check_environment():
    """Verify required environment variables are set."""
    required = {
        "ARCGIS_ORG_URL": os.getenv("ARCGIS_ORG_URL", ""),
        "ARCGIS_CLIENT_ID": os.getenv("ARCGIS_CLIENT_ID", ""),
        "ARCGIS_CLIENT_SECRET": os.getenv("ARCGIS_CLIENT_SECRET", ""),
    }
    missing = [k for k, v in required.items() if not v]
    return {
        "check": "environment",
        "passed": len(missing) == 0,
        "detail": {"missing": missing} if missing else {"variables": len(required)},
    }


def check_token_acquisition():
    """Test OAuth2 token acquisition."""
    try:
        from arcgis_online_client import ArcGISOnlineClient
        client = ArcGISOnlineClient()
        token = client._get_token()
        return {
            "check": "token_acquisition",
            "passed": bool(token),
            "detail": {"token_length": len(token)} if token else {"error": "empty token"},
        }
    except SystemExit:
        return {
            "check": "token_acquisition",
            "passed": False,
            "detail": {"error": "Client initialization failed (missing credentials?)"},
        }
    except Exception as e:
        return {
            "check": "token_acquisition",
            "passed": False,
            "detail": {"error": str(e)},
        }


def check_api_connection():
    """Test API connectivity by fetching org info."""
    try:
        from arcgis_online_client import ArcGISOnlineClient
        client = ArcGISOnlineClient()
        result = client.test_connection()
        return {
            "check": "api_connection",
            "passed": result.get("ok", False),
            "detail": result,
        }
    except SystemExit:
        return {
            "check": "api_connection",
            "passed": False,
            "detail": {"error": "Client initialization failed"},
        }
    except Exception as e:
        return {
            "check": "api_connection",
            "passed": False,
            "detail": {"error": str(e)},
        }


def main():
    quick = "--quick" in sys.argv

    checks = [check_environment()]

    if not quick:
        if checks[0]["passed"]:
            checks.append(check_token_acquisition())
            if checks[-1]["passed"]:
                checks.append(check_api_connection())
        else:
            checks.append({
                "check": "token_acquisition",
                "passed": False,
                "detail": {"skipped": "environment check failed"},
            })

    all_passed = all(c["passed"] for c in checks)
    output = {
        "status": "ok" if all_passed else "error",
        "bridge": "arcgis-online",
        "checks": checks,
    }

    print(json.dumps(output, indent=2))
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
