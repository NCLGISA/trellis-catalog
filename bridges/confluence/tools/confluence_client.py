"""Confluence Cloud REST API client.

Uses the v2 API for pages, spaces, and blog posts, and the v1 API for
CQL search.  Authentication is per-user via email + API token (basic auth).

Environment:
    CONFLUENCE_URL          Atlassian site URL (e.g. https://yourorg.atlassian.net)
    CONFLUENCE_EMAIL        Atlassian account email for basic auth
    CONFLUENCE_API_TOKEN    API token from https://id.atlassian.com/manage-profile/security/api-tokens
"""

import json
import os
import sys

import requests

CONFLUENCE_URL = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
CONFLUENCE_EMAIL = os.environ.get("CONFLUENCE_EMAIL", "")
CONFLUENCE_API_TOKEN = os.environ.get("CONFLUENCE_API_TOKEN", "")


def die(msg):
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(1)


class ConfluenceClient:
    """REST client for Confluence Cloud (v2 + v1 search)."""

    def __init__(self):
        for name, val in [
            ("CONFLUENCE_URL", CONFLUENCE_URL),
            ("CONFLUENCE_EMAIL", CONFLUENCE_EMAIL),
            ("CONFLUENCE_API_TOKEN", CONFLUENCE_API_TOKEN),
        ]:
            if not val:
                die(f"{name} environment variable must be set.")

        self.base_url = CONFLUENCE_URL
        self.v2 = f"{self.base_url}/wiki/api/v2"
        self.v1 = f"{self.base_url}/wiki/rest/api"

        self.session = requests.Session()
        self.session.auth = (CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def _check(self, resp):
        if not resp.ok:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text[:500]
            die(f"API {resp.status_code}: {json.dumps(detail)}")
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    # ===== Spaces ==========================================================

    def list_spaces(self, limit=25, cursor=None, space_type=None):
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if space_type:
            params["type"] = space_type
        return self._check(self.session.get(f"{self.v2}/spaces", params=params))

    def get_space(self, space_id):
        return self._check(self.session.get(f"{self.v2}/spaces/{space_id}"))

    # ===== Pages ===========================================================

    def list_pages(self, space_id=None, limit=25, cursor=None, status="current",
                   title=None, sort=None, body_format=None):
        params = {"limit": limit, "status": status}
        if cursor:
            params["cursor"] = cursor
        if title:
            params["title"] = title
        if sort:
            params["sort"] = sort
        if body_format:
            params["body-format"] = body_format

        if space_id:
            url = f"{self.v2}/spaces/{space_id}/pages"
        else:
            url = f"{self.v2}/pages"
        return self._check(self.session.get(url, params=params))

    def get_page(self, page_id, body_format="storage"):
        """Get a page by ID. body_format: storage, atlas_doc_format, or view."""
        params = {"body-format": body_format}
        return self._check(self.session.get(f"{self.v2}/pages/{page_id}", params=params))

    def create_page(self, space_id, title, body, body_format="storage",
                    parent_id=None, status="current"):
        payload = {
            "spaceId": str(space_id),
            "status": status,
            "title": title,
            "body": {
                "representation": body_format,
                "value": body,
            },
        }
        if parent_id:
            payload["parentId"] = str(parent_id)
        return self._check(self.session.post(f"{self.v2}/pages", json=payload))

    def update_page(self, page_id, title, body, version_number,
                    body_format="storage", status="current"):
        payload = {
            "id": str(page_id),
            "status": status,
            "title": title,
            "body": {
                "representation": body_format,
                "value": body,
            },
            "version": {
                "number": version_number,
            },
        }
        return self._check(self.session.put(f"{self.v2}/pages/{page_id}", json=payload))

    def delete_page(self, page_id):
        return self._check(self.session.delete(f"{self.v2}/pages/{page_id}"))

    # ===== Blog Posts ======================================================

    def list_blogposts(self, space_id=None, limit=25, cursor=None,
                       body_format=None):
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if body_format:
            params["body-format"] = body_format
        if space_id:
            url = f"{self.v2}/spaces/{space_id}/blogposts"
        else:
            url = f"{self.v2}/blogposts"
        return self._check(self.session.get(url, params=params))

    def get_blogpost(self, blogpost_id, body_format="storage"):
        params = {"body-format": body_format}
        return self._check(
            self.session.get(f"{self.v2}/blogposts/{blogpost_id}", params=params))

    # ===== Comments ========================================================

    def get_page_comments(self, page_id, limit=25, body_format="storage"):
        params = {"limit": limit, "body-format": body_format}
        return self._check(
            self.session.get(f"{self.v2}/pages/{page_id}/footer-comments", params=params))

    def create_comment(self, page_id, body, body_format="storage"):
        payload = {
            "pageId": str(page_id),
            "body": {
                "representation": body_format,
                "value": body,
            },
        }
        return self._check(
            self.session.post(f"{self.v2}/footer-comments", json=payload))

    # ===== Labels ==========================================================

    def get_page_labels(self, page_id, limit=25):
        params = {"limit": limit}
        return self._check(
            self.session.get(f"{self.v2}/pages/{page_id}/labels", params=params))

    def add_page_label(self, page_id, label):
        payload = [{"prefix": "global", "name": label}]
        resp = self.session.post(
            f"{self.v1}/content/{page_id}/label", json=payload)
        return self._check(resp)

    # ===== Attachments =====================================================

    def get_page_attachments(self, page_id, limit=25):
        params = {"limit": limit}
        return self._check(
            self.session.get(f"{self.v2}/pages/{page_id}/attachments", params=params))

    # ===== Search (v1 CQL) =================================================

    def search(self, cql, limit=25, start=0, excerpt=True):
        """Search using CQL (Confluence Query Language)."""
        params = {"cql": cql, "limit": limit, "start": start}
        if excerpt:
            params["excerpt"] = "highlight"
        return self._check(self.session.get(f"{self.v1}/search", params=params))

    # ===== Children / Ancestors ============================================

    def get_page_children(self, page_id, limit=25):
        params = {"limit": limit}
        return self._check(
            self.session.get(f"{self.v2}/pages/{page_id}/children", params=params))

    def get_page_ancestors(self, page_id):
        return self._check(
            self.session.get(f"{self.v2}/pages/{page_id}/ancestors"))

    # ===== Versions ========================================================

    def get_page_versions(self, page_id, limit=25):
        params = {"limit": limit}
        return self._check(
            self.session.get(f"{self.v2}/pages/{page_id}/versions", params=params))

    # ===== Users ===========================================================

    def get_current_user(self):
        return self._check(self.session.get(f"{self.v1}/user/current"))

    # ===== Tasks ===========================================================

    def list_tasks(self, limit=25, cursor=None, status=None):
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        return self._check(self.session.get(f"{self.v2}/tasks", params=params))

    # ===== Info ============================================================

    def info(self):
        return {
            "base_url": self.base_url,
            "wiki_url": f"{self.base_url}/wiki",
            "api_v2": self.v2,
            "api_v1": self.v1,
            "email": CONFLUENCE_EMAIL,
        }
