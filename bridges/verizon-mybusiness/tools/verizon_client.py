"""
Verizon MyBusiness API Client

Core HTTP client for the Verizon MyBusiness portal. Manages session cookies,
keepalive pings, and provides typed methods for all discovered API endpoints.

Session cookies are loaded from an encrypted file or from environment-injected
credentials. All API calls go through the `_post()` method which handles
session expiry detection (HTTP 302 redirect).
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://mb.verizonwireless.com"
SESSION_DIR = Path(os.getenv("VZ_SESSION_DIR", "/opt/bridge/data/session"))
COOKIES_FILE = SESSION_DIR / "cookies.json"
CACHE_DIR = Path(os.getenv("VZ_CACHE_DIR", "/opt/bridge/data/cache"))


def require_credentials() -> tuple[str, str]:
    """Verify VZ_USERNAME and VZ_PASSWORD are in the environment.
    These are injected by Tendril bridge_credentials for the authenticated operator."""
    username = os.getenv("VZ_USERNAME", "").strip()
    password = os.getenv("VZ_PASSWORD", "").strip()
    if not username or not password:
        print("ERROR: Verizon credentials not configured for this operator.")
        print("Set up credentials via:")
        print('  bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_USERNAME", value="...")')
        print('  bridge_credentials(action="set", bridge="verizon-mybusiness", key="VZ_PASSWORD", value="...")')
        sys.exit(1)
    return username, password


def credentials_available() -> bool:
    """Check if credentials are configured without exiting."""
    return bool(os.getenv("VZ_USERNAME", "").strip()) and bool(os.getenv("VZ_PASSWORD", "").strip())


class SessionExpiredError(Exception):
    """Raised when the Verizon session has expired (302 redirect detected)."""
    pass


class VerizonClient:
    """HTTP client for Verizon MyBusiness portal APIs."""

    def __init__(self, cookies_path: Path | str | None = None):
        self._cookies_path = Path(cookies_path) if cookies_path else COOKIES_FILE
        self._jar = self._load_cookies()
        self._session_params = self._extract_session_params()
        self._client: httpx.Client | None = None

    def _load_cookies(self) -> httpx.Cookies:
        if not self._cookies_path.exists():
            raise FileNotFoundError(
                f"No session cookies at {self._cookies_path}. "
                "Run auth_session.py login to authenticate."
            )
        raw = json.loads(self._cookies_path.read_text())
        jar = httpx.Cookies()
        seen = set()
        for c in raw:
            key = (c["name"], c.get("domain", ""))
            if key in seen:
                continue
            seen.add(key)
            jar.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        return jar

    def _extract_session_params(self) -> dict:
        """Extract ecpdId, userId, gon from cookies."""
        params = {}
        for cookie_name in self._jar.jar:
            name = cookie_name.name
            value = cookie_name.value
            if name == "profileId" and value:
                params["ecpdId"] = value
            elif name == "GROUP_ORDER_NUMBER" and value:
                params["gon"] = value
        params["userId"] = os.getenv("VZ_USERNAME", "")
        return params

    @property
    def ecpd_id(self) -> str:
        return self._session_params.get("ecpdId", "")

    @property
    def user_id(self) -> str:
        return self._session_params.get("userId", "")

    @property
    def gon(self) -> str:
        return self._session_params.get("gon", "")

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=BASE_URL,
                cookies=self._jar,
                headers={
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/131.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/mbt/secure/index?appName=esm",
                },
                follow_redirects=False,
                timeout=30.0,
            )
        return self._client

    def _post(self, path: str, body: dict | None = None) -> dict:
        """POST to a Verizon API endpoint. Raises SessionExpiredError on 302."""
        client = self._get_client()
        resp = client.post(path, json=body or {})

        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("location", "")
            raise SessionExpiredError(
                f"Session expired: {resp.status_code} redirect to {location}"
            )

        resp.raise_for_status()
        return resp.json()

    def close(self):
        if self._client and not self._client.is_closed:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── Session management ─────────────────────────────────────────────────

    def is_session_alive(self) -> bool:
        try:
            self._post("/mbt/secure/esmcompositesvc/mbt/esmhome/getMbtData")
            return True
        except (SessionExpiredError, httpx.HTTPStatusError):
            return False

    def keepalive_ping(self) -> bool:
        return self.is_session_alive()

    # ── Fleet inventory ────────────────────────────────────────────────────

    def retrieve_entitled_mtn(self) -> dict:
        return self._post("/mbt/secure/accountandlinesvc/mbt/wno/retrieveEntitledMtn")

    def retrieve_line_summary_count(self) -> dict:
        return self._post(
            "/mbt/secure/accountandlinesvc/mbt/wno/retrieveLineSummaryCount",
            {
                "ecpdId": self.ecpd_id,
                "clientId": "MBT_WNO",
                "gon": self.gon,
                "pageInfo": "WNO",
                "lineCounts": [
                    "total", "active", "suspended",
                    "upgradeEligible", "5G", "4G", "mdnlessZeroPricePlan",
                ],
            },
        )

    # ── Per-line detail ────────────────────────────────────────────────────

    def retrieve_mtn_device_info(self, mtn: str, account_number: str) -> dict:
        return self._post(
            "/mbt/secure/accountandlinedetails/mbt/wnc/retrieveMtnDeviceInfo",
            {
                "accountNumber": account_number,
                "mtn": mtn,
                "clientId": "MBT_ANC",
                "ecpdId": self.ecpd_id,
                "gon": self.gon,
                "loadSection": "DEVICEINFO",
            },
        )

    def retrieve_user_info(self, mtn: str, account_number: str) -> dict:
        return self._post(
            "/mbt/secure/accountandlinedetails/mbt/wnc/retrieveUserInfoForSelectedMtn",
            {
                "mtn": mtn,
                "gon": self.gon,
                "clientId": "MBT_ANO",
                "accountNumber": account_number,
                "ecpdId": self.ecpd_id,
                "loadSection": "USERINFO",
            },
        )

    def retrieve_device_lock(self, mtn: str, account_number: str, device_id: str) -> dict:
        return self._post(
            "/mbt/secure/smmanagetransactionsvc/mbt/sm/manage/deviceLock/retreive",
            {
                "mtn": mtn,
                "accountNumber": account_number,
                "deviceId": device_id,
                "clientId": "MBT_WNC",
                "ecpdId": self.ecpd_id,
                "gon": self.gon,
            },
        )

    def check_upgrade_eligibility(self, mtn: str, account_number: str) -> dict:
        return self._post(
            "/mbt/secure/aecompositesvc/mbt/ae/checkUpgradeActivationEligibility",
            {
                "mtn": mtn,
                "accountNumber": account_number,
                "ecpdId": self.ecpd_id,
                "gon": self.gon,
            },
        )

    # ── Billing ────────────────────────────────────────────────────────────

    def get_billing_accounts(self, bill_period: int = -1) -> dict:
        return self._post(
            "/mbt/secure/invoiceusagecompositesvc/mbt/invoice-usage/v1/invoice/billing/accounts/get",
            {
                "billPeriod": bill_period,
                "page": 1,
                "limit": 100,
                "searchField": "ACCOUNTNUMBER",
                "searchValue": "",
                "ecpdId": self.ecpd_id,
                "userId": self.user_id,
            },
        )

    # ── Dashboard / summary ────────────────────────────────────────────────

    def get_mbt_data(self) -> dict:
        return self._post("/mbt/secure/esmcompositesvc/mbt/esmhome/getMbtData")

    def get_line_upgrade_eligible(self) -> dict:
        return self._post(
            "/mbt/secure/esmcompositesvc/mbt/esmhome/summary/lineAndUpgrdEligible/get",
            {"ecpdId": self.ecpd_id, "userId": self.user_id},
        )

    def get_total_orders(self) -> dict:
        return self._post(
            "/mbt/secure/esmcompositesvc/mbt/esmhome/summary/totalOrders/get",
            {"ecpdId": self.ecpd_id, "userId": self.user_id},
        )


# ── CLI quick access ───────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: verizon_client.py <command>")
        print("Commands: test, fleet, keepalive")
        sys.exit(1)

    cmd = sys.argv[1]
    client = VerizonClient()

    if cmd == "test":
        alive = client.is_session_alive()
        print(f"Session: {'ALIVE' if alive else 'EXPIRED'}")
        sys.exit(0 if alive else 1)

    elif cmd == "fleet":
        data = client.retrieve_line_summary_count()
        counts = data.get("lineCounts", {})
        print(f"Total: {counts.get('total', '?')}")
        print(f"Active: {counts.get('active', '?')}")
        print(f"Suspended: {counts.get('suspended', '?')}")
        print(f"5G: {counts.get('5G', '?')}")
        print(f"4G: {counts.get('4G', '?')}")
        print(f"Upgrade eligible: {counts.get('upgradeEligible', '?')}")

    elif cmd == "keepalive":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
        print(f"Keepalive every {interval}s. Ctrl+C to stop.")
        while True:
            alive = client.keepalive_ping()
            ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            print(f"  {ts} -- {'ALIVE' if alive else 'EXPIRED'}", flush=True)
            if not alive:
                print("Session expired. Run auth_session.py login to re-authenticate.")
                sys.exit(1)
            time.sleep(interval)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
