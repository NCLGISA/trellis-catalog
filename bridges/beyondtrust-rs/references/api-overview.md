# BeyondTrust Remote Support API Reference

Quick reference for the BeyondTrust Remote Support APIs consumed by this bridge.

## Official Documentation

- [API Guide](https://docs.beyondtrust.com/rs/reference/api-guide)
- [Command API](https://docs.beyondtrust.com/rs/reference/command-api)
- [Session Generation API](https://docs.beyondtrust.com/rs/reference/session-generation-api)
- [Reporting API](https://docs.beyondtrust.com/rs/reference/reporting-api)
- [Configuration API](https://docs.beyondtrust.com/rs/reference/rs-configuration-api)
- [Backup API](https://docs.beyondtrust.com/rs/docs/backup-api)

## Authentication

All APIs use OAuth2 `client_credentials` grant.

```
POST https://<host>/oauth2/token
Authorization: Basic <base64(client_id:client_secret)>
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
```

Response:
```json
{
  "access_token": "<token>",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

Token lifetime: 1 hour. Max 30 concurrent tokens per API account.

All subsequent requests include:
```
Authorization: Bearer <access_token>
```

## Command API

**Base URL:** `https://<host>/api/command`
**Method:** GET or POST (form-encoded)
**Response:** XML with namespace `https://www.beyondtrust.com/namespaces/API/command`

### Actions

| Action | Description | Access |
|--------|-------------|--------|
| `check_health` | Appliance health/failover | Read-only |
| `get_appliances` | Cluster appliance list | Read-only |
| `get_api_info` | API version and permissions | Read-only |
| `get_logged_in_reps` | Logged-in representatives | Read-only |
| `set_rep_status` | Change rep availability | Full access |
| `logout_rep` | Force rep logout | Full access |
| `get_support_teams` | Teams and issue queues | Read-only |
| `generate_session_key` | Create session key | Full access |
| `create_virtual_customer` | Create virtual chat customer | Full access |
| `get_session_attributes` | Get session custom fields | Read-only |
| `set_session_attributes` | Set session custom fields | Full access |
| `join_session` | Add rep to session | Full access |
| `leave_session` | Remove rep from session | Full access |
| `transfer_session` | Move session to queue | Full access |
| `terminate_session` | End a session | Full access |
| `get_connected_client_list` | Client summary/list | Read-only |
| `get_connected_clients` | Detailed client info | Read-only |
| `import_jump_shortcut` | Import Jump shortcut | Full access |
| `set_failover_role` | Change failover role | Full access |

## Reporting API

**Base URL:** `https://<host>/api/reporting`
**Method:** GET or POST
**Response:** XML with namespace `https://www.beyondtrust.com/namespaces/API/reporting`

### Report Types

| Type | Description |
|------|-------------|
| `SupportSession` | Full session detail |
| `SupportSessionListing` | Session summary listing |
| `LicenseUsage` | License utilization |
| `SupportTeam` | Team activity |
| `Archive` | Archived sessions |
| `ArchiveListing` | Archived session summary |
| `JumpItem` | Jump Item report |
| `CommandShellRecording` | Command shell recordings |
| `SupportSessionRecording` | Session recordings |
| `Syslog` | Syslog events |
| `VaultAccountActivity` | Vault activity audit |

### Common Parameters

| Parameter | Description |
|-----------|-------------|
| `start_date` | Start of date range (ISO 8601) |
| `end_date` | End of date range (ISO 8601) |
| `duration` | ISO 8601 duration (e.g., P1D, PT1H, P7D) |
| `lsid` | Specific session LSID |
| `generate_report` | Set to `last_n_hours:N` for quick reports |

## Configuration API

**Base URL:** `https://<host>/api/config/v1/`
**Method:** GET, POST, PATCH, DELETE
**Response:** JSON
**Pagination:** `per_page` (max 100), `current_page` (1-based)

### Endpoints

| Resource | GET | POST | PATCH | DELETE |
|----------|-----|------|-------|--------|
| `/user` | List/detail | Create | Update | - |
| `/jumpoint` | List/detail | Create | Update | Delete |
| `/jump-group` | List/detail | Create | Update | Delete |
| `/jump-item/shell-jump` | List/detail | Create | Update | Delete |
| `/jump-item/remote-rdp` | List/detail | Create | Update | Delete |
| `/jump-item/remote-vnc` | List/detail | Create | Update | Delete |
| `/jump-item/local-jump` | List/detail | Create | Update | Delete |
| `/jump-item/protocol-tunnel-jump` | List/detail | Create | Update | Delete |
| `/jump-item/web-jump` | List/detail | Create | Update | Delete |
| `/vault/account` | List/detail | Create | Update | Delete |
| `/vault/endpoint` | List/detail | - | - | - |
| `/group-policy` | List/detail | - | Update | - |
| `/group-policy/{id}/jumpoint` | List | Add | - | Remove |
| `/group-policy/{id}/jump-group` | List | Add | - | Remove |
| `/group-policy/{id}/vault-account` | List | Add | - | Remove |

## Backup API

**URL:** `https://<host>/api/backup`
**Method:** GET
**Response:** ZIP file containing configuration and logged data (excluding recordings)

Limitations: Files > 200KB excluded, max 50 files.

## Rate Limits

- 20 requests/second
- 15,000 requests/hour

Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`

## XML Namespaces

When parsing XML responses with a namespace-aware parser:
- Command API: `https://www.beyondtrust.com/namespaces/API/command`
- Reporting API: `https://www.beyondtrust.com/namespaces/API/reporting`

These are namespace identifiers, not functional URLs.
