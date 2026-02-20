---
name: change-request
description: Create, document, and push IT Change Requests to Freshservice. Use when the operator has completed infrastructure work via Tendril and wants to create a CR document, push it to Freshservice, link CMDB assets, or update/close an existing change. Triggers on mentions of change request, CR, Freshservice, change management, or documenting a change.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.15"
metadata:
  author: tendril-project
  version: "1.0.0"
  tendril-bridge: "true"
  tags:
    - freshservice
    - change-requests
    - itsm
    - documentation
credentials:
  - key: api_key
    env: FRESHSERVICE_API_KEY
    description: Freshservice REST API key for operator-specific authentication (Basic auth with key as username)
---

# Change Request Workflow

Create, document, and push IT Change Requests into Freshservice from Tendril-based infrastructure work.

## Bridge-Native Workflow

The operator (AI) is the orchestrator. No batch sync, no CLI, no local venv required.

```
1. Gather context     (Tendril investigation, what changed, why)
2. Write CR markdown  (use template below, fill all sections)
3. Push to bridge     (file_push to /opt/bridge/data/cr/)
4. Parse              (cr_parser.py on bridge extracts structured data)
5. Create change      (freshservice_client.py calls Freshservice API)
6. Add notes + assets (planning notes, CMDB asset links, requester)
```

## Step 1: Gather Context

Before writing the CR, collect what was done using Tendril:

- **What changed**: service config, software install, registry, firewall, etc.
- **Which servers**: exact hostnames (these become CMDB asset links)
- **Why**: the problem that triggered the change
- **When**: dates of planning, implementation
- **Risk**: what could go wrong and how to revert
- **Who requested it**: name of the person or team

Check Azure tags on affected servers for application/department context:

```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\Tendril\ServerInfo' | Select Application, Department, Lifecycle, ServerType, Vendor
```

## Step 2: Write the CR Document

### File naming

```
cr-YYYY-MMDD-short-name.md
```

Examples: `cr-2026-0216-is01s077-sql-database-cleanup.md`, `cr-2026-0205-pwsh7-dev-servers.md`

### Template

Use this template. The summary table fields map directly to Freshservice Change API fields. The section headings map to Freshservice planning notes.

```markdown
# Change Request: CR-YYYY-MMDD-SHORT-NAME

## Title of the Change

---

## Change Request Summary

| Field | Value |
|-------|-------|
| **CR Number** | CR-YYYY-MMDD-SHORT-NAME |
| **Title** | Title of the Change |
| **Type** | Standard Change |
| **Priority** | Medium |
| **Risk Level** | Low |
| **Status** | Pending Approval |
| **Requested Date** | YYYY-MM-DD |
| **Implemented Date** | -- |
| **Requested By** | Name / Team |
| **Implemented By** | -- |
| **Change Window** | Business hours / After hours / Maintenance window |

---

## Problem Statement
(WHY this change is needed. Maps to Freshservice "Reason for Change" note.)

## Affected Servers
(Hostnames in a code block. Automatically linked to CMDB assets.)

## Impact Analysis
(Risk matrix, scope of impact. Maps to "Impact Analysis" note.)

## Implementation Plan
(Prerequisites, steps, method. Maps to "Rollout Plan" note.)

## Rollback Plan
(Revert steps, triggers, estimated time. Maps to "Backout Plan" note.)

## Verification
(Post-implementation checks. Not sent to Freshservice.)

## Timeline
(Chronological event log.)
```

### Field Mapping

| Template Field | Freshservice API Field | Valid Values |
|---|---|---|
| CR Number | Subject prefix | `CR-YYYY-MMDD-SHORT-NAME` |
| Title | subject | Free text |
| Type | change_type | 1=Minor, 2=Standard, 3=Major, 4=Emergency |
| Priority | priority | 1=Low, 2=Medium, 3=High, 4=Urgent |
| Risk Level | risk | 1=Low, 2=Medium, 3=High, 4=Very High |
| Status | status | 1=Open, 2=Planning, 3=Awaiting Approval, 4=Pending Release, 5=Pending Review, 6=Closed |
| Requested Date | planned_start_date | YYYY-MM-DD (sent as ISO 8601) |
| Implemented Date | planned_end_date | YYYY-MM-DD (sent as ISO 8601) |
| Requested By | requester_id | Resolved by name lookup (see Requester Resolution) |
| Implemented By | agent_id | Resolved by name lookup or defaults to operator |

### Planning Sections -> Freshservice Notes

The Freshservice API cannot write to Planning tab fields directly. These CR sections are posted as formatted Change Notes:

| CR Section | Freshservice Note Title |
|---|---|
| Problem Statement | Reason for Change |
| Impact Analysis | Impact Analysis |
| Implementation Plan | Rollout Plan |
| Rollback Plan | Backout Plan |

