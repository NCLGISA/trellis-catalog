# Microsoft Teams Bot Bridge -- Setup Reference

## Automated Setup

```bash
./setup_teams_bot.sh contoso.onmicrosoft.com "Tendril Bot"
```

The script handles steps 1-6 automatically. Steps 7-8 (Azure Bot Service and
Teams channel) require a resource group -- set `TEAMS_BOT_RESOURCE_GROUP` env
var or follow the manual commands printed by the script.

## Prerequisites

- Azure CLI (`az`) installed and logged in (`az login`)
- Global Administrator or: Application Administrator + Teams Administrator
- Active Azure subscription (for Azure Bot Service resource)
- Cloudflare account with Zero Trust access (for tunnel)

## What the Script Creates

| Resource | Purpose |
|----------|---------|
| Entra App Registration | Single-tenant app for bot authentication |
| Client Secret | Bot Framework authentication credential |
| Service Principal | Identity for Graph API permissions |
| Graph API Permissions | ChatMessage.Read.All, ChannelMessage.Read.All, Team.ReadBasic.All, Channel.ReadBasic.All |
| Azure Bot Service | Bot Framework registration (if resource group provided) |
| Teams Channel | Enables Teams as a bot channel (if resource group provided) |

## Post-Setup: Cloudflare Tunnel

1. Go to [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) > Networks > Tunnels
2. Create a new tunnel (or use an existing one)
3. Add a public hostname routing to `http://localhost:3978`
4. Copy the tunnel token
5. Update the Azure Bot messaging endpoint: `https://<tunnel-hostname>/api/messages`

## Post-Setup: Teams App Distribution

### Per-team install
Users can search for and install the bot from the Teams app store.

### Tenant-wide deployment
1. Go to Teams Admin Center > Teams apps > Setup policies
2. Add the bot to the default or a custom policy
3. The bot will be automatically installed for all users in scope

## Polling Mode (No Tunnel)

If Cloudflare tunnels are not available, set `TEAMS_BOT_MODE=polling` in `.env`.
This disables the bot server and cloudflared, providing only Graph API read
access to tenant messages. Proactive messaging is not available in polling mode.
