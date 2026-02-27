# NAVEX PolicyTech Bridge -- Setup Guide

## Prerequisites

Before deploying this bridge, you must enable the API Keys add-on and create an API key in your NAVEX PolicyTech instance.

> **Plan requirement:** The API Keys add-on is only available on the PolicyTech **Professional** plan. If you are on a lower-tier plan, the option will not appear in IT Settings even after contacting NAVEX Support.

> **Unofficial use:** NAVEX officially supports the OpenSearch API only for SharePoint integration scenarios. Using it for other purposes (such as this bridge) is technically functional but not officially supported by NAVEX -- your mileage may vary.

> **Search-only:** This bridge can find documents by keyword and return their titles and links, but it **cannot retrieve document content**. Document links require SSO/browser authentication to view. The API key authorizes search requests only. Think of it as a policy directory, not a policy reader.

## Step 1: Determine Your Base URL

Your NAVEX One base URL follows the pattern:

```
https://yourorg.navexone.com
```

You can find this from your PolicyTech login URL. For example, if you log in at `https://yourorg.navexone.com/content/dotNet/noAuth/login.aspx`, then your base URL is `https://yourorg.navexone.com`.

Set this as `POLICYTECH_BASE_URL` in your `.env` file (no trailing slash).

## Step 2: Enable the API Keys Add-on

The OpenSearch API requires the "API Keys" add-on to be activated. This is available on the **Professional** plan and must be turned on by NAVEX Support.

1. Contact NAVEX Support:
   - **Phone:** 888-359-8123
   - **Portal:** https://support.navex.com/s/contactsupport
2. Request: "Please enable the API Keys add-on for our PolicyTech instance"
3. They will provide a **registration code**

If the API Keys option does not appear after enablement, confirm that your PolicyTech license is on the Professional plan.

## Step 3: Enter the Registration Code

1. Log into NAVEX One as an administrator
2. Navigate to **Settings & Tools** > **IT Settings** > **Registration Info**
3. Enter the registration code provided by NAVEX Support
4. Click **Save**

## Step 4: Create an API Key

1. Navigate to **Settings & Tools** > **IT Settings** > **API Keys**
2. Click **New**
3. Set a **Display Name** (e.g., "Tendril Bridge")
4. Optionally restrict the key to specific IP addresses for security
5. Select which **sites** the key should have access to (select all unless you have specific restrictions)
6. Click **Save**
7. Copy the generated API key

Set this as `POLICYTECH_API_KEY` in your `.env` file.

## Step 5: Configure and Deploy

1. Copy `.env.example` to `.env`
2. Fill in all required values:
   ```
   POLICYTECH_BASE_URL=https://yourorg.navexone.com
   POLICYTECH_API_KEY=<your-api-key>
   ```
3. Build and start the container:
   ```bash
   docker compose build
   docker compose up -d
   ```

## Step 6: Verify

Run the health check to confirm connectivity:

```bash
docker exec bridge-navex-policytech python3 /opt/bridge/data/tools/policytech_check.py
```

Expected output:
```json
{
  "bridge": "navex-policytech",
  "checks": [
    {"name": "connect", "status": "pass", ...},
    {"name": "search", "status": "pass", "total_results": ..., "sample_count": ...}
  ],
  "summary": "2/2 checks passed",
  "healthy": true
}
```

## Troubleshooting

### "Policy Manager Error" (HTTP 500)

The API key is invalid, expired, or the API Keys add-on is not enabled. Verify the key in Settings & Tools > IT Settings > API Keys. If the API Keys menu item doesn't exist, contact NAVEX Support to enable the add-on (Step 2).

### "API Keys" menu not visible

Either the add-on hasn't been enabled by NAVEX Support (Step 2), or your PolicyTech license is not on the Professional plan. Contact NAVEX Support to confirm your plan level and request enablement.

### Document links prompt for login

This is expected. The API key authorizes search requests only -- it does not grant access to view document content. Document links redirect to SSO login. Users must authenticate in their browser to read the full document.

### Empty search results

- The API only returns documents with **"All Users"** or **"Public"** security level in **Published** status
- Documents with restricted security levels (specific groups/roles) are not returned
- Try a broader search term

### Connection timeout

Ensure the Docker host can reach `*.navexone.com` on TCP port 443. Check firewall rules and DNS resolution.

### SSL certificate error

If a proxy or inspection device intercepts TLS connections, set `POLICYTECH_VERIFY_TLS=false` in your `.env` file.

## API Reference

The bridge uses the PolicyTech OpenSearch 1.0/1.1 API:

```
GET {base_url}/content/api/opensearch/2014/06/?MethodName=GetDocuments
    &APIKey={api_key}
    &SearchField={ALL|TITLE}
    &itemsPerPage={count}
    &startIndex={offset}
    &SearchTerms={query}
```

**Working search fields:**

| SearchField | Behavior |
|-------------|----------|
| `ALL` | Searches across title and body content |
| `TITLE` | Searches document titles only |

The `BODY` and `NUMBER` fields are documented by NAVEX but return HTTP 500 errors in practice. The CLI restricts choices to `ALL` and `TITLE`.

The response is RSS 2.0 XML with OpenSearch 1.1 extensions containing matching published documents. Each item includes a title and a link to view the document (SSO login required). Description fields are typically empty.

> **Note:** NAVEX officially documents this API for SharePoint integration only. The endpoint behavior, response format, and availability may change without notice in future PolicyTech releases.

For full API documentation, see the PolicyTech help files:
https://helpfiles.policytech.com/en/18-5-0-0/HelpCenter/Content/IT_Stgs/API_Keys.htm
