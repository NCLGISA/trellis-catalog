---
name: arcgis-online-api
description: >
  ArcGIS Online bridge for content management, user/group administration,
  feature service queries, geocoding, and portal administration via the
  ArcGIS REST API with OAuth2 client credentials authentication.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.19"
metadata:
  author: "NCLGISA"
  version: "2026.03.06.1"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - arcgis
    - esri
    - gis
    - geospatial
    - mapping
    - feature-services
    - geocoding
---

# ArcGIS Online API Bridge

Full programmatic access to an ArcGIS Online organization via the ArcGIS REST API.
Supports Organizational Plan and Developer accounts.

## Authentication

| Field | Value |
|-------|-------|
| **Auth type** | OAuth2 client credentials |
| **Token URL** | `https://www.arcgis.com/sharing/rest/oauth2/token` |
| **Token lifetime** | ~2 hours (auto-refreshed) |
| **Env vars** | `ARCGIS_ORG_URL`, `ARCGIS_CLIENT_ID`, `ARCGIS_CLIENT_SECRET` |

### Registering an OAuth2 Application

1. Sign in to your ArcGIS Online org as an administrator
2. Navigate to **Content** > **My Content**
3. Click **New item** > **Application** > **Other application** > **Application**
4. Name the app (e.g., "Tendril Bridge") and click **Register**
5. Copy the **Client ID** and **Client Secret** from the item page

### Configuring Application Privileges

After registering, you must explicitly set the app's privileges:

1. On the app's item page, go to the **Settings** tab
2. Scroll to the **Application** section
3. Click the **Edit** button (next to "Reset Secret" and "Unregister Application")
4. Enable required privileges: content and analysis, geocoding, portal
   administration, and premium content if needed
5. Click **Save**

Without setting privileges, the OAuth2 token will authenticate but API calls
will return permission errors or empty results.

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `arcgis_online_client.py` | `/opt/bridge/data/tools/` | REST API client with OAuth2, pagination, rate limiting |
| `arcgis_online_check.py` | `/opt/bridge/data/tools/` | Health check (env + token + API connectivity) |
| `arcgis_online_bridge_tests.py` | `/opt/bridge/data/tools/` | Integration test battery (7 tests, read-only) |
| `arcgis_online_content.py` | `/opt/bridge/data/tools/` | Content: search items, item details, layers, folders |
| `arcgis_online_users.py` | `/opt/bridge/data/tools/` | Users: list, search, groups, membership |
| `arcgis_online_features.py` | `/opt/bridge/data/tools/` | Features: query layers, counts, schema, export |
| `arcgis_online_admin.py` | `/opt/bridge/data/tools/` | Admin: org info, credits, usage reports, roles |
| `arcgis_online_geocoding.py` | `/opt/bridge/data/tools/` | Geocoding: forward, reverse, suggest, batch |

## Quick Start

```bash
# Health check
python3 /opt/bridge/data/tools/arcgis_online_check.py

# Full test battery
python3 /opt/bridge/data/tools/arcgis_online_bridge_tests.py

# Search for items
python3 /opt/bridge/data/tools/arcgis_online_content.py search "parcels"

# List org users
python3 /opt/bridge/data/tools/arcgis_online_users.py list-users

# Query a feature layer
python3 /opt/bridge/data/tools/arcgis_online_features.py query <service_url> 0 --where "1=1" --num 5

# Geocode an address
python3 /opt/bridge/data/tools/arcgis_online_geocoding.py geocode "123 Main St, Springfield, IL"

# Check org credits
python3 /opt/bridge/data/tools/arcgis_online_admin.py credits
```

## Tool Reference

### arcgis_online_content.py

| Subcommand | Description |
|------------|-------------|
| `search <query>` | Search items (--type, --num, --sort) |
| `item <item_id>` | Full item metadata (JSON) |
| `item-data <item_id>` | Item data payload |
| `layers <service_url>` | List layers and tables in a service |
| `folders <username>` | List user's content folders |
| `folder-items <user> <folder>` | Items in a specific folder |

### arcgis_online_users.py

| Subcommand | Description |
|------------|-------------|
| `list-users` | Paginated user list (--num, --start) |
| `user <username>` | Full user profile (JSON) |
| `search-users <query>` | Search by name/email |
| `list-groups` | List org groups (--query) |
| `group <group_id>` | Group details (JSON) |
| `group-members <group_id>` | List owner, admins, members |

### arcgis_online_features.py

| Subcommand | Description |
|------------|-------------|
| `query <url> <layer>` | Query features (--where, --fields, --num, --geometry) |
| `count <url> <layer>` | Feature count (--where) |
| `info <url> <layer>` | Layer schema: fields, geometry type, limits |
| `export <url> <layer>` | Export to geojson, json, or csv (--format) |

### arcgis_online_admin.py

| Subcommand | Description |
|------------|-------------|
| `org-info` | Organization name, region, subscription, helper services |
| `credits` | Available credits and subscription expiration |
| `usage` | Usage reports (--days) |
| `roles` | Custom and built-in role definitions |

### arcgis_online_geocoding.py

Uses the org's configured geocode service or falls back to the ArcGIS World
Geocoding Service (Esri hosted).

| Subcommand | Description |
|------------|-------------|
| `geocode <address>` | Forward geocode (--max, --country) |
| `reverse <lat> <lon>` | Reverse geocode to address |
| `suggest <text>` | Address autocomplete suggestions |
| `batch <file>` | Batch geocode from text file (one address per line) |

## Known Issues / API Quirks

- **Content search returns 0 items**: The OAuth2 app may need content sharing
  privileges enabled (Settings > Application > Edit), or items must be shared
  with "Everyone" or the app's group to appear in search.
- **Search is fuzzy**: ArcGIS search is designed for human use. Search by item
  ID for precision.
- **Token in query params**: ArcGIS REST API passes tokens as query parameters,
  not Authorization headers. The client handles this automatically.
- **Error-in-200**: ArcGIS often returns HTTP 200 with an error object in the
  JSON body. The client detects and raises these.
- **Geocoding consumes credits**: Forward, reverse, and batch geocoding consume
  ArcGIS credits. Batch is more efficient per address. Monitor your credit
  balance with `arcgis_online_admin.py credits`.
- **Rate limits**: The client retries on HTTP 429 with exponential backoff.
- **Org geocoder reachability**: If your org configures an on-premise geocode
  service, it may not be reachable from the bridge container. The geocoding
  tool discovers the org's service and falls back to the World Geocoder
  automatically.

## Battery Test

```bash
python3 /opt/bridge/data/tools/arcgis_online_bridge_tests.py --json
```

Tests: env vars, OAuth2 token, org info, content search, users, groups, geocoding.
