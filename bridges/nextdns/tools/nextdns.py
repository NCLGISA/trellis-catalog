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

"""NextDNS unified CLI.

Subcommands:
    profiles    list|get|create|delete
    security    get|update
    privacy     get|update|blocklists
    parental    get|update
    denylist    list|add|remove|toggle
    allowlist   list|add|remove|toggle
    settings    get|update
    analytics   status|domains|reasons|devices|protocols|querytypes|ips|
                destinations|dnssec|encryption|ipversions
    logs        query|clear

Usage:
    python3 nextdns.py profiles list
    python3 nextdns.py profiles get --profile abc123
    python3 nextdns.py security get
    python3 nextdns.py analytics status --from=-7d --limit 20
    python3 nextdns.py logs query --search facebook --status blocked --limit 50
    python3 nextdns.py denylist add --domain malware.example.com
    python3 nextdns.py allowlist add --domain trusted.example.com
"""

import argparse
import json
import os
import sys

try:
    from nextdns_client import NextDNSClient
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from nextdns_client import NextDNSClient


def _out(data):
    print(json.dumps(data, indent=2))


# ===== Profiles ============================================================

def cmd_profiles(client, args):
    action = args.action

    if action == "list":
        profiles = client.list_profiles()
        _out({"count": len(profiles), "profiles": profiles})

    elif action == "get":
        data = client.get_profile()
        _out(data)

    elif action == "create":
        if not args.name:
            print("Error: --name is required for profiles create", file=sys.stderr)
            sys.exit(1)
        result = client.create_profile({"name": args.name})
        _out(result)

    elif action == "delete":
        target = args.target_profile
        if not target:
            print("Error: --target-profile is required for profiles delete", file=sys.stderr)
            sys.exit(1)
        result = client.delete_profile(target)
        _out({"profile": target, "status": "deleted"})


# ===== Security ============================================================

def cmd_security(client, args):
    action = args.action

    if action == "get":
        data = client.get_security()
        _out(data)

    elif action == "update":
        if not args.json_body:
            print("Error: --json is required for security update", file=sys.stderr)
            sys.exit(1)
        body = json.loads(args.json_body)
        result = client.update_security(body)
        _out(result)


# ===== Privacy =============================================================

def cmd_privacy(client, args):
    action = args.action

    if action == "get":
        data = client.get_privacy()
        _out(data)

    elif action == "update":
        if not args.json_body:
            print("Error: --json is required for privacy update", file=sys.stderr)
            sys.exit(1)
        body = json.loads(args.json_body)
        result = client.update_privacy(body)
        _out(result)

    elif action == "blocklists":
        data = client.get_blocklists()
        _out(data)

    elif action == "add-blocklist":
        if not args.blocklist_id:
            print("Error: --blocklist-id is required", file=sys.stderr)
            sys.exit(1)
        result = client.add_blocklist(args.blocklist_id)
        _out(result)

    elif action == "remove-blocklist":
        if not args.blocklist_id:
            print("Error: --blocklist-id is required", file=sys.stderr)
            sys.exit(1)
        result = client.remove_blocklist(args.blocklist_id)
        _out({"blocklist": args.blocklist_id, "status": "removed"})


# ===== Parental Controls ===================================================

def cmd_parental(client, args):
    action = args.action

    if action == "get":
        data = client.get_parental_control()
        _out(data)

    elif action == "update":
        if not args.json_body:
            print("Error: --json is required for parental update", file=sys.stderr)
            sys.exit(1)
        body = json.loads(args.json_body)
        result = client.update_parental_control(body)
        _out(result)


# ===== Denylist ============================================================

def cmd_denylist(client, args):
    action = args.action

    if action == "list":
        data = client.get_denylist()
        _out(data)

    elif action == "add":
        if not args.domain:
            print("Error: --domain is required for denylist add", file=sys.stderr)
            sys.exit(1)
        result = client.add_denylist(args.domain, active=not args.inactive)
        _out(result)

    elif action == "remove":
        if not args.domain:
            print("Error: --domain is required for denylist remove", file=sys.stderr)
            sys.exit(1)
        result = client.remove_denylist(args.domain)
        _out({"domain": args.domain, "status": "removed"})

    elif action == "toggle":
        if not args.domain:
            print("Error: --domain is required for denylist toggle", file=sys.stderr)
            sys.exit(1)
        active = not args.inactive
        result = client.toggle_denylist(args.domain, active)
        _out({"domain": args.domain, "active": active})


