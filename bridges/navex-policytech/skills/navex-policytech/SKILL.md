---
name: navex-policytech
description: NAVEX PolicyTech bridge -- search and retrieve published policy and procedure documents via the OpenSearch API. Supports keyword search, category browsing, and document listing.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.24"
metadata:
  author: tendril-project
  version: "2026.02.27.2"
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

## API Limitations

- **Read-only** -- no document creation, approval, or workflow actions
- **Published documents only** -- drafts, archived, and retired documents are not returned
- **Security-filtered** -- only documents with "All Users" or "Public" security level
- **XML responses** -- the API returns RSS/Atom XML (the client handles parsing)
- **No individual document retrieval** -- you search by keyword; individual documents are accessed via the `link` URL in results
- **Unofficially supported** -- NAVEX documents this API for SharePoint integration only; behavior may change without notice

## Quick Start

```bash
# Verify connectivity and credentials
python3 policytech_check.py

# Search for documents by keyword
python3 policytech.py search --query "travel"

# Search in document titles only
python3 policytech.py search --query "acceptable use" --field TITLE

# Search all pages of results
python3 policytech.py search-all --query "safety"

# List all published documents accessible via the API key
python3 policytech.py list

# Show connection info
python3 policytech.py info
```

## CLI Reference

### `search` -- Search published documents

```
python3 policytech.py search --query <keywords> [--field ALL|TITLE|BODY|NUMBER] [--limit 25] [--offset 0]
```

**Arguments:**
| Arg | Default | Description |
|-----|---------|-------------|
| `--query`, `-q` | (required) | Search keywords |
| `--field` | `ALL` | Field to search: `ALL`, `TITLE`, `BODY`, or `NUMBER` |
| `--limit` | `25` | Results per page |
| `--offset` | `0` | Start index for pagination |

**Returns:** JSON with `total_results`, `start_index`, `items_per_page`, and `documents` array. Each document contains `title`, `description`, `link`, `pubDate`, and optionally `download_url`, `mime_type`, `category`.

### `search-all` -- Paginate through all search results

```
python3 policytech.py search-all --query <keywords> [--field ALL|TITLE|BODY|NUMBER]
```

Automatically paginates through all result pages (up to 20 pages of 50). Returns a single combined result with all matching documents.

### `list` -- List all published documents

```
python3 policytech.py list
```

Returns all documents accessible via the API key using a wildcard search. Automatically paginates.

### `info` -- Connection information

```
python3 policytech.py info
```

Returns the base URL and API endpoint URL.

## Response Format

Documents returned from search have this structure:

```json
{
  "total_results": 42,
  "start_index": 0,
  "items_per_page": 25,
  "documents": [
    {
      "title": "Travel Policy",
      "description": "Guidelines for employee travel and reimbursement...",
      "link": "https://yourorg.navexone.com/content/docview/?docid=123",
      "pubDate": "2025-06-15T00:00:00Z",
      "category": "Human Resources",
      "download_url": "https://yourorg.navexone.com/content/...",
      "mime_type": "application/pdf"
    }
  ]
}
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| HTTP 500 "Policy Manager Error" | Invalid or expired API key | Verify API key in Settings & Tools > IT Settings > API Keys |
| HTTP 404 | API Keys add-on not enabled | Contact NAVEX Support to enable it |
| "API Keys" not in IT Settings | Not on Professional plan, or add-on not enabled | Confirm plan level with NAVEX Support |
| Connection timeout | Network/firewall issue | Ensure the bridge host can reach `*.navexone.com` on port 443 |
| Empty results | Search terms too specific, or all documents have restricted security levels | Try a broader search; verify document security levels in PolicyTech |
| SSL certificate error | Proxy or inspection device intercepting TLS | Set `POLICYTECH_VERIFY_TLS=false` |
