#!/usr/bin/env python3
"""
ArcGIS Online API Client

Handles OAuth2 client_credentials authentication, token caching/refresh,
rate limiting, pagination, and session management for the ArcGIS REST API.

Usage (from Tendril execute):
    python3 /opt/bridge/data/tools/arcgis_online_client.py

Environment variables:
    ARCGIS_ORG_URL        - Organization portal URL (required)
    ARCGIS_CLIENT_ID      - OAuth2 app client ID (required)
    ARCGIS_CLIENT_SECRET  - OAuth2 app client secret (required)
"""

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parents[2] / ".env")
except ImportError:
    pass

import requests


# ── Configuration ──────────────────────────────────────────────────────

ORG_URL = os.getenv("ARCGIS_ORG_URL", "").rstrip("/")
CLIENT_ID = os.getenv("ARCGIS_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("ARCGIS_CLIENT_SECRET", "")

TOKEN_URL = "https://www.arcgis.com/sharing/rest/oauth2/token"

MAX_RETRIES = 3
REQUEST_TIMEOUT = 30


class ArcGISOnlineClient:
    """REST API client for ArcGIS Online with OAuth2 and pagination."""

    def __init__(self):
        missing = []
        if not ORG_URL:
            missing.append("ARCGIS_ORG_URL")
        if not CLIENT_ID:
            missing.append("ARCGIS_CLIENT_ID")
        if not CLIENT_SECRET:
            missing.append("ARCGIS_CLIENT_SECRET")
        if missing:
            print(f"ERROR: Missing env vars: {', '.join(missing)}", file=sys.stderr)
            sys.exit(1)

        self.org_url = ORG_URL
        self.sharing_url = f"{ORG_URL}/sharing/rest"
        self.session = requests.Session()
        self._token = None
        self._token_expiry = 0

    # ── OAuth2 Client Credentials ─────────────────────────────────

    def _get_token(self):
        """Obtain or refresh the OAuth2 access token."""
        if self._token and time.time() < self._token_expiry - 60:
            return self._token

        resp = requests.post(TOKEN_URL, data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "client_credentials",
            "f": "json",
        }, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise RuntimeError(
                f"Token error: {data['error'].get('message', data['error'])}"
            )

        self._token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 7200)
        return self._token

    # ── Core request method ────────────────────────────────────────

    def _request(self, method, url, params=None, data=None, json_body=None):
        """
        Make an authenticated API request with rate limiting and retries.
        ArcGIS REST API returns errors inside 200 responses, so we check
        the JSON body for error objects too.
        """
        params = dict(params or {})
        params["f"] = "json"
        params["token"] = self._get_token()

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.request(
                    method, url,
                    params=params if method == "GET" else None,
                    data={**params, **(data or {})} if method == "POST" and not json_body else data,
                    json=json_body,
                    timeout=REQUEST_TIMEOUT,
                )

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 5))
                    time.sleep(retry_after)
                    continue

                resp.raise_for_status()

                if not resp.text:
                    return {}

                result = resp.json()
                if isinstance(result, dict) and "error" in result:
                    err = result["error"]
                    code = err.get("code", 0)
                    msg = err.get("message", str(err))
                    if code == 498 or code == 499:
                        self._token = None
                        self._token_expiry = 0
                        continue
                    raise RuntimeError(f"ArcGIS error {code}: {msg}")

                return result

            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)

        raise last_error if last_error else RuntimeError("Request failed after retries")

    def get(self, path, params=None):
        """GET against the sharing/rest API."""
        url = f"{self.sharing_url}/{path.lstrip('/')}"
        return self._request("GET", url, params=params)

    def post(self, path, data=None, json_body=None):
        """POST against the sharing/rest API."""
        url = f"{self.sharing_url}/{path.lstrip('/')}"
        return self._request("POST", url, data=data, json_body=json_body)

    def get_url(self, url, params=None):
        """GET against an arbitrary URL (e.g. feature service endpoint)."""
        return self._request("GET", url, params=params)

    def post_url(self, url, data=None):
        """POST against an arbitrary URL."""
        return self._request("POST", url, data=data)

    # ── Pagination ─────────────────────────────────────────────────

    def search(self, query, item_type=None, sort_field="modified",
               sort_order="desc", num=10, start=1):
        """Search for items in the organization."""
        params = {
            "q": query,
            "sortField": sort_field,
            "sortOrder": sort_order,
            "num": num,
            "start": start,
        }
        if item_type:
            params["q"] += f' type:"{item_type}"'
        return self.get("search", params=params)

    def search_all(self, query, item_type=None, max_items=1000):
        """Fetch all matching items across pages."""
        all_results = []
        start = 1
        while len(all_results) < max_items:
            batch_size = min(100, max_items - len(all_results))
            result = self.search(query, item_type=item_type, num=batch_size, start=start)
            items = result.get("results", [])
            if not items:
                break
            all_results.extend(items)
            next_start = result.get("nextStart", -1)
            if next_start == -1:
                break
            start = next_start
        return all_results

    # ── Connection test ────────────────────────────────────────────

    def test_connection(self):
        """Verify API connectivity and authentication."""
        try:
            self._get_token()
            result = self.get("portals/self")
            return {
                "ok": True,
                "org_url": self.org_url,
                "org_name": result.get("name", "unknown"),
                "org_id": result.get("id", "unknown"),
                "subscription_type": result.get("subscriptionInfo", {}).get("type", "unknown"),
            }
        except Exception as e:
            return {
                "ok": False,
                "org_url": self.org_url,
                "error": str(e),
            }


if __name__ == "__main__":
    client = ArcGISOnlineClient()
    result = client.test_connection()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)
