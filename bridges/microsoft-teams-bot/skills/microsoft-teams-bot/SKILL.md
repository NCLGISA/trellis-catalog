---
name: microsoft-teams-bot
description: >
  Teams Bot Framework bridge for real-time messaging, proactive sends, and
  tenant-wide chat/channel message reads via Graph API. Supports dual-mode:
  webhook (cloudflared tunnel + Bot Framework) or polling (Graph API only).
compatibility:
  - tendril-agent
metadata:
  author: tendril-project
  version: "2026.02.24.1"
  tendril-bridge: "true"
  skill_scope: bridge
  tags: microsoft, teams, bot-framework, chat, proactive-messaging, cloudflare-tunnel
---

# Microsoft Teams Bot Bridge

## Purpose

Provides Microsoft Teams integration through two complementary paths:

1. **Bot Framework (webhook mode)** -- Real-time message receipt and proactive
   sends via a registered Azure Bot behind a Cloudflare tunnel
2. **Graph API (both modes)** -- Tenant-wide read access to all chat and channel
   messages for compliance, audit, and search

The bot operates as its **own identity** (configurable via `TEAMS_BOT_NAME`). It
cannot impersonate users -- messages sent by the bot appear from the bot account.

## Architecture

### Dual-Mode Operation

| Mode | Components | Capabilities |
|------|-----------|-------------|
| **webhook** (default) | cloudflared + bot_server.py + Tendril | Real-time message receipt, proactive messaging, Graph API reads |
| **polling** | Tendril only | Graph API message reads only, no real-time receipt, no proactive send |

### Webhook Mode Data Flow

```
Teams User -> Azure Bot Service -> Cloudflare Tunnel -> cloudflared -> bot_server.py (:3978)
                                                                            |
                                                                    Store ConversationReference
                                                                            |
Tendril Tools -> localhost API -> bot_server.py -> Azure Bot Service -> Teams User (proactive)
Tendril Tools -> Graph API -> Read all messages tenant-wide
```

## Authentication

**Client secret** (not certificate) -- Bot Framework standard pattern.

| Component | Auth Method | Scope |
|-----------|------------|-------|
| Bot Framework | App ID + Client Secret | Single-tenant, message webhook |
| Graph API | MSAL client_credentials | Application permissions for tenant reads |

## Setup

### Automated (recommended)

```bash
# From the bridge directory:
bash references/setup_teams_bot.sh contoso.onmicrosoft.com
```

The script creates the Entra app, client secret, Azure Bot Service resource,
enables the Teams channel, adds Graph permissions, and grants admin consent.

### Manual Steps

1. **Entra App Registration**
   - Sign-in audience: "Accounts in this organizational directory only" (single-tenant)
   - Create a client secret (note the value -- it is only shown once)

2. **Azure Bot Service**
   - Create an Azure Bot resource linked to the app registration
   - Set messaging endpoint to your Cloudflare tunnel URL + `/api/messages`
   - Enable the Microsoft Teams channel

3. **Graph API Permissions** (Application, admin consent required)
   - `Chat.Read.All` -- Enumerate user chats (via /users/{id}/chats)
   - `ChatMessage.Read.All` -- Read all chat messages
   - `ChannelMessage.Read.All` -- Read all channel messages
   - `User.Read.All` -- Enumerate users (for user-scoped chat access)
   - `Team.ReadBasic.All` -- List teams
   - `Channel.ReadBasic.All` -- List channels

4. **Cloudflare Tunnel**
   - Create a tunnel at Cloudflare Zero Trust dashboard
   - Route the tunnel hostname to `http://localhost:3978`
   - Copy the tunnel token for `CLOUDFLARE_TUNNEL_TOKEN`

