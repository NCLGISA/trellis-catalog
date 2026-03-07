"""
Verizon MyBusiness Bridge -- Session Management

REST-based authentication using ForgeRock callback tree.
Supports three modes:

  Interactive:  auth_session.py login          (prompts for SMS code on stdin)
  Single-shot:  auth_session.py login --mfa-code 123456
  Two-phase:    auth_session.py initiate       (triggers SMS, saves state)
                auth_session.py complete --code 123456  (submits code)

Also: status, refresh, keepalive, export
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SESSION_DIR = Path(os.getenv("VZ_SESSION_DIR", "/opt/bridge/data/session"))
COOKIES_FILE = SESSION_DIR / "cookies.json"
AUTH_STATE_FILE = SESSION_DIR / "auth_state.json"


def require_credentials() -> tuple[str, str]:
    """Check for VZ_USERNAME and VZ_PASSWORD in environment (injected by bridge_credentials)."""
    username = os.getenv("VZ_USERNAME", "").strip()
    password = os.getenv("VZ_PASSWORD", "").strip()
    if not username or not password:
        print("ERROR: Verizon credentials not configured for this operator.")
        print("Set up credentials via:")
        print('  bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_USERNAME", value="...")')
        print('  bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_PASSWORD", value="...")')
        sys.exit(1)
    return username, password


def save_cookies(cookies: list[dict]):
    """Persist session cookies to disk."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cookie_count": len(cookies),
    }
    (SESSION_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"{len(cookies)} cookies saved to {COOKIES_FILE}")


