---
name: adobe-sign-api
description: >
  Adobe Acrobat Sign e-signature bridge via REST API v6 -- agreements,
  templates, web forms, users, webhooks, workflows, document download,
  document content extraction (text + OCR), audit trails, and form data.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.20"
metadata:
  author: tendril-project
  version: "2026.02.20.2"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - adobe
    - acrobat-sign
    - echosign
    - e-signature
    - agreements
    - documents
    - workflows
    - collaboration
    - ocr
    - pdf
---

# Adobe Sign API Bridge

Full programmatic access to Adobe Acrobat Sign (formerly EchoSign) via the REST API v6. Covers the complete e-signature lifecycle: sending agreements from templates or uploaded files, tracking status, downloading signed documents and audit trails, extracting document text content (with OCR for scanned pages), managing users, configuring webhooks, and browsing web forms.

## Authentication

| Field | Value |
|-------|-------|
| **Auth type** | Integration Key (permanent Bearer token) |
| **API base** | Auto-discovered via `GET /baseUris` |
| **Token lifetime** | Permanent (until revoked) |
| **Env var** | `ADOBE_SIGN_INTEGRATION_KEY` |

The Integration Key is used as a Bearer token on every request. The API base URL is auto-discovered on first call -- the client calls `GET https://api.adobesign.com/api/rest/v6/baseUris` to resolve the correct `apiAccessPoint` for the account's shard.

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `adobe_sign_client.py` | `/opt/bridge/data/tools/` | Core REST API v6 client with Bearer auth, base URI discovery, cursor pagination, rate limiting. All other tools depend on this. |
| `adobe_sign_check.py` | `/opt/bridge/data/tools/` | Health check: validates env vars, base URI discovery, account access, and endpoint coverage |
| `adobe_sign_bridge_tests.py` | `/opt/bridge/data/tools/` | Read-only integration test battery (20+ tests across 10 categories) |
| `adobe_sign_agreements.py` | `/opt/bridge/data/tools/` | Agreement lifecycle: list, inspect, download, read text, audit, send, cancel, remind |
| `adobe_sign_document_reader.py` | `/opt/bridge/data/tools/` | Document content extraction: text (hybrid native + OCR), page analysis, search, compare |
| `adobe_sign_templates.py` | `/opt/bridge/data/tools/` | Library document / template browsing and search |
| `adobe_sign_users.py` | `/opt/bridge/data/tools/` | User listing, detail, search, and group membership |
| `adobe_sign_webhooks.py` | `/opt/bridge/data/tools/` | Webhook management: list, inspect, create, delete |
| `adobe_sign_widgets.py` | `/opt/bridge/data/tools/` | Web form management: list, inspect, agreements, form data |

## Quick Start

```bash
# Verify bridge connectivity
python3 /opt/bridge/data/tools/adobe_sign_check.py

# Test API connection directly
python3 /opt/bridge/data/tools/adobe_sign_client.py test

# List recent agreements
python3 /opt/bridge/data/tools/adobe_sign_agreements.py list

# Read the text content of a signed agreement
python3 /opt/bridge/data/tools/adobe_sign_agreements.py read <agreement_id>

# Run full test battery
python3 /opt/bridge/data/tools/adobe_sign_bridge_tests.py
```

## Tool Reference

### adobe_sign_client.py -- Core API Client

```bash
python3 adobe_sign_client.py test          # Health check / connection test
python3 adobe_sign_client.py agreements    # List recent agreements
python3 adobe_sign_client.py templates     # List library documents
python3 adobe_sign_client.py users         # List users
python3 adobe_sign_client.py widgets       # List web forms
python3 adobe_sign_client.py webhooks      # List webhooks
```

### adobe_sign_agreements.py -- Agreement Lifecycle

