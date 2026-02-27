---
name: ukg-ready
description: UKG Ready bridge for employee directory, time & attendance, PTO/leave management, payroll configuration, scheduling, reports, web clock, and company configuration via the UKG Ready REST API (V1/V2).
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.27"
metadata:
  author: tendril-project
  version: "2026.02.27.1"
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
    description: UKG Ready host URL (e.g. https://secure6.saashr.com)
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

Programmatic access to UKG Ready (formerly Kronos Workforce Ready) via REST API. Supports employee management, PTO/leave, payroll configuration, scheduling, reports, web clock, and company configuration.

## Authentication

The bridge authenticates via a two-step token flow:

1. **POST /ta/rest/v1/login** with `Api-Key` header and service account credentials
2. Receives a JWT token (1-hour TTL) containing the company ID (`cid`)
3. All subsequent requests use `Authentication: Bearer {token}` + `Api-Key` headers

The client automatically refreshes the token before expiry and retries on 401.

## Credentials

| Variable | Scope | Description |
|----------|-------|-------------|
| `UKG_BASE_URL` | shared | Host URL (e.g. `https://secure6.saashr.com`) |
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
| `ukg_check.py` | `/opt/bridge/data/tools/` | Health check: auth, employees, config |

## Quick Start

```bash
python3 /opt/bridge/data/tools/ukg_check.py
python3 /opt/bridge/data/tools/ukg.py info
python3 /opt/bridge/data/tools/ukg.py employees list
python3 /opt/bridge/data/tools/ukg.py employees list --active-only
python3 /opt/bridge/data/tools/ukg.py pto categories
python3 /opt/bridge/data/tools/ukg.py reports list
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
python3 ukg.py employees custom-fields --id 12345  # HR custom fields
python3 ukg.py employees search --query "Smith"    # Search by name
```

### pto -- PTO / Time-Off

```bash
python3 ukg.py pto categories                      # Time-off categories
python3 ukg.py pto requests                        # All PTO requests
python3 ukg.py pto requests --id 12345             # Employee PTO requests
python3 ukg.py pto accruals --id 12345             # Accrual balances
python3 ukg.py pto submit --id 12345 --start-date 2026-03-01 --end-date 2026-03-02 --category "Vacation"
```

### payroll -- Payroll Configuration

```bash
python3 ukg.py payroll pay-periods                 # Pay period profiles
python3 ukg.py payroll pay-types                   # Pay types
python3 ukg.py payroll rate-tables                 # Rate tables
python3 ukg.py payroll deductions --id 12345       # Employee deductions
python3 ukg.py payroll compensation --id 12345     # Total compensation
```

### schedule -- Scheduling

```bash
python3 ukg.py schedule list --id 12345            # Employee schedule
python3 ukg.py schedule work-prefs --id 12345      # Work time preferences
```

### reports -- Reports

```bash
python3 ukg.py reports list                        # Available reports
python3 ukg.py reports run --report-id 100         # Run global report
python3 ukg.py reports saved --report-id 100       # Run saved report
python3 ukg.py reports metadata --report-id 100    # Report metadata
```

### webclock -- Web Clock

```bash
python3 ukg.py webclock punch --id 12345           # Clock punch
python3 ukg.py webclock punch --id 12345 --punch-type in
```

### contracts -- Employee Contracts

```bash
python3 ukg.py contracts list --id 12345           # Employee contracts
```

### config -- Company Configuration

```bash
python3 ukg.py config cost-centers                 # Cost centers
python3 ukg.py config account-groups               # Account groups
python3 ukg.py config announcements                # Announcements
python3 ukg.py config holidays                     # Holiday profiles
```

### export -- Data Exports

```bash
python3 ukg.py export list                         # Available exports
python3 ukg.py export status --export-id 100       # Export status
```

### info -- Connection Info

```bash
python3 ukg.py info                                # Token status, company ID
```

## API Notes

- V2 endpoints use `/ta/rest/v2/companies/{cid}/...` (plural)
- V1 endpoints use `/ta/rest/v1/company/{cid}/...` (singular)
- Company ID (`cid`) is extracted from the JWT, not the 7-digit short name
- Token TTL is 1 hour; the client refreshes automatically
- Rate limiting returns HTTP 429; the client retries with exponential backoff
- Employee records include HATEOAS `_links` to sub-resources (demographics, badges, pay-info, profiles)
