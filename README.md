# Trellis Catalog -- First-Party Tendril Bridges

Battle-tested bridge definitions for the [Trellis](https://github.com/NCLGISA/trellis) ecosystem. Each bridge is a production-quality integration package containing tools, skills, reference knowledge, and a declarative manifest.

## Bridges

| Bridge | Category | Description |
|--------|----------|-------------|
| [meraki](bridges/meraki/) | networking | Cisco Meraki Dashboard API -- SD-WAN, wireless, switching, VPN, firewall |
| [azure](bridges/azure/) | cloud | Azure Resource Manager -- subscriptions, resource groups, VMs, NSGs |
| [cloudflare](bridges/cloudflare/) | networking | Cloudflare API -- DNS, WAF, Zero Trust, tunnels |
| [freshservice](bridges/freshservice/) | itsm | Freshservice ITSM -- tickets, CMDB, change management, assets |
| [microsoft-graph](bridges/microsoft-graph/) | identity | Microsoft Graph API -- Entra ID, Exchange, Intune, Teams, LAPS |
| [zoom](bridges/zoom/) | collaboration | Zoom Server-to-Server OAuth -- meetings, users, phone admin |

## Using These Bridges

### With Trellis CLI

The Trellis CLI knows about this repository as its built-in first-party origin. Fetch the catalog and browse:

```bash
trellis graft update
trellis catalog list
trellis catalog info meraki
trellis catalog init meraki
```

### As a Graft Source

If the catalog hasn't been fetched yet, or you want to be explicit:

```bash
trellis graft add NCLGISA/trellis-catalog
```

### Pre-Built Docker Images

Multi-arch Docker images (`linux/amd64`, `linux/arm64`) are published to GHCR on each release:

```bash
docker pull ghcr.io/nclgisa/bridge-meraki:latest
docker pull ghcr.io/nclgisa/bridge-meraki:2026.02.20.3
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose new bridges or improve existing ones, and [docs/bridge-authoring-guide.md](docs/bridge-authoring-guide.md) for the full bridge authoring reference.

## License

Apache-2.0