def login(mfa_code: str | None = None):
    """
    Full login flow using ForgeRock REST auth.

    If mfa_code is provided, it's submitted immediately.
    Otherwise, prompts on stdin when the SMS arrives.
    """
    sys.path.insert(0, str(Path(__file__).parent))
    from forgerock_auth import ForgeRockAuth, ForgeRockAuthError, MFARequiredError

    username, password = require_credentials()

    print(f"Authenticating as {username}...")
    with ForgeRockAuth() as auth:
        try:
            result = auth.authenticate(username, password, mfa_code=mfa_code)
            save_cookies(result["cookies"])
            print("Session established successfully.")
            return

        except MFARequiredError as e:
            if mfa_code:
                print(f"ERROR: MFA code was provided but another MFA prompt appeared: {e}")
                sys.exit(1)

            print(f"\n{e}")
            try:
                code = input("Enter SMS code: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                sys.exit(1)

            if not code:
                print("No code entered. Aborting.")
                sys.exit(1)

            try:
                result = auth.complete_mfa(e.auth_state, code)
                save_cookies(result["cookies"])
                print("Session established successfully.")
            except ForgeRockAuthError as e2:
                print(f"ERROR: MFA completion failed: {e2}")
                sys.exit(1)

        except ForgeRockAuthError as e:
            print(f"ERROR: Authentication failed: {e}")
            sys.exit(1)


def initiate():
    """
    Phase 1 of two-phase auth: submit credentials, trigger SMS, save state.

    The operator then runs `auth_session.py complete --code <code>`.
    """
    sys.path.insert(0, str(Path(__file__).parent))
    from forgerock_auth import ForgeRockAuth, ForgeRockAuthError, MFARequiredError

    username, password = require_credentials()

    print(f"Authenticating as {username} (phase 1: initiate)...")
    with ForgeRockAuth() as auth:
        try:
            result = auth.authenticate(username, password, mfa_code=None)
            # Auth completed without MFA (rare but possible)
            save_cookies(result["cookies"])
            print("Session established without MFA.")
            return

        except MFARequiredError as e:
            SESSION_DIR.mkdir(parents=True, exist_ok=True)
            AUTH_STATE_FILE.write_text(json.dumps(e.auth_state, indent=2))
            print(f"\n{e}")
            print(f"Auth state saved to {AUTH_STATE_FILE}")
            print(f"\nRun: python3 auth_session.py complete --code <sms_code>")

        except ForgeRockAuthError as e:
            print(f"ERROR: Authentication failed: {e}")
            sys.exit(1)


def complete(mfa_code: str):
    """
    Phase 2 of two-phase auth: submit SMS code using saved auth state.
    """
    sys.path.insert(0, str(Path(__file__).parent))
    from forgerock_auth import ForgeRockAuth, ForgeRockAuthError

    if not AUTH_STATE_FILE.exists():
        print("ERROR: No auth state found. Run: python3 auth_session.py initiate")
        sys.exit(1)

    auth_state = json.loads(AUTH_STATE_FILE.read_text())
    print(f"Completing authentication with SMS code...")

    with ForgeRockAuth() as auth:
        try:
            result = auth.complete_mfa(auth_state, mfa_code)
            save_cookies(result["cookies"])
            print("Session established successfully.")
            AUTH_STATE_FILE.unlink(missing_ok=True)
        except ForgeRockAuthError as e:
            print(f"ERROR: MFA completion failed: {e}")
            sys.exit(1)


def status():
    """Check session validity and credential configuration."""
    has_creds = bool(os.getenv("VZ_USERNAME")) and bool(os.getenv("VZ_PASSWORD"))
    print(f"Credentials configured: {'Yes' if has_creds else 'No'}")

    if not COOKIES_FILE.exists():
        print("Session: NO COOKIES (not authenticated)")
        if not has_creds:
            print("\nSet up credentials via:")
            print('  bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_USERNAME", value="...")')
            print('  bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_PASSWORD", value="...")')
        else:
            print("\nRun: python3 auth_session.py login")
        sys.exit(1)

    sys.path.insert(0, str(Path(__file__).parent))
    from verizon_client import VerizonClient

    try:
        client = VerizonClient()
    except FileNotFoundError:
        print("Session: NO COOKIES")
        sys.exit(1)

    alive = client.is_session_alive()
    mtime = datetime.fromtimestamp(COOKIES_FILE.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(timezone.utc) - mtime

    print(f"Session status: {'ALIVE' if alive else 'EXPIRED'}")
    print(f"Cookies saved: {mtime.isoformat()}")
    print(f"Session age: {age}")

    if not alive:
        print("\nSession expired. Re-authenticate:")
        print("  python3 auth_session.py initiate")
        print("  python3 auth_session.py complete --code <sms_code>")
        sys.exit(1)


def refresh():
    """Keepalive ping."""
    sys.path.insert(0, str(Path(__file__).parent))
    from verizon_client import VerizonClient

    try:
        client = VerizonClient()
        alive = client.keepalive_ping()
        print(f"Keepalive: {'OK' if alive else 'EXPIRED'}")
        if not alive:
            sys.exit(1)
    except Exception as e:
        print(f"Keepalive failed: {e}")
        sys.exit(1)


def keepalive():
    """Run keepalive daemon (pings every 5 minutes)."""
    sys.path.insert(0, str(Path(__file__).parent))
    from verizon_client import VerizonClient

    interval = 300
    print(f"Keepalive daemon: pinging every {interval}s. Ctrl+C to stop.")

    client = VerizonClient()
    while True:
        alive = client.keepalive_ping()
        ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        print(f"  {ts} -- {'ALIVE' if alive else 'EXPIRED'}", flush=True)
        if not alive:
            print("Session expired. Re-authenticate.")
            sys.exit(1)
        time.sleep(interval)


def export_cookies():
    """Print cookies for debugging."""
    if not COOKIES_FILE.exists():
        print("No cookies found.")
        sys.exit(1)
    cookies = json.loads(COOKIES_FILE.read_text())
    for c in cookies:
        val = c.get("value", "")
        display = val[:40] + "..." if len(val) > 40 else val
        print(f"  {c['name']}: {display} (domain={c.get('domain', '')})")
    print(f"\nTotal: {len(cookies)} cookies")


def main():
    if len(sys.argv) < 2:
        print("Usage: auth_session.py <command> [options]")
        print()
        print("Commands:")
        print("  login [--mfa-code CODE]  Full login (interactive or with known code)")
        print("  initiate                 Phase 1: submit credentials, trigger SMS")
        print("  complete --code CODE     Phase 2: submit SMS code")
        print("  status                   Check session validity and credential config")
        print("  refresh                  Keepalive ping")
        print("  keepalive                Start keepalive daemon")
        print("  export                   Print cookies for debugging")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "login":
        mfa_code = None
        if "--mfa-code" in sys.argv:
            idx = sys.argv.index("--mfa-code")
            if idx + 1 < len(sys.argv):
                mfa_code = sys.argv[idx + 1]
            else:
                print("ERROR: --mfa-code requires a value")
                sys.exit(1)
        login(mfa_code)

    elif cmd == "initiate":
        initiate()

    elif cmd == "complete":
        code = None
        if "--code" in sys.argv:
            idx = sys.argv.index("--code")
            if idx + 1 < len(sys.argv):
                code = sys.argv[idx + 1]
        if not code:
            print("ERROR: --code <sms_code> is required")
            print("Usage: auth_session.py complete --code 123456")
            sys.exit(1)
        complete(code)

    elif cmd == "status":
        status()

    elif cmd == "refresh":
        refresh()

    elif cmd == "keepalive":
        keepalive()

    elif cmd == "export":
        export_cookies()

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
