---
name: ticket-search
description: Search and filter Freshservice tickets by keyword, category, status, and department with local text matching for subject/description fields
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.15"
metadata:
  author: tendril-project
  version: "1.0.0"
  tags:
    - freshservice
    - tickets
    - search
    - helpdesk
---

# Ticket Search

Search Freshservice service desk tickets by keyword, category, status, and department. Returns structured JSON suitable for analysis, cross-referencing, and reporting.

## Why Local Filtering?

The Freshservice `/tickets/filter` endpoint only supports a limited set of fields (`status`, `priority`, `created_at`, etc.). It does **not** support filtering by `subject` or `description` content. To search ticket content, this skill paginates through `/tickets` and applies local text matching in Python. This is the only reliable approach.

## Script

**Path:** `/opt/tendril/scripts/ticket_search.py`

**Requirements:** Python 3.x, `requests` (pre-installed on bridge)

**Environment:** Reads `FRESHSERVICE_DOMAIN` and `FRESHSERVICE_API_KEY` from environment variables (pre-configured on bridge-freshservice).

## Usage

### Search by keyword (subject + description)

```bash
python3 /opt/tendril/scripts/ticket_search.py --keyword "UPS"
```

### Filter by status

```bash
python3 /opt/tendril/scripts/ticket_search.py --keyword "UPS" --status open
```

Valid statuses: `open`, `pending`, `resolved`, `closed`

### Filter by category

```bash
python3 /opt/tendril/scripts/ticket_search.py --category "UPS"
```

### Filter by department

```bash
python3 /opt/tendril/scripts/ticket_search.py --department "IT"
```

### Combine filters

```bash
python3 /opt/tendril/scripts/ticket_search.py --keyword "battery" --category "UPS" --status open
```

### Exclude false positives

```bash
python3 /opt/tendril/scripts/ticket_search.py --keyword "battery" --exclude-keywords "laptop,phone,mouse"
```

### Include ticket conversations and notes

```bash
python3 /opt/tendril/scripts/ticket_search.py --keyword "UPS" --with-conversations
```

### Human-readable table summary

```bash
python3 /opt/tendril/scripts/ticket_search.py --keyword "power" --summary
```

## Output Format

Default output is JSON array of ticket objects:

```json
[
  {
    "id": 12345,
    "subject": "UPS Battery Replacement - DSS",
    "status": "Open",
    "priority": "Medium",
    "category": "UPS",
    "sub_category": "Replace UPS",
    "department": "IT",
    "created_at": "2025-06-04",
    "updated_at": "2025-12-15",
    "description_text": "UPS unit beeping intermittently..."
  }
]
```

With `--with-conversations`, each ticket includes a `conversations` array.

With `--summary`, output is a human-readable table with status/category breakdowns.

## Performance

- Scans up to 5,000 tickets by default (50 pages x 100 per page)
- Typical scan: 25-40 seconds depending on ticket volume
- Use `--max-pages 10` to limit scan to 1,000 most recent tickets for faster results
- Rate limiting: Freshservice allows 120 req/min; script auto-retries on 429

## Ticket Categories (customize for your instance)

| Category | Common Subcategories |
|----------|---------------------|
| UPS | Replace UPS, Replace Battery |
| Desktop | Installation, Problem, Replace |
| Server | Data Recovery, Installation, Problem |
| Software | Installation, Problem, Setup, Upgrade |
| Email | Phishing, Problem, Setup |
| Phone | Change, Installation, Problem |
| Printer | Installation, Problem |
| Security Access / ID Badges | Change, Problem, Replace, Setup |
| User | Authorization, Problem, Removal, Setup |

## Department ID Reference

Use department names with the `--department` flag. Partial matching is supported. Department IDs are organization-specific; obtain them from your Freshservice admin console or API.

| ID | Department |
|----|-----------|
| \<dept_id\> | Department Name |

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
