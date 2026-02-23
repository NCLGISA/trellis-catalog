"""
Exchange Online Bridge Healthcheck

Validates environment variables and Exchange Online PowerShell connectivity.
Used by Docker healthcheck and manual verification.

Usage:
    python3 exchange_check.py          # Full healthcheck (JSON output)
    python3 exchange_check.py --quick  # Quick env-var-only check (for Docker healthcheck)
"""

import os
import sys
import json
import time

sys.path.insert(0, "/opt/bridge/data/tools")


def check_env_vars() -> list:
    """Check required environment variables."""
    required = {
        "EXO_TENANT_ID": os.getenv("EXO_TENANT_ID"),
        "EXO_APP_ID": os.getenv("EXO_APP_ID"),
        "EXO_CERT_THUMBPRINT": os.getenv("EXO_CERT_THUMBPRINT"),
        "EXO_ORGANIZATION": os.getenv("EXO_ORGANIZATION"),
    }

    missing = [k for k, v in required.items() if not v]
    return missing


def check_certificate() -> dict:
    """Verify certificate file exists."""
    cert_dir = os.getenv("EXO_CERT_DIR", "/opt/bridge/certs")
    cert_file = os.getenv("EXO_CERT_FILENAME", "exchange-bridge.pfx")
    cert_path = os.path.join(cert_dir, cert_file)

    if os.path.isfile(cert_path):
        size = os.path.getsize(cert_path)
        return {"ok": True, "path": cert_path, "size_bytes": size}
    return {"ok": False, "error": f"Certificate not found: {cert_path}"}


def check_connectivity() -> dict:
    """Test Exchange Online PowerShell connectivity."""
    try:
        from exchange_client import ExchangeClient
        client = ExchangeClient()
        return client.test_connection()
    except SystemExit:
        return {"ok": False, "error": "Missing credentials (ExchangeClient init failed)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    quick = "--quick" in sys.argv

    results = {
        "bridge": "microsoft-exchange",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checks": {},
    }

    # Check 1: Environment variables
    missing = check_env_vars()
    results["checks"]["env_vars"] = {
        "ok": len(missing) == 0,
        "missing": missing,
    }

    # Check 2: Certificate file
    cert = check_certificate()
    results["checks"]["certificate"] = cert

    if quick:
        all_ok = results["checks"]["env_vars"]["ok"] and cert["ok"]
        results["status"] = "healthy" if all_ok else "unhealthy"
        print(json.dumps(results, indent=2))
        sys.exit(0 if all_ok else 1)

    # Check 3: Exchange Online connectivity (full check only)
    conn = check_connectivity()
    results["checks"]["connectivity"] = conn

    all_ok = (
        results["checks"]["env_vars"]["ok"]
        and cert["ok"]
        and conn.get("ok", False)
    )
    results["status"] = "healthy" if all_ok else "unhealthy"

    if conn.get("organization"):
        results["organization"] = conn["organization"]

    print(json.dumps(results, indent=2))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
