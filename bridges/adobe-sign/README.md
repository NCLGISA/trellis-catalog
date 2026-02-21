# Tendril Bridge -- Adobe Sign

## Overview

This bridge connects the Tendril fleet to Adobe Acrobat Sign (formerly EchoSign) via its REST API v6. It runs as a Docker container with a Tendril agent, providing AI-accessible tools for the complete e-signature lifecycle: sending agreements, tracking status, downloading signed documents, extracting document text content (with OCR for scanned pages), managing templates, users, webhooks, and web forms.

## Development Workflow

```
1. Edit bridge.yaml       -- credentials, dependencies, metadata
2. Edit tools/*_client.py -- auth model, base URL, domain methods
3. trellis build adobe-sign     -- generate Dockerfile, docker-compose.yml, etc.
4. trellis validate adobe-sign  -- verify bridge structure
5. Copy .env.example to .env, fill in credentials
6. trellis deploy adobe-sign    -- deploy to Docker
7. Verify: run check, then test battery via Tendril execute
```

## Directory Structure

```
bridge.yaml                       Manifest (single source of truth)
requirements.txt                  Additional pip dependencies
tools/
  adobe_sign_client.py            API client (auth, pagination, rate limiting)
  adobe_sign_check.py             Health check (env + API + permissions)
  adobe_sign_bridge_tests.py      Integration test battery (21 tests, 10 categories)
  adobe_sign_agreements.py        Agreement lifecycle (list, send, download, read, cancel)
  adobe_sign_document_reader.py   Document content extraction (text + OCR + search + compare)
  adobe_sign_templates.py         Library document / template management
  adobe_sign_users.py             User listing, search, group membership
  adobe_sign_webhooks.py          Webhook management (list, create, delete)
  adobe_sign_widgets.py           Web form management (list, agreements, form data)
skills/
  adobe-sign-api/
    SKILL.md                      AI capability discovery and operational knowledge
references/
  README.md                       Guide for adding institutional knowledge docs
```

After `trellis build`, these files are generated (do not edit manually):
```
Dockerfile                        Generated from bridge.yaml
docker-compose.yml                Generated from bridge.yaml
entrypoint.sh                     Generated from bridge.yaml
.env.example                      Generated from bridge.yaml credentials
```

## Credentials

This bridge uses an **Integration Key** (permanent access token) for authentication. Generate one from:

**Adobe Sign > Account > Personal Preferences > Access Tokens > Create Integration Key**

Required scopes:
- `account_read`, `user_read` -- account and user access
- `agreement_read`, `agreement_write`, `agreement_send` -- agreement lifecycle
- `widget_read` -- web form access
- `library_read` -- template access
- `workflow_read` -- workflow access
- `webhook_read`, `webhook_write` -- webhook management

The Integration Key is set via the `ADOBE_SIGN_INTEGRATION_KEY` environment variable.

## Document Content Extraction

The bridge includes a hybrid PDF text extraction pipeline:

- **Born-digital PDFs** (contracts authored in Word, form-filled templates) -- text extracted natively via pdfminer.six
- **Scanned documents** (signed paper copies, vendor quotes) -- pages rendered to images via PyMuPDF, then OCR'd with Tesseract

System dependencies: `tesseract-ocr`, `tesseract-ocr-eng`, `poppler-utils`, `libmagic1`
Python dependencies: `pdfminer.six`, `pymupdf`, `pytesseract`, `Pillow`

Quick usage:
```bash
# Read full text of a signed agreement
python3 /opt/bridge/data/tools/adobe_sign_agreements.py read <agreement_id>

# Analyze page types (born-digital vs scanned)
python3 /opt/bridge/data/tools/adobe_sign_document_reader.py pages <agreement_id>

# Search within agreement text
python3 /opt/bridge/data/tools/adobe_sign_document_reader.py search <agreement_id> "total cost"

# Compare two agreements
python3 /opt/bridge/data/tools/adobe_sign_document_reader.py compare <id1> <id2>
```

## Verification

After deployment, verify via Tendril MCP:

```
list_tendrils(hostname="bridge-adobe-sign")
list_tendril_skills(agent="bridge-adobe-sign")
execute(agent="bridge-adobe-sign", script="python3 /opt/bridge/data/tools/adobe_sign_check.py")
execute(agent="bridge-adobe-sign", script="python3 /opt/bridge/data/tools/adobe_sign_bridge_tests.py")
```

## Quick API Tour

```bash
# List recent agreements
python3 /opt/bridge/data/tools/adobe_sign_agreements.py list

# Download a signed PDF
python3 /opt/bridge/data/tools/adobe_sign_agreements.py download <agreement_id>

# Read the text content of a signed agreement
python3 /opt/bridge/data/tools/adobe_sign_agreements.py read <agreement_id>

# Send an agreement from a template
python3 /opt/bridge/data/tools/adobe_sign_agreements.py send \
  --name "Offer Letter" --signer candidate@example.com --template <template_id>

# Search templates
python3 /opt/bridge/data/tools/adobe_sign_templates.py search "Employee"

# Find a user
python3 /opt/bridge/data/tools/adobe_sign_users.py search "john@example.com"

# List webhooks
python3 /opt/bridge/data/tools/adobe_sign_webhooks.py list

# List web forms
python3 /opt/bridge/data/tools/adobe_sign_widgets.py list
```

## Trellis Catalog

This bridge is built to the trellis spec and can be published to the catalog at `github.com/NCLGISA/trellis-catalog`. Validate before submitting:

```bash
trellis validate adobe-sign
```

The catalog submission includes only: `bridge.yaml`, `tools/`, `skills/`, `references/`, and `README.md`. All other files (Dockerfile, docker-compose.yml, entrypoint.sh, .env.example) are generated by `trellis build` and should not be included in catalog PRs.

Ensure all org-specific content (domains, IPs, keys) is removed before opening a catalog PR.
