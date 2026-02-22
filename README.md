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
| [munis](bridges/munis/) | container | erp | Tyler Munis ERP -- read-only ODBC access to financial, payroll, HR, and procurement data via Reporting Services |
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

### Building Bridges

Container bridges are built locally by the operator using `trellis build` (or `trellis build --standalone` for environments without a pre-built base image). Host bridges are packaged via `trellis package` and deployed via `trellis deploy --target <agent>`. No pre-built images are distributed -- the catalog provides source definitions only.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose new bridges or improve existing ones, and [docs/bridge-authoring-guide.md](docs/bridge-authoring-guide.md) for the full bridge authoring reference.

## License

Apache-2.0
