---
name: navex-policytech
description: NAVEX PolicyTech bridge -- search and retrieve published policy and procedure documents via the OpenSearch API. Supports keyword search across all fields or by title, full document listing with pagination, and health checks.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.24"
metadata:
  author: tendril-project
  version: "2026.02.27.3"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - navex
    - policytech
    - navex-one
    - policy
    - procedure
    - compliance
    - governance
    - documents
    - opensearch
credentials:
  - key: POLICYTECH_BASE_URL
    env: POLICYTECH_BASE_URL
    scope: shared
    description: "NAVEX One PolicyTech base URL (e.g. https://yourorg.navexone.com). See references/README.md Step 1."
  - key: POLICYTECH_API_KEY
    env: POLICYTECH_API_KEY
    scope: shared
    description: "API key from Settings & Tools > IT Settings > API Keys (requires Professional plan)"
  - key: POLICYTECH_VERIFY_TLS
    env: POLICYTECH_VERIFY_TLS
    scope: shared
    description: "Set to false for self-signed certificates (default: true)"
---

# NAVEX PolicyTech Bridge

Search and retrieve published policy and procedure documents from NAVEX PolicyTech (part of NAVEX One) via the OpenSearch API.

> **Plan requirement:** The API Keys add-on requires the PolicyTech **Professional** plan.

> **Unofficial use:** NAVEX officially supports this API only for SharePoint integration. Using it for general-purpose document search (as this bridge does) is functional but not officially supported -- your mileage may vary.

## Authentication

- **Type:** API key passed as a URL parameter
- **Key source:** PolicyTech admin panel: Settings & Tools > IT Settings > API Keys
- **Prerequisite:** The "API Keys" add-on must be enabled by NAVEX Support (Professional plan required)
- **Environment:** `POLICYTECH_BASE_URL` (shared) + `POLICYTECH_API_KEY` (shared) + `POLICYTECH_VERIFY_TLS` (shared, optional)
- **Scope:** API key can access documents with "All Users" or "Public" security level in "Published" status only

## Deployment Prerequisites

