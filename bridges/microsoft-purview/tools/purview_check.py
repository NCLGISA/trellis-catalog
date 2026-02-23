"""
Microsoft Purview Bridge Healthcheck

Validates environment variables and Security & Compliance PowerShell connectivity.

Usage:
    python3 purview_check.py          # Full healthcheck (JSON output)
    python3 purview_check.py --quick  # Quick env-var-only check (for Docker healthcheck)
"""

import os
import sys
import json
import time

sys.path.insert(0, "/opt/bridge/data/tools")


def check_env_vars() -> list:
    required = {
        "PURVIEW_TENANT_ID": os.getenv("PURVIEW_TENANT_ID"),
        "PURVIEW_APP_ID": os.getenv("PURVIEW_APP_ID"),
        "PURVIEW_CERT_THUMBPRINT": os.getenv("PURVIEW_CERT_THUMBPRINT"),
        "PURVIEW_ORGANIZATION": os.getenv("PURVIEW_ORGANIZATION"),
    }
    return [k for k, v in required.items() if not v]


def check_certificate() -> dict:
    cert_dir = os.getenv("PURVIEW_CERT_DIR", "/opt/bridge/certs")
    cert_file = os.getenv("PURVIEW_CERT_FILENAME", "purview-bridge.pfx")
    cert_path = os.path.join(cert_dir, cert_file)

    if os.path.isfile(cert_path):
        size = os.path.getsize(cert_path)
        return {"ok": True, "path": cert_path, "size_bytes": size}
    return {"ok": False, "error": f"Certificate not found: {cert_path}"}


def check_connectivity() -> dict:
    try:
        from purview_client import PurviewClient
        client = PurviewClient()
        return client.test_connection()
    except SystemExit:
        return {"ok": False, "error": "Missing credentials (PurviewClient init failed)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    quick = "--quick" in sys.argv

    results = {
        "bridge": "microsoft-purview",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checks": {},
    }

    missing = check_env_vars()
    results["checks"]["env_vars"] = {"ok": len(missing) == 0, "missing": missing}

    cert = check_certificate()
    results["checks"]["certificate"] = cert

    if quick:
        all_ok = results["checks"]["env_vars"]["ok"] and cert["ok"]
        results["status"] = "healthy" if all_ok else "unhealthy"
        print(json.dumps(results, indent=2))
        sys.exit(0 if all_ok else 1)

    conn = check_connectivity()
    results["checks"]["connectivity"] = conn

    all_ok = (
        results["checks"]["env_vars"]["ok"]
        and cert["ok"]
        and conn.get("ok", False)
    )
    results["status"] = "healthy" if all_ok else "unhealthy"
    print(json.dumps(results, indent=2))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
