#!/usr/bin/env python3
"""
Munis Bridge Health Check

Validates:
  1. Required shared environment variables (MUNIS_DB_HOST, MUNIS_DB_NAME)
  2. ODBC Driver 18 for SQL Server is installed
  3. TCP connectivity to the Munis SQL Server host
  4. (Full mode only) Database authentication and metadata via per-operator creds

Usage:
  python3 munis_check.py          # Full check (requires per-operator creds)
  python3 munis_check.py --quick  # Infrastructure-only (no auth needed)
"""

import os
import sys
import socket
import subprocess


def check_env():
    host = os.getenv("MUNIS_DB_HOST", "")
    db = os.getenv("MUNIS_DB_NAME", "")
    print(f"\n[1/4] Environment variables:")
    print(f"  MUNIS_DB_HOST: {'set (' + host + ')' if host else 'NOT SET'}")
    print(f"  MUNIS_DB_NAME: {'set (' + db + ')' if db else 'NOT SET'}")
    if not host or not db:
        print("  FAIL: Shared env vars must be set in docker-compose.yml")
        return False
    print("  PASS")
    return True


def check_driver():
    print("\n[2/4] ODBC Driver 18 for SQL Server:")
    try:
        import pyodbc
        drivers = pyodbc.drivers()
        found = any("ODBC Driver 18" in d for d in drivers)
        if found:
            print(f"  Installed drivers: {', '.join(drivers)}")
            print("  PASS")
            return True
        else:
            print(f"  Available drivers: {', '.join(drivers) if drivers else 'none'}")
            print("  FAIL: ODBC Driver 18 for SQL Server not found")
            return False
    except ImportError:
        print("  FAIL: pyodbc module not installed")
        return False


def check_tcp():
    host = os.getenv("MUNIS_DB_HOST", "")
    port = 1433
    print(f"\n[3/4] TCP connectivity to {host}:{port}:")
    if not host:
        print("  SKIP: MUNIS_DB_HOST not set")
        return False
    try:
        sock = socket.create_connection((host, port), timeout=10)
        sock.close()
        print("  PASS")
        return True
    except socket.timeout:
        print(f"  FAIL: Connection timed out (host may be unreachable via VPN)")
        return False
    except OSError as e:
        print(f"  FAIL: {e}")
        return False


def check_auth():
    user = os.getenv("MUNIS_DB_USER", "")
    print(f"\n[4/4] Database authentication:")
    if not user:
        print("  SKIP: No per-operator credentials available (MUNIS_DB_USER not set)")
        print("  Per-operator credentials are injected at runtime by Tendril Root")
        return True

    try:
        from munis_client import MunisClient
        client = MunisClient()
        result = client.test_connection()
        if result.get("ok"):
            print(f"  Server:    {result.get('server_version', 'unknown')}")
            print(f"  Database:  {result.get('database', 'unknown')}")
            print(f"  Tables:    {result.get('table_count', 'unknown')}")
            print("  PASS")
            return True
        else:
            print(f"  FAIL: {result.get('error', 'unknown error')}")
            return False
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def main():
    quick = "--quick" in sys.argv

    print("=" * 60)
    print("Munis Bridge Health Check" + (" (quick)" if quick else ""))
    print("=" * 60)

    env_ok = check_env()
    driver_ok = check_driver()
    tcp_ok = check_tcp() if env_ok else False

    if quick:
        print(f"\n[4/4] Database authentication:")
        print("  SKIP: Quick mode (infrastructure checks only)")
        auth_ok = True
    else:
        auth_ok = check_auth() if (env_ok and driver_ok and tcp_ok) else False

    print("\n" + "=" * 60)
    all_ok = env_ok and driver_ok and tcp_ok and auth_ok
    if all_ok:
        print("All checks passed. Munis bridge is operational.")
    else:
        print("One or more checks failed. See details above.")
    print("=" * 60)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
