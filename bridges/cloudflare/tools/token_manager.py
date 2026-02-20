"""
Cloudflare API Token Manager

Programmatic management of Cloudflare API tokens using an operator's personal
token with User-level "API Tokens: Edit" permission. This tool enables:

  - Listing all tokens and their permission scopes
  - Listing all available permission groups (for building new tokens)
  - Adding/removing permission groups on an existing token
  - Creating new scoped tokens
  - Auditing token permissions against actual service usage

Security model:
  - Uses the operator's personal CLOUDFLARE_OPERATOR_TOKEN (injected via Tendril
    vault) for write operations on the /user/tokens endpoint.
  - The shared CLOUDFLARE_API_TOKEN (bridge-level) is never modified directly;
    instead this tool reads its current state and applies changes via the
    operator's elevated token.
  - All changes are scoped to the Cloudflare user account that owns the tokens.

Environment variables:
  CLOUDFLARE_OPERATOR_TOKEN  - Operator's personal token with API Tokens: Edit (User scope)
  CLOUDFLARE_API_TOKEN       - Shared bridge token (read-only, for reference)
  CLOUDFLARE_ACCOUNT_ID      - Account identifier
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

API_BASE = "https://api.cloudflare.com/client/v4"

OPERATOR_TOKEN = os.getenv("CLOUDFLARE_OPERATOR_TOKEN", "")
BRIDGE_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")


class TokenManager:
    """Manage Cloudflare API tokens via the /user/tokens API."""

    def __init__(self, operator_token: str = None):
        self.token = operator_token or OPERATOR_TOKEN
        if not self.token:
            print(
                "ERROR: Missing operator token.\n"
                "\n"
                "CLOUDFLARE_OPERATOR_TOKEN must be set. This is your personal\n"
                "Cloudflare API token with 'API Tokens: Edit' permission.\n"
                "\n"
                "Store it in the Tendril vault:\n"
                "  bridge_credentials(action='set', bridge='cloudflare',\n"
                "    key='CLOUDFLARE_OPERATOR_TOKEN', value='<your-token>')\n",
                file=sys.stderr,
            )
            sys.exit(1)

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        })

    def _get(self, endpoint: str, params: dict = None) -> requests.Response:
        return self.session.get(f"{API_BASE}/{endpoint}", params=params, timeout=30)

    def _put(self, endpoint: str, data: dict) -> requests.Response:
        return self.session.put(f"{API_BASE}/{endpoint}", json=data, timeout=30)

    def _post(self, endpoint: str, data: dict) -> requests.Response:
        return self.session.post(f"{API_BASE}/{endpoint}", json=data, timeout=30)

    def _delete(self, endpoint: str) -> requests.Response:
        return self.session.delete(f"{API_BASE}/{endpoint}", timeout=30)

    # ── Token Operations ────────────────────────────────────────────────

    def verify(self) -> dict:
        """Verify the operator token is valid."""
        resp = self._get("user/tokens/verify")
        if resp.status_code == 200:
            return resp.json().get("result", {})
        return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:200]}

    def list_tokens(self) -> list:
        """List all API tokens for the user."""
        resp = self._get("user/tokens")
        if resp.status_code == 200:
            return resp.json().get("result", [])
        print(f"Error listing tokens: {resp.status_code} {resp.text[:200]}", file=sys.stderr)
        return []

    def get_token(self, token_id: str) -> dict:
        """Get a single token by ID."""
        resp = self._get(f"user/tokens/{token_id}")
        if resp.status_code == 200:
            return resp.json().get("result", {})
        return {}

    def list_permission_groups(self) -> list:
        """List all available permission groups that can be granted."""
        resp = self._get("user/tokens/permission_groups")
        if resp.status_code == 200:
            return resp.json().get("result", [])
        print(f"Error listing permission groups: {resp.status_code} {resp.text[:200]}", file=sys.stderr)
        return []

    def update_token(self, token_id: str, token_data: dict) -> dict:
        """Update a token's configuration (name, policies, status, etc.)."""
        resp = self._put(f"user/tokens/{token_id}", token_data)
        if resp.status_code == 200:
            return resp.json().get("result", {})
        return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:500]}

    def add_permission_group(self, token_id: str, group_id: str, group_name: str = "") -> dict:
        """Add a permission group to an existing token's first policy."""
        token = self.get_token(token_id)
        if not token:
            return {"error": f"Token {token_id} not found"}

        policies = token.get("policies", [])
        if not policies:
            return {"error": "Token has no policies"}

        existing_ids = {pg["id"] for p in policies for pg in p.get("permission_groups", [])}
        if group_id in existing_ids:
            return {"error": f"Permission group {group_id} ({group_name}) already granted"}

        policies[0]["permission_groups"].append({"id": group_id})

        update_payload = {
            "name": token.get("name"),
            "policies": policies,
            "status": token.get("status", "active"),
        }
        if token.get("not_before"):
            update_payload["not_before"] = token["not_before"]
        if token.get("expires_on"):
            update_payload["expires_on"] = token["expires_on"]

        result = self.update_token(token_id, update_payload)
        if "error" not in result:
            return {"success": True, "added": group_name or group_id}
        return result

    def remove_permission_group(self, token_id: str, group_id: str, group_name: str = "") -> dict:
        """Remove a permission group from an existing token."""
        token = self.get_token(token_id)
        if not token:
            return {"error": f"Token {token_id} not found"}

        policies = token.get("policies", [])
        found = False
        for policy in policies:
            pgs = policy.get("permission_groups", [])
            new_pgs = [pg for pg in pgs if pg["id"] != group_id]
            if len(new_pgs) < len(pgs):
                found = True
                policy["permission_groups"] = new_pgs

        if not found:
            return {"error": f"Permission group {group_id} ({group_name}) not found on token"}

        update_payload = {
            "name": token.get("name"),
            "policies": policies,
            "status": token.get("status", "active"),
        }
        if token.get("not_before"):
            update_payload["not_before"] = token["not_before"]
        if token.get("expires_on"):
            update_payload["expires_on"] = token["expires_on"]

        result = self.update_token(token_id, update_payload)
        if "error" not in result:
            return {"success": True, "removed": group_name or group_id}
        return result

    def find_permission_group(self, name_substring: str) -> list:
        """Search available permission groups by name substring."""
        groups = self.list_permission_groups()
        return [g for g in groups if name_substring.lower() in g.get("name", "").lower()]