5. **Teams App Installation**
   - Install the bot to desired teams/channels, or deploy tenant-wide via admin policy

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TEAMS_BOT_APP_ID` | Yes | | Entra app registration client ID |
| `TEAMS_BOT_APP_SECRET` | Yes | | Client secret |
| `TEAMS_BOT_TENANT_ID` | Yes | | Entra tenant ID |
| `TEAMS_BOT_NAME` | No | Tendril Bot | Display name in Teams |
| `TEAMS_BOT_MODE` | No | webhook | `webhook` or `polling` |
| `TEAMS_BOT_PORT` | No | 3978 | aiohttp server port |
| `CLOUDFLARE_TUNNEL_TOKEN` | webhook | | Cloudflare tunnel token |
| `TENDRIL_INSTALL_KEY` | Yes | | Tendril agent install key |

## Tools

| Script | Path | Purpose |
|--------|------|---------|
| `bot_server.py` | `/opt/bridge/data/tools/bot_server.py` | Bot Framework webhook server (long-running) |
| `bot_handler.py` | `/opt/bridge/data/tools/bot_handler.py` | TeamsActivityHandler with conversation ref storage |
| `teams_client.py` | `/opt/bridge/data/tools/teams_client.py` | Graph API client + bot server localhost API |
| `teams_check.py` | `/opt/bridge/data/tools/teams_check.py` | Health check (env, Graph API, bot server) |
| `teams_bridge_tests.py` | `/opt/bridge/data/tools/teams_bridge_tests.py` | Battery tests (8 tests across Graph + bot) |
| `chat_messages.py` | `/opt/bridge/data/tools/chat_messages.py` | Read/search 1:1 and group chat messages |
| `channel_messages.py` | `/opt/bridge/data/tools/channel_messages.py` | Read/search channel messages, team/channel listing |
| `proactive_send.py` | `/opt/bridge/data/tools/proactive_send.py` | Send proactive messages via bot server |

## Quick Start Examples

### Read channel messages
```bash
python3 channel_messages.py teams                           # List all teams
python3 channel_messages.py channels "IT Department"        # List channels
python3 channel_messages.py messages "IT Department" General # Read messages
```

### Read chat messages
```bash
python3 chat_messages.py chats "Jane Doe"             # List user's chats
python3 chat_messages.py messages <chat_id>            # Read messages
python3 chat_messages.py search "Jane Doe" "outage"   # Search user's chats
python3 chat_messages.py summary "Jane Doe"            # Chat summary
```

### Proactive messaging (webhook mode)
```bash
python3 proactive_send.py list                              # List known conversations
python3 proactive_send.py send <conv_id> "Server alert: disk 95%"
python3 proactive_send.py broadcast "Maintenance window starting"
```

### Health check
```bash
python3 teams_check.py          # Full check (env + Graph + bot server)
python3 teams_check.py --quick  # Quick check (env + bot server only)
```

### Battery tests
```bash
python3 teams_bridge_tests.py        # All tests
python3 teams_bridge_tests.py graph  # Graph API tests only
python3 teams_bridge_tests.py bot    # Bot server tests only
```

## Common Patterns

### Alert Notification to a Channel
```bash
# Find the conversation ID for a channel where the bot is installed
python3 proactive_send.py list
# Send an alert
python3 proactive_send.py send "19:abc123@thread.tacv2" "ALERT: Server srv-web01 unresponsive"
```

### Compliance Search
```bash
# Search all chats for sensitive content
python3 chat_messages.py search "password" --top 50
# Search a specific team's channels
python3 channel_messages.py search "IT Department" "credentials" --top 20
```

### Bot Status Check
```bash
python3 proactive_send.py status
```

## Bot Behavior

When users message the bot directly in Teams:

| Message | Response |
|---------|----------|
| `hello` / `hi` / `hey` | Greeting identifying the bot as an IT notification bridge |
| `help` | Command list and purpose |
| `status` | Simple operational confirmation |
| _(anything else)_ | Silently logged, no response to user |

The bot's user-facing surface is intentionally minimal -- it is primarily a
notification delivery vehicle controlled by Tendril operators, not an interactive
chatbot.

## Cross-Bridge References

| Operation | Bridge | Why |
|-----------|--------|-----|
| Teams structure (teams, channels, members) | `bridge-microsoft-graph` | Graph REST API `teams_check.py` tool |
| User lookup / group membership | `bridge-microsoft-graph` | Graph REST API `user_lookup.py` tool |
| Email quarantine / message trace | `bridge-microsoft-exchange` | Exchange Online PowerShell |
| DLP, retention, sensitivity labels | `bridge-microsoft-purview` | Security & Compliance PowerShell |

## Design Exception: Inbound Endpoint

This is the only Tendril bridge that requires inbound connectivity. Normal bridges
make only outbound HTTPS calls. The Teams bot requires an inbound webhook for the
Bot Framework to deliver messages. This is addressed by baking `cloudflared` into
the Docker image, creating a secure tunnel without exposing ports.

For operators who cannot use Cloudflare tunnels, **polling mode** provides a
degraded but functional alternative using Graph API reads only.

## Webhook Endpoint Security

In webhook mode the `/api/messages` endpoint is publicly reachable through the
Cloudflare tunnel. Only Microsoft Bot Framework servers ever need to reach it.
Restricting access at the network edge prevents probing and abuse before traffic
touches the container.

The bot server already validates Bot Framework JWT tokens (application-layer
defense), but adding edge-level rules provides defense in depth.

### Option A -- ASN + Path + Header (recommended)

Create two Cloudflare WAF / Firewall rules. No IP list maintenance required.

**Rule 1 -- ALLOW legitimate Bot Framework traffic**

```
Expression (Cloudflare wirefilter):
  (http.host eq "your-bot-hostname.example.com"
   and http.request.method eq "POST"
   and http.request.uri.path eq "/api/messages"
   and any(http.request.headers["authorization"][*] ne "")
   and ip.geoip.asnum eq 8075)

