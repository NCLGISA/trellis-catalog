"""
Cisco Meraki Dashboard REST API v1 Client

Provides authenticated access to your Meraki organization via
the Dashboard API with automatic pagination, rate-limit handling, and
organization auto-discovery.

Authentication uses a static API key (Bearer token):
  - Authorization: Bearer <MERAKI_API_KEY>
  - No token refresh required (keys do not expire unless revoked)

Environment variables (set in docker-compose.yml):
  MERAKI_API_KEY  - Dashboard API key with full org access
"""

import os
import sys
import json
import time
import re
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

API_KEY = os.getenv("MERAKI_API_KEY", "")
API_BASE = "https://api.meraki.com/api/v1"


class MerakiClient:
    """Cisco Meraki Dashboard REST API v1 client."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or API_KEY

        if not self.api_key:
            print(
                "ERROR: Missing Meraki Dashboard API key.\n"
                "\n"
                "Required environment variable:\n"
                "  MERAKI_API_KEY\n"
                "\n"
                "Generate from Meraki Dashboard:\n"
                "  Organization > Settings > Dashboard API access\n"
                "  or My Profile > API access\n",
                file=sys.stderr,
            )
            sys.exit(1)

        self._org_id = None
        self.session = requests.Session()

    # ── Auth ────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict:
        """Return headers with Bearer token."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ── Organization Auto-Discovery ────────────────────────────────────

    def _get_org_id(self) -> str:
        """Auto-discover the organization ID (cached after first call)."""
        if self._org_id:
            return self._org_id

        resp = self.get("/organizations")
        resp.raise_for_status()
        orgs = resp.json()

        if not orgs:
            print("ERROR: API key has no organization access.", file=sys.stderr)
            sys.exit(1)

        if len(orgs) == 1:
            self._org_id = orgs[0]["id"]
        else:
            self._org_id = orgs[0]["id"]
            names = ", ".join(o["name"] for o in orgs)
            print(
                f"  Note: API key has access to {len(orgs)} orgs ({names}). "
                f"Using first: {orgs[0]['name']} ({self._org_id})",
                file=sys.stderr,
            )

        return self._org_id

    @property
    def org_id(self) -> str:
        return self._get_org_id()

    # ── Core HTTP Methods ──────────────────────────────────────────────

    def _request(
        self, method: str, endpoint: str, **kwargs
    ) -> requests.Response:
        """Make an API request with auth, rate-limit retry, and redirect follow."""
        url = endpoint if endpoint.startswith("http") else f"{API_BASE}{endpoint}"
        max_retries = 3

        for attempt in range(max_retries):
            kwargs["headers"] = self._auth_headers()
            resp = self.session.request(method, url, timeout=60, allow_redirects=True, **kwargs)

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

    def put(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("PUT", endpoint, json=json_data)

    def delete(self, endpoint: str, params: dict = None) -> requests.Response:
        return self._request("DELETE", endpoint, params=params)

    # ── Pagination Helper ──────────────────────────────────────────────

    def get_all(
        self,
        endpoint: str,
        params: dict = None,
        per_page: int = 1000,
        max_pages: int = 100,
    ) -> list:
        """
        Paginate through all results for a list endpoint.

        Meraki uses Link header with rel=next for cursor-based pagination.
        The response body is a JSON array (no wrapper key).
        """
        params = dict(params or {})
        if "perPage" not in params:
            params["perPage"] = int(per_page)
        results = []
        url = endpoint

        for _ in range(max_pages):
            resp = self.get(url, params=params if not url.startswith("http") else None)
            if resp.status_code != 200:
                print(
                    f"  Error fetching {url}: {resp.status_code} {resp.text[:200]}",
                    file=sys.stderr,
                )
                break

            data = resp.json()
            if isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)

            next_url = self._parse_next_link(resp.headers.get("Link", ""))
            if not next_url:
                break

            url = next_url
            params = None

        return results

    @staticmethod
    def _parse_next_link(link_header: str) -> str | None:
        """Parse the 'next' URL from a Meraki Link header."""
        if not link_header:
            return None
        for part in link_header.split(","):
            match = re.search(r'<([^>]+)>;\s*rel=next', part)
            if match:
                return match.group(1)
        return None

    # ── Organization ───────────────────────────────────────────────────

    def get_org(self) -> dict:
        """Get organization details."""
        resp = self.get(f"/organizations/{self.org_id}")
        resp.raise_for_status()
        return resp.json()

    def list_networks(self) -> list:
        """List all networks in the organization."""
        return self.get_all(f"/organizations/{self.org_id}/networks")

    def list_admins(self) -> list:
        """List organization admins."""
        resp = self.get(f"/organizations/{self.org_id}/admins")
        resp.raise_for_status()
        return resp.json()

    def get_license_overview(self) -> dict:
        """Get license overview for the organization."""
        resp = self.get(f"/organizations/{self.org_id}/licenses/overview")
        resp.raise_for_status()
        return resp.json()

    def list_inventory(self, per_page: int = 1000) -> list:
        """List all inventory devices (claimed devices)."""
        return self.get_all(
            f"/organizations/{self.org_id}/inventory/devices",
            per_page=per_page,
        )

    # ── Devices ────────────────────────────────────────────────────────

    def list_devices(self, per_page: int = 1000) -> list:
        """List all devices in the organization."""
        return self.get_all(
            f"/organizations/{self.org_id}/devices",
            per_page=per_page,
        )

    def list_device_statuses(self, per_page: int = 1000) -> list:
        """List device statuses (online/offline/alerting/dormant)."""
        return self.get_all(
            f"/organizations/{self.org_id}/devices/statuses",
            per_page=per_page,
        )

    def get_device_status_overview(self) -> dict:
        """Get device status counts overview."""
        resp = self.get(f"/organizations/{self.org_id}/devices/statuses/overview")
        resp.raise_for_status()
        return resp.json()

    def get_device(self, serial: str) -> dict:
        """Get a single device by serial number."""
        resp = self.get(f"/devices/{serial}")
        resp.raise_for_status()
        return resp.json()

    def get_device_clients(self, serial: str, timespan: int = 86400) -> list:
        """Get clients connected to a device (default: last 24h)."""
        return self.get_all(
            f"/devices/{serial}/clients",
            params={"timespan": timespan},
        )

    # ── Uplinks ────────────────────────────────────────────────────────

    def list_uplink_statuses(self, per_page: int = 1000) -> list:
        """List uplink statuses for all appliances in the org."""
        return self.get_all(
            f"/organizations/{self.org_id}/uplinks/statuses",
            per_page=per_page,
        )

    # ── Networks ───────────────────────────────────────────────────────

    def get_network(self, network_id: str) -> dict:
        """Get a single network by ID."""
        resp = self.get(f"/networks/{network_id}")
        resp.raise_for_status()
        return resp.json()

    def list_network_devices(self, network_id: str) -> list:
        """List devices in a specific network."""
        resp = self.get(f"/networks/{network_id}/devices")
        resp.raise_for_status()
        return resp.json()

    def list_network_clients(
        self, network_id: str, timespan: int = 86400, per_page: int = 1000
    ) -> list:
        """List clients on a network (default: last 24h)."""
        return self.get_all(
            f"/networks/{network_id}/clients",
            params={"timespan": timespan},
            per_page=per_page,
        )

    # ── Wireless ───────────────────────────────────────────────────────

    def get_ssids(self, network_id: str) -> list:
        """Get wireless SSIDs for a network."""
        resp = self.get(f"/networks/{network_id}/wireless/ssids")
        if resp.status_code == 400:
            return []
        resp.raise_for_status()
        return resp.json()

    def get_ssid(self, network_id: str, number: int) -> dict:
        """Get a single SSID by number (0-14)."""
        resp = self.get(f"/networks/{network_id}/wireless/ssids/{number}")
        resp.raise_for_status()
        return resp.json()

    # ── Appliance / VLANs ─────────────────────────────────────────────

    def get_vlans(self, network_id: str) -> list:
        """Get VLANs for a network (appliance networks only)."""
        resp = self.get(f"/networks/{network_id}/appliance/vlans")
        if resp.status_code == 400:
            return []
        resp.raise_for_status()
        return resp.json()

    def get_vlan(self, network_id: str, vlan_id: int) -> dict:
        """Get a single VLAN by ID."""
        resp = self.get(f"/networks/{network_id}/appliance/vlans/{vlan_id}")
        resp.raise_for_status()
        return resp.json()

    # ── Firewall ───────────────────────────────────────────────────────

    def get_l3_firewall_rules(self, network_id: str) -> list:
        """Get L3 firewall rules for an appliance network."""
        resp = self.get(f"/networks/{network_id}/appliance/firewall/l3FirewallRules")
        if resp.status_code == 400:
            return []
        resp.raise_for_status()
        data = resp.json()
        return data.get("rules", data) if isinstance(data, dict) else data

    def get_l7_firewall_rules(self, network_id: str) -> list:
        """Get L7 firewall rules for an appliance network."""
        resp = self.get(f"/networks/{network_id}/appliance/firewall/l7FirewallRules")
        if resp.status_code == 400:
            return []
        resp.raise_for_status()
        data = resp.json()
        return data.get("rules", data) if isinstance(data, dict) else data

    # ── VPN ────────────────────────────────────────────────────────────

    def list_vpn_statuses(self, per_page: int = 300) -> list:
        """List site-to-site VPN statuses for the org.
        Note: This endpoint requires perPage between 3 and 300."""
        return self.get_all(
            f"/organizations/{self.org_id}/appliance/vpn/statuses",
            per_page=per_page,
        )

    def get_site_to_site_vpn(self, network_id: str) -> dict:
        """Get site-to-site VPN settings for a network."""
        resp = self.get(f"/networks/{network_id}/appliance/vpn/siteToSiteVpn")
        if resp.status_code == 400:
            return {}
        resp.raise_for_status()
        return resp.json()

    # ── Switch Ports ───────────────────────────────────────────────────

    def get_switch_ports(self, serial: str) -> list:
        """Get switch port configuration for a device."""
        resp = self.get(f"/devices/{serial}/switch/ports")
        if resp.status_code == 400:
            return []
        resp.raise_for_status()
        return resp.json()

    def get_switch_port_statuses(self, serial: str, timespan: int = 86400) -> list:
        """Get switch port statuses for a device (default: last 24h)."""
        resp = self.get(
            f"/devices/{serial}/switch/ports/statuses",
            params={"timespan": timespan},
        )
        if resp.status_code == 400:
            return []
        resp.raise_for_status()
        return resp.json()

    # ── Firmware ───────────────────────────────────────────────────────

    def get_firmware_upgrades(self, network_id: str) -> dict:
        """Get firmware upgrade information for a network."""
        resp = self.get(f"/networks/{network_id}/firmwareUpgrades")
        if resp.status_code == 400:
            return {}
        resp.raise_for_status()
        return resp.json()

    def list_firmware_upgrades(self, per_page: int = 1000) -> list:
        """List firmware upgrade history for the org."""
        return self.get_all(
            f"/organizations/{self.org_id}/firmware/upgrades",
            per_page=per_page,
        )

    # ── Utility ────────────────────────────────────────────────────────

    def find_network_by_name(self, name: str) -> dict | None:
        """Find a network by name (case-insensitive substring match)."""
        networks = self.list_networks()
        name_lower = name.lower()
        for net in networks:
            if name_lower in net.get("name", "").lower():
                return net
        return None

    def find_device_by_name(self, name: str) -> dict | None:
        """Find a device by name (case-insensitive substring match)."""
        devices = self.list_devices()
        name_lower = name.lower()
        for dev in devices:
            if name_lower in (dev.get("name") or "").lower():
                return dev
        return None

    def test_connection(self) -> dict:
        """Health check: validate API key and basic access."""
        try:
            org = self.get_org()
            overview = self.get_device_status_overview()
            networks = self.list_networks()
            admins = self.list_admins()

            return {
                "ok": True,
                "organization": org.get("name"),
                "org_id": org.get("id"),
                "licensing": org.get("licensing", {}).get("model"),
                "networks": len(networks),
                "admins": len(admins),
                "devices": overview.get("counts", {}).get("byStatus", {}),
            }
        except requests.HTTPError as e:
            return {
                "ok": False,
                "error": str(e),
                "status": getattr(e.response, "status_code", None),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── CLI Entrypoint ─────────────────────────────────────────────────────
# Allows quick testing: python3 meraki_client.py test

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "test"
    client = MerakiClient()

    if action == "test":
        result = client.test_connection()
        print(json.dumps(result, indent=2))

    elif action == "networks":
        networks = client.list_networks()
        print(f"Total networks: {len(networks)}")
        for n in sorted(networks, key=lambda x: x.get("name", "")):
            types = ", ".join(n.get("productTypes", []))
            print(f"  {n['name']:50s}  {types}")

    elif action == "devices":
        devices = client.list_devices()
        from collections import Counter
        types = Counter(d.get("productType", "unknown") for d in devices)
        print(f"Total devices: {len(devices)}")
        for t, c in types.most_common():
            print(f"  {t:20s}  {c}")

    elif action == "status":
        overview = client.get_device_status_overview()
        counts = overview.get("counts", {}).get("byStatus", {})
        print("Device status overview:")
        for status, count in counts.items():
            print(f"  {status:12s}  {count}")

    elif action == "admins":
        admins = client.list_admins()
        print(f"Organization admins: {len(admins)}")
        for a in admins:
            name = a.get("name", "?")
            email = a.get("email", "?")
            access = a.get("orgAccess", "?")
            mfa = "MFA" if a.get("twoFactorAuthEnabled") else "no-MFA"
            print(f"  {name:30s}  {email:40s}  {access:6s}  {mfa}")

    else:
        print(f"Unknown action: {action}")
        print("Usage: python3 meraki_client.py [test|networks|devices|status|admins]")
        sys.exit(1)