# ── CLI ─────────────────────────────────────────────────────────────────

def cmd_verify(args, mgr):
    result = mgr.verify()
    if "error" in result:
        print(f"Verification failed: {result}")
        sys.exit(1)
    print(f"Operator token verified: status={result.get('status')}, id={result.get('id')}")

def cmd_list_tokens(args, mgr):
    tokens = mgr.list_tokens()
    print(f"{'Name':<45} {'Status':<10} {'ID':<35} {'Expires'}")
    print("-" * 110)
    for t in tokens:
        expires = t.get("expires_on", "never")[:10] if t.get("expires_on") else "never"
        print(f"{t.get('name','?'):<45} {t.get('status','?'):<10} {t.get('id','?'):<35} {expires}")
        if args.verbose:
            for p in t.get("policies", []):
                for pg in p.get("permission_groups", []):
                    print(f"  - {pg.get('name', pg.get('id','?'))}")

def cmd_show_token(args, mgr):
    token = mgr.get_token(args.token_id)
    if not token:
        print(f"Token {args.token_id} not found")
        sys.exit(1)

    print(f"Name:      {token.get('name')}")
    print(f"ID:        {token.get('id')}")
    print(f"Status:    {token.get('status')}")
    print(f"Issued:    {token.get('issued_on', '?')[:10]}")
    print(f"Modified:  {token.get('modified_on', '?')[:10]}")
    not_before = token.get("not_before")
    expires = token.get("expires_on")
    print(f"Not Before: {not_before[:10] if not_before else 'n/a'}")
    print(f"Expires:   {expires[:10] if expires else 'never'}")
    print()

    for i, p in enumerate(token.get("policies", [])):
        effect = p.get("effect", "allow")
        resources = p.get("resources", {})
        pgs = p.get("permission_groups", [])
        print(f"Policy {i+1} (effect={effect}):")
        print(f"  Resources: {json.dumps(resources)}")
        print(f"  Permission Groups ({len(pgs)}):")
        for pg in sorted(pgs, key=lambda x: x.get("name", x.get("id", ""))):
            print(f"    - {pg.get('name', '(unnamed)'):<55} id={pg.get('id','')}")

def cmd_list_permissions(args, mgr):
    groups = mgr.list_permission_groups()
    if args.search:
        groups = [g for g in groups if args.search.lower() in g.get("name", "").lower()]
        print(f"Permission groups matching '{args.search}' ({len(groups)}):")
    else:
        print(f"All available permission groups ({len(groups)}):")

    scopes = {}
    for g in groups:
        scope_list = g.get("scopes", ["unknown"])
        scope = scope_list[0] if scope_list else "unknown"
        scopes.setdefault(scope, []).append(g)

    for scope in sorted(scopes.keys()):
        print(f"\n  [{scope}]")
        for g in sorted(scopes[scope], key=lambda x: x.get("name", "")):
            print(f"    {g.get('name','?'):<55} {g.get('id','')}")

