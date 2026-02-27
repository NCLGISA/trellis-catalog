"""UKG Ready REST API client.

Token-based authentication via POST /ta/rest/v1/login with Api-Key header
and service account credentials.  The JWT response contains the company ID
(cid) used to build V1/V2 endpoint URLs.
"""

import base64
import json
import os
import sys
import time

import requests

UKG_BASE_URL = os.environ.get("UKG_BASE_URL", "").rstrip("/")
UKG_COMPANY_SHORT_NAME = os.environ.get("UKG_COMPANY_SHORT_NAME", "")
UKG_API_KEY = os.environ.get("UKG_API_KEY", "")
UKG_USERNAME = os.environ.get("UKG_USERNAME", "")
UKG_PASSWORD = os.environ.get("UKG_PASSWORD", "")
UKG_VERIFY_TLS = os.environ.get("UKG_VERIFY_TLS", "true").lower() not in (
    "false",
    "0",
    "no",
)


def die(msg):
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(1)


class UKGClient:
    """Authenticated REST client for UKG Ready V1/V2 APIs."""

    def __init__(self):
        for name, val in [
            ("UKG_BASE_URL", UKG_BASE_URL),
            ("UKG_COMPANY_SHORT_NAME", UKG_COMPANY_SHORT_NAME),
            ("UKG_API_KEY", UKG_API_KEY),
            ("UKG_USERNAME", UKG_USERNAME),
            ("UKG_PASSWORD", UKG_PASSWORD),
        ]:
            if not val:
                die(f"{name} environment variable must be set.")

        self.base_url = UKG_BASE_URL
        self.company_short_name = UKG_COMPANY_SHORT_NAME
        self.api_key = UKG_API_KEY
        self.username = UKG_USERNAME
        self.password = UKG_PASSWORD

        self.session = requests.Session()
        self.session.verify = UKG_VERIFY_TLS
        self.session.headers.update(
            {
                "Api-Key": self.api_key,
                "Accept": "application/json",
            }
        )

        if not UKG_VERIFY_TLS:
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.token = None
        self.token_expiry = 0
        self.company_id = None

        self._login()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _login(self):
        """Authenticate and cache JWT + company ID."""
        url = f"{self.base_url}/ta/rest/v1/login"
        payload = {
            "credentials": {
                "username": self.username,
                "password": self.password,
                "company": self.company_short_name,
            }
        }
        resp = self.session.post(
            url, json=payload, headers={"Content-Type": "application/json"}
        )
        if not resp.ok:
            body = resp.text[:500]
            die(f"Login failed ({resp.status_code}): {body}")

        data = resp.json()
        self.token = data["token"]
        ttl_ms = data.get("ttl", 3600000)
        self.token_expiry = time.time() + (ttl_ms / 1000) - 60

        # Extract company ID from JWT payload
        parts = self.token.split(".")
        if len(parts) < 2:
            die("Unexpected JWT format from login endpoint.")
        payload_b64 = parts[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        jwt_payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        self.company_id = jwt_payload.get("cid")
        if not self.company_id:
            die("JWT missing cid (company ID) claim.")

        self.session.headers["Authentication"] = f"Bearer {self.token}"

    def _ensure_token(self):
        if time.time() >= self.token_expiry:
            self._login()

    # ------------------------------------------------------------------
    # URL builders
    # ------------------------------------------------------------------

    def _url_v2(self, path):
        return f"{self.base_url}/ta/rest/v2/companies/{self.company_id}/{path.lstrip('/')}"

    def _url_v1(self, path):
        return f"{self.base_url}/ta/rest/v1/company/{self.company_id}/{path.lstrip('/')}"

    def url(self, path, version=2):
        self._ensure_token()
        if version == 1:
            return self._url_v1(path)
        return self._url_v2(path)

    # ------------------------------------------------------------------
    # HTTP verbs
    # ------------------------------------------------------------------

    def _request(self, method, path, version=2, params=None, json_data=None):
        self._ensure_token()
        target = self.url(path, version)

        resp = self.session.request(method, target, params=params, json=json_data)

        if resp.status_code == 401:
            self._login()
            target = self.url(path, version)
            resp = self.session.request(method, target, params=params, json=json_data)

        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 2))
            for attempt in range(3):
                time.sleep(wait)
                resp = self.session.request(
                    method, target, params=params, json=json_data
                )
                if resp.status_code != 429:
                    break
                wait = min(wait * 2, 30)

        if not resp.ok:
            body = resp.text[:1000]
            die(f"{method} {path} failed ({resp.status_code}): {body}")

        if resp.content:
            return resp.json()
        return {}

    def get(self, path, params=None, version=2):
        return self._request("GET", path, version=version, params=params)

    def post(self, path, data=None, version=2):
        return self._request("POST", path, version=version, json_data=data)

    def put(self, path, data=None, version=2):
        return self._request("PUT", path, version=version, json_data=data)

    def delete(self, path, version=2):
        return self._request("DELETE", path, version=version)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def get_all_pages(self, path, key=None, params=None, version=2, max_pages=50):
        """Follow HATEOAS pagination links, collecting results."""
        if params is None:
            params = {}
        results = []
        self._ensure_token()
        target = self.url(path, version)

        for _ in range(max_pages):
            resp = self.session.get(target, params=params)
            if resp.status_code == 401:
                self._login()
                target = self.url(path, version)
                resp = self.session.get(target, params=params)
            if not resp.ok:
                break
            data = resp.json()
            if key and key in data:
                results.extend(data[key])
            elif isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)
            next_link = data.get("_links", {}).get("next") if isinstance(data, dict) else None
            if not next_link:
                break
            target = next_link
            params = {}
        return results

    def info(self):
        """Return login metadata (company ID, token TTL)."""
        return {
            "base_url": self.base_url,
            "company_short_name": self.company_short_name,
            "company_id": self.company_id,
            "token_expires_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.token_expiry + 60)
            ),
        }
