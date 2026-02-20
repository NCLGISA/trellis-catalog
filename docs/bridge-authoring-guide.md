# Bridge Authoring Guide

This guide covers everything you need to know to build a Trellis bridge. It extracts the key architectural patterns from the [Trellis Design Document](https://github.com/NCLGISA/trellis/blob/main/docs/design/tendril-trellis-design.md) into a practical reference.

## What Is a Bridge?

A Tendril bridge is an integration package that connects an AI-powered operations platform (Tendril) to an external system. A bridge is not just an API wrapper -- it is a **portable operations team** containing:

- **Tools** -- Python scripts the AI can execute to interact with the target platform
- **Skills** -- SKILL.md files that tell the AI what operations are available and how to use them
- **References** -- Institutional knowledge documents that give the AI context about organizational standards and configurations
- **Manifest** -- A `bridge.yaml` that declares the bridge's configuration, dependencies, and deployment requirements

## The Bridge Manifest (`bridge.yaml`)

The manifest is the single source of truth for a bridge definition. The Trellis CLI reads it to build, validate, and deploy the bridge.

### Required Fields

```yaml
name: meraki                              # lowercase, hyphenated
version: "2026.02.20.3"                   # CalVer: YYYY.MM.DD.MICRO
description: "Cisco Meraki Dashboard API bridge for SD-WAN, wireless, switching, VPN, and firewall management"

deployment:
  type: container                         # "container" or "host"
  base: "tendril-bridge-base:latest"      # base Docker image
  hostname: "bridge-meraki"               # container hostname
  timezone: "UTC"                         # TZ env var

credentials:
  - name: "Meraki API Key"
    env_var: MERAKI_API_KEY
    description: >
      Meraki Dashboard API key. Generate from Dashboard > Organization >
      Settings > Dashboard API access. Should belong to a service account
      with full org read access.
    scope: "shared"                       # "shared" or "per-operator"
    required: true

dependencies:
  pip:
    - "requests>=2.31.0"
    - "python-dotenv>=1.0.0"
  system: []                              # additional apt packages

healthcheck:
  script: "python3 /opt/bridge/data/tools/meraki_check.py"
  interval: "60s"
  timeout: "10s"

metadata:
  author: "tendril-project"
  category: "networking"                  # networking, identity, itsm, collaboration, security, cloud
  tags: "cisco, meraki, sdwan, wireless"
  platform_url: "https://api.meraki.com/api/v1"
```

### Credential Scopes

- **`shared`** -- baked into the container environment at deploy time. One key serves all operators (e.g., a Meraki org-level API key).
- **`per-operator`** -- injected at runtime from Tendril Root's credential vault. Each operator authenticates with their own key (e.g., a Freshservice API key tied to an individual).

### Editions (Optional)

For platforms with multiple product tiers (Standard/Professional/Enterprise), declare editions in metadata:

```yaml
metadata:
  editions:
    - name: Standard
      features: [incidents, requests]
    - name: Professional
      features: [incidents, requests, cmdb, projects]
    - name: Enterprise
      features: [incidents, requests, cmdb, projects, changes, releases]
```

Tools document which features they require, and the SKILL.md maps tool availability to editions.

## Tool Architecture

### Core Triad (Required)

Every bridge must include three foundational tools:

**`{name}_client.py`** -- The API client class. Handles:
- Authentication (bearer token, basic auth, OAuth, etc.)
- Rate limiting with exponential backoff
- Pagination (Link headers, cursor-based, offset-based)
- A `test_connection()` method for healthcheck use
- Structured error responses

**`{name}_check.py`** -- The healthcheck script. Verifies:
- Required environment variables are set
- API connectivity works
- Permissions are sufficient
- Supports a `--quick` flag for fast checks
- Outputs JSON for Docker healthcheck integration

**`{name}_bridge_tests.py`** -- The integration test battery:
- Read-only tests organized by category (Health, Connectivity, Permissions)
- `run_test()` harness with pass/fail/skip reporting
- Summary report with exit code
- Never makes destructive API calls

### Domain Tools

Beyond the core triad, add domain-specific tools as needed:

| Pattern | File Convention | Purpose |
|---------|----------------|---------|
| Domain operations | `{name}_{domain}.py` | Admin, query, or management with argparse subcommands |
| Audit | `{name}_audit.py` | Compliance checking against a defined standard |
| Sync | `{name}_sync.py` | Data synchronization with dry-run mode |
| Reference-as-code | `{name}_reference.py` | Institutional knowledge as Python data structures |

Each tool is a standalone script invoked via `execute()`. Use `argparse` for subcommands and produce structured JSON output.

### Naming Convention

All tool filenames use `snake_case` with the bridge name prefix: `meraki_client.py`, not `client.py`. This ensures tools are self-identifying when listed on the filesystem.

## Auth Model Patterns

The six production bridges demonstrate five authentication patterns:

| Auth Model | Implementation |
|-----------|----------------|
| Static Bearer token | `Authorization: Bearer {key}` header from env var |
| Basic auth | `requests.auth.HTTPBasicAuth(api_key, "X")` |
| OAuth client_credentials (MSAL) | `msal.ConfidentialClientApplication` with tenant/client/secret |
| Server-to-Server OAuth | `POST /oauth/token` with `account_credentials` grant |
| Per-operator vault injection | Credential injected at runtime; `scope: "per-operator"` in manifest |

The `{name}_client.py` scaffold template includes commented examples for each model.

## SKILL.md Requirements

Every bridge skill must have a SKILL.md with YAML frontmatter:

```yaml
---
name: meraki-api
description: >
  Cisco Meraki Dashboard API integration for network management.
compatibility:
  - platform: linux
metadata:
  author: "tendril-project"
  version: "2026.02.20.3"
  tags:
    - meraki
    - cisco
    - networking
---

# Meraki API Skill

## Available Tools
...
```

The markdown body should document:
- Available tools with a table mapping names to capabilities
- Required credentials and how to obtain them
- Usage examples with specific `python3 /opt/bridge/data/tools/...` invocations
- Test battery description and how to run it
- Known limitations and platform edition requirements

## References Directory

The `references/` directory holds institutional knowledge documents:

- VLAN standards, IP addressing schemes
- CMDB schemas and relationship models
- Change management workflows
- Security baselines and compliance frameworks
- Vendor-specific configuration guides

These documents give the AI context that no API documentation provides. They transform a bridge from an API connector into an integration that understands your organization.

Include at minimum a `references/README.md` describing what reference materials are available and how to contribute them.

## Testing Locally

```bash
# Validate the bridge manifest
trellis validate meraki

# Build the Docker image
trellis build meraki

# Run the test battery (requires valid credentials in .env)
docker exec -it bridge-meraki python3 /opt/bridge/data/tools/meraki_bridge_tests.py
```

## One Bridge Per Platform

The default is **one bridge per platform** with tier-aware tools. Split into separate bridges only when:

- The platform has entirely separate API endpoints with different auth mechanisms
- The SKILL.md exceeds ~2000 lines and cannot be reasonably organized
- Two instances serve completely different organizational functions requiring separate credentials

For edition-aware development, multiple contributors can work on different feature subsets of the same bridge. Tools are standalone scripts that import the shared client, so they compose without conflict.