```bash
# List and filter
python3 adobe_sign_agreements.py list                              # Recent agreements
python3 adobe_sign_agreements.py list --status SIGNED --limit 20   # Completed agreements
python3 adobe_sign_agreements.py list --status OUT_FOR_SIGNATURE   # Pending signatures

# Inspect
python3 adobe_sign_agreements.py info <agreement_id>               # Full agreement details (JSON)
python3 adobe_sign_agreements.py events <agreement_id>             # Event history / timeline
python3 adobe_sign_agreements.py documents <agreement_id>          # List attached documents
python3 adobe_sign_agreements.py signing-urls <agreement_id>       # Get per-signer signing URLs

# Download
python3 adobe_sign_agreements.py download <agreement_id>           # Download combined signed PDF
python3 adobe_sign_agreements.py download <agreement_id> out.pdf   # Download to specific path
python3 adobe_sign_agreements.py audit <agreement_id>              # Download audit trail PDF
python3 adobe_sign_agreements.py form-data <agreement_id>          # Extract form field data (CSV)

# Read document text (hybrid native text + OCR for scanned pages)
python3 adobe_sign_agreements.py read <agreement_id>               # Full text from all pages
python3 adobe_sign_agreements.py read <agreement_id> --page 2      # Text from specific page

# Send new agreement
python3 adobe_sign_agreements.py send --name "Contract" --signer user@example.com --template <template_id>
python3 adobe_sign_agreements.py send --name "NDA" --signer alice@example.com --signer bob@example.com --file /path/to/doc.pdf
python3 adobe_sign_agreements.py send --name "Offer" --signer hr@example.com --template <id> --message "Please sign by Friday"

# Manage
python3 adobe_sign_agreements.py cancel <agreement_id>             # Cancel an in-progress agreement
python3 adobe_sign_agreements.py remind <agreement_id>             # Send reminder to pending signers
python3 adobe_sign_agreements.py remind <agreement_id> --message "Reminder: please sign today"
```

### adobe_sign_document_reader.py -- Document Content Extraction

```bash
# Extract text from agreement PDF (hybrid: native text + OCR fallback)
python3 adobe_sign_document_reader.py text <agreement_id>

# Extract text from a specific document within the agreement
python3 adobe_sign_document_reader.py text <agreement_id> --document <doc_id>

# Extract text from a single page
python3 adobe_sign_document_reader.py text <agreement_id> --page 3

# Analyze pages: count, per-page classification (born-digital vs scanned)
python3 adobe_sign_document_reader.py pages <agreement_id>

# Search for text within a document
python3 adobe_sign_document_reader.py search <agreement_id> "total cost"

# Compare text content of two agreements (unified diff)
python3 adobe_sign_document_reader.py compare <agreement_id_1> <agreement_id_2>
```

### adobe_sign_templates.py -- Library Documents

```bash
python3 adobe_sign_templates.py list                    # All templates
python3 adobe_sign_templates.py list --limit 10         # First 10 templates
python3 adobe_sign_templates.py info <template_id>      # Template details (JSON)
python3 adobe_sign_templates.py search "Employee"       # Search by name
```

### adobe_sign_users.py -- User Management

```bash
python3 adobe_sign_users.py list                        # All users in the account
python3 adobe_sign_users.py list --limit 10             # First 10 users
python3 adobe_sign_users.py info <user_id>              # User details (JSON)
python3 adobe_sign_users.py search "john@example.com"   # Find by email
python3 adobe_sign_users.py search "John"               # Find by name
python3 adobe_sign_users.py groups <user_id>            # Group membership
```

### adobe_sign_webhooks.py -- Webhook Management

```bash
python3 adobe_sign_webhooks.py list                                              # All webhooks
python3 adobe_sign_webhooks.py info <webhook_id>                                 # Webhook details (JSON)
python3 adobe_sign_webhooks.py create --name "Notify" --url https://example.com/hook  # Create with defaults (AGREEMENT_ALL, ACCOUNT scope)
python3 adobe_sign_webhooks.py create --name "Signed" --url https://example.com/hook --events AGREEMENT_ACTION_COMPLETED --scope GROUP
python3 adobe_sign_webhooks.py delete <webhook_id>                               # Delete a webhook
```

### adobe_sign_widgets.py -- Web Forms

```bash
python3 adobe_sign_widgets.py list                       # All web forms
python3 adobe_sign_widgets.py info <widget_id>           # Web form details (JSON)
python3 adobe_sign_widgets.py agreements <widget_id>     # Agreements generated from this form
python3 adobe_sign_widgets.py form-data <widget_id>      # Form submission data (CSV)
```

### adobe_sign_check.py -- Health Check

```bash
python3 adobe_sign_check.py          # Full 4-step validation
python3 adobe_sign_check.py --quick  # Env vars only (no API calls)
```

### adobe_sign_bridge_tests.py -- Test Battery

