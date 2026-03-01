# Catalog Scanning Rules

This document defines the scanning rules enforced by the trellis-catalog
CI gate. It serves as the **contract between the catalog and the Trellis
CLI** -- Trellis should ensure that generated bridge code never triggers
these rules.

Last updated: 2026-02-28

---

## How the Gate Works

The catalog CI workflow (`validate.yml`) scans all files under `bridges/`
on every pull request and push to main. Scans are organized into three
tiers:

| Tier | Behavior | Purpose |
|------|----------|---------|
| 1 -- Credentials | **Blocks merge** | Hardcoded secrets, keys, and passwords |
| 2 -- PII / Internal refs | **Advisory warning** | Email addresses, internal IPs, UUIDs, hostnames |
| 3 -- Org-specific | **Blocks merge** | Organization-specific domains and infrastructure names |

### File Types Scanned

All scanning tiers inspect these extensions:

- `.py` -- Python scripts
- `.yaml`, `.yml` -- Manifests, compose files, configs
- `.md` -- Documentation and skills
- `.sh` -- Shell scripts and entrypoints
- `.ps1` -- PowerShell scripts
- `.env.example` -- Credential templates (Tier 1 only)

---

## Tier 1: Credential Detection (Blocking)

These patterns cause an immediate **hard failure**. No PR will merge if
any of these are detected.

### AWS Access Keys

```
AKIA[0-9A-Z]{16}
```

Matches AWS IAM access key IDs. There is no allowlist for this pattern.

### Private Keys

```
-----BEGIN [A-Z ]*PRIVATE KEY-----
```

Matches RSA, EC, DSA, OPENSSH, and generic private key headers.

### Hardcoded Credential Assignments

```
(password|passwd|api_key|apikey|secret_key|access_key|auth_token|client_secret|private_key)\s*=\s*["'][^"']{8,}["']
```

Matches variable assignments where a credential-named variable is set
to a string literal of 8 or more characters. The following are
automatically excluded:

- Lines using `os.environ`, `os.getenv`, `.get(`, `environ[`
- Lines containing placeholder words: `your-`, `example`, `placeholder`,
  `changeme`, `CHANGE_ME`, `replace_with`, `INSERT`, `TODO`, `FIXME`, `xxx`
- Lines using template syntax: `${...}`, `<VARIABLE_NAME>`

### Connection Strings with Embedded Passwords

```
(mongodb|postgres|postgresql|mysql|redis|amqp|mssql)://[^:]+:[^@{$]+@
```

Matches database and message broker URIs with inline `user:password@host`
credentials. Excluded: `username:password`, `user:pass`, placeholder
patterns, and template variables.

---

## Tier 2: PII and Internal References (Advisory)

These patterns generate **warnings** in the CI log but do not block
the merge. Reviewers should verify that flagged items are documentation
examples, not real data.

### Email Addresses

```
[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}
```

**Allowlisted domains** (not flagged):

| Domain | Reason |
|--------|--------|
| `@example.com` | RFC 2606 reserved |
| `@example.org` | RFC 2606 reserved |
| `@example.net` | RFC 2606 reserved |
| `@yourdomain.com` | Common placeholder |
| `@contoso.com` | Microsoft documentation domain |
| `@contoso.onmicrosoft.com` | Microsoft documentation tenant |

### RFC 1918 Private IP Addresses

```
\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b
```

**Allowlisted addresses** (not flagged):

| Address | Reason |
|---------|--------|
| `10.0.0.0`, `10.0.0.1` | Common documentation defaults |
| `192.168.0.0`, `192.168.0.1` | Common documentation defaults |
| `192.168.1.1` | Common router address in examples |
| `172.16.0.0`, `172.16.0.1` | Common documentation defaults |
| `192.0.2.*` | RFC 5737 TEST-NET-1 (documentation) |
| `198.51.100.*` | RFC 5737 TEST-NET-2 (documentation) |
| `203.0.113.*` | RFC 5737 TEST-NET-3 (documentation) |

