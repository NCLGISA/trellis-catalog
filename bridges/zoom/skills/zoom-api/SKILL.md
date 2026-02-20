---
name: zoom-api
description: >
  Zoom tenant administration via Server-to-Server OAuth API. Manage users, meetings, recordings,
  reports, dashboard metrics, Zoom Phone, groups, Zoom Rooms, account settings, voicemail admin,
  and call reporting.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.16"
metadata:
  author: tendril-project
  version: "1.4.0"
  tendril-bridge: "true"
  tags:
    - zoom
    - api
    - meetings
    - users
    - recordings
    - reports
    - phone
    - transcripts
    - voicemail
    - call-reporting
---

# Zoom API Bridge

Full programmatic access to your Zoom tenant via Server-to-Server OAuth.

## Authentication

- **Type:** Server-to-Server OAuth (`grant_type=account_credentials`)
- **Token URL:** `https://zoom.us/oauth/token`
- **API Base:** `https://api.zoom.us/v2`
- **Token lifetime:** 1 hour (auto-refreshed 5 minutes before expiry)
- **Scope:** Account-level, 1,510 granular scopes granted
- **Credentials:** `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET` in container environment (not per-operator)

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `zoom_client.py` | `/opt/bridge/data/tools/` | REST API v2 client with S2S OAuth auto-refresh, pagination, rate limiting, and department workflow helpers |
| `zoom_check.py` | `/opt/bridge/data/tools/` | Health check: validates env vars, token generation, and API access |
| `zoom_bridge_tests.py` | `/opt/bridge/data/tools/` | Comprehensive read-only battery test |
| `zoom_phone_admin.py` | `/opt/bridge/data/tools/` | Phone admin: voicemail settings, call reporting, auto attendant management, call queue membership |

## Quick Start

```bash
cd /opt/bridge/data/tools && python3 -c "
from zoom_client import ZoomClient; import json
print(json.dumps(ZoomClient().test_connection(), indent=2))
"
```

## Canonical Workflows (Preferred)

These three helper methods eliminate redundant API calls and return clean, AI-friendly output. **Always prefer these over raw API calls for phone workflows.**

### Full department phone analysis in 3 lines

```python
from zoom_client import ZoomClient
client = ZoomClient()

dept = client.phone_department('Building Inspections')
recs = client.phone_recordings('2026-02-16', department='Building Inspections')
transcripts = [client.phone_transcript(r['transcript_url']) for r in recs if r['has_transcript']]
```

### phone_department(department_name) -> dict

Returns complete phone infrastructure for a department: auto attendant(s), call queue(s) with members, and individual user extensions. One composable call instead of 3 separate explorations.

```python
dept = client.phone_department('Information Technology')
# Returns:
# {
#   "department": "Information Technology",
#   "users": [{"name": "Jane Doe", "ext": "8116", "did": "+15551234567", "email": "..."}],
#   "auto_attendants": [{"name": "Information Technology", "ext": "8105", "did": "+15551234567"}],
#   "call_queues": [{"name": "IT Help Desk", "ext": "81051", "id": "...", "members": ["Jane Doe", ...]}]
# }
```

### phone_recordings(from_date, to_date=None, department=None, owner=None) -> list

Returns recordings from the account-level endpoint (the correct one), pre-filtered and with clean field names. Handles pagination for busy days (900+/day).

**IMPORTANT:** Always use this instead of `/phone/users/{id}/recordings`. Call queue recordings are owned by the queue, not individual users, and only appear on the account-level endpoint.

```python
recs = client.phone_recordings('2026-02-16', department='Building Inspections')
# Filter by specific owner name instead of department
recs = client.phone_recordings('2026-02-16', owner='Teri Shaw')
```

### phone_transcript(transcript_url) -> list

Downloads a transcript and returns only speaker:text pairs. Strips QA disclaimers and all metadata noise.

**Context savings:** ~4KB raw JSON per call reduced to ~200 bytes clean text. For 13 transcripts: ~50KB down to ~5KB (10x reduction).

```python
for r in recs:
    if r['has_transcript']:
        lines = client.phone_transcript(r['transcript_url'])
        print(f"\n--- {r['caller']} -> {r['callee']} ({r['duration']}s) ---")
        for line in lines:
            print(f"  {line['speaker']}: {line['text']}")
```

## Phone Admin Tool Reference

### zoom_phone_admin.py -- Voicemail, Call Reporting, and Queue Management