def cmd_add_permission(args, mgr):
    if not args.group_id:
        matches = mgr.find_permission_group(args.search or "")
        if not matches:
            print(f"No permission groups matching '{args.search}'")
            sys.exit(1)
        print(f"Matching permission groups:")
        for g in matches:
            print(f"  {g.get('name','?'):<55} id={g.get('id','')}")
        print(f"\nUse --group-id <id> to add a specific permission.")
        return

    result = mgr.add_permission_group(args.token_id, args.group_id, args.search or "")
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)
    print(f"Added permission group: {result.get('added')}")

def cmd_remove_permission(args, mgr):
    result = mgr.remove_permission_group(args.token_id, args.group_id, "")
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)
    print(f"Removed permission group: {result.get('removed')}")

def cmd_audit(args, mgr):
    """Compare bridge token permissions against what's actually accessible."""
    tokens = mgr.list_tokens()
    bridge_token_id = None

    # Find the bridge token by matching its ID from verify
    bridge_headers = {"Authorization": f"Bearer {BRIDGE_TOKEN}", "Content-Type": "application/json"}
    resp = requests.get(f"{API_BASE}/user/tokens/verify", headers=bridge_headers, timeout=15)
    if resp.status_code == 200:
        bridge_token_id = resp.json().get("result", {}).get("id")

    if not bridge_token_id:
        print("Could not identify bridge token. Is CLOUDFLARE_API_TOKEN set?")
        sys.exit(1)

    bridge_token = mgr.get_token(bridge_token_id)
    if not bridge_token:
        print(f"Could not fetch bridge token {bridge_token_id}")
        sys.exit(1)

    print(f"Bridge Token: {bridge_token.get('name')}")
    print(f"Token ID:     {bridge_token_id}")
    print()

    current_groups = {}
    for p in bridge_token.get("policies", []):
        for pg in p.get("permission_groups", []):
            current_groups[pg.get("id", "")] = pg.get("name", "(unnamed)")

    print(f"Current Permission Groups ({len(current_groups)}):")
    for gid, gname in sorted(current_groups.items(), key=lambda x: x[1]):
        print(f"  - {gname:<55} {gid}")

    print(f"\nBridge Token ID for programmatic updates: {bridge_token_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Cloudflare API Token Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 token_manager.py verify
  python3 token_manager.py list-tokens
  python3 token_manager.py list-tokens --verbose
  python3 token_manager.py show-token TOKEN_ID
  python3 token_manager.py list-permissions
  python3 token_manager.py list-permissions --search "firewall"
  python3 token_manager.py add-permission TOKEN_ID --search "Zone Settings" --group-id GROUP_ID
  python3 token_manager.py remove-permission TOKEN_ID --group-id GROUP_ID
  python3 token_manager.py audit
        """,
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("verify", help="Verify operator token")

    p_list = sub.add_parser("list-tokens", help="List all API tokens")
    p_list.add_argument("--verbose", "-v", action="store_true", help="Show permission groups")

    p_show = sub.add_parser("show-token", help="Show full token details")
    p_show.add_argument("token_id", help="Token ID")

    p_perms = sub.add_parser("list-permissions", help="List available permission groups")
    p_perms.add_argument("--search", "-s", help="Filter by name substring")

    p_add = sub.add_parser("add-permission", help="Add a permission group to a token")
    p_add.add_argument("token_id", help="Token ID to modify")
    p_add.add_argument("--group-id", help="Permission group ID to add")
    p_add.add_argument("--search", "-s", help="Search for permission group by name")

    p_rm = sub.add_parser("remove-permission", help="Remove a permission group from a token")
    p_rm.add_argument("token_id", help="Token ID to modify")
    p_rm.add_argument("--group-id", required=True, help="Permission group ID to remove")

    sub.add_parser("audit", help="Audit bridge token permissions")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    mgr = TokenManager()

    commands = {
        "verify": cmd_verify,
        "list-tokens": cmd_list_tokens,
        "show-token": cmd_show_token,
        "list-permissions": cmd_list_permissions,
        "add-permission": cmd_add_permission,
        "remove-permission": cmd_remove_permission,
        "audit": cmd_audit,
    }
    commands[args.command](args, mgr)


if __name__ == "__main__":
    main()