1. **Confirm Professional plan** -- the API Keys add-on is only available on PolicyTech Professional
2. **Contact NAVEX Support** (888-359-8123 or https://support.navex.com/s/contactsupport) to enable the API Keys add-on and obtain a registration code
3. **Enter the registration code** in NAVEX One: Settings & Tools > IT Settings > Registration Info
4. **Create an API key** in Settings & Tools > IT Settings > API Keys
5. **Determine the base URL** -- for NAVEX One this is `https://yourorg.navexone.com`

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `policytech_client.py` | `/opt/bridge/data/tools/` | Core OpenSearch API client -- auth, search, pagination, RSS/XML parsing |
| `policytech.py` | `/opt/bridge/data/tools/` | CLI: search, search-all, list, info |
| `policytech_check.py` | `/opt/bridge/data/tools/` | Health check: connectivity and API key validation |

## Capabilities

### What This Bridge Can Do

- **Search published documents by keyword** -- full-text search across all document fields (titles, body content) or title-only search
- **List all published documents** -- enumerate every document accessible via the API key with automatic pagination
- **Paginate large result sets** -- automatically walks through multiple pages of results (up to 1,000 documents)
- **Direct document links** -- each result includes a direct URL to view the document in PolicyTech
- **Health monitoring** -- validates API key and connectivity on a 60-second interval

### What This Bridge Cannot Do

- **No document content retrieval** -- the API returns metadata (title, link) but not the full document body; documents must be viewed via their link URL in a browser
- **No document creation or editing** -- entirely read-only; no workflow actions (approve, retire, etc.)
- **No draft/archived documents** -- only Published status documents are returned
- **No per-group documents** -- only documents with "All Users" or "Public" security level are visible
- **No document number search** -- the `NUMBER` and `BODY` search fields are not functional; only `ALL` and `TITLE` work
- **No category/department filtering** -- the API does not support filtering by category, department, or owner
- **No document metadata** -- the API does not return publication date, category, author, or version information (descriptions are typically empty)

## Quick Start

```bash
# Verify connectivity and credentials
python3 policytech_check.py

# Search for documents by keyword (searches titles + body)
python3 policytech.py search --query "travel"

# Search in document titles only
python3 policytech.py search --query "safety" --field TITLE

# Get all results for a search (auto-paginates)
python3 policytech.py search-all --query "safety"

# List all published documents accessible via the API key
python3 policytech.py list

# Show connection info
python3 policytech.py info
```

## CLI Reference

### policytech.py search -- Search published documents

```bash
python3 policytech.py search --query "travel"
python3 policytech.py search --query "blood" --field TITLE --limit 10
python3 policytech.py search --query "emergency" --offset 25
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--query`, `-q` | (required) | Search keywords |
| `--field` | `ALL` | Field to search: `ALL` (title + body) or `TITLE` (title only) |
| `--limit` | `25` | Results per page (max varies by server) |
| `--offset` | `0` | Start index for pagination |

Returns a single page of results. Use `--offset` to manually paginate, or use `search-all` for automatic pagination.

### policytech.py search-all -- Paginate through all results

```bash
python3 policytech.py search-all --query "safety"
python3 policytech.py search-all --query "reimbursement" --field TITLE
```

Automatically paginates through all result pages (up to 20 pages of 50 results each, max 1,000 documents). Returns a single combined JSON result.

### policytech.py list -- List all published documents

```bash
python3 policytech.py list
```

Returns all documents accessible via the API key. Uses automatic pagination. This is a wildcard search that retrieves the complete published document inventory.

### policytech.py info -- Connection information

```bash
python3 policytech.py info
```

Returns the configured base URL and API endpoint URL. Useful for verifying configuration.

## Response Format

Each API call returns JSON. Documents have this structure:

```json
{
  "total_results": 264,
  "start_index": 0,
  "items_per_page": 25,
  "documents": [
    {
      "title": "24/7 Communicable Disease Response Policy",
      "link": "https://yourorg.navexone.com/content/docview/?docid=823",
      "description": ""
    }
  ]
}
```

**Fields per document:**

| Field | Always present | Description |
|-------|---------------|-------------|
| `title` | Yes | Document title |
| `link` | Yes | Direct URL to view the document in PolicyTech (requires authentication) |
| `description` | Yes | Document description (typically empty in practice) |

The `link` URL follows the pattern `https://yourorg.navexone.com/content/docview/?docid=NNN` where `NNN` is the internal document ID.

## Verified Search Field Behavior

| SearchField | Status | Behavior |
|-------------|--------|----------|
| `ALL` | Works | Searches across title and body content |
| `TITLE` | Works | Searches document titles only |
| `BODY` | Broken | Returns HTTP 500 error |
| `NUMBER` | Broken | Returns HTTP 500 error |

Only `ALL` and `TITLE` are functional. The CLI restricts choices to these two.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| HTTP 500 "Policy Manager Error" | Invalid or expired API key | Verify API key in Settings & Tools > IT Settings > API Keys |
| HTTP 500 on search | Using `BODY` or `NUMBER` search field | Use `ALL` or `TITLE` only |
| HTTP 404 | API Keys add-on not enabled | Contact NAVEX Support to enable it |
| "API Keys" not in IT Settings | Not on Professional plan, or add-on not enabled | Confirm plan level with NAVEX Support |
| Connection timeout | Network/firewall issue | Ensure the bridge host can reach `*.navexone.com` on port 443 |
| Empty results | Search too specific, or all docs have restricted security | Try a broader search; check document security levels |
| SSL certificate error | Proxy or TLS inspection | Set `POLICYTECH_VERIFY_TLS=false` |
| Empty `description` fields | Normal -- NAVEX does not populate this field for most documents | Use the `link` URL to view full document content |

## Notes

- NAVEX officially documents this API for SharePoint integration only; behavior may change without notice in future PolicyTech releases
- The API returns RSS 2.0 XML with OpenSearch 1.1 extensions; the client parses this into JSON
- Document links require PolicyTech authentication to view -- they are not publicly accessible URLs
- The API key can optionally be IP-restricted in PolicyTech admin settings for security
- Pagination starts at index 0; the API returns `totalResults` for the total matching count
