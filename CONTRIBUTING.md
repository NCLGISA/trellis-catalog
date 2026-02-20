# Contributing to the Trellis Catalog

Thank you for considering a contribution to the first-party Trellis bridge catalog. This document covers the process for proposing new bridges, improving existing ones, and the review criteria applied to all submissions.

## Before You Start

1. **Read the [Bridge Authoring Guide](docs/bridge-authoring-guide.md)** for the full specification of bridge structure, manifest fields, tool architecture, and skill requirements.
2. **Check existing bridges** to see if the platform you're targeting is already covered. If it is, consider contributing tools to the existing bridge rather than creating a new one (see the "one bridge per platform" principle in the authoring guide).
3. **Open an issue first** for new bridges to discuss scope, auth model, and edition considerations before writing code.

## Bridge Directory Structure

Every bridge lives in `bridges/{name}/` and must contain at minimum:

```
bridges/{name}/
  bridge.yaml           # Manifest (required)
  Dockerfile            # Container build instructions
  docker-compose.yml    # Local development compose file
  entrypoint.sh         # Container entrypoint (must be chmod +x)
  requirements.txt      # Python pip dependencies
  tools/
    {name}_client.py    # API client (required)
    {name}_check.py     # Healthcheck script (required)
    {name}_bridge_tests.py  # Integration test battery (required)
  skills/
    {name}-api/
      SKILL.md          # Skill definition with YAML frontmatter (required)
  references/
    README.md           # Reference knowledge directory
```

## Required `bridge.yaml` Fields

Every manifest must include:

- `name` -- lowercase, hyphenated bridge name
- `version` -- CalVer format (YYYY.MM.DD.MICRO)
- `description` -- one-sentence summary of what the bridge integrates with
- `deployment.type` -- `container` or `host`
- `deployment.base` -- base Docker image
- `credentials[]` -- at least one credential with `env_var`, `description`, and `scope`
- `healthcheck.script` -- path to the healthcheck script
- `metadata.author` -- contributor or organization name
- `metadata.category` -- one of: networking, identity, itsm, collaboration, security, cloud
- `metadata.tags` -- comma-separated tags for catalog search

## Sanitization Rules

All bridges in this catalog are designed for cross-organizational use. Submissions must not contain:

- Organization-specific domains, IP addresses, or hostnames
- Account IDs, tenant IDs, or subscription identifiers
- API keys, tokens, or credentials (even expired ones)
- Internal network ranges or VLAN configurations
- Employee names, email addresses, or other PII

Environment variables in `docker-compose.yml` must use `${VARIABLE_NAME}` syntax with placeholder values.

## Pull Request Process

1. **Fork this repository** and create a feature branch
2. **Add or modify your bridge** following the directory structure above
3. **Run `trellis validate`** locally against your bridge to catch structural issues
4. **Submit a PR** with a description of what the bridge does, what auth model it uses, and what platforms/editions it supports
5. **CI validation** runs automatically -- the PR must pass all checks before review

### PR Checklist

- [ ] `bridge.yaml` has all required fields
- [ ] `entrypoint.sh` has execute permissions (`chmod +x`)
- [ ] Core triad present: `{name}_client.py`, `{name}_check.py`, `{name}_bridge_tests.py`
- [ ] SKILL.md has valid YAML frontmatter with description, tags, and author
- [ ] No organization-specific content (domains, IDs, credentials)
- [ ] `requirements.txt` lists all Python dependencies with version pins
- [ ] Bridge builds successfully with `trellis build`
- [ ] Tests pass with valid credentials (describe how to verify in PR description)

## Version Bumping and Releases

Bridge versions use CalVer (`YYYY.MM.DD.MICRO`). When updating an existing bridge:

1. Bump the `version` field in `bridge.yaml`
2. Update the SKILL.md `metadata.version` to match
3. Describe what changed in the PR description

Release tags on this repository trigger multi-arch Docker image builds for all bridges whose versions changed since the previous tag. Only repository maintainers create release tags.

## Code of Conduct

This project follows the same security-first philosophy as the Trellis CLI:

- **No telemetry**: Bridges must not collect, transmit, or expose any telemetry, metrics, or usage signals
- **No phone-home**: Tools must not make calls to external analytics services
- **Read-only by default**: Tools should prefer read-only API operations; destructive operations must be clearly documented and gated behind explicit confirmation

## Questions?

Open an issue or reach out to the maintainers listed in the repository settings.