# ===== Allowlist ===========================================================

def cmd_allowlist(client, args):
    action = args.action

    if action == "list":
        data = client.get_allowlist()
        _out(data)

    elif action == "add":
        if not args.domain:
            print("Error: --domain is required for allowlist add", file=sys.stderr)
            sys.exit(1)
        result = client.add_allowlist(args.domain, active=not args.inactive)
        _out(result)

    elif action == "remove":
        if not args.domain:
            print("Error: --domain is required for allowlist remove", file=sys.stderr)
            sys.exit(1)
        result = client.remove_allowlist(args.domain)
        _out({"domain": args.domain, "status": "removed"})

    elif action == "toggle":
        if not args.domain:
            print("Error: --domain is required for allowlist toggle", file=sys.stderr)
            sys.exit(1)
        active = not args.inactive
        result = client.toggle_allowlist(args.domain, active)
        _out({"domain": args.domain, "active": active})


# ===== Settings ============================================================

def cmd_settings(client, args):
    action = args.action

    if action == "get":
        data = client.get_settings()
        _out(data)

    elif action == "update":
        if not args.json_body:
            print("Error: --json is required for settings update", file=sys.stderr)
            sys.exit(1)
        body = json.loads(args.json_body)
        result = client.update_settings(body)
        _out(result)


# ===== Analytics ===========================================================

def cmd_analytics(client, args):
    endpoint_map = {
        "status": "analytics_status",
        "domains": "analytics_domains",
        "reasons": "analytics_reasons",
        "devices": "analytics_devices",
        "protocols": "analytics_protocols",
        "querytypes": "analytics_query_types",
        "ips": "analytics_ips",
        "destinations": "analytics_destinations",
        "dnssec": "analytics_dnssec",
        "encryption": "analytics_encryption",
        "ipversions": "analytics_ip_versions",
    }

    method_name = endpoint_map.get(args.endpoint)
    if not method_name:
        print(f"Error: unknown analytics endpoint '{args.endpoint}'", file=sys.stderr)
        sys.exit(1)

    params = {}
    if args.time_from:
        params["from"] = args.time_from
    if args.time_to:
        params["to"] = args.time_to
    if args.limit:
        params["limit"] = args.limit
    if args.device:
        params["device"] = args.device
    if args.status:
        params["status"] = args.status

    method = getattr(client, method_name)

    if args.endpoint == "destinations" and args.dest_type:
        data = method(dest_type=args.dest_type, **params)
    else:
        data = method(**params)

    _out(data)


# ===== Logs ================================================================

def cmd_logs(client, args):
    action = args.action

    if action == "query":
        params = {}
        if args.time_from:
            params["from"] = args.time_from
        if args.time_to:
            params["to"] = args.time_to
        if args.limit:
            params["limit"] = args.limit
        if args.search:
            params["search"] = args.search
        if args.status:
            params["status"] = args.status
        if args.device:
            params["device"] = args.device
        if args.raw:
            params["raw"] = 1
        data = client.logs(**params)
        _out(data)

    elif action == "clear":
        result = client.clear_logs()
        _out(result)


# ===== Main ================================================================

