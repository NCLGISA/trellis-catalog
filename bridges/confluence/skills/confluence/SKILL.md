---
name: confluence
description: Confluence Cloud bridge -- full CRUD for pages, CQL search with content retrieval, spaces, blog posts, comments, labels, and tasks via REST API v2. Per-operator authentication via Atlassian email + API token.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.24"
metadata:
  author: tendril-project
  version: "2026.02.27.1"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - confluence
    - atlassian
    - wiki
    - pages
    - spaces
    - blog
    - comments
    - labels
    - tasks
    - search
    - cql
    - knowledge-base
    - collaboration
credentials:
  - key: CONFLUENCE_URL
    env: CONFLUENCE_URL
    scope: shared
    description: "Atlassian site URL (e.g. https://yourorg.atlassian.net)"
  - key: CONFLUENCE_EMAIL
    env: CONFLUENCE_EMAIL
    scope: operator
    description: "Atlassian account email for basic auth"
  - key: CONFLUENCE_API_TOKEN
    env: CONFLUENCE_API_TOKEN
    scope: operator
    description: "Per-user API token from https://id.atlassian.com/manage-profile/security/api-tokens"
---

# Confluence Cloud Bridge

Full CRUD access to Confluence Cloud via the REST API v2. Read and write pages, search with CQL, manage spaces, blog posts, comments, labels, and tasks. Retrieves full page content (not just titles).

## Authentication

- **Type:** Per-user basic auth (email + API token)
- **Token source:** https://id.atlassian.com/manage-profile/security/api-tokens
- **Environment:** `CONFLUENCE_URL` (shared) + `CONFLUENCE_EMAIL` (per-operator) + `CONFLUENCE_API_TOKEN` (per-operator)
- **Scope:** Token inherits the creating user's Confluence permissions (spaces, pages, admin rights)
- **Audit trail:** API calls are attributed to the individual user, visible in Confluence audit logs

## Deployment Prerequisites

1. **Confirm Confluence Cloud** -- this bridge targets `*.atlassian.net` (not Data Center or Server)
2. **Create an API token** at https://id.atlassian.com/manage-profile/security/api-tokens
3. **Store per-operator credentials** via Tendril `bridge_credentials`:
   - `CONFLUENCE_EMAIL` -- your Atlassian email
   - `CONFLUENCE_API_TOKEN` -- your API token
4. **Set the shared URL** in `.env`: `CONFLUENCE_URL=https://yourorg.atlassian.net`

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `confluence_client.py` | `/opt/bridge/data/tools/` | Core REST API client -- v2 pages/spaces/blogposts/comments/labels/tasks + v1 CQL search |
| `confluence.py` | `/opt/bridge/data/tools/` | CLI: spaces, pages, search, blogposts, comments, labels, tasks, info |
| `confluence_check.py` | `/opt/bridge/data/tools/` | Health check: auth, user context, space access |

## Capabilities

### Spaces
- **List spaces** -- enumerate all spaces the user can see
- **Get space** -- retrieve space details by ID

### Pages (full CRUD)
- **List pages** -- list pages in a space or across all spaces
- **Get page with content** -- retrieve a page including its full body (storage format, atlas_doc_format, or rendered HTML)
- **Create page** -- create a new page in a space with HTML body content
- **Update page** -- update title and body (auto-increments version if omitted)
- **Delete page** -- move a page to trash
- **Get children** -- list child pages
- **Get ancestors** -- list parent page hierarchy
- **Get versions** -- list page version history

### Search
- **CQL search** -- full Confluence Query Language search with highlighted excerpts and content
- Supports all CQL operators: `type`, `space`, `label`, `text~`, `title~`, `ancestor`, `created`, `lastModified`, etc.

### Blog Posts
- **List blog posts** -- by space or across all spaces
- **Get blog post** -- retrieve with full body content

### Comments
- **List comments** -- footer comments on a page
- **Create comment** -- add a comment to a page

### Labels
- **List labels** -- labels on a page
- **Add label** -- tag a page with a label

### Tasks
- **List tasks** -- list inline tasks (complete or incomplete)

### Health Check
- **3-point check** -- validates connectivity, authentication (current user), and space access

## Quick Start