```bash
python3 adobe_sign_bridge_tests.py          # Run all tests with text output
python3 adobe_sign_bridge_tests.py --json   # Include JSON report
```

## Document Content Extraction

The bridge includes a hybrid PDF text extraction pipeline that handles both born-digital documents (contracts authored in Word, templates with form fields) and scanned documents (signed paper copies uploaded as images).

### How It Works

1. **Download** -- the agreement PDF is fetched from the Adobe Sign API
2. **Native extraction** -- pdfminer.six extracts text from each page (fast, handles most born-digital PDFs)
3. **OCR fallback** -- pages with fewer than 50 characters of native text are rendered to images via PyMuPDF, then processed with Tesseract OCR
4. **Output** -- combined text with page markers and method annotations (pdfminer vs ocr-tesseract)

### When to Use Each Tool

| Need | Tool |
|------|------|
| Quick read of agreement text | `adobe_sign_agreements.py read <id>` |
| Detailed page-by-page analysis | `adobe_sign_document_reader.py pages <id>` |
| Extract from specific document | `adobe_sign_document_reader.py text <id> --document <doc_id>` |
| Find specific text in agreement | `adobe_sign_document_reader.py search <id> "query"` |
| Compare two agreement versions | `adobe_sign_document_reader.py compare <id1> <id2>` |

### Document Types in Adobe Sign

Most agreements contain multiple PDFs within a single agreement:
- **Memo** -- contract memorandum with budget info and approval routing
- **Contract** -- the legal agreement (usually born-digital, extractable text)
- **Quote** -- vendor quote (may be scanned, may need OCR)
- **Back Page** -- standard county contract terms (born-digital)

Use `adobe_sign_agreements.py documents <id>` to list individual documents, then `adobe_sign_document_reader.py text <id> --document <doc_id>` to extract a specific one.

## API Coverage

### Agreements
- `list_agreements()` -- paginated list of all agreements
- `get_agreement(id)` -- full agreement details
- `get_agreement_members(id)` -- participant info
- `get_agreement_documents(id)` -- list document IDs
- `get_agreement_combined_document(id)` -- download signed PDF (bytes)
- `get_agreement_audit_trail(id)` -- download audit trail PDF (bytes)
- `get_agreement_form_data(id)` -- extract form field values (CSV)
- `get_agreement_signing_urls(id)` -- per-signer signing URLs
- `get_agreement_events(id)` -- event history / timeline
- `get_agreement_reminders(id)` -- list active reminders
- `create_agreement(info)` -- send for signature
- `cancel_agreement(id)` -- cancel in-progress agreement
- `send_agreement_reminder(id, message)` -- nudge pending signers

### Transient Documents
- `upload_transient_document(file_path)` -- upload file for use in agreement (valid ~7 days)

### Library Documents (Templates)
- `list_library_documents()` -- paginated list of all templates
- `get_library_document(id)` -- template details
- `find_template_by_name(query)` -- search by name substring

### Widgets (Web Forms)
- `list_widgets()` -- paginated list of all web forms
- `get_widget(id)` -- web form details
- `get_widget_form_data(id)` -- submission data (CSV)
- `get_widget_agreements(id)` -- agreements generated from this web form

### Users
- `list_users()` -- paginated list of all users
- `get_user(id)` -- user details
- `get_user_groups(id)` -- group membership
- `find_user_by_email(email)` -- search by email

### Webhooks
- `list_webhooks()` -- paginated list of all webhooks
- `get_webhook(id)` -- webhook details
- `create_webhook(name, url, scope, events)` -- register a webhook
- `delete_webhook(id)` -- remove a webhook

### Workflows
- `list_workflows()` -- list configured workflows

## Common Patterns

### Reading Agreement Content
1. List agreements: `python3 adobe_sign_agreements.py list --status SIGNED`
2. Read full text: `python3 adobe_sign_agreements.py read <agreement_id>`
3. Or analyze pages first: `python3 adobe_sign_document_reader.py pages <agreement_id>`
4. Search for specific terms: `python3 adobe_sign_document_reader.py search <agreement_id> "$8,400"`

### Sending an Agreement from a Template
1. Find the template: `python3 adobe_sign_templates.py search "Employee Onboarding"`
2. Copy the template ID from the results
3. Send: `python3 adobe_sign_agreements.py send --name "Onboarding - John Doe" --signer john@example.com --template <template_id>`

