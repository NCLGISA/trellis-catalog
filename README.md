# Trellis Catalog -- First-Party Tendril Bridges

Battle-tested bridge definitions for the [Trellis](https://github.com/NCLGISA/trellis) ecosystem. Each bridge is a production-quality integration package containing tools, skills, reference knowledge, and a declarative manifest.

## Bridges

| Bridge | Type | Category | Description |
|--------|------|----------|-------------|
| [adobe-sign](bridges/adobe-sign/) | container | document-management | Adobe Acrobat Sign -- e-signatures, agreements, templates, web forms, audit trails |
| [azure](bridges/azure/) | container | cloud | Azure Resource Manager (Commercial & Government) -- VMs, NSGs, storage, AVD, Arc, Key Vault, Recovery Services, SQL, monitoring, cost data via az CLI and REST API |
| [confluence](bridges/confluence/) | container | collaboration | Confluence Cloud -- full CRUD for pages, CQL search with content retrieval, spaces, blog posts, comments, labels, tasks via REST API v2 (per-operator auth) |
| [cloudflare](bridges/cloudflare/) | container | networking | Cloudflare API -- DNS, WAF, Zero Trust, tunnels |
| [endpoint-central](bridges/endpoint-central/) | container | endpoint-management | ManageEngine Endpoint Central -- patch management, inventory, software deployment, UEM |
| [freshservice](bridges/freshservice/) | container | itsm | Freshservice ITSM -- tickets, CMDB, change management, assets |
| [hycu](bridges/hycu/) | container | backup | HYCU Backup & Recovery -- VM, application, and file share protection, backup jobs, policies, targets, events, restore operations via REST API v1.0 |
| [meraki](bridges/meraki/) | container | networking | Cisco Meraki Dashboard API -- SD-WAN, wireless, switching, VPN, firewall |
| [microsoft-defender](bridges/microsoft-defender/) | container | security | Defender XDR, MDE P2, and Sentinel -- advanced hunting, incident response, vulnerability management, IoC management, SIEM operations |
| [microsoft-exchange](bridges/microsoft-exchange/) | container | identity | Exchange Online PowerShell -- quarantine, message trace, mailbox delegation, shared mailbox conversion, transport rules |
| [microsoft-graph](bridges/microsoft-graph/) | container | identity | Microsoft Graph API -- Entra ID, Exchange, Intune, Teams, LAPS |
| [microsoft-purview](bridges/microsoft-purview/) | container | identity | Security & Compliance PowerShell -- DLP, retention, sensitivity labels, alerts, eDiscovery |
| [microsoft-teams-bot](bridges/microsoft-teams-bot/) | container | collaboration | Teams Bot Framework -- real-time messaging, proactive sends, tenant-wide chat/channel reads via Graph API, Cloudflare tunnel |
| [munis](bridges/munis/) | container | erp | Tyler Munis ERP -- read-only ODBC access to financial, payroll, HR, and procurement data via Reporting Services |
| [navex-policytech](bridges/navex-policytech/) | container | compliance | NAVEX PolicyTech -- search published policy & procedure documents via OpenSearch API (titles & links only; document content requires browser login; Professional plan required; unofficially supported) |
| [nextdns](bridges/nextdns/) | container | networking | NextDNS protective DNS -- profile management, security/privacy settings, analytics, query logs, allowlist/denylist |
| [nutanix-cvm](bridges/nutanix-cvm/) | host | hyperconverged | Nutanix CVM operations -- cluster health, VM management, storage capacity, alerts, hypervisor access via ncli/acli and passwordless SSH |
| [servicedesk-plus](bridges/servicedesk-plus/) | container | itsm | ManageEngine ServiceDesk Plus Cloud -- changes, requests, problems, CMDB, assets |
| [sophos-central](bridges/sophos-central/) | container | security | Sophos Central -- endpoint inventory, alerts, isolation, directory, policies, SIEM events, XDR Data Lake forensics |
| [splunk](bridges/splunk/) | container | siem | Splunk Cloud & Enterprise -- ad-hoc SPL searches, saved searches, fired alerts, index inventory, server health via REST API |
| [ukg-ready](bridges/ukg-ready/) | container | hcm | UKG Ready (Kronos) -- employee directory, time & attendance, compensation, notifications, company configuration via REST API |
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

## CI Validation and Security Scanning

Every pull request and push to `main` that touches `bridges/**` runs an
automated validation pipeline. The workflow is organized into three areas:

### Structure and Manifest Checks

- `bridge.yaml` presence and required fields (`name`, `version`, `description`, `deployment.type`)
- CalVer version format (`YYYY.MM.DD.MICRO`)
- Entrypoint execute permissions (`chmod +x`)
- SKILL.md YAML frontmatter
- Core triad enforcement for container bridges (`{name}_client.py`, `{name}_check.py`, `{name}_bridge_tests.py`)
- Python syntax compilation (`py_compile`) across all bridge scripts

### Security Scanning (Three Tiers)

| Tier | Behavior | What It Catches |
|------|----------|-----------------|
| 1 -- Credentials | **Blocks merge** | AWS access keys, private keys, hardcoded passwords/secrets, connection strings with embedded credentials |
| 2 -- PII | **Advisory warning** | Email addresses, RFC 1918 private IPs, UUIDs, internal hostname patterns (with allowlists for documentation examples) |
| 3 -- Org-specific | **Blocks merge** | Organization-specific domains and infrastructure names (configurable via `.github/sanitization-patterns.txt`) |

The full scanning rules, regexes, allowlists, and safe-pattern guidance
are documented in [docs/SCANNING-RULES.md](docs/SCANNING-RULES.md). The
Trellis CLI references this document to ensure generated bridge code
passes the catalog gate.

### Dependency Scanning

All `bridges/*/requirements.txt` files are scanned with
[pip-audit](https://github.com/pypa/pip-audit) for known vulnerabilities.
This runs as an advisory check (does not block merge). GitHub Actions
dependencies are monitored by Dependabot.

## Security Methodology

The catalog's security posture is defined in
[docs/SECURE-CODE-METHODOLOGY.md](docs/SECURE-CODE-METHODOLOGY.md),
adapted from the
[Trellis CLI Secure Code Methodology](https://github.com/NCLGISA/trellis/blob/main/docs/SECURE-CODE-METHODOLOGY.md)
for a content repository with executable scripts.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose new bridges or improve existing ones, and [docs/bridge-authoring-guide.md](docs/bridge-authoring-guide.md) for the full bridge authoring reference.

## License

Apache-2.0
