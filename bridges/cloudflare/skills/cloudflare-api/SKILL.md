---
name: cloudflare-api
description: >
  Manage Cloudflare zones, DNS, tunnels, Zero Trust (Access, Gateway), email routing,
  WAF, SSL/TLS, and caching via the Cloudflare API v4 on bridge-cloudflare.
  Use for DNS audits, tunnel-to-origin mapping, Access app inventory,
  service token expiry checks, or any Cloudflare operations.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.16"
metadata:
  author: tendril-project
  version: "1.1.0"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - cloudflare
    - dns
    - tunnels
    - zero-trust
    - email
    - waf
credentials:
  - key: CLOUDFLARE_OPERATOR_TOKEN
    env: CLOUDFLARE_OPERATOR_TOKEN
    description: >
      Personal Cloudflare API token with User-level "API Tokens: Edit" permission.
      Enables programmatic token management (add/remove permissions, create tokens).
      Create at: Cloudflare Dashboard > My Profile > API Tokens > Create Token >
      User scope > API Tokens: Edit.
---

# Cloudflare API Bridge

Full read/write access to the Cloudflare platform for your account via the Cloudflare REST API v4. The bridge token has
Edit permissions across all active service areas for operational management.

## Quick Start

```
MCP Server: user-tendril
Tool: execute
Agent: bridge-cloudflare
Shell: bash
```

Verify the bridge is working:

```bash
python3 /opt/bridge/data/tools/cloudflare_check.py
```

## Environment

| Setting | Value |
|---------|-------|
| Product | Cloudflare (Free/Pro/Business/Enterprise) |
| API Base | `https://api.cloudflare.com/client/v4` |
| Auth | Bearer token (scoped API token) |
| Zone | Discovered automatically from API token |
| Agent | bridge-cloudflare |
| Host | bridge-cloudflare (Docker, tendril-bridges stack) |

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `cloudflare_client.py` | `/opt/bridge/data/tools/` | REST API client with pagination, rate limiting |
| `cloudflare_check.py` | `/opt/bridge/data/tools/` | Health check: validates token and all service areas |
| `tunnel_map.py` | `/opt/bridge/data/tools/` | Maps tunnels to FQDN -> origin service pairs |
| `dns_audit.py` | `/opt/bridge/data/tools/` | DNS zone export, classification, orphan detection |
| `zero_trust_audit.py` | `/opt/bridge/data/tools/` | Access apps, policies, service tokens, gateway audit |
| `token_manager.py` | `/opt/bridge/data/tools/` | Programmatic API token permission management (operator token required) |

## Authentication

Two-tier credential model following the Tendril Bridge Architecture:

### Shared Bridge Token (container environment)

Pre-configured in the Docker container. Available to all operators for
full Cloudflare management -- DNS, tunnels, firewall, Zero Trust, etc.

```
CLOUDFLARE_API_TOKEN   - Scoped API token (Bearer auth, Edit access)
CLOUDFLARE_ACCOUNT_ID  - Account identifier
```

Token scopes (Edit where available, Read for audit-only services):
Zone (Edit), DNS (Edit), SSL and Certificates (Edit),
Zone Settings (Edit), Firewall Services (Edit), Logs (Read),
Transform Rules (Edit), Dynamic Redirect (Edit),
Access: Apps and Policies (Read), Access: Audit Logs (Read),
Access: Organizations/IdPs/Groups (Read), Access: Service Tokens (Read),
Account Settings (Read), Cloudflare Tunnel (Read),
Cloudflare One Networks (Read), Cloud Email Security (Read),
Email Routing Addresses (Read), Zero Trust (Read).

### Operator Token (per-operator, via Tendril vault)

Personal token with User-level "API Tokens: Edit" permission for
programmatic token management. Stored in the Tendril credential vault
and injected only during command execution.

```
CLOUDFLARE_OPERATOR_TOKEN  - Personal token with API Tokens: Edit (User scope)
```

Store via:
```
bridge_credentials(action="set", bridge="cloudflare",
  key="CLOUDFLARE_OPERATOR_TOKEN", value="<your-token>")
```