### Checking Agreement Status
1. List recent: `python3 adobe_sign_agreements.py list --status OUT_FOR_SIGNATURE`
2. Get details: `python3 adobe_sign_agreements.py info <agreement_id>`
3. View timeline: `python3 adobe_sign_agreements.py events <agreement_id>`

### Downloading Completed Documents
1. Find signed agreements: `python3 adobe_sign_agreements.py list --status SIGNED --limit 10`
2. Download PDF: `python3 adobe_sign_agreements.py download <agreement_id>`
3. Download audit trail: `python3 adobe_sign_agreements.py audit <agreement_id>`
4. Extract form data: `python3 adobe_sign_agreements.py form-data <agreement_id>`

### Comparing Two Agreements
1. Identify both agreement IDs
2. Run diff: `python3 adobe_sign_document_reader.py compare <id1> <id2>`

### Finding a User
1. Search by email: `python3 adobe_sign_users.py search "jsmith@example.com"`
2. Get full details: `python3 adobe_sign_users.py info <user_id>`
3. Check groups: `python3 adobe_sign_users.py groups <user_id>`

### Setting Up a Webhook
1. List existing: `python3 adobe_sign_webhooks.py list`
2. Create: `python3 adobe_sign_webhooks.py create --name "Completion alerts" --url https://hooks.example.com/adobe-sign`
3. Verify: `python3 adobe_sign_webhooks.py list`

### Agreement Status Values
| Status | Meaning |
|--------|---------|
| `DRAFT` | Created but not yet sent |
| `AUTHORING` | Being authored (form fields being placed) |
| `OUT_FOR_SIGNATURE` | Sent, waiting for signatures |
| `OUT_FOR_APPROVAL` | Sent for approval (not signature) |
| `SIGNED` | All parties signed -- completed |
| `APPROVED` | All parties approved |
| `CANCELLED` | Cancelled by sender |
| `EXPIRED` | Passed expiration date |
| `OUT_FOR_ACCEPTANCE` | Sent for acceptance |
| `ARCHIVED` | Moved to archive |

## Rate Limiting

- Adobe Sign enforces per-user rate limits at minute/hour/day intervals
- HTTP 429 responses include `retryAfter` in the JSON body (seconds to wait)
- The client automatically sleeps and retries (max 3 attempts)
- GET endpoints have a Minimum Object Polling Interval (MOPI) -- avoid repeated identical GETs within ~20 seconds

## Pagination

Adobe Sign uses cursor-based pagination:
- Request params: `pageSize` (default 100) and `cursor`
- Response includes `page.nextCursor` when more results exist
- The `get_all()` helper iterates automatically until all pages are fetched
- Maximum effective page size varies by endpoint (usually 100)

## API Quirks and Known Issues

1. **Base URI varies by shard.** Always discover via `GET /baseUris` -- hardcoding `api.na2.adobesign.com` only works for NA2 accounts.
2. **Transient documents expire.** Uploaded files are only valid for ~7 days. Upload immediately before creating the agreement.
3. **Form data is CSV.** The `/formData` endpoint returns CSV text, not JSON. Parse accordingly.
4. **Form data may be 403.** Some agreement types (particularly those not created by the Integration Key owner) return HTTP 403 on the `/formData` endpoint. Use the document reader text extraction as a fallback.
5. **Audit trail is a PDF.** The `/auditTrail` endpoint returns binary PDF, not JSON.
6. **Combined document is a PDF.** The `/combinedDocument` endpoint returns the merged, signed PDF as binary.
7. **Agreement status is immutable once signed.** You cannot cancel or modify a `SIGNED` agreement.
8. **Multiple signers use `order` field.** Sequential signing is controlled by the `order` property in `participantSetsInfo`. Parallel signing uses the same order value.
9. **Webhook events require HTTPS callback.** The webhook URL must be publicly accessible and use HTTPS.
10. **User search is client-side.** The v6 API does not provide a server-side user search -- the client fetches all users and filters locally.
11. **Library document sharing modes.** Templates can be `USER`, `GROUP`, or `ACCOUNT` scoped. Only templates matching the Integration Key's access level are visible.
12. **OCR quality depends on scan quality.** Scanned documents with poor resolution, skewed pages, or handwritten text may produce lower-quality OCR results. The page analysis command (`pages`) shows which extraction method was used per page.