```bash
# Voicemail and phone settings
python3 zoom_phone_admin.py voicemail user@example.com               # View phone/VM settings
python3 zoom_phone_admin.py voicemail-set user@... '{"key":"val"}'   # Update phone settings
python3 zoom_phone_admin.py settings user@example.com                # Full phone settings JSON

# Call reporting
python3 zoom_phone_admin.py call-report 2026-02-16 2026-02-16       # Account-wide call summary
python3 zoom_phone_admin.py call-report 2026-02-16 2026-02-16 --dept "Finance"  # Department summary
python3 zoom_phone_admin.py user-report user@... 2026-02-10 2026-02-16  # Individual user calls

# Auto attendants
python3 zoom_phone_admin.py aa-list                                   # List all auto attendants
python3 zoom_phone_admin.py aa-detail <aa-id>                        # AA detail and IVR config

# Call queue management
python3 zoom_phone_admin.py cq-members "Building Inspections"        # List queue members
python3 zoom_phone_admin.py cq-add <queue-id> <user-id>             # Add member to queue
python3 zoom_phone_admin.py cq-remove <queue-id> <member-id>        # Remove from queue
```

## Common Patterns

### Voicemail Troubleshooting (Freshservice: "Voicemail not working")
1. Check phone settings: `python3 zoom_phone_admin.py voicemail user@example.com`
2. Verify desk phone registration (check `status` field)
3. Review voicemail access delegates
4. Check outbound caller IDs for correct routing

### Call Reporting for Department Review
1. Full department call summary: `python3 zoom_phone_admin.py call-report 2026-02-01 2026-02-28 --dept "Social Services"`
2. Individual user report: `python3 zoom_phone_admin.py user-report user@... 2026-02-01 2026-02-28`
3. Review call queue membership: `python3 zoom_phone_admin.py cq-members "Social Services"`

### Call Queue Member Management
1. List current members: `python3 zoom_phone_admin.py cq-members "Building Inspections"`
2. Add new member: `python3 zoom_phone_admin.py cq-add <queue-id> <user-id>`
3. Remove member: `python3 zoom_phone_admin.py cq-remove <queue-id> <member-id>`

### New Employee Phone Setup
1. Check if user has phone license: `python3 zoom_phone_admin.py settings user@example.com`
2. View department phone structure: use `phone_department('Department Name')` in Python
3. Add to department call queue: `python3 zoom_phone_admin.py cq-add <queue-id> <user-id>`

## Client API Reference

### get_all(endpoint, key, params=None, page_size=300, max_pages=100)

Paginate through all results. The `key` parameter is the JSON response key containing the results array.

```python
from zoom_client import ZoomClient
client = ZoomClient()

# List all users (key='users')
users = client.get_all('/users', key='users')

# List all phone users (key='users')
phone_users = client.get_all('/phone/users', key='users', page_size=100)

# List all groups (key='groups')
groups = client.get_all('/groups', key='groups')
```

## Reference Patterns

### Phone user record structure

Key fields returned by `/phone/users`:

| Field | Type | Example |
|-------|------|---------|
| `name` | string | `"Jane Doe"` |
| `email` | string | `"user@example.com"` |
| `department` | string | `"Information Technology"` |
| `extension_number` | string | `"8116"` |
| `phone_numbers` | array | `[{"number": "+15551234567"}]` |
| `status` | string | `"activate"` |
| `calling_plans` | array | Plan details (Zoom Phone license type) |

### Phone user settings structure