## API Coverage

### Core Services

| Method | Endpoint | Description |
|--------|----------|-------------|
| `list_zones()` | GET /zones | List all zones |
| `get_zone(zone_id)` | GET /zones/{id} | Get zone details |
| `find_zone_id(domain)` | GET /zones?name= | Find zone ID by domain name |
| `list_dns_records(zone_id)` | GET /zones/{id}/dns_records | List DNS records |
| `get_dns_record(zone_id, record_id)` | GET /zones/{id}/dns_records/{rid} | Get single record |
| `get_ssl_settings(zone_id)` | GET /zones/{id}/settings/ssl | SSL/TLS mode |
| `get_ssl_verification(zone_id)` | GET /zones/{id}/ssl/verification | Certificate status |
| `list_certificates(zone_id)` | GET /zones/{id}/ssl/certificate_packs | SSL certificates |
| `get_tls_settings(zone_id)` | GET /zones/{id}/settings/min_tls_version | Minimum TLS version |
| `list_page_rules(zone_id)` | GET /zones/{id}/pagerules | Page rules |
| `list_firewall_rules(zone_id)` | GET /zones/{id}/firewall/rules | Firewall rules |
| `list_waf_packages(zone_id)` | GET /zones/{id}/firewall/waf/packages | WAF rule packages |
| `get_cache_level(zone_id)` | GET /zones/{id}/settings/cache_level | Cache level |
| `get_browser_cache_ttl(zone_id)` | GET /zones/{id}/settings/browser_cache_ttl | Browser cache TTL |
| `list_zone_settings(zone_id)` | GET /zones/{id}/settings | All zone settings |

### Cloudflare Tunnels

| Method | Endpoint | Description |
|--------|----------|-------------|
| `list_tunnels()` | GET /accounts/{id}/cfd_tunnel | List all tunnels |
| `get_tunnel(tunnel_id)` | GET /accounts/{id}/cfd_tunnel/{tid} | Get tunnel details |
| `get_tunnel_configurations(tunnel_id)` | GET .../cfd_tunnel/{tid}/configurations | Ingress rules (hostname -> origin) |
| `list_tunnel_connections(tunnel_id)` | GET .../cfd_tunnel/{tid}/connections | Active connector connections |
| `list_tunnel_routes()` | GET /accounts/{id}/teamnet/routes | CIDR-to-tunnel route mappings |

### Zero Trust: Access

| Method | Endpoint | Description |
|--------|----------|-------------|
| `list_access_apps()` | GET /accounts/{id}/access/apps | All Access Applications |
| `get_access_app(app_id)` | GET .../access/apps/{aid} | Single app details |
| `list_access_policies(app_id)` | GET .../access/apps/{aid}/policies | Policies for an app |
| `list_access_groups()` | GET /accounts/{id}/access/groups | Access Groups |
| `get_access_group(group_id)` | GET .../access/groups/{gid} | Single group |
| `list_service_tokens()` | GET /accounts/{id}/access/service_tokens | Service Tokens |
| `list_identity_providers()` | GET /accounts/{id}/access/identity_providers | Configured IdPs |

### Zero Trust: Gateway

| Method | Endpoint | Description |
|--------|----------|-------------|
| `list_gateway_rules()` | GET /accounts/{id}/gateway/rules | Gateway filtering rules |
| `list_gateway_locations()` | GET /accounts/{id}/gateway/locations | DNS endpoint locations |
| `list_gateway_categories()` | GET /accounts/{id}/gateway/categories | Content categories |
| `get_gateway_configuration()` | GET /accounts/{id}/gateway/configuration | Account-level gateway config |

### Email Routing

| Method | Endpoint | Description |
|--------|----------|-------------|
| `get_email_routing_settings(zone_id)` | GET /zones/{id}/email/routing | Email routing status |
| `list_email_routing_rules(zone_id)` | GET /zones/{id}/email/routing/rules | Routing rules |
| `list_email_routing_addresses(zone_id)` | GET /zones/{id}/email/routing/addresses | Destination addresses |

### Account

