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

"""NextDNS REST API client.

Handles API-key authentication and provides methods for profile management,
security/privacy configuration, analytics, query logs, and allowlist/denylist
operations via the NextDNS API (https://api.nextdns.io).

Environment:
    NEXTDNS_API_KEY     API key from https://my.nextdns.io/account
    NEXTDNS_PROFILE     Default profile ID (optional, e.g. abc123)
"""

import json
import os
import sys

import requests

NEXTDNS_API_KEY = os.environ.get("NEXTDNS_API_KEY", "")
NEXTDNS_PROFILE = os.environ.get("NEXTDNS_PROFILE", "")
BASE_URL = "https://api.nextdns.io"


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


class NextDNSClient:
    """REST client for the NextDNS API."""

    def __init__(self, profile_id=None):
        if not NEXTDNS_API_KEY:
            die("NEXTDNS_API_KEY must be set (from https://my.nextdns.io/account).")

        self.profile_id = profile_id or NEXTDNS_PROFILE
        self.session = requests.Session()
        self.session.headers.update({
            "X-Api-Key": NEXTDNS_API_KEY,
            "Content-Type": "application/json",
        })

    def _require_profile(self):
        if not self.profile_id:
            die("No profile specified. Set NEXTDNS_PROFILE or pass --profile.")

    # -- HTTP helpers -------------------------------------------------------

    def _url(self, path):
        return f"{BASE_URL}/{path.lstrip('/')}"

    def get(self, path, params=None, timeout=30):
        r = self.session.get(self._url(path), params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def post(self, path, body=None, timeout=30):
        r = self.session.post(self._url(path), json=body, timeout=timeout)
        r.raise_for_status()
        if r.content:
            return r.json()
        return {"status": "created"}

    def patch(self, path, body=None, timeout=30):
        r = self.session.patch(self._url(path), json=body, timeout=timeout)
        r.raise_for_status()
        if r.content:
            return r.json()
        return {"status": "updated"}

    def put(self, path, body=None, timeout=30):
        r = self.session.put(self._url(path), json=body, timeout=timeout)
        r.raise_for_status()
        if r.content:
            return r.json()
        return {"status": "replaced"}

    def delete(self, path, timeout=30):
        r = self.session.delete(self._url(path), timeout=timeout)
        r.raise_for_status()
        if r.content:
            return r.json()
        return {"status": "deleted"}

    # -- Pagination helper --------------------------------------------------

    def get_all(self, path, params=None, limit=100):
        """Fetch all pages from a paginated endpoint."""
        params = dict(params or {})
        params["limit"] = limit
        all_items = []
        cursor = None

        while True:
            if cursor:
                params["cursor"] = cursor
            data = self.get(path, params=params)
            items = data.get("data", [])
            all_items.extend(items)
            pagination = data.get("meta", {}).get("pagination", {})
            cursor = pagination.get("cursor")
            if not cursor:
                break

        return all_items

    # ===== Profiles ========================================================

    def list_profiles(self):
        """List all profiles on the account."""
        return self.get_all("profiles")

    def get_profile(self, profile_id=None):
        """Get full profile configuration."""
        pid = profile_id or self.profile_id
        if not pid:
            die("No profile specified.")
        return self.get(f"profiles/{pid}")

    def create_profile(self, config):
        """Create a new profile. Returns the new profile ID."""
        return self.post("profiles", body=config)

    def update_profile(self, config, profile_id=None):
        """Patch top-level profile settings."""
        pid = profile_id or self.profile_id
        if not pid:
            die("No profile specified.")
        return self.patch(f"profiles/{pid}", body=config)

    def delete_profile(self, profile_id):
        """Delete a profile by ID."""
        return self.delete(f"profiles/{profile_id}")

    # ===== Security Settings ===============================================

    def get_security(self, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.get(f"profiles/{pid}/security")

    def update_security(self, settings, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.patch(f"profiles/{pid}/security", body=settings)

    # ===== Privacy Settings ================================================

    def get_privacy(self, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.get(f"profiles/{pid}/privacy")

    def update_privacy(self, settings, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.patch(f"profiles/{pid}/privacy", body=settings)

    def get_blocklists(self, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.get(f"profiles/{pid}/privacy/blocklists")

    def add_blocklist(self, blocklist_id, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.post(f"profiles/{pid}/privacy/blocklists", body={"id": blocklist_id})

    def remove_blocklist(self, blocklist_id, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.delete(f"profiles/{pid}/privacy/blocklists/{blocklist_id}")

    # ===== Parental Controls ===============================================

    def get_parental_control(self, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.get(f"profiles/{pid}/parentalControl")

    def update_parental_control(self, settings, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.patch(f"profiles/{pid}/parentalControl", body=settings)

    # ===== Denylist ========================================================

    def get_denylist(self, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.get(f"profiles/{pid}/denylist")

    def add_denylist(self, domain, active=True, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.post(f"profiles/{pid}/denylist", body={"id": domain, "active": active})

    def remove_denylist(self, domain, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.delete(f"profiles/{pid}/denylist/{domain}")

    def toggle_denylist(self, domain, active, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.patch(f"profiles/{pid}/denylist/{domain}", body={"active": active})

    # ===== Allowlist =======================================================

    def get_allowlist(self, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.get(f"profiles/{pid}/allowlist")

    def add_allowlist(self, domain, active=True, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.post(f"profiles/{pid}/allowlist", body={"id": domain, "active": active})

    def remove_allowlist(self, domain, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.delete(f"profiles/{pid}/allowlist/{domain}")

    def toggle_allowlist(self, domain, active, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.patch(f"profiles/{pid}/allowlist/{domain}", body={"active": active})

    # ===== Settings ========================================================

    def get_settings(self, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.get(f"profiles/{pid}/settings")

    def update_settings(self, settings, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.patch(f"profiles/{pid}/settings", body=settings)

    # ===== Analytics =======================================================

    def analytics(self, endpoint, profile_id=None, **params):
        """Generic analytics query. endpoint examples: status, domains, protocols, etc."""
        pid = profile_id or self.profile_id
        self._require_profile()
        clean = {k: v for k, v in params.items() if v is not None}
        return self.get(f"profiles/{pid}/analytics/{endpoint}", params=clean)

    def analytics_status(self, profile_id=None, **params):
        return self.analytics("status", profile_id=profile_id, **params)

    def analytics_domains(self, profile_id=None, **params):
        return self.analytics("domains", profile_id=profile_id, **params)

    def analytics_reasons(self, profile_id=None, **params):
        return self.analytics("reasons", profile_id=profile_id, **params)

    def analytics_devices(self, profile_id=None, **params):
        return self.analytics("devices", profile_id=profile_id, **params)

    def analytics_protocols(self, profile_id=None, **params):
        return self.analytics("protocols", profile_id=profile_id, **params)

    def analytics_query_types(self, profile_id=None, **params):
        return self.analytics("queryTypes", profile_id=profile_id, **params)

    def analytics_ips(self, profile_id=None, **params):
        return self.analytics("ips", profile_id=profile_id, **params)

    def analytics_destinations(self, dest_type="countries", profile_id=None, **params):
        params["type"] = dest_type
        return self.analytics("destinations", profile_id=profile_id, **params)

    def analytics_dnssec(self, profile_id=None, **params):
        return self.analytics("dnssec", profile_id=profile_id, **params)

    def analytics_encryption(self, profile_id=None, **params):
        return self.analytics("encryption", profile_id=profile_id, **params)

    def analytics_ip_versions(self, profile_id=None, **params):
        return self.analytics("ipVersions", profile_id=profile_id, **params)

    # ===== Logs ============================================================

    def logs(self, profile_id=None, **params):
        """Fetch DNS query logs with optional filters."""
        pid = profile_id or self.profile_id
        self._require_profile()
        clean = {k: v for k, v in params.items() if v is not None}
        return self.get(f"profiles/{pid}/logs", params=clean)

    def clear_logs(self, profile_id=None):
        pid = profile_id or self.profile_id
        self._require_profile()
        return self.delete(f"profiles/{pid}/logs")


def _main():
    import argparse
    parser = argparse.ArgumentParser(prog="nextdns_client.py")
    parser.add_argument("command", choices=["test", "profiles"])
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()
    client = NextDNSClient(profile_id=args.profile)
    if args.command == "test":
        profiles = client.list_profiles()
        print(json.dumps({
            "success": True,
            "profile_count": len(profiles),
        }, indent=2))
    elif args.command == "profiles":
        profiles = client.list_profiles()
        print(json.dumps(profiles, indent=2))


if __name__ == "__main__":
    _main()
