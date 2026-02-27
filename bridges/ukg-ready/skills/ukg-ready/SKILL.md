---
name: ukg-ready
description: UKG Ready bridge for employee directory, time & attendance, compensation, notifications, and company configuration via the UKG Ready REST API (V1/V2).
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.27"
metadata:
  author: tendril-project
  version: "2026.02.27.2"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - ukg
    - ukg-ready
    - kronos
    - hcm
    - hr
    - payroll
    - time-attendance
    - pto
    - scheduling
    - employees
credentials:
  - key: UKG_BASE_URL
    env: UKG_BASE_URL
    scope: shared
    description: UKG Ready host URL (e.g. https://secureN.saashr.com) -- see references/README.md Step 5
  - key: UKG_COMPANY_SHORT_NAME
    env: UKG_COMPANY_SHORT_NAME
    scope: shared
    description: 7-digit company identifier from login URL
  - key: UKG_API_KEY
    env: UKG_API_KEY
    scope: shared
    description: REST API key from Company Setup > Login Config > API Keys
  - key: UKG_USERNAME
    env: UKG_USERNAME
    scope: shared
    description: Service account username from Login Config > Service Accounts
  - key: UKG_PASSWORD
    env: UKG_PASSWORD
    scope: shared
    description: Service account password
---

# UKG Ready Bridge

Programmatic access to UKG Ready (formerly Kronos Workforce Ready) via REST API. Supports employee management, compensation, time & attendance, notifications, and company configuration.

## Authentication

The bridge authenticates via a two-step token flow:

1. **POST /ta/rest/v1/login** with `Api-Key` header and service account credentials
2. Receives a JWT token (1-hour TTL) containing the company ID (`cid`)
3. All subsequent requests use `Authentication: Bearer {token}` + `Api-Key` headers

The client automatically refreshes the token before expiry and retries on 401.

## Determining Your API Endpoint URL

UKG Ready hosts tenants across regional clusters (`secure3`, `secure4`, `secure5`, `secure6`, `secure7`, etc.). Find yours from your login URL:

```
https://secureN.saashr.com/ta/XXXXXXX.login
         ^^^^^^^ this is your host
```

Set `UKG_BASE_URL` to `https://secureN.saashr.com` (no trailing slash). See `references/README.md` Step 5 for full details.

## Credentials

| Variable | Scope | Description |
|----------|-------|-------------|
| `UKG_BASE_URL` | shared | Host URL (e.g. `https://secureN.saashr.com`) |
| `UKG_COMPANY_SHORT_NAME` | shared | 7-digit company ID from login URL |
| `UKG_API_KEY` | shared | REST API key from Login Config > API Keys |
| `UKG_USERNAME` | shared | Service account username |
| `UKG_PASSWORD` | shared | Service account password |
| `UKG_VERIFY_TLS` | shared | Set `false` for self-signed certs (default: `true`) |

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `ukg_client.py` | `/opt/bridge/data/tools/` | Core REST client -- login, token management, V1/V2 URL construction |
| `ukg.py` | `/opt/bridge/data/tools/` | Unified CLI for all modules |
| `ukg_check.py` | `/opt/bridge/data/tools/` | Health check: auth + employee endpoint validation |

## Quick Start

```bash
python3 /opt/bridge/data/tools/ukg_check.py
python3 /opt/bridge/data/tools/ukg.py info
python3 /opt/bridge/data/tools/ukg.py employees list
python3 /opt/bridge/data/tools/ukg.py employees list --active-only
python3 /opt/bridge/data/tools/ukg.py config cost-centers
python3 /opt/bridge/data/tools/ukg.py notifications mailbox
```

## CLI Reference

### employees -- Employee Management

```bash
python3 ukg.py employees list                     # All employees
python3 ukg.py employees list --active-only        # Active only
python3 ukg.py employees get --id 12345            # Single employee
python3 ukg.py employees demographics --id 12345   # Demographics
python3 ukg.py employees pay-info --id 12345       # Pay information
python3 ukg.py employees badges --id 12345         # Badge info
python3 ukg.py employees contacts --id 12345       # Contacts
python3 ukg.py employees profiles --id 12345       # Employee profiles
python3 ukg.py employees attendance --id 12345     # Attendance status
python3 ukg.py employees holidays --id 12345       # Holiday assignments
python3 ukg.py employees search --query "Smith"    # Search by name
```

### compensation -- Employee Compensation

```bash
python3 ukg.py compensation total --id 12345       # Total compensation
python3 ukg.py compensation history --id 12345     # Compensation history
python3 ukg.py compensation additional --id 12345  # Additional compensation
```

### config -- Company Configuration

```bash
python3 ukg.py config cost-centers                           # Cost centers (default tree 0)
python3 ukg.py config cost-centers --tree-index 4            # Specific tree index
python3 ukg.py config cost-center-lists                      # Cost center list definitions
```

### notifications -- Notifications and Mailbox

```bash
python3 ukg.py notifications mailbox                                       # Last 30 days
python3 ukg.py notifications mailbox --created-from 2026-01-01 --created-to 2026-01-31  # Date range
python3 ukg.py notifications todo --id 12345                               # Employee to-do items
```

### info -- Connection Info

```bash
python3 ukg.py info                                # Token status, company ID, base URL
```

## Per-Employee Time Entries

The V2 API exposes per-employee time entries (max 31-day range per request):

```
GET /ta/rest/v2/companies/{cid}/employees/{id}/time-entries?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

Each entry includes `total` (milliseconds), `type` (TIME, etc.), `cost_centers`, and `approval_status`. The `ukg_client.py` helper can be used directly for bulk time queries.

## API Notes

- V2 endpoints use `/ta/rest/v2/companies/{cid}/...` (plural)
- V1 endpoints use `/ta/rest/v1/company/{cid}/...` (singular)
- Company ID (`cid`) is extracted from the JWT, not the 7-digit short name
- Token TTL is 1 hour; the client refreshes automatically
- Rate limiting returns HTTP 429; the client retries with exponential backoff
- Employee records include HATEOAS `_links` to sub-resources (demographics, badges, pay-info, profiles)
- Time entry queries are limited to 31-day ranges; iterate in monthly chunks for longer periods
