#!/usr/bin/env python3
"""
UniFi Network Controller REST API Client

Provides authenticated session-based access to the UniFi controller API with
automatic controller-type detection (standard vs UniFi OS), site discovery,
SSL handling (self-signed certs), and structured error reporting.

First leg of the core triad. The check script, battery test, and all domain
tools import this client.

Authentication:
  UniFi uses cookie-based sessions. POST credentials to the login endpoint,
  receive a `unifises` cookie, and include it in subsequent requests.
  Standard controllers use /api/login; UniFi OS (UDM/UCG) uses /api/auth/login
  with a /proxy/network prefix on all API paths.

Environment variables (set in docker-compose.yml or injected by Tendril Root):
  UNIFI_URL      - Base URL (e.g. https://unifi.example.com:8443)
  UNIFI_USERNAME - Admin username
  UNIFI_PASSWORD - Admin password
  UNIFI_SITE     - Default site name (default: "default")
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

UNIFI_URL = os.getenv("UNIFI_URL", "")
UNIFI_USERNAME = os.getenv("UNIFI_USERNAME", "")
UNIFI_PASSWORD = os.getenv("UNIFI_PASSWORD", "")
UNIFI_SITE = os.getenv("UNIFI_SITE", "default")


class UniFiClient:
    """UniFi Network Controller REST API client with session auth."""

    def __init__(self, url: str = None, username: str = None, password: str = None,
                 site: str = None):
        self.base_url = (url or UNIFI_URL).rstrip("/")
        self.username = username or UNIFI_USERNAME
        self.password = password or UNIFI_PASSWORD
        self.site = site or UNIFI_SITE
        self._is_unifi_os = None
        self._api_prefix = ""
        self._logged_in = False

        if not self.base_url or not self.username or not self.password:
            print(
                "ERROR: Missing UniFi credentials.\n"
                "\n"
                "Required environment variables:\n"
                "  UNIFI_URL       (e.g. https://unifi.example.com:8443)\n"
                "  UNIFI_USERNAME\n"
                "  UNIFI_PASSWORD\n",
                file=sys.stderr,
            )
            sys.exit(1)

        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({"Content-Type": "application/json"})

    # ── Controller Type Detection ──────────────────────────────────────

    def _detect_controller_type(self):
        """Detect whether this is a standard controller or UniFi OS (UDM/UCG)."""
        if self._is_unifi_os is not None:
            return

        try:
            resp = self.session.get(f"{self.base_url}/api/auth/login", timeout=10,
                                   allow_redirects=False)
            if resp.status_code in (200, 400, 401):
                self._is_unifi_os = True
                self._api_prefix = "/proxy/network"
                return
        except requests.RequestException:
            pass

        self._is_unifi_os = False
        self._api_prefix = ""

    # ── Authentication ─────────────────────────────────────────────────

    def login(self):
        """Authenticate and establish a session cookie."""
        if self._logged_in:
            return

        self._detect_controller_type()

        if self._is_unifi_os:
            login_url = f"{self.base_url}/api/auth/login"
        else:
            login_url = f"{self.base_url}/api/login"

        payload = {"username": self.username, "password": self.password}

        try:
            resp = self.session.post(login_url, json=payload, timeout=15)
        except requests.RequestException as e:
            raise ConnectionError(f"Cannot reach UniFi controller at {self.base_url}: {e}")

        if resp.status_code == 200:
            self._logged_in = True
            if self._is_unifi_os:
                csrf = resp.headers.get("X-CSRF-Token")
                if csrf:
                    self.session.headers["X-CSRF-Token"] = csrf
            return

        error_msg = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
        raise PermissionError(f"UniFi login failed (HTTP {resp.status_code}): {error_msg}")

    def logout(self):
        """End the session."""
        if not self._logged_in:
            return
        try:
            if self._is_unifi_os:
                self.session.post(f"{self.base_url}/api/auth/logout", timeout=5)
            else:
                self.session.post(f"{self.base_url}/api/logout", timeout=5)
        except requests.RequestException:
            pass
        self._logged_in = False

    def _ensure_login(self):
        if not self._logged_in:
            self.login()

    # ── Core HTTP ──────────────────────────────────────────────────────

    def _url(self, endpoint: str) -> str:
        """Build full URL with API prefix for the controller type."""
        return f"{self.base_url}{self._api_prefix}/{endpoint.lstrip('/')}"

    def _request(self, method: str, endpoint: str, retries: int = 1,
                 **kwargs) -> requests.Response:
        """HTTP request with auto-login and re-auth on 401."""
        self._ensure_login()

        for attempt in range(retries + 1):
            resp = self.session.request(method, self._url(endpoint), timeout=30, **kwargs)

            if resp.status_code == 401 and attempt < retries:
                self._logged_in = False
                self.login()
                continue

            return resp

        return resp

    def get(self, endpoint: str, params: dict = None) -> requests.Response:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("POST", endpoint, json=json_data)

    def put(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("PUT", endpoint, json=json_data)

    def delete(self, endpoint: str) -> requests.Response:
        return self._request("DELETE", endpoint)

    # ── Response Helpers ───────────────────────────────────────────────

    def _data(self, resp: requests.Response) -> list:
        """Extract the 'data' array from a standard UniFi API response."""
        if not resp.ok:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        if isinstance(body, dict):
            return body.get("data", [])
        return body

    # ── Site Operations ────────────────────────────────────────────────

    def list_sites(self) -> list:
        """List all sites on the controller."""
        return self._data(self.get("api/self/sites"))

    def site_health(self, site: str = None) -> list:
        """Get health summary for a site."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/stat/health"))

    # ── Device Operations ──────────────────────────────────────────────

    def list_devices(self, site: str = None) -> list:
        """List all adopted devices (APs, switches, gateways)."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/stat/device"))

    def get_device(self, mac: str, site: str = None) -> dict:
        """Get details for a single device by MAC address."""
        s = site or self.site
        devices = self._data(self.get(f"api/s/{s}/stat/device/{mac}"))
        return devices[0] if devices else {}

    def restart_device(self, mac: str, site: str = None) -> dict:
        """Restart (reboot) a device."""
        s = site or self.site
        return self._data(self.post(
            f"api/s/{s}/cmd/devmgr",
            json_data={"cmd": "restart", "mac": mac}
        ))

    def adopt_device(self, mac: str, site: str = None) -> dict:
        """Adopt a device into the site."""
        s = site or self.site
        return self._data(self.post(
            f"api/s/{s}/cmd/devmgr",
            json_data={"cmd": "adopt", "mac": mac}
        ))

    def upgrade_device(self, mac: str, site: str = None) -> dict:
        """Trigger firmware upgrade on a device."""
        s = site or self.site
        return self._data(self.post(
            f"api/s/{s}/cmd/devmgr",
            json_data={"cmd": "upgrade", "mac": mac}
        ))

    def force_provision(self, mac: str, site: str = None) -> dict:
        """Force re-provision a device."""
        s = site or self.site
        return self._data(self.post(
            f"api/s/{s}/cmd/devmgr",
            json_data={"cmd": "force-provision", "mac": mac}
        ))

    # ── Client Operations ──────────────────────────────────────────────

    def list_clients(self, site: str = None) -> list:
        """List currently connected clients."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/stat/sta"))

    def list_all_users(self, site: str = None) -> list:
        """List all known users (historical), not just currently connected."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/rest/user"))

    def get_client(self, mac: str, site: str = None) -> dict:
        """Get details for a client by MAC address."""
        s = site or self.site
        clients = self._data(self.get(f"api/s/{s}/stat/sta/{mac}"))
        return clients[0] if clients else {}

    def block_client(self, mac: str, site: str = None) -> dict:
        """Block a client from the network."""
        s = site or self.site
        return self._data(self.post(
            f"api/s/{s}/cmd/stamgr",
            json_data={"cmd": "block-sta", "mac": mac}
        ))

    def unblock_client(self, mac: str, site: str = None) -> dict:
        """Unblock a previously blocked client."""
        s = site or self.site
        return self._data(self.post(
            f"api/s/{s}/cmd/stamgr",
            json_data={"cmd": "unblock-sta", "mac": mac}
        ))

    def reconnect_client(self, mac: str, site: str = None) -> dict:
        """Force a client to reconnect (kick)."""
        s = site or self.site
        return self._data(self.post(
            f"api/s/{s}/cmd/stamgr",
            json_data={"cmd": "kick-sta", "mac": mac}
        ))

    # ── WLAN Operations ────────────────────────────────────────────────

    def list_wlans(self, site: str = None) -> list:
        """List all wireless networks."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/rest/wlanconf"))

    def get_wlan(self, wlan_id: str, site: str = None) -> dict:
        """Get a single WLAN configuration."""
        s = site or self.site
        wlans = self._data(self.get(f"api/s/{s}/rest/wlanconf/{wlan_id}"))
        return wlans[0] if wlans else {}

    def update_wlan(self, wlan_id: str, settings: dict, site: str = None) -> dict:
        """Update WLAN settings (e.g. name, password, enabled)."""
        s = site or self.site
        resp = self.put(f"api/s/{s}/rest/wlanconf/{wlan_id}", json_data=settings)
        return self._data(resp)

    def enable_wlan(self, wlan_id: str, site: str = None) -> dict:
        """Enable a wireless network."""
        return self.update_wlan(wlan_id, {"enabled": True}, site)

    def disable_wlan(self, wlan_id: str, site: str = None) -> dict:
        """Disable a wireless network."""
        return self.update_wlan(wlan_id, {"enabled": False}, site)

    # ── Network / VLAN Operations ──────────────────────────────────────

    def list_networks(self, site: str = None) -> list:
        """List all network configurations (VLANs, subnets)."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/rest/networkconf"))

    def get_network(self, network_id: str, site: str = None) -> dict:
        """Get a single network configuration."""
        s = site or self.site
        nets = self._data(self.get(f"api/s/{s}/rest/networkconf/{network_id}"))
        return nets[0] if nets else {}

    # ── Firewall / Routing ─────────────────────────────────────────────

    def list_firewall_rules(self, site: str = None) -> list:
        """List firewall rules."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/rest/firewallrule"))

    def list_port_forwards(self, site: str = None) -> list:
        """List port forwarding rules."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/rest/portforward"))

    def list_routes(self, site: str = None) -> list:
        """List static routes."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/rest/routing"))

    # ── Statistics ─────────────────────────────────────────────────────

    def get_dpi_stats(self, site: str = None) -> list:
        """Get DPI (Deep Packet Inspection) statistics."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/stat/dpi"))

    def get_site_stats(self, site: str = None, interval: str = "hourly",
                       attrs: list = None) -> list:
        """Get site statistics (traffic, latency)."""
        s = site or self.site
        payload = {"attrs": attrs or ["bytes", "num_sta"]}
        return self._data(self.post(f"api/s/{s}/stat/report/site.{interval}", json_data=payload))

    # ── Events / Alarms ────────────────────────────────────────────────

    def list_events(self, site: str = None, limit: int = 100) -> list:
        """Get recent events."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/stat/event", params={"_limit": limit}))

    def list_alarms(self, site: str = None) -> list:
        """Get active alarms."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/stat/alarm"))

    def list_rogue_aps(self, site: str = None) -> list:
        """Get detected rogue access points."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/stat/rogueap"))

    # ── System ─────────────────────────────────────────────────────────

    def sysinfo(self, site: str = None) -> list:
        """Get controller system information."""
        s = site or self.site
        return self._data(self.get(f"api/s/{s}/stat/sysinfo"))

    def server_status(self) -> dict:
        """Get basic server status (no auth required)."""
        try:
            resp = self.session.get(f"{self.base_url}/status", timeout=10)
            return resp.json() if resp.ok else {"error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    # ── Health Check ───────────────────────────────────────────────────

    def test_connection(self) -> dict:
        """
        Validate credentials and API access. Called by the check script
        and the battery test's first test case.
        """
        try:
            self.login()
            sites = self.list_sites()
            site_names = [s.get("desc", s.get("name", "?")) for s in sites]
            return {
                "ok": True,
                "controller_type": "UniFi OS" if self._is_unifi_os else "Standard",
                "sites": len(sites),
                "site_names": site_names,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── CLI Entrypoint ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="UniFi Network Controller API Client")
    parser.add_argument("action", nargs="?", default="test",
                        choices=["test", "sites", "devices", "clients",
                                 "wlans", "networks", "health", "sysinfo",
                                 "events", "alarms", "status"],
                        help="Action to perform")
    parser.add_argument("--site", default=None, help="Site name (default: from env)")
    parser.add_argument("--limit", type=int, default=100, help="Result limit")
    args = parser.parse_args()

    client = UniFiClient()

    try:
        if args.action == "test":
            result = client.test_connection()
        elif args.action == "sites":
            result = client.list_sites()
        elif args.action == "devices":
            result = client.list_devices(site=args.site)
        elif args.action == "clients":
            result = client.list_clients(site=args.site)
        elif args.action == "wlans":
            result = client.list_wlans(site=args.site)
        elif args.action == "networks":
            result = client.list_networks(site=args.site)
        elif args.action == "health":
            result = client.site_health(site=args.site)
        elif args.action == "sysinfo":
            result = client.sysinfo(site=args.site)
        elif args.action == "events":
            result = client.list_events(site=args.site, limit=args.limit)
        elif args.action == "alarms":
            result = client.list_alarms(site=args.site)
        elif args.action == "status":
            result = client.server_status()
        else:
            result = {"error": f"Unknown action: {args.action}"}

        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)
    finally:
        client.logout()


if __name__ == "__main__":
    main()
