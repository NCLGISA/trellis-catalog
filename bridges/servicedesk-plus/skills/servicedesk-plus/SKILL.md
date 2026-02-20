---
name: servicedesk-plus
description: Gateway to ManageEngine ServiceDesk Plus Cloud. Manages changes, requests, problems, solutions, assets, CMDB, and announcements via REST API v3.
metadata:
  author: tendril-project
  version: "2.0"
  skill_scope: "bridge"
credentials:
  - key: client_id
    env: SDP_CLIENT_ID
    description: Zoho OAuth client ID (from api.zoho.com app registration)
  - key: client_secret
    env: SDP_CLIENT_SECRET
    description: Zoho OAuth client secret
  - key: refresh_token
    env: SDP_REFRESH_TOKEN
    description: Zoho OAuth refresh token (SDPOnDemand.changes.ALL, SDPOnDemand.requests.ALL, SDPOnDemand.problems.ALL, SDPOnDemand.setup.READ)
---

# ServiceDesk Plus Cloud Bridge

- **Instance**: Configured via SDP_INSTANCE_URL environment variable
- **Auth**: Zoho OAuth 2.0 (refresh token flow, auto-refreshed)
- **API version**: v3
- **CLI**: `python3 /opt/tendril/scripts/sdp.py <module> <action> [options]`

## Modules

### changes — Change Request Management

```
python3 /opt/tendril/scripts/sdp.py changes <action> [options]
```

| Action   | Required Args | Optional Args | Description |
|----------|--------------|---------------|-------------|
| create   | --title, --description | --change-type, --risk, --impact, --urgency, --priority, --roll-out-plan, --back-out-plan | Create change request |
| get      | --change-id | | Get change details and status |
| update   | --change-id | --description, --stage, --status | Update change fields |
| close    | --change-id | --description | Move to Completed/Close |
| list     | | --status, --limit | List recent changes |
| add-note | --change-id, --text | --public | Add note to change |

Defaults: --change-type=Standard, --risk=Medium, --impact="3 - Low", --urgency="3 - Low", --priority="5 - Standard"

### requests — Service Request / Ticket Management

```
python3 /opt/tendril/scripts/sdp.py requests <action> [options]
```

| Action   | Required Args | Optional Args | Description |
|----------|--------------|---------------|-------------|
| create   | --subject, --description | --priority, --urgency, --impact, --category, --subcategory | Create request |
| get      | --request-id | | Get request details |
| update   | --request-id | --subject, --description, --status, --priority | Update request |
| add-note | --request-id, --text | --public | Add note to request |
| close    | --request-id | --close-comment | Close request |
| list     | | --status, --limit | List recent requests |

### problems — ITIL Problem Management

```
python3 /opt/tendril/scripts/sdp.py problems <action> [options]
```

| Action   | Required Args | Optional Args | Description |
|----------|--------------|---------------|-------------|
| create   | --title, --description | --priority, --urgency, --impact, --status | Create problem |
| get      | --problem-id | | Get problem with root cause/workaround |
| update   | --problem-id | --title, --description, --status, --priority, --root-cause, --workaround | Update problem |
| close    | --problem-id | --description | Close problem |
| list     | | --status, --limit | List recent problems |
| add-note | --problem-id, --text | --public | Add note to problem |

### solutions — Knowledge Base

```
python3 /opt/tendril/scripts/sdp.py solutions <action> [options]
```

| Action | Required Args | Optional Args | Description |
|--------|--------------|---------------|-------------|
| create | --title, --description | --topic-id | Create KB article |
| get    | --solution-id | | Get article content |
| list   | | --limit | List recent articles |
| search | --query | --limit | Search articles by title |

### assets — Asset Inventory

```
python3 /opt/tendril/scripts/sdp.py assets <action> [options]
```

| Action | Required Args | Optional Args | Description |
|--------|--------------|---------------|-------------|
| get    | --asset-id | | Get asset details |
| list   | | --limit | List assets |
| search | | --name, --serial, --tag, --limit | Search by name/serial/tag |

### cmdb — Configuration Items

```
python3 /opt/tendril/scripts/sdp.py cmdb <action> [options]
```

| Action | Required Args | Optional Args | Description |
|--------|--------------|---------------|-------------|
| get    | --ci-id | | Get CI details |
| list   | | --ci-type-id, --limit | List CIs, optionally by type |
| search | --name | --limit | Search CIs by name |

### announcements — Service Announcements

```
python3 /opt/tendril/scripts/sdp.py announcements <action> [options]
```

| Action | Required Args | Optional Args | Description |
|--------|--------------|---------------|-------------|
| create | --title, --description | | Post announcement |
| get    | --announcement-id | | Get announcement |
| list   | | --limit | List recent announcements |
| delete | --announcement-id | | Delete announcement |

## SDP Value Reference

**Change Types:** Standard, Minor, Major, Significant
**Risks:** Low, Medium, High
**Impacts:** 1 - High, 2 - Medium, 3 - Low
**Urgencies:** 1 - High, 2 - Medium, 3 - Low
**Priorities:** 1 - Critical, 2 - High, 3 - Medium, 4 - Low, 5 - Standard
**Change Stages:** Submission, Planning, CAB Evaluation, Implementation, UAT, Release, Review, Close
**Change Statuses:** Accepted, Approval Pending, Approved, Back Out, Cancelled, Completed
**Request Statuses:** Open, On Hold, Resolved, Closed
**Problem Statuses:** Open, Closed

## Change Type Guidelines

| Scenario | Change Type | Risk |
|----------|------------|------|
| Server reboot | Minor | Medium |
| Registry modification | Standard | Medium |
| Software install/upgrade | Standard | Low |
| Active Directory changes | Major | High |
| DNS zone modifications | Standard | Medium |
| Firewall/network changes | Major | High |
| Tendril agent deployment | Minor | Low |
| OS patching / Windows Updates | Standard | Medium |
| Database schema changes | Major | High |
| Group Policy changes | Significant | High |

## Output Format

All commands output JSON to stdout. Errors go to stderr with exit code 1.
Successful operations include a `url` field with a direct link to the SDP object.

## Operator Credential Setup

Each operator stores their Zoho OAuth credentials via the Tendril credential vault:

```
bridge_credentials(action="set", bridge="servicedesk-plus", key="client_id", value="<zoho client id>")
bridge_credentials(action="set", bridge="servicedesk-plus", key="client_secret", value="<zoho client secret>")
bridge_credentials(action="set", bridge="servicedesk-plus", key="refresh_token", value="<zoho refresh token>")
```

Required OAuth scopes: SDPOnDemand.changes.ALL, SDPOnDemand.requests.ALL, SDPOnDemand.problems.ALL, SDPOnDemand.setup.READ