Action: allow
Priority: lower number than the block rule (evaluated first)
```

**Rule 2 -- BLOCK everything else to the bot hostname**

```
Expression:
  (http.host eq "your-bot-hostname.example.com")

Action: block
Priority: higher number than the allow rule
```

Together these ensure:
- Only `POST /api/messages` from Microsoft's network (ASN 8075) with an
  `Authorization` header reaches the container
- All other traffic (wrong method, wrong path, missing auth, non-Microsoft
  origin) is blocked at the Cloudflare edge

ASN 8075 covers Microsoft's entire network, not solely the Bot Service. This is
acceptable because the bot server still validates the Bot Framework JWT -- an
attacker on a different Microsoft service would need a valid token to do anything.

### Option B -- AzureBotService IP List (strictest)

For operators who want IP-level precision, replace the ASN check with a
Cloudflare IP List populated from Microsoft's `AzureBotService` service tag.

1. **Download the current IP ranges** from Microsoft's weekly-updated JSON:
   `https://www.microsoft.com/en-us/download/details.aspx?id=56519`
   Filter for the `AzureBotService` service tag (141+ IPv4 CIDRs, 91+ IPv6).
   A browsable view is at:
   `https://www.azurespeed.com/Information/AzureIpRanges/AzureBotService`

2. **Create a Cloudflare IP List** via API or dashboard:
   ```
   POST /accounts/<account-id>/rules/lists
   { "name": "AzureBotService", "kind": "ip", "description": "Microsoft Bot Framework IPs" }
   ```
   Then bulk-add the CIDRs as list items.

3. **Reference the list** in the ALLOW rule instead of the ASN check:
   ```
   ip.src in $AzureBotService
   ```

4. **Schedule periodic refresh** -- Microsoft publishes updated ranges weekly.
   Automate a script to diff and update the list, or review quarterly at minimum.

### Defense in Depth Summary

| Layer | What | Blocks |
|-------|------|--------|
| **Cloudflare WAF** (edge) | ASN or IP list + path + method + header check | Non-Microsoft traffic, wrong paths, probes |
| **Bot Framework JWT** (application) | `CloudAdapter` validates token signature and claims | Forged or expired tokens |
| **Geo-block** (existing WAF rule) | Block non-US traffic to non-public hostnames | International scanning |

All three layers operate independently. Even if one is bypassed, the others
still protect the endpoint.

## Tenant-Wide Deployment

To deploy the bot silently for all users (pre-approved, no user action required):

1. **Upload to tenant app catalog** -- Use `New-TeamsApp -DistributionMethod organization`
   via MicrosoftTeams PowerShell, or Graph API with `AppCatalog.ReadWrite.All`.