```bash
# Health check
python3 confluence_check.py

# List spaces
python3 confluence.py spaces list

# Search for pages containing "runbook"
python3 confluence.py search --cql 'type=page AND text~"runbook"'

# Get a specific page with content
python3 confluence.py pages get --id 12345678

# Create a page
python3 confluence.py pages create --space-id 98765 --title "New Page" --body "<p>Hello world</p>"

# Update a page (auto-increments version)
python3 confluence.py pages update --id 12345678 --title "Updated Title" --body "<p>New content</p>"

# Delete a page
python3 confluence.py pages delete --id 12345678

# List blog posts
python3 confluence.py blogposts list --space-id 98765

# Add a comment to a page
python3 confluence.py comments create --page-id 12345678 --body "<p>Looks good!</p>"

# Add a label to a page
python3 confluence.py labels add --page-id 12345678 --label "reviewed"

# List tasks
python3 confluence.py tasks list --status incomplete

# Connection info
python3 confluence.py info
```

## CLI Reference

### spaces list / get

```bash
python3 confluence.py spaces list [--limit 25]
python3 confluence.py spaces get --id <space_id>
```

### pages list / get / create / update / delete

```bash
python3 confluence.py pages list [--space-id <id>] [--limit 25] [--body-format storage|view]
python3 confluence.py pages get --id <page_id> [--body-format storage|atlas_doc_format|view]
python3 confluence.py pages create --space-id <id> --title "Title" --body "<p>HTML</p>" [--parent-id <id>]
python3 confluence.py pages update --id <page_id> --title "Title" --body "<p>HTML</p>" [--version N]
python3 confluence.py pages delete --id <page_id>
```

**Body formats:**
- `storage` -- Confluence storage format (XML/HTML, default, best for programmatic use)
- `atlas_doc_format` -- Atlassian Document Format (ADF JSON)
- `view` -- rendered HTML as displayed in the browser

### search

```bash
python3 confluence.py search --cql '<CQL query>' [--limit 25]
```

**Common CQL patterns:**

| Pattern | Description |
|---------|-------------|
| `type=page AND text~"keyword"` | Full-text search across pages |
| `type=page AND title~"exact phrase"` | Title search |
| `type=page AND space="KEY"` | Pages in a specific space |
| `type=page AND label="tag"` | Pages with a label |
| `type=page AND creator=currentUser()` | Pages created by you |
| `type=page AND lastModified>"2025-01-01"` | Recently modified pages |
| `type=blogpost AND space="KEY"` | Blog posts in a space |

### blogposts list / get

```bash
python3 confluence.py blogposts list [--space-id <id>] [--limit 25]
python3 confluence.py blogposts get --id <blogpost_id> [--body-format storage|view]
```

### comments list / create

```bash
python3 confluence.py comments list --page-id <id> [--limit 25]
python3 confluence.py comments create --page-id <id> --body "<p>Comment text</p>"
```

### labels list / add

```bash
python3 confluence.py labels list --page-id <id>
python3 confluence.py labels add --page-id <id> --label "my-label"
```

### tasks list

```bash
python3 confluence.py tasks list [--limit 25] [--status complete|incomplete]
```

### info

```bash
python3 confluence.py info
```

## Page Body Format

Pages use **Confluence storage format** (a subset of XHTML) by default:

```html
<p>This is a paragraph.</p>
<h2>Heading</h2>
<ul><li>Bullet point</li></ul>
<ac:structured-macro ac:name="info"><ac:rich-text-body><p>Info panel</p></ac:rich-text-body></ac:structured-macro>
```

When creating or updating pages, pass the body in storage format. Use `--body-format view` when reading to get rendered HTML.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| HTTP 401 | Invalid email or API token | Verify credentials; regenerate token at id.atlassian.com |
| HTTP 403 | User lacks permission | Check space/page permissions in Confluence admin |
| HTTP 404 on spaces | No spaces accessible, or wrong URL | Verify `CONFLUENCE_URL` includes no `/wiki` suffix |
| Version conflict on update | Stale version number | Omit `--version` to auto-increment, or get current version first |
| Empty search results | CQL syntax error or no matches | Test CQL in Confluence UI first; check quoting |

## Notes

- Per-operator auth: each user's API calls run as their Atlassian identity with their permissions
- The v2 API uses cursor-based pagination; the CLI handles single pages; use the client library for cursor traversal
- CQL search uses the v1 API (`/wiki/rest/api/search`) which returns richer results with excerpts
- Page bodies in storage format can contain Confluence macros (`ac:structured-macro`)
- API tokens never expire but can be revoked at https://id.atlassian.com/manage-profile/security/api-tokens