## Step 3: Push to Bridge

Push the completed CR markdown to the bridge:

```
file_push(agent="bridge-freshservice", remote_path="/opt/bridge/data/cr/cr-YYYY-MMDD-name.md", content="<markdown>")
```

## Step 4: Parse the CR

Run the parser on the bridge to extract structured data:

```python
cd /opt/bridge/data/tools && python3 -c "
from cr_parser import parse_cr_file, to_freshservice_change
cr = parse_cr_file('/opt/bridge/data/cr/cr-YYYY-MMDD-name.md')
payload = to_freshservice_change(cr)
import json
print(json.dumps(payload, indent=2, default=str))
"
```

The parser returns a dict with all fields plus `affected_servers`, `reason_for_change`, `impact_analysis`, `implementation_plan`, `rollback_procedure`, `requested_by`, `implemented_by`, and `description_html`.

The `to_freshservice_change()` function converts it to a Freshservice-ready payload with integer field values.

## Step 5: Create the Change in Freshservice

```python
cd /opt/bridge/data/tools && python3 -c "
from freshservice_client import FreshserviceClient
from cr_parser import parse_cr_file, to_freshservice_change, _markdown_to_simple_html

client = FreshserviceClient()
cr = parse_cr_file('/opt/bridge/data/cr/cr-YYYY-MMDD-name.md')
payload = to_freshservice_change(cr, requester_id=REQUESTER_ID)
payload['agent_id'] = AGENT_ID

result = client.create_change(payload)
change = result.get('change', {})
change_id = change.get('id')
print(f'Created change #{change_id}')
"
```

## Step 6: Add Planning Notes and Link Assets

### Planning notes

For each non-empty planning section, create a formatted note:

```python
sections = [
    ('Reason for Change', cr.get('reason_for_change', '')),
    ('Impact Analysis', cr.get('impact_analysis', '')),
    ('Rollout Plan', cr.get('implementation_plan', '')),
    ('Backout Plan', cr.get('rollback_procedure', '')),
]
for title, content in sections:
    if content:
        html = _markdown_to_simple_html(content)
        note_body = f'<h2 style="color:#2c5282; border-bottom:2px solid #2c5282; padding-bottom:4px;">{title}</h2>\n{html}'
        client.create_change_note(change_id, note_body)
```

### Link CMDB assets

Affected servers should already exist as CMDB assets in Freshservice. Look up their display_id and link them:

```python
# Get asset display_id by searching
assets = client.filter_assets(f"name:'{hostname}'")
display_id = assets[0]['display_id'] if assets else None

# Link to change
client.put(f'changes/{change_id}', json={'assets': [{'display_id': display_id}]})
```

If an affected server is not yet in Freshservice CMDB, sync it first using the asset_sync tools or create it manually before linking.

## Requester Resolution

When the CR specifies a **Requested By** name (e.g., "John Smith"), resolve it to a Freshservice requester_id:

```python
requesters = client.list_requesters()
# Match by first_name + last_name
for r in requesters:
    full_name = f"{r.get('first_name','')} {r.get('last_name','')}".strip()
    if search_name.lower() in full_name.lower():
        requester_id = r['id']
        break
```

Default `requester_id`: Resolve by name or use your instance's default requester
Default `agent_id`: Resolve by name or use your instance's default agent
Default `department_id`: Use your IT department's ID from Freshservice admin console

## Post-Implementation Updates

After the change is implemented, update the Freshservice change:

### Close the change

```python
client.update_change(change_id, {'status': 6})  # 6 = Closed
```

### Update requester (if different from creator)

```python
client.update_change(change_id, {'requester_id': resolved_requester_id})
```

### Add implementation note

```python
client.create_change_note(change_id, '<h3>Implementation Completed</h3><div>Details...</div>')
```

## Freshservice IDs (customize for your instance)

| Entity | ID |
|---|---|
| Default agent | \<agent_id\> |
| IT Department | \<dept_id\> |

## Bridge Tools Reference

| Tool | Path | Purpose |
|---|---|---|
| cr_parser.py | /opt/bridge/data/tools/cr_parser.py | Parse CR markdown into structured dict, convert to Freshservice payload |
| freshservice_client.py | /opt/bridge/data/tools/freshservice_client.py | Freshservice REST API v2 client with rate limiting |

## Quality Gates

Before creating a Freshservice change:

1. All affected server hostnames should resolve to CMDB assets in Freshservice. If any are missing, create/sync them first.
2. The **Requested By** name should resolve to a valid Freshservice requester. If not found, default to your instance's primary agent and note the discrepancy.
3. Review the parsed payload with the operator before creating (show subject, status, priority, risk, affected servers).
