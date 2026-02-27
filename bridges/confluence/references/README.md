# Confluence Cloud Bridge -- Setup Guide

## Prerequisites

This bridge requires a Confluence Cloud instance (`*.atlassian.net`) and per-user API tokens.

## Step 1: Determine Your Site URL

Your Confluence Cloud URL is your Atlassian site URL:

```
https://yourorg.atlassian.net
```

Do **not** include `/wiki` -- the bridge appends that automatically.

Set this as `CONFLUENCE_URL` in your `.env` file.

## Step 2: Create an API Token

Each operator needs their own API token:

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Name it (e.g., "Tendril Bridge")
4. Copy the generated token immediately (it won't be shown again)

API tokens inherit the creating user's Confluence permissions. They do not expire but can be revoked at any time.

## Step 3: Store Per-Operator Credentials

Per-operator credentials are stored via the Tendril bridge credentials system, not in the `.env` file:

```
bridge_credentials set confluence CONFLUENCE_EMAIL your.email@example.com
bridge_credentials set confluence CONFLUENCE_API_TOKEN your-api-token-here
```

These are auto-injected when you execute commands on the bridge.

## Step 4: Configure and Deploy

1. Copy `.env.example` to `.env`
2. Fill in the shared values:
   ```
   CONFLUENCE_URL=https://yourorg.atlassian.net
   ```
3. Build and start the container:
   ```bash
   docker compose build
   docker compose up -d
   ```

## Step 5: Verify

Run the health check (requires per-operator credentials to be stored first):

```bash
# Via Tendril (credentials auto-injected)
python3 /opt/bridge/data/tools/confluence_check.py
```

Expected output:
```json
{
  "bridge": "confluence",
  "checks": [
    {"name": "connect", "status": "pass", ...},
    {"name": "auth", "status": "pass", "user": "Your Name", ...},
    {"name": "spaces", "status": "pass", "space_count": 5, ...}
  ],
  "summary": "3/3 checks passed",
  "healthy": true
}
```

## Per-Operator Authentication Model

This bridge uses **per-operator** credentials (like the Splunk bridge):

- `CONFLUENCE_URL` is **shared** -- same for all operators, set in `.env`
- `CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN` are **per-operator** -- each user stores their own via `bridge_credentials`
- API calls run as the individual user with their permissions
- All actions are attributed to the user in Confluence audit logs
- Users can only access spaces/pages they have permission to see

This provides a proper audit trail and respects Confluence's permission model.

## Troubleshooting

### HTTP 401 Unauthorized

The email or API token is incorrect. Verify:
- The email matches your Atlassian account exactly
- The API token is current (regenerate at https://id.atlassian.com/manage-profile/security/api-tokens)
- Your Atlassian account has access to the Confluence instance

### HTTP 403 Forbidden

The authenticated user lacks permission for the requested operation. Check space and page permissions in Confluence.

### HTTP 404 on API calls

- Verify `CONFLUENCE_URL` does not include `/wiki`
- Ensure the site has Confluence enabled (not just Jira)

### "Current user not permitted to use Confluence"

The Atlassian account exists but doesn't have a Confluence license. Contact your Atlassian admin to grant access.

## API Reference

The bridge uses two API versions:

**REST API v2** (primary) -- `/wiki/api/v2/`
- Pages, spaces, blog posts, comments, labels, tasks, attachments, versions
- Cursor-based pagination
- Docs: https://developer.atlassian.com/cloud/confluence/rest/v2/intro/

**REST API v1** (search) -- `/wiki/rest/api/`
- CQL search with excerpts and content expansion
- User info
- Label management
- Docs: https://developer.atlassian.com/cloud/confluence/rest/v1/intro/

**Authentication:** Basic auth with `email:api_token` base64-encoded in the `Authorization` header.

**Rate limits:** Confluence Cloud enforces rate limits. The bridge does not implement retry logic -- if you hit limits, space out requests.