def main():
    parser = argparse.ArgumentParser(
        prog="nextdns.py",
        description="NextDNS unified CLI",
    )
    parser.add_argument("--profile", default=None, help="Profile ID (overrides NEXTDNS_PROFILE)")
    sub = parser.add_subparsers(dest="command", required=True)

    # -- profiles
    p_profiles = sub.add_parser("profiles", help="Manage profiles")
    p_profiles.add_argument("action", choices=["list", "get", "create", "delete"])
    p_profiles.add_argument("--name", help="Profile name (for create)")
    p_profiles.add_argument("--target-profile", help="Profile ID to delete")

    # -- security
    p_security = sub.add_parser("security", help="Security settings")
    p_security.add_argument("action", choices=["get", "update"])
    p_security.add_argument("--json", dest="json_body", help="JSON body for update")

    # -- privacy
    p_privacy = sub.add_parser("privacy", help="Privacy settings and blocklists")
    p_privacy.add_argument("action", choices=["get", "update", "blocklists", "add-blocklist", "remove-blocklist"])
    p_privacy.add_argument("--json", dest="json_body", help="JSON body for update")
    p_privacy.add_argument("--blocklist-id", help="Blocklist ID (e.g. nextdns-recommended, oisd)")

    # -- parental
    p_parental = sub.add_parser("parental", help="Parental controls")
    p_parental.add_argument("action", choices=["get", "update"])
    p_parental.add_argument("--json", dest="json_body", help="JSON body for update")

    # -- denylist
    p_deny = sub.add_parser("denylist", help="Manage denied domains")
    p_deny.add_argument("action", choices=["list", "add", "remove", "toggle"])
    p_deny.add_argument("--domain", help="Domain name")
    p_deny.add_argument("--inactive", action="store_true", help="Add or toggle as inactive")

    # -- allowlist
    p_allow = sub.add_parser("allowlist", help="Manage allowed domains")
    p_allow.add_argument("action", choices=["list", "add", "remove", "toggle"])
    p_allow.add_argument("--domain", help="Domain name")
    p_allow.add_argument("--inactive", action="store_true", help="Add or toggle as inactive")

    # -- settings
    p_settings = sub.add_parser("settings", help="Profile settings (logs, performance, block page)")
    p_settings.add_argument("action", choices=["get", "update"])
    p_settings.add_argument("--json", dest="json_body", help="JSON body for update")

    # -- analytics
    p_analytics = sub.add_parser("analytics", help="Query analytics")
    p_analytics.add_argument("endpoint", choices=[
        "status", "domains", "reasons", "devices", "protocols",
        "querytypes", "ips", "destinations", "dnssec", "encryption", "ipversions",
    ])
    p_analytics.add_argument("--from", dest="time_from", help="Start date (e.g. -7d, -24h, ISO 8601)")
    p_analytics.add_argument("--to", dest="time_to", help="End date (e.g. now, ISO 8601)")
    p_analytics.add_argument("--limit", type=int, help="Max results (1-500)")
    p_analytics.add_argument("--device", help="Filter by device ID")
    p_analytics.add_argument("--status", choices=["default", "blocked", "allowed"], help="Filter by status (domains only)")
    p_analytics.add_argument("--dest-type", choices=["countries", "gafam"], default="countries", help="Destination grouping")

    # -- logs
    p_logs = sub.add_parser("logs", help="DNS query logs")
    p_logs.add_argument("action", choices=["query", "clear"])
    p_logs.add_argument("--from", dest="time_from", help="Start date (inclusive)")
    p_logs.add_argument("--to", dest="time_to", help="End date (exclusive)")
    p_logs.add_argument("--limit", type=int, default=100, help="Max results (10-1000, default: 100)")
    p_logs.add_argument("--search", help="Domain search filter (e.g. facebook)")
    p_logs.add_argument("--status", choices=["default", "error", "blocked", "allowed"], help="Filter by status")
    p_logs.add_argument("--device", help="Filter by device ID")
    p_logs.add_argument("--raw", action="store_true", help="Show all query types (not just navigational)")

    args = parser.parse_args()
    client = NextDNSClient(profile_id=args.profile)

    commands = {
        "profiles": cmd_profiles,
        "security": cmd_security,
        "privacy": cmd_privacy,
        "parental": cmd_parental,
        "denylist": cmd_denylist,
        "allowlist": cmd_allowlist,
        "settings": cmd_settings,
        "analytics": cmd_analytics,
        "logs": cmd_logs,
    }
    commands[args.command](client, args)


if __name__ == "__main__":
    main()
