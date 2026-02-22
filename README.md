# Trellis Catalog -- First-Party Tendril Bridges

Battle-tested bridge definitions for the [Trellis](https://github.com/NCLGISA/trellis) ecosystem. Each bridge is a production-quality integration package containing tools, skills, reference knowledge, and a declarative manifest.

## Bridges

| Bridge | Type | Category | Description |
|--------|------|----------|-------------|
| [adobe-sign](bridges/adobe-sign/) | container | document-management | Adobe Acrobat Sign -- e-signatures, agreements, templates, web forms, audit trails |
| [azure](bridges/azure/) | container | cloud | Azure Resource Manager -- subscriptions, resource groups, VMs, NSGs |
| [cloudflare](bridges/cloudflare/) | container | networking | Cloudflare API -- DNS, WAF, Zero Trust, tunnels |
| [endpoint-central](bridges/endpoint-central/) | container | endpoint-management | ManageEngine Endpoint Central -- patch management, inventory, software deployment, UEM |
| [freshservice](bridges/freshservice/) | container | itsm | Freshservice ITSM -- tickets, CMDB, change management, assets |
| [meraki](bridges/meraki/) | container | networking | Cisco Meraki Dashboard API -- SD-WAN, wireless, switching, VPN, firewall |
| [microsoft-graph](bridges/microsoft-graph/) | container | identity | Microsoft Graph API -- Entra ID, Exchange, Intune, Teams, LAPS |
| [servicedesk-plus](bridges/servicedesk-plus/) | container | itsm | ManageEngine ServiceDesk Plus Cloud -- changes, requests, problems, CMDB, assets |
| [veeam-m365](bridges/veeam-m365/) | host | backup | Veeam Backup for Microsoft 365 -- backup jobs, granular restore, organization inventory |
| [zoom](bridges/zoom/) | container | collaboration | Zoom Server-to-Server OAuth -- meetings, users, phone admin |

## Using These Bridges

### With Trellis CLI

The Trellis CLI auto-fetches this catalog on first use -- no manual setup required. Browse and initialize:

```bash
trellis catalog list
trellis catalog info meraki
trellis info meraki              # AI-synthesized setup guide from manifest + SKILL.md
trellis catalog init meraki      # copy to local workspace
```

### Third-Party Catalogs

The `graft` command is for adding catalogs from other organizations or Git-compatible platforms:

```bash
trellis graft add some-org/their-catalog
trellis graft list
```

This first-party catalog is always available automatically.

### Pre-Built Docker Images

Multi-arch Docker images (`linux/amd64`, `linux/arm64`) are published to GHCR on each release for container bridges:

```bash
docker pull ghcr.io/nclgisa/bridge-meraki:latest
docker pull ghcr.io/nclgisa/bridge-meraki:2026.02.20.3
```

Host bridges (e.g., `veeam-m365`) are deployed via `trellis package` and `trellis deploy --target <agent>` -- no Docker image required.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose new bridges or improve existing ones, and [docs/bridge-authoring-guide.md](docs/bridge-authoring-guide.md) for the full bridge authoring reference.

## License

Apache-2.0
