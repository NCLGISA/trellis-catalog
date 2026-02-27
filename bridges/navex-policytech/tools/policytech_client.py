"""NAVEX PolicyTech OpenSearch API client.

Searches published policy/procedure documents via the OpenSearch 1.0/1.1
endpoint.  Authentication is API-key-based (key passed as a URL parameter).
Responses are RSS/Atom XML which this client parses into Python dicts.
"""

import json
import os
import sys
import xml.etree.ElementTree as ET

import requests

POLICYTECH_BASE_URL = os.environ.get("POLICYTECH_BASE_URL", "").rstrip("/")
POLICYTECH_API_KEY = os.environ.get("POLICYTECH_API_KEY", "")
POLICYTECH_VERIFY_TLS = os.environ.get("POLICYTECH_VERIFY_TLS", "true").lower() not in (
    "false",
    "0",
    "no",
)

OPENSEARCH_PATH = "/content/api/opensearch/2014/06/"

# XML namespaces used in OpenSearch RSS responses
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    "rss": "",
}


def die(msg):
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(1)


class PolicyTechClient:
    """Read-only client for the PolicyTech OpenSearch API."""

    def __init__(self):
        for name, val in [
            ("POLICYTECH_BASE_URL", POLICYTECH_BASE_URL),
            ("POLICYTECH_API_KEY", POLICYTECH_API_KEY),
        ]:
            if not val:
                die(f"{name} environment variable must be set.")

        self.base_url = POLICYTECH_BASE_URL
        self.api_key = POLICYTECH_API_KEY
        self.api_url = f"{self.base_url}{OPENSEARCH_PATH}"

        self.session = requests.Session()
        self.session.verify = POLICYTECH_VERIFY_TLS

        if not POLICYTECH_VERIFY_TLS:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _build_params(self, search_terms, items_per_page=25, start_index=0,
                      search_field="ALL"):
        return {
            "MethodName": "GetDocuments",
            "APIKey": self.api_key,
            "SearchField": search_field,
            "itemsPerPage": str(items_per_page),
            "startIndex": str(start_index),
            "SearchTerms": search_terms,
        }

    def _parse_rss(self, xml_text):
        """Parse RSS/Atom XML response into a list of document dicts."""
        root = ET.fromstring(xml_text)
        documents = []
        total_results = 0
        start_index = 0
        items_per_page = 0

        channel = root.find("channel")
        if channel is None:
            channel = root

        # OpenSearch metadata
        for elem in channel:
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "totalResults":
                total_results = int(elem.text or 0)
            elif tag == "startIndex":
                start_index = int(elem.text or 0)
            elif tag == "itemsPerPage":
                items_per_page = int(elem.text or 0)

        for item in channel.findall("item"):
            doc = {}
            for child in item:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "link":
                    doc["link"] = child.text or child.get("href", "")
                elif tag == "enclosure":
                    doc["download_url"] = child.get("url", "")
                    doc["mime_type"] = child.get("type", "")
                    doc["size"] = child.get("length", "")
                else:
                    doc[tag] = (child.text or "").strip()
            documents.append(doc)

        return {
            "total_results": total_results,
            "start_index": start_index,
            "items_per_page": items_per_page,
            "documents": documents,
        }

    def _parse_atom(self, xml_text):
        """Parse Atom XML response into a list of document dicts."""
        root = ET.fromstring(xml_text)
        documents = []
        total_results = 0

        for elem in root:
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "totalResults":
                total_results = int(elem.text or 0)

        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            doc = {}
            for child in entry:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "link":
                    doc["link"] = child.get("href", "")
                elif tag == "content":
                    doc["content"] = (child.text or "").strip()
                else:
                    doc[tag] = (child.text or "").strip()
            documents.append(doc)

        return {
            "total_results": total_results,
            "documents": documents,
        }

    def search(self, query, items_per_page=25, start_index=0,
               search_field="ALL"):
        """Search published documents by keyword."""
        params = self._build_params(query, items_per_page, start_index,
                                    search_field)
        resp = self.session.get(self.api_url, params=params)

        if not resp.ok:
            die(f"API request failed ({resp.status_code}): {resp.text[:500]}")

        content_type = resp.headers.get("Content-Type", "")
        body = resp.text

        if not body.strip():
            return {"total_results": 0, "documents": []}

        try:
            if "atom" in content_type.lower() or "<feed" in body[:200]:
                return self._parse_atom(body)
            else:
                return self._parse_rss(body)
        except ET.ParseError as exc:
            die(f"Failed to parse XML response: {exc}\nBody: {body[:500]}")

    def search_all(self, query, search_field="ALL", max_pages=20,
                   page_size=50):
        """Paginate through all search results."""
        all_docs = []
        start = 0
        for _ in range(max_pages):
            result = self.search(query, items_per_page=page_size,
                                 start_index=start, search_field=search_field)
            all_docs.extend(result["documents"])
            total = result.get("total_results", 0)
            if not result["documents"] or len(all_docs) >= total:
                break
            start += len(result["documents"])
        return {
            "total_results": len(all_docs),
            "documents": all_docs,
        }

    def list_all(self, page_size=50, max_pages=20):
        """List all published documents accessible via the API key.

        Uses a wildcard search -- PolicyTech returns all documents when
        SearchTerms is a single space or asterisk on most configurations.
        """
        return self.search_all(" ", page_size=page_size, max_pages=max_pages)

    def info(self):
        """Return connection metadata."""
        return {
            "base_url": self.base_url,
            "api_url": self.api_url,
        }
