---
name: freshservice-api
description: Freshservice REST API v2 reference covering authentication, CMDB, tickets, change requests, departments, and the existing bridge tool inventory
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.15"
metadata:
  author: tendril-project
  version: "1.2.0"
  tendril-bridge: "true"
  tags:
    - freshservice
    - api
    - cmdb
    - change-requests
    - reference
credentials:
  - key: api_key
    env: FRESHSERVICE_API_KEY
    description: Freshservice REST API key for operator-specific authentication (Basic auth with key as username)
---

# Freshservice API Reference

Institutional knowledge for your Freshservice instance (yourorg.freshservice.com). This skill documents the API patterns, field mappings, and existing tools available on the bridge-freshservice agent.

## Authentication

All API calls use HTTP Basic Auth:

- **Username:** Operator's Freshservice API key (injected from Tendril credential vault as `FRESHSERVICE_API_KEY`)
- **Password:** `X` (literal string)
- **Base URL:** `https://{FRESHSERVICE_DOMAIN}/api/v2`

Each operator must store their personal Freshservice API key in the Tendril credential vault. The key is found in Freshservice under Profile > Profile Settings > API Key.

```
bridge_credentials(action='set', bridge='freshservice-api', key='api_key', value='<your-API-key>')
```

```python
import os, requests
domain = os.environ["FRESHSERVICE_DOMAIN"]
api_key = os.environ["FRESHSERVICE_API_KEY"]
auth = (api_key, "X")
resp = requests.get(f"https://{domain}/api/v2/tickets", auth=auth)
```

## Rate Limiting

- **Limit:** 120 requests per minute
- **Response:** HTTP 429 with `Retry-After` header (seconds)
- **Strategy:** Sleep for `Retry-After` seconds, then retry (max 3 attempts)

## Ticket API

### List tickets

```
GET /api/v2/tickets?per_page=100&page=1
```

Returns: `{ "tickets": [...] }`

Pagination: Up to 100 per page, iterate until empty response.

### Get single ticket

```
GET /api/v2/tickets/{id}
```

### Get ticket conversations

```
GET /api/v2/tickets/{id}/conversations?per_page=100&page=1
```

Returns: `{ "conversations": [...] }`

### Filter tickets (limited fields)

```
GET /api/v2/tickets/filter?query="status:2 AND priority:3"
```

**Supported filter fields:** `status`, `priority`, `type`, `created_at`, `updated_at`, `due_by`, `group_id`, `agent_id`, `department_id`, `category`, `sub_category`

**NOT supported:** `subject`, `description`, `description_text` -- use local filtering via `/tickets` pagination instead.

### Create ticket

Both `group_id` and `department_id` may be **required** by your instance. The `responder_id` (assigned agent) **must be a member of the specified `group_id`** or the API returns HTTP 400.

If the requester email does not match an existing requester, Freshservice will auto-create one. Replace `department_id`, `group_id`, and `responder_id` with values from your instance (see Department Mapping and Agent Group Mapping).

```
POST /api/v2/tickets
Content-Type: application/json

{
  "subject": "UPS Battery Alert - DSS Server Room",
  "description": "Battery age exceeds recommended replacement...",
  "email": "helpdesk@example.com",
  "status": 2,
  "priority": 3,
  "category": "UPS",
  "sub_category": "Replace UPS",
  "department_id": 7000000001,
  "group_id": 7000000002,
  "responder_id": 7000000003
}
```

**Using the Python client:**

```python
from freshservice_client import FreshserviceClient
fs = FreshserviceClient()
result = fs.create_ticket({
    "subject": "UPS Battery Alert - DSS Server Room",
    "description": "Battery age exceeds recommended replacement...",
    "email": "helpdesk@example.com",
    "status": 2,
    "priority": 3,
    "category": "UPS",
    "sub_category": "Replace UPS",
    "department_id": 7000000001,
    "group_id": 7000000002,
    "responder_id": 7000000003,
    "assets": [{"display_id": 4090}]
})
```

### Requester Lookup

Find an existing requester by email before ticket creation:

```python
requester = fs.find_requester_by_email("user@example.com")
if requester:
    print(f"Found: {requester['id']} - {requester['first_name']} {requester['last_name']}")
else:
    print("Not found -- pass email to create_ticket() and Freshservice will auto-create")
```

## CMDB / Assets API

### List assets

```
GET /api/v2/assets?per_page=100&page=1
```

### Get single asset

```
GET /api/v2/assets/{display_id}
```

### Find asset by name

The `search` query parameter on `/assets` is broken (returns HTTP 400). Use the `filter` parameter or the Python client's `find_asset_by_name()` method which handles fallback:

```python
asset = fs.find_asset_by_name("IS01S163")
if asset:
    print(f"Found: display_id={asset['display_id']}, name={asset['name']}")
```

### Create asset

```
POST /api/v2/assets
Content-Type: application/json

{
  "name": "IS01S064",
  "asset_type_id": 7000003713,
  "type_fields": {
    "product_7000003713": "Dell PowerEdge R640",
    "os_7000003713": "Windows Server 2019"
  }
}
```

### Asset relationships