| Method | Endpoint | Description |
|--------|----------|-------------|
| `get_account()` | GET /accounts/{id} | Account details |
| `list_account_members()` | GET /accounts/{id}/members | Account members |

## Common Patterns

### Map all public FQDNs to internal origins

```bash
python3 /opt/bridge/data/tools/tunnel_map.py --table
```

Returns every Cloudflare Tunnel hostname with its origin service URL,
e.g., `app.example.com -> https://localhost:443`.

### Full DNS zone export

```bash
python3 /opt/bridge/data/tools/dns_audit.py --table
```

Classifies every DNS record as tunnel-backed, proxied, or DNS-only.
Flags DNS-only A records pointing to private IPs.

### Zero Trust inventory

```bash
python3 /opt/bridge/data/tools/zero_trust_audit.py --table
```

Shows all Access Applications with their policies, service tokens
with expiry dates, identity providers, and Gateway rules.

### Check service token expiry

```bash
python3 /opt/bridge/data/tools/zero_trust_audit.py --section tokens
```

Returns service tokens sorted by days until expiry. Flags tokens
expiring within 30 days and already-expired tokens.

### Quick client usage from Python

```python
import sys; sys.path.insert(0, '/opt/bridge/data/tools')
from cloudflare_client import CloudflareClient

client = CloudflareClient()
zones = client.list_zones()
zone_id = client.find_zone_id('example.com')
records = client.list_dns_records(zone_id)
tunnels = client.list_tunnels()
apps = client.list_access_apps()
```

### List all zone settings

```bash
python3 -c "
import sys; sys.path.insert(0, '/opt/bridge/data/tools')
from cloudflare_client import CloudflareClient
import json
c = CloudflareClient()
zid = c.find_zone_id()
settings = c.list_zone_settings(zid)
for s in settings:
    print(f\"{s['id']:30s}  {json.dumps(s.get('value', '?'))}\")
"
```

### Manage API token permissions (requires operator token)

```bash
# Verify operator token access
python3 /opt/bridge/data/tools/token_manager.py verify

# List all tokens and their permissions
python3 /opt/bridge/data/tools/token_manager.py list-tokens --verbose

# Show full details for a specific token
python3 /opt/bridge/data/tools/token_manager.py show-token TOKEN_ID

# Search available permission groups
python3 /opt/bridge/data/tools/token_manager.py list-permissions --search "firewall"

# Add a permission to the bridge token
python3 /opt/bridge/data/tools/token_manager.py add-permission TOKEN_ID --group-id GROUP_ID

# Remove a permission from a token
python3 /opt/bridge/data/tools/token_manager.py remove-permission TOKEN_ID --group-id GROUP_ID

# Audit bridge token: show current permissions
python3 /opt/bridge/data/tools/token_manager.py audit
```

## API Quirks and Known Issues

- **Pagination**: Cloudflare uses `page`/`per_page` with `result_info.total_pages`.
  The client handles this automatically via `get_all()`.
- **Result wrapping**: All API responses wrap results in `{"success": true, "result": ...}`.
  The client extracts `result` automatically.
- **Rate limits**: 1200 requests per 5 minutes per user. The client retries on 429
  with the `Retry-After` header value.
- **Tunnel config endpoint**: Returns the full ingress configuration including
  catch-all rules. The `service` field uses `http_status:404` for the default
  catch-all, not a URL.
- **Access app types**: Common types are `self_hosted`, `saas`, `ssh`, `vnc`,
  `bookmark`. Self-hosted apps have a `domain` field; SaaS apps have `saas_app`.
- **Service token expiry**: Tokens without an `expires_at` field never expire.
  The API returns ISO 8601 timestamps in UTC for those that do.
- **Gateway rules**: Rules are evaluated in `precedence` order. The `traffic`
  field contains the wire filter expression (e.g., `dns.fqdn == "example.com"`).
- **Email routing**: Returns 404 if Email Routing is not enabled for the zone.
  The check script handles this gracefully.
- **Zone ID required**: Most zone-level endpoints require the zone ID, not the
  domain name. Use `find_zone_id('example.com')` (or your domain) to resolve it.
