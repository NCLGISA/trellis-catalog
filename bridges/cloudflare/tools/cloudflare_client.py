"""
Cloudflare REST API v4 Client

Provides authenticated access to the Cloudflare API for your Cloudflare account
with automatic pagination, rate-limit handling, and methods organized by service area:

  - Core: Zones, DNS, SSL/TLS, Page Rules, Firewall, Caching
  - Tunnels: Cloudflare Tunnel management and routing
  - Zero Trust: Access Applications, Policies, Service Tokens, Gateway
  - Email: Email Routing rules and settings

Authentication uses a scoped API token (Bearer) with Edit access across all
active service areas. The token supports both read and write operations.

  - Created in Cloudflare Dashboard > My Profile > API Tokens
  - Tokens are long-lived (no refresh needed)
  - Scoped to specific permissions per the README

Environment variables (set in docker-compose.yml or .env):
  CLOUDFLARE_API_TOKEN    - Scoped API token (Edit access)
  CLOUDFLARE_ACCOUNT_ID   - Account identifier
  CLOUDFLARE_DOMAIN       - Default zone domain (optional, default: example.com)
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")

API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareClient:
    """Cloudflare REST API v4 client with pagination and rate-limit handling."""

    def __init__(
        self,
        api_token: str = None,
        account_id: str = None,
    ):
        self.api_token = api_token or API_TOKEN
        self.account_id = account_id or ACCOUNT_ID

        if not self.api_token:
            print(
                "ERROR: Missing Cloudflare credentials.\n"
                "\n"
                "Required environment variables:\n"
                "  CLOUDFLARE_API_TOKEN\n"
                "  CLOUDFLARE_ACCOUNT_ID\n"
                "\n"
                "Create an API token in the Cloudflare Dashboard:\n"
                "  My Profile > API Tokens > Create Token\n",
                file=sys.stderr,
            )
            sys.exit(1)

        self.session = requests.Session()

    # ── Auth Headers ────────────────────────────────────────────────────

    def _auth_headers(self) -> dict:
        """Return headers with Bearer token."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    # ── Core HTTP Methods ───────────────────────────────────────────────

    def _request(
        self, method: str, endpoint: str, **kwargs
    ) -> requests.Response:
        """Make an API request with auth, rate-limit retry."""
        url = endpoint if endpoint.startswith("http") else f"{API_BASE}/{endpoint.lstrip('/')}"
        max_retries = 3

        for attempt in range(max_retries):
            kwargs["headers"] = self._auth_headers()
            resp = self.session.request(method, url, timeout=60, **kwargs)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                print(f"  Rate limited. Waiting {retry_after}s...", file=sys.stderr)
                time.sleep(retry_after)
                continue

            return resp

        return resp

    def get(self, endpoint: str, params: dict = None) -> requests.Response:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("POST", endpoint, json=json_data)

    def patch(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("PATCH", endpoint, json=json_data)

    def put(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("PUT", endpoint, json=json_data)

    def delete(self, endpoint: str, params: dict = None) -> requests.Response:
        return self._request("DELETE", endpoint, params=params)

    # ── Pagination Helper ───────────────────────────────────────────────

    def get_all(
        self,
        endpoint: str,
        key: str = "result",
        params: dict = None,
        per_page: int = 50,
        max_pages: int = 100,
    ) -> list:
        """
        Paginate through all results for a list endpoint.

        Cloudflare uses page/per_page pagination with result_info metadata.
        `key` is the JSON key containing the array (usually 'result').
        """
        params = dict(params or {})
        params["per_page"] = per_page
        results = []

        for page_num in range(1, max_pages + 1):
            params["page"] = page_num
            resp = self.get(endpoint, params=params)

            if resp.status_code != 200:
                print(
                    f"  Error fetching {endpoint}: {resp.status_code} {resp.text[:200]}",
                    file=sys.stderr,
                )
                break

            data = resp.json()
            items = data.get(key, [])
            results.extend(items)

            result_info = data.get("result_info", {})
            total_pages = result_info.get("total_pages", 1)
            if page_num >= total_pages:
                break

        return results

    # ── Token Verification ──────────────────────────────────────────────

    def verify_token(self) -> dict:
        """Verify the API token is valid and active."""
        resp = self.get("user/tokens/verify")
        if resp.status_code == 200:
            data = resp.json()
            return {"ok": True, **data.get("result", {})}
        return {"ok": False, "status": resp.status_code, "error": resp.text[:200]}

    # ── Zones ───────────────────────────────────────────────────────────

    def list_zones(self, name: str = None) -> list:
        """List all zones. Optionally filter by domain name."""
        params = {}
        if name:
            params["name"] = name
        return self.get_all("zones", params=params)

    def get_zone(self, zone_id: str) -> dict:
        """Get a single zone by ID."""
        resp = self.get(f"zones/{zone_id}")
        resp.raise_for_status()
        return resp.json().get("result", {})

    def find_zone_id(self, domain: str = None) -> str:
        """Find the zone ID for a domain name."""
        domain = domain or os.environ.get("CLOUDFLARE_DOMAIN", "example.com")
        zones = self.list_zones(name=domain)
        for z in zones:
            if z.get("name") == domain:
                return z["id"]
        return ""

    # ── DNS Records ─────────────────────────────────────────────────────

    def list_dns_records(
        self, zone_id: str, record_type: str = None, name: str = None
    ) -> list:
        """List DNS records for a zone. Optionally filter by type or name."""
        params = {}
        if record_type:
            params["type"] = record_type
        if name:
            params["name"] = name
        return self.get_all(f"zones/{zone_id}/dns_records", params=params)

    def get_dns_record(self, zone_id: str, record_id: str) -> dict:
        """Get a single DNS record."""
        resp = self.get(f"zones/{zone_id}/dns_records/{record_id}")
        resp.raise_for_status()
        return resp.json().get("result", {})

    # ── SSL/TLS ─────────────────────────────────────────────────────────

    def get_ssl_settings(self, zone_id: str) -> dict:
        """Get SSL/TLS mode for a zone (off, flexible, full, strict)."""
        resp = self.get(f"zones/{zone_id}/settings/ssl")
        resp.raise_for_status()
        return resp.json().get("result", {})

    def get_ssl_verification(self, zone_id: str) -> list:
        """Get SSL certificate verification status."""
        resp = self.get(f"zones/{zone_id}/ssl/verification")
        if resp.status_code == 200:
            return resp.json().get("result", [])
        return []

    def list_certificates(self, zone_id: str) -> list:
        """List SSL certificates for a zone."""
        return self.get_all(f"zones/{zone_id}/ssl/certificate_packs")

    def get_tls_settings(self, zone_id: str) -> dict:
        """Get TLS version settings (min TLS version)."""
        resp = self.get(f"zones/{zone_id}/settings/min_tls_version")
        resp.raise_for_status()
        return resp.json().get("result", {})

    # ── Page Rules ──────────────────────────────────────────────────────

    def list_page_rules(self, zone_id: str) -> list:
        """List page rules for a zone."""
        return self.get_all(f"zones/{zone_id}/pagerules")

    # ── Firewall / WAF ──────────────────────────────────────────────────

    def list_firewall_rules(self, zone_id: str) -> list:
        """List firewall rules for a zone."""
        return self.get_all(f"zones/{zone_id}/firewall/rules")

    def list_waf_packages(self, zone_id: str) -> list:
        """List WAF packages for a zone."""
        return self.get_all(f"zones/{zone_id}/firewall/waf/packages")

    # ── Caching ─────────────────────────────────────────────────────────

    def get_cache_level(self, zone_id: str) -> dict:
        """Get cache level setting for a zone."""
        resp = self.get(f"zones/{zone_id}/settings/cache_level")
        resp.raise_for_status()
        return resp.json().get("result", {})

    def get_browser_cache_ttl(self, zone_id: str) -> dict:
        """Get browser cache TTL setting for a zone."""
        resp = self.get(f"zones/{zone_id}/settings/browser_cache_ttl")
        resp.raise_for_status()
        return resp.json().get("result", {})

    # ── Cloudflare Tunnels ──────────────────────────────────────────────

    def list_tunnels(self, is_deleted: bool = False) -> list:
        """List Cloudflare Tunnels for the account."""
        params = {"is_deleted": str(is_deleted).lower()}
        return self.get_all(
            f"accounts/{self.account_id}/cfd_tunnel", params=params
        )

    def get_tunnel(self, tunnel_id: str) -> dict:
        """Get a single tunnel by ID."""
        resp = self.get(f"accounts/{self.account_id}/cfd_tunnel/{tunnel_id}")
        resp.raise_for_status()
        return resp.json().get("result", {})

    def get_tunnel_configurations(self, tunnel_id: str) -> dict:
        """Get the configuration (ingress rules) for a tunnel."""
        resp = self.get(
            f"accounts/{self.account_id}/cfd_tunnel/{tunnel_id}/configurations"
        )
        resp.raise_for_status()
        return resp.json().get("result", {})

    def list_tunnel_connections(self, tunnel_id: str) -> list:
        """List active connections for a tunnel."""
        resp = self.get(
            f"accounts/{self.account_id}/cfd_tunnel/{tunnel_id}/connections"
        )
        if resp.status_code == 200:
            return resp.json().get("result", [])
        return []

    def list_tunnel_routes(self) -> list:
        """List all tunnel routes (CIDR to tunnel mappings)."""
        return self.get_all(f"accounts/{self.account_id}/teamnet/routes")

    # ── Zero Trust: Access Applications ─────────────────────────────────

    def list_access_apps(self) -> list:
        """List all Access Applications."""
        return self.get_all(f"accounts/{self.account_id}/access/apps")

    def get_access_app(self, app_id: str) -> dict:
        """Get a single Access Application."""
        resp = self.get(f"accounts/{self.account_id}/access/apps/{app_id}")
        resp.raise_for_status()
        return resp.json().get("result", {})

    def list_access_policies(self, app_id: str) -> list:
        """List policies for an Access Application."""
        return self.get_all(
            f"accounts/{self.account_id}/access/apps/{app_id}/policies"
        )

    # ── Zero Trust: Access Groups ───────────────────────────────────────

    def list_access_groups(self) -> list:
        """List Access Groups."""
        return self.get_all(f"accounts/{self.account_id}/access/groups")

    def get_access_group(self, group_id: str) -> dict:
        """Get a single Access Group."""
        resp = self.get(
            f"accounts/{self.account_id}/access/groups/{group_id}"
        )
        resp.raise_for_status()
        return resp.json().get("result", {})

    # ── Zero Trust: Service Tokens ──────────────────────────────────────

    def list_service_tokens(self) -> list:
        """List Access Service Tokens."""
        return self.get_all(
            f"accounts/{self.account_id}/access/service_tokens"
        )

    # ── Zero Trust: Identity Providers ──────────────────────────────────

    def list_identity_providers(self) -> list:
        """List configured identity providers (IdPs) for Access."""
        return self.get_all(
            f"accounts/{self.account_id}/access/identity_providers"
        )

    # ── Zero Trust: Gateway ─────────────────────────────────────────────

    def list_gateway_rules(self) -> list:
        """List Zero Trust Gateway filtering rules."""
        resp = self.get(f"accounts/{self.account_id}/gateway/rules")
        if resp.status_code == 200:
            return resp.json().get("result", [])
        return []

    def list_gateway_locations(self) -> list:
        """List Gateway locations (DNS endpoints)."""
        resp = self.get(f"accounts/{self.account_id}/gateway/locations")
        if resp.status_code == 200:
            return resp.json().get("result", [])
        return []

    def list_gateway_categories(self) -> list:
        """List Gateway content categories."""
        resp = self.get(f"accounts/{self.account_id}/gateway/categories")
        if resp.status_code == 200:
            return resp.json().get("result", [])
        return []

    def get_gateway_configuration(self) -> dict:
        """Get the Zero Trust Gateway account configuration."""
        resp = self.get(f"accounts/{self.account_id}/gateway/configuration")
        if resp.status_code == 200:
            return resp.json().get("result", {})
        return {}

    # ── Email Routing ───────────────────────────────────────────────────

    def get_email_routing_settings(self, zone_id: str) -> dict:
        """Get email routing settings for a zone."""
        resp = self.get(f"zones/{zone_id}/email/routing")
        if resp.status_code == 200:
            return resp.json().get("result", {})
        return {}

    def list_email_routing_rules(self, zone_id: str) -> list:
        """List email routing rules for a zone.

        Note: requires zone-level Email Routing permissions. Returns empty
        list if the permission is not granted or email routing is disabled.
        """
        resp = self.get(f"zones/{zone_id}/email/routing/rules")
        if resp.status_code == 200:
            return resp.json().get("result", [])
        return []

    def list_email_routing_addresses(self, zone_id: str) -> list:
        """List destination addresses for email routing.

        Note: requires Email Routing Addresses permission. Returns empty
        list if not granted or email routing is disabled.
        """
        resp = self.get(f"zones/{zone_id}/email/routing/addresses")
        if resp.status_code == 200:
            return resp.json().get("result", [])
        return []

    # ── Account ─────────────────────────────────────────────────────────

    def get_account(self) -> dict:
        """Get the account details."""
        resp = self.get(f"accounts/{self.account_id}")
        resp.raise_for_status()
        return resp.json().get("result", {})

    def list_account_members(self) -> list:
        """List account members."""
        return self.get_all(f"accounts/{self.account_id}/members")

    # ── Zone Settings ───────────────────────────────────────────────────

    def list_zone_settings(self, zone_id: str) -> list:
        """List all settings for a zone."""
        resp = self.get(f"zones/{zone_id}/settings")
        if resp.status_code == 200:
            return resp.json().get("result", [])
        return []

    # ── Utility ─────────────────────────────────────────────────────────

    def test_connection(self) -> dict:
        """Health check: validate token and basic API access."""
        try:
            verify = self.verify_token()
            if not verify.get("ok"):
                return verify

            result = {"ok": True, "token_status": verify.get("status", "active")}

            zones = self.list_zones()
            result["zone_count"] = len(zones)
            result["zones"] = [
                {"name": z["name"], "status": z.get("status")} for z in zones
            ]

            target_domain = os.environ.get("CLOUDFLARE_DOMAIN", "example.com")
            target = next(
                (z for z in zones if z["name"] == target_domain), None
            )
            if target:
                result["target_zone"] = target["name"]
                result["target_zone_id"] = target["id"]

            return result
        except requests.HTTPError as e:
            return {
                "ok": False,
                "error": str(e),
                "status": getattr(e.response, "status_code", None),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── CLI Entrypoint ─────────────────────────────────────────────────────
# Quick testing: python3 cloudflare_client.py test

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "test"
    client = CloudflareClient()

    if action == "test":
        result = client.test_connection()
        print(json.dumps(result, indent=2))

    elif action == "zones":
        zones = client.list_zones()
        print(f"Total zones: {len(zones)}")
        for z in zones:
            print(f"  {z['name']:40s}  {z.get('status', '?'):10s}  plan={z.get('plan', {}).get('name', '?')}")

    elif action == "dns":
        zone_id = sys.argv[2] if len(sys.argv) > 2 else client.find_zone_id()
        if not zone_id:
            print("ERROR: Could not find zone ID. Pass zone_id as argument or set domain.", file=sys.stderr)
            sys.exit(1)
        records = client.list_dns_records(zone_id)
        print(f"Total DNS records: {len(records)}")
        from collections import Counter
        by_type = Counter(r.get("type", "?") for r in records)
        for rtype, count in by_type.most_common():
            print(f"  {rtype:10s}  {count}")

    elif action == "tunnels":
        tunnels = client.list_tunnels()
        print(f"Total tunnels: {len(tunnels)}")
        for t in tunnels:
            status = t.get("status", "?")
            print(f"  {t.get('name', '?'):40s}  {status:12s}  id={t['id'][:12]}")

    elif action == "access-apps":
        apps = client.list_access_apps()
        print(f"Total Access Applications: {len(apps)}")
        for a in apps:
            print(f"  {a.get('name', '?'):40s}  type={a.get('type', '?'):20s}  domain={a.get('domain', '?')}")

    elif action == "service-tokens":
        tokens = client.list_service_tokens()
        print(f"Total Service Tokens: {len(tokens)}")
        for t in tokens:
            expires = t.get("expires_at", "never")
            print(f"  {t.get('name', '?'):40s}  expires={expires}")

    else:
        print(f"Unknown action: {action}")
        print("Usage: python3 cloudflare_client.py [test|zones|dns|tunnels|access-apps|service-tokens]")
        sys.exit(1)