```
GET /api/v2/assets/{display_id}/relationships
POST /api/v2/assets/{display_id}/relationships
```

## Change Requests API

### Create change request

```
POST /api/v2/changes
Content-Type: application/json

{
  "subject": "Replace UPS battery - Jail server room",
  "description": "Scheduled replacement of 11.7-year-old battery...",
  "priority": 2,
  "status": 1,
  "change_type": 1,
  "risk": 2,
  "impact": 2,
  "planned_start_date": "2026-02-20T09:00:00Z",
  "planned_end_date": "2026-02-20T11:00:00Z"
}
```

### Change types

| Code | Type |
|------|------|
| 1 | Minor |
| 2 | Standard |
| 3 | Major |
| 4 | Emergency |

## Department Mapping

> **Note:** Department IDs are organization-specific. Obtain them from your Freshservice admin console or API. Example format:

| ID | Department |
|----|-----------|
| \<dept_id\> | Department Name |

## Agent Group Mapping

The `responder_id` (assigned agent) must be a member of the `group_id` specified on the ticket, or the API returns HTTP 400 ("Assigned agent isn't a member of the group").

| ID | Group |
|----|-------|
| \<group_id\> | Group Name |

## Ticket Categories and Subcategories

| Category | Subcategories |
|----------|--------------|
| Cabling | -- |
| Cell Phone | Problem, Replace, Setup |
| County Website | Add, Change, Problem |
| Desktop | Installation, Problem, Replace |
| Email | Phishing, Problem, Setup |
| GIS | Address/Road Naming, Change, Maps, Other, Problem |
| Internet | Connectivity, Website Change, Website Problem |
| Laptop | Installation, Problem, Quote, Reimage, Replace |
| MUNIS | ESS Account Locked, ESS Supervisor Setup, Password, Problem, Access Denied |
| Other | -- |
| Phone | Change, Installation, Problem |
| Printer | Installation, Problem |
| Report | Other, SQL |
| Scanner | Problem |
| Security Access / ID Badges | Change, Problem, Replace, Setup |
| Server | Data Recovery, Installation, Problem |
| Software | Installation, Problem, Profile Issue, Setup, Training, Upgrade |
| Tablet | Problem, Setup |
| UPS | Replace UPS, Replace Battery |
| User | Authorization, Problem, Removal, Setup, Update |

## Status and Priority Codes

| Code | Status |
|------|--------|
| 2 | Open |
| 3 | Pending |
| 4 | Resolved |
| 5 | Closed |

| Code | Priority |
|------|----------|
| 1 | Low |
| 2 | Medium |
| 3 | High |
| 4 | Urgent |

## Existing Bridge Tools

The bridge-freshservice container includes these tools at `/opt/bridge/data/tools/`:

| Script | Purpose |
|--------|---------|
| `freshservice_client.py` | Python API client class wrapping all endpoints |
| `cli.py` | CLI interface for interactive API operations |
| `cmdb_sync.py` | Sync server documentation to CMDB assets |
| `cr_parser.py` | Create and manage Change Requests |
| `cmdb_parser.py` | Map discovered services to CI types |
| `asset_sync.py` | Asset synchronization utilities |
| `change_sync.py` | Change request sync operations |
| `collect_all.py` | Bulk collection and export |

### Using existing tools

```bash
# Verify API connectivity
python3 /opt/bridge/data/tools/cli.py --help

# Sync server documentation to CMDB
python3 /opt/bridge/data/tools/cmdb_sync.py --server IS01S064

# Create a change request
python3 /opt/bridge/data/tools/cr_parser.py --subject "UPS Battery Replacement" --type minor
```

## API Quirks and Known Issues

1. **Filter endpoint is limited:** `/tickets/filter` does not accept `subject` or `description` as query fields. Use the ticket-search skill's paginated approach instead.

2. **Include parameter on /tickets:** Adding `?include=stats` or `?include=requester` to `/tickets` returns HTTP 400 on some endpoints. Omit the include parameter and fetch details separately if needed.

3. **Pagination ceiling:** The API returns a maximum of 10 pages (1,000 items) for some endpoints. For tickets, pagination up to 50+ pages works reliably.

4. **Date formats:** All dates are ISO 8601 (`2026-02-15T14:30:00Z`). Filter queries use quoted strings: `"created_at:>'2026-01-01'"`.

5. **HTML in descriptions:** `description` field contains HTML; use `description_text` for plain-text searches.

6. **Asset search parameter is broken:** `GET /assets?search="name"` returns HTTP 400. Use the filter parameter instead: `GET /assets?filter="name:'HOSTNAME'"`. Even the filter can miss assets with mixed-case names -- the `find_asset_by_name()` client method handles this with a paginated fallback.

7. **Requester auto-creation:** If a requester email does not exist in Freshservice, passing it in the `email` field of `create_ticket()` will automatically create the requester. No need to pre-create them via `/requesters`.

## Tenant Context

- **Instance:** Configured via FRESHSERVICE_DOMAIN environment variable
- **Agents/Requesters/Departments:** Varies by instance. Check your Freshservice admin console.
- **CMDB assets, relationship types, change requests, ticket volume:** All vary by organization.