Key fields returned by `/phone/users/{email}/settings`:

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"Active"` |
| `extension_number` | int | User extension |
| `company_number` | string | E.164 company number |
| `outbound_caller` | object | `{"number": "+15551234567"}` |
| `voice_mail` | array | Voicemail access delegates (user IDs, download/delete perms) |
| `desk_phone` | object | `{"devices": [...]}` -- registered desk phones with MAC, type, status |
| `outbound_caller_ids` | array | Available outbound caller IDs |
| `delegation` | object | `{"locked": false, "privacy": false}` |

### Get a single user's details

```python
user = client.get_user('user@example.com')
settings = client.get_user_settings('user@example.com')
```

### Zoom Phone hierarchy: auto attendants, call queues, and users

Departments typically have a three-tier call routing structure:

1. **Auto Attendant** (e.g., "Building Inspections" ext 8619, DID +15551234567) -- the public-facing number with an IVR menu
2. **Call Queue** (e.g., "Building Inspections" ext 86191) -- distributes calls to member users, may have automatic recording enabled
3. **Individual Users** (e.g., Lisa Scott ext 8610, Teri Shaw ext 8613) -- receive calls from the queue

Use `client.phone_department('Building Inspections')` to get all three tiers in one call.

## API Coverage

- **Users**: list_users, get_user, create_user, update_user, delete_user, get_user_settings
- **Meetings**: list_meetings, get_meeting, create_meeting, update_meeting, delete_meeting, list_meeting_participants
- **Recordings**: list_recordings, get_meeting_recordings, delete_meeting_recordings
- **Dashboard**: dashboard_meetings, dashboard_meeting_detail, dashboard_meeting_participants
- **Reports**: report_daily, report_users, report_meetings, report_operation_logs
- **Groups**: list_groups, get_group, list_group_members
- **Phone**: phone_list_users, phone_list_call_queues, phone_user_call_logs, phone_account_call_logs
- **Phone Workflows**: phone_department(), phone_recordings(), phone_transcript()
- **Phone Recordings**: `/phone/recordings` (account-level), `/phone/users/{id}/recordings` (user-level -- avoid for call queue recordings)
- **Phone Auto Attendants**: `/phone/auto_receptionists` (list), `/phone/auto_receptionists/{id}` (detail)
- **Phone Call Queues**: `/phone/call_queues` (list), `/phone/call_queues/{id}` (detail with members)
- **Phone Admin**: voicemail settings, phone user settings, call queue member management via `zoom_phone_admin.py`
- **Account**: get_account_info, get_account_settings
- **Rooms**: list_rooms, get_room
- **Webinars**: list_webinars, get_webinar

## Tenant Context

- **Tenant:** Configured via ZOOM_ACCOUNT_ID
- **Zoom Phone:** Users, auto attendants, and call queues vary by tenant
- **Extension format:** Typically 4-digit for users, 5-digit for call queues
- **Recordings:** Account-level recordings available via `/phone/recordings`

## Rate Limiting

- **Limit:** ~10 requests/second (varies by endpoint and plan)
- **Response:** HTTP 429 with `Retry-After` header (seconds)
- **Strategy:** Sleep for `Retry-After` seconds, then retry (max 3 attempts)

## Pagination

Zoom uses cursor-based pagination with `next_page_token`. The `get_all()` helper handles this automatically. Max `page_size` is 300.

## API Quirks and Known Issues

1. **User type codes:** 1=Basic, 2=Licensed, 3=On-Prem. Many users are Basic (free).
2. **Date formats:** ISO 8601 (`2026-02-16`) for date parameters. Some report endpoints require `from` and `to` dates.
3. **Meeting types:** 1=Instant, 2=Scheduled, 3=Recurring (no fixed time), 8=Recurring (fixed time).
4. **Past meetings:** Use `/past_meetings/{id}/participants` for participant data from completed meetings.
5. **Recordings:** Cloud recordings only. Date range limited to 30 days per request.
6. **Dashboard endpoints:** Require Business or higher plan. Return quality metrics, not available on Basic plans.
7. **Phone number format:** E.164 (e.g., `+15551234567`). Strip the `+1` prefix and format as `(XXX) XXX-XXXX` for display.
8. **Department filtering:** Not available as an API query parameter -- fetch all users then filter client-side. Use `phone_department()` to handle this automatically.
9. **Call queue recordings are NOT on user endpoints.** `/phone/users/{id}/recordings` only returns recordings owned by that user. Call queue recordings are owned by the queue and only appear in `/phone/recordings` (account-level). Use `phone_recordings()` which always hits the correct endpoint.
10. **Recording timestamps are UTC.** The `date_time` field is UTC regardless of the call queue's configured timezone. Convert to Eastern for display.
11. **Account recordings pagination.** `/phone/recordings` returns max 300 per page. The `total_records` field shows the true count. `phone_recordings()` handles pagination automatically via `get_all()`.
12. **Call queue members structure.** `/phone/call_queues/{id}` returns members as `{"users": [...]}` nested object, not a flat array. `phone_department()` handles this automatically.
13. **Transcript noise.** Raw transcript JSON is ~4KB per call with avatar_url, client_type, channel_mark, word_items, etc. Use `phone_transcript()` which strips all metadata and QA disclaimers, returning only speaker:text pairs (~200 bytes per call).
14. **Phone user settings key names.** The `/phone/users/{email}/settings` endpoint uses `voice_mail` (with underscore) not `voicemail`. Extension numbers are returned as integers, not strings.