### UUIDs

```
[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}
```

**Allowlisted:** The zero UUID (`00000000-0000-0000-0000-000000000000`)
is not flagged.

### Internal Hostname Patterns

```
\b(az[0-9]+s[0-9]+|srv-[a-zA-Z0-9-]+|dc-[a-zA-Z0-9-]+)\b
```

Matches common infrastructure naming conventions (Azure VMs, server
names, domain controllers). Organizations may extend this pattern.

---

## Tier 3: Organization-Specific Patterns (Blocking)

Patterns are loaded from `.github/sanitization-patterns.txt` at
runtime. Each line is a grep-E extended regex. Comments (`#`) and
blank lines are ignored.

Current default patterns:

```
rowancountync\.gov
\.internal\.
```

Organizations forking this catalog should replace these with their
own domain and infrastructure patterns.

---

## Safe Patterns Guide

This section documents what Trellis-generated code **should** do to
pass the catalog gate. These patterns are safe by construction.

### Credentials: Use Environment Variables

```python
# SAFE -- reads from environment at runtime
api_key = os.environ["MERAKI_API_KEY"]
password = os.getenv("SERVICE_PASSWORD", "")
token = os.environ.get("AUTH_TOKEN")
```

```python
# BLOCKED -- hardcoded credential value
api_key = "k8s9d7f6g5h4j3k2l1"
password = "SuperSecret123!"
```

### Compose Files: Use Variable Substitution

```yaml
# SAFE -- resolved from .env at deploy time
environment:
  - API_KEY=${MERAKI_API_KEY}
  - PASSWORD=${SERVICE_PASSWORD}
```

```yaml
# BLOCKED -- hardcoded value
environment:
  - API_KEY=k8s9d7f6g5h4j3k2l1
```

### .env.example: Use Placeholders Only

```bash
# SAFE -- descriptive placeholder
MERAKI_API_KEY=your-meraki-api-key-here
TENANT_ID=your-azure-tenant-id

# BLOCKED -- looks like a real key
MERAKI_API_KEY=a1b2c3d4e5f6g7h8i9j0
```

### Documentation: Use Reserved Domains and IPs

```markdown
# SAFE -- RFC 2606 reserved domain
Configure the webhook URL: https://webhook.example.com/callback

# SAFE -- RFC 5737 documentation IP
Set the gateway address to 192.0.2.1

# SAFE -- allowlisted example IP
Default gateway: 10.0.0.1
```

```markdown
# FLAGGED (advisory) -- real-looking internal IP
Set the server address to 10.47.12.5

# BLOCKED (org-specific) -- real organization domain
Contact admin@rowancountync.gov for access
```

### Documentation: Use Placeholder Identifiers

```markdown
# SAFE -- obviously fake
Tenant ID: your-azure-tenant-id
Subscription: 00000000-0000-0000-0000-000000000000

# FLAGGED (advisory) -- looks like a real UUID
Tenant ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### Database Connections: Use Variable References

```python
# SAFE -- credentials injected from environment
conn_string = f"postgresql://{os.environ['DB_USER']}:{os.environ['DB_PASS']}@{os.environ['DB_HOST']}/mydb"
```

```python
# BLOCKED -- credentials embedded in URI
conn_string = "postgresql://admin:realpassword@db.internal:5432/mydb"
```

---

## Adding New Rules

When adding patterns to the catalog gate:

1. Add the regex to the appropriate tier in `validate.yml`
2. Update this document with the pattern, explanation, and any allowlist entries
3. If adding an allowlist entry, verify it won't mask real leakage
4. Test the pattern against existing bridges before merging:
   ```bash
   grep -rEn 'YOUR_PATTERN' bridges/ --include='*.py' --include='*.yaml' --include='*.yml' --include='*.md' --include='*.sh' --include='*.ps1'
   ```

---

## Revision History

| Date | Change |
|------|--------|
| 2026-02-28 | Initial scanning rules document |
