#!/usr/bin/env python3
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
Teams Bot Bridge Health Check -- validates environment, Graph API access,
and bot server status. Used by Docker healthcheck and operator diagnostics.

Usage:
  python3 teams_check.py           Full check
  python3 teams_check.py --quick   Env vars + bot server ping only
"""

import json
import os
import sys

try:
    from dotenv import load_dotenv

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass


def check_env() -> dict:
    required = ["TEAMS_BOT_APP_ID", "TEAMS_BOT_APP_SECRET", "TEAMS_BOT_TENANT_ID"]
    missing = [v for v in required if not os.environ.get(v)]
    mode = os.environ.get("TEAMS_BOT_MODE", "webhook")

    result = {"env_ok": len(missing) == 0, "mode": mode}
    if missing:
        result["missing"] = missing

    if mode == "webhook" and not os.environ.get("CLOUDFLARE_TUNNEL_TOKEN"):
        result["warning"] = "Webhook mode but CLOUDFLARE_TUNNEL_TOKEN not set"

    return result


def check_bot_server() -> dict:
    """Ping the local bot server health endpoint."""
    import requests

    port = int(os.environ.get("TEAMS_BOT_PORT", 3978))
    try:
        resp = requests.get(f"http://localhost:{port}/api/health", timeout=5)
        return resp.json()
    except Exception as exc:
        return {"status": "unreachable", "error": str(exc)}


def check_graph_api() -> dict:
    """Test Graph API token acquisition and basic access."""
    try:
        from teams_client import TeamsClient

        client = TeamsClient()
        return client.test_connection()
    except Exception as exc:
        return {"graph_api": False, "error": str(exc)}


def main():
    quick = "--quick" in sys.argv
    results = {"check": "teams-bot-bridge"}

    env_result = check_env()
    results["environment"] = env_result

    if not env_result["env_ok"]:
        print(json.dumps(results, indent=2))
        sys.exit(1)

    mode = env_result["mode"]

    if mode == "webhook":
        results["bot_server"] = check_bot_server()

    if not quick:
        results["graph_api"] = check_graph_api()

    ok = env_result["env_ok"]
    if mode == "webhook":
        bot_ok = results.get("bot_server", {}).get("status") == "ok"
        ok = ok and bot_ok

    if not quick:
        ok = ok and results.get("graph_api", {}).get("graph_api", False)

    results["healthy"] = ok
    print(json.dumps(results, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