2. **Fix app permission policy** -- The default `PrivateCatalogAppsType` is often
   `AllowedAppList` with an empty list, which **blocks all custom apps**. Change it:
   ```powershell
   Set-CsTeamsAppPermissionPolicy -Identity 'Global' -PrivateCatalogAppsType 'BlockedAppList'
   ```
   This inverts the logic: empty blocked list = all custom apps allowed.

3. **Verify per-app status** -- Even after the policy change, the app may show as
   "Blocked" in Teams Admin Center. Explicitly allow it:
   ```powershell
   Update-M365TeamsApp -Id '<teams-app-catalog-id>' -IsBlocked $false
   ```

4. **Add to global setup policy** -- Pre-install for all users:
   ```powershell
   $app = [Microsoft.Teams.Policy.Administration.Cmdlets.Core.AppPreset]::new()
   $app.Id = '<teams-app-catalog-id>'
   Set-CsTeamsAppSetupPolicy -Identity 'Global' -AppPresetList @{Add=@($app)}
   ```

5. **Install for specific users immediately** -- The global policy takes up to 24
   hours to propagate. For immediate install, use Graph API:
   ```
   POST /users/{user-id}/teamwork/installedApps
   ```
   Requires `TeamsAppInstallation.ReadWriteForUser.All` (application permission).

### Propagation Delays

- **App permission policy changes**: 1-24 hours across Teams services
- **App role assignments** (new Graph API permissions): 15-60 minutes for token refresh
- **Global setup policy**: Up to 24 hours for auto-install on all user clients
- **Per-app unblock** via `Update-M365TeamsApp`: Minutes

### Additional Permissions for Tenant-Wide Install

Beyond the Graph API read permissions, tenant-wide deployment requires:

| Permission | Purpose |
|-----------|---------|
| `AppCatalog.ReadWrite.All` | Upload app to tenant catalog |
| `TeamsAppInstallation.ReadWriteForUser.All` | Install app in user personal scope |
| `TeamsAppInstallation.ReadWriteForTeam.All` | Install app in team scope |

These are added to the same Entra app registration and require admin consent.

## Proactive Messaging Prerequisites

The bot can only proactively message users/channels where it is **installed**. The
Bot Framework `CreateConversation` API returns "Bot is not installed in user's
personal scope" if the app is not present. Ensure either:

- The global setup policy has propagated, OR
- The app is explicitly installed via Graph API for the target user

## File Attachments (Optional)

For sending files via Teams, the recommended approach is a dedicated M365 service
account (e.g., `tendril.bot@yourdomain.com`) with a license that includes OneDrive.
Files are uploaded to the service account's OneDrive, a sharing link is generated,
and the bot sends a file card attachment. This avoids granting broad
`Files.ReadWrite.All` to the bot's app identity.

## API Quirks and Known Issues

- **Chat message reads** in app-only context require user-scoped endpoints
  (`/users/{id}/chats`). The top-level `/chats` endpoint only supports delegated
  access and returns "not supported in application-only context".
- **Proactive messaging** requires the bot to be installed in the target conversation.
  Use Teams admin policies for tenant-wide deployment (see above).
- **Conversation references** are stored in `/opt/bridge/data/conversations.json`.
  If the container is recreated without the `bridge-data` volume, references are lost
  and users must re-interact with the bot to re-establish them.
- **BRIDGE_SEED_VERSION** must be incremented in `.env` when updating bridge code,
  and the container must be recreated via `docker compose up -d` (not just
  `docker restart`) to pick up the new env var and trigger re-seeding.
- **Tendril agent first-start timing** -- On initial deployment, the Tendril agent
  may fail websocket handshake on first boot. A container restart resolves this.
- **Rate limits**: Graph API applies throttling. The client handles pagination but
  does not implement retry-after backoff -- large bulk reads may hit limits.
- **Bot Framework SDK**: Uses `botbuilder-core` / `botbuilder-integration-aiohttp`.
  Microsoft is migrating to the M365 Agents SDK; the bridge should be updated when
  the new SDK reaches GA stability.
- **MicrosoftTeams PowerShell session persistence** -- Each `pwsh -Command` starts
  a new process. Batch all Teams admin operations in a single session to avoid
  repeated device code authentication.
