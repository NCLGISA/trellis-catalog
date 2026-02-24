"""
BeyondTrust Remote Support API Client

Core REST/XML client handling OAuth2 authentication, token refresh, and
request execution against the Command, Reporting, and Configuration APIs.

Environment variables required:
  BT_API_HOST      - B Series Appliance hostname (no https:// prefix)
  BT_CLIENT_ID     - OAuth2 client ID
  BT_CLIENT_SECRET - OAuth2 client secret
"""

import base64
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

import requests

BT_API_HOST = os.environ.get("BT_API_HOST", "")
BT_CLIENT_ID = os.environ.get("BT_CLIENT_ID", "")
BT_CLIENT_SECRET = os.environ.get("BT_CLIENT_SECRET", "")

RATE_LIMIT_PER_SECOND = 20
RATE_LIMIT_PER_HOUR = 15000


class BTAuthError(Exception):
    pass


class BTAPIError(Exception):
    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class BTClient:
    """OAuth2 client for BeyondTrust Remote Support APIs."""

    def __init__(self, host=None, client_id=None, client_secret=None):
        self.host = host or BT_API_HOST
        self.client_id = client_id or BT_CLIENT_ID
        self.client_secret = client_secret or BT_CLIENT_SECRET
        self.base_url = f"https://{self.host}"
        self.token = None
        self.token_expiry = 0
        self.session = requests.Session()

        if not all([self.host, self.client_id, self.client_secret]):
            raise BTAuthError(
                "Missing credentials. Set BT_API_HOST, BT_CLIENT_ID, "
                "and BT_CLIENT_SECRET environment variables."
            )

    def _authenticate(self):
        """Obtain an OAuth2 bearer token via client_credentials grant."""
        creds = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        resp = self.session.post(
            f"{self.base_url}/oauth2/token",
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data="grant_type=client_credentials",
            timeout=15,
        )

        if resp.status_code != 200:
            raise BTAuthError(
                f"OAuth2 token request failed: {resp.status_code} {resp.text}"
            )

        data = resp.json()
        self.token = data["access_token"]
        self.token_expiry = time.time() + data.get("expires_in", 3600) - 60

    def _ensure_token(self):
        if not self.token or time.time() >= self.token_expiry:
            self._authenticate()

    def _auth_headers(self):
        self._ensure_token()
        return {"Authorization": f"Bearer {self.token}"}

    # ------------------------------------------------------------------
    # Command API (XML responses)
    # ------------------------------------------------------------------

    def command(self, action, **params):
        """Execute a Command API action. Returns parsed XML Element."""
        self._ensure_token()
        params["action"] = action
        resp = self.session.get(
            f"{self.base_url}/api/command",
            headers=self._auth_headers(),
            params=params,
            timeout=30,
        )
        if resp.status_code == 401:
            self._authenticate()
            resp = self.session.get(
                f"{self.base_url}/api/command",
                headers=self._auth_headers(),
                params=params,
                timeout=30,
            )
        if resp.status_code != 200:
            raise BTAPIError(
                f"Command API error: {resp.status_code}",
                status_code=resp.status_code,
                response_body=resp.text,
            )
        return ET.fromstring(resp.content)

    def command_post(self, action, **params):
        """Execute a Command API action via POST. Returns parsed XML Element."""
        self._ensure_token()
        params["action"] = action
        resp = self.session.post(
            f"{self.base_url}/api/command",
            headers={
                **self._auth_headers(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=urlencode(params),
            timeout=30,
        )
        if resp.status_code == 401:
            self._authenticate()
            resp = self.session.post(
                f"{self.base_url}/api/command",
                headers={
                    **self._auth_headers(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data=urlencode(params),
                timeout=30,
            )
        if resp.status_code != 200:
            raise BTAPIError(
                f"Command API error: {resp.status_code}",
                status_code=resp.status_code,
                response_body=resp.text,
            )
        return ET.fromstring(resp.content)

    # ------------------------------------------------------------------
    # Reporting API (XML responses)
    # ------------------------------------------------------------------

    def report(self, report_type, **params):
        """Execute a Reporting API query. Returns parsed XML Element."""
        self._ensure_token()
        params["report_type"] = report_type
        resp = self.session.get(
            f"{self.base_url}/api/reporting",
            headers=self._auth_headers(),
            params=params,
            timeout=60,
        )
        if resp.status_code == 401:
            self._authenticate()
            resp = self.session.get(
                f"{self.base_url}/api/reporting",
                headers=self._auth_headers(),
                params=params,
                timeout=60,
            )
        if resp.status_code != 200:
            raise BTAPIError(
                f"Reporting API error: {resp.status_code}",
                status_code=resp.status_code,
                response_body=resp.text,
            )
        return ET.fromstring(resp.content)

    # ------------------------------------------------------------------
    # Configuration API (JSON responses)
    # ------------------------------------------------------------------

    def config_get(self, endpoint, **params):
        """GET a Configuration API resource. Returns parsed JSON."""
        self._ensure_token()
        resp = self.session.get(
            f"{self.base_url}/api/config/v1/{endpoint}",
            headers={
                **self._auth_headers(),
                "Accept": "application/json",
            },
            params=params or None,
            timeout=30,
        )
        if resp.status_code == 401:
            self._authenticate()
            resp = self.session.get(
                f"{self.base_url}/api/config/v1/{endpoint}",
                headers={
                    **self._auth_headers(),
                    "Accept": "application/json",
                },
                params=params or None,
                timeout=30,
            )
        if resp.status_code != 200:
            raise BTAPIError(
                f"Config API GET error: {resp.status_code}",
                status_code=resp.status_code,
                response_body=resp.text,
            )
        return resp.json()

    def config_post(self, endpoint, data):
        """POST to a Configuration API resource. Returns parsed JSON."""
        self._ensure_token()
        resp = self.session.post(
            f"{self.base_url}/api/config/v1/{endpoint}",
            headers={
                **self._auth_headers(),
                "Content-Type": "application/json",
            },
            json=data,
            timeout=30,
        )
        if resp.status_code == 401:
            self._authenticate()
            resp = self.session.post(
                f"{self.base_url}/api/config/v1/{endpoint}",
                headers={
                    **self._auth_headers(),
                    "Content-Type": "application/json",
                },
                json=data,
                timeout=30,
            )
        if resp.status_code not in (200, 201):
            raise BTAPIError(
                f"Config API POST error: {resp.status_code}",
                status_code=resp.status_code,
                response_body=resp.text,
            )
        return resp.json()

    def config_patch(self, endpoint, data):
        """PATCH a Configuration API resource. Returns parsed JSON."""
        self._ensure_token()
        resp = self.session.patch(
            f"{self.base_url}/api/config/v1/{endpoint}",
            headers={
                **self._auth_headers(),
                "Content-Type": "application/json",
            },
            json=data,
            timeout=30,
        )
        if resp.status_code == 401:
            self._authenticate()
            resp = self.session.patch(
                f"{self.base_url}/api/config/v1/{endpoint}",
                headers={
                    **self._auth_headers(),
                    "Content-Type": "application/json",
                },
                json=data,
                timeout=30,
            )
        if resp.status_code != 200:
            raise BTAPIError(
                f"Config API PATCH error: {resp.status_code}",
                status_code=resp.status_code,
                response_body=resp.text,
            )
        return resp.json()

    def config_delete(self, endpoint):
        """DELETE a Configuration API resource."""
        self._ensure_token()
        resp = self.session.delete(
            f"{self.base_url}/api/config/v1/{endpoint}",
            headers={
                **self._auth_headers(),
                "Accept": "application/json",
            },
            timeout=30,
        )
        if resp.status_code == 401:
            self._authenticate()
            resp = self.session.delete(
                f"{self.base_url}/api/config/v1/{endpoint}",
                headers={
                    **self._auth_headers(),
                    "Accept": "application/json",
                },
                timeout=30,
            )
        if resp.status_code not in (200, 204):
            raise BTAPIError(
                f"Config API DELETE error: {resp.status_code}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

    def config_get_paginated(self, endpoint, per_page=100, **params):
        """GET all pages of a Configuration API resource. Returns list."""
        all_items = []
        page = 1
        while True:
            p = {**params, "per_page": per_page, "current_page": page}
            resp = self.config_get(endpoint, **p)
            if isinstance(resp, list):
                if not resp:
                    break
                all_items.extend(resp)
                if len(resp) < per_page:
                    break
            else:
                all_items.append(resp)
                break
            page += 1
        return all_items


# ------------------------------------------------------------------
# XML parsing helpers
# ------------------------------------------------------------------

def xml_to_dict(element):
    """Recursively convert an XML Element to a dict."""
    result = dict(element.attrib)
    for child in element:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        child_data = xml_to_dict(child)
        if tag in result:
            if not isinstance(result[tag], list):
                result[tag] = [result[tag]]
            result[tag].append(child_data)
        else:
            result[tag] = child_data
    if element.text and element.text.strip():
        if result:
            result["_text"] = element.text.strip()
        else:
            return element.text.strip()
    return result


def strip_ns(root):
    """Remove XML namespaces for easier parsing."""
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def print_json(data):
    """Pretty-print data as JSON."""
    print(json.dumps(data, indent=2, default=str))
