# NAVEX PolicyTech Bridge -- Setup Guide

## Prerequisites

Before deploying this bridge, you must enable the API Keys add-on and create an API key in your NAVEX PolicyTech instance.

## Step 1: Determine Your Base URL

Your NAVEX One base URL follows the pattern:

```
https://yourorg.navexone.com
```

You can find this from your PolicyTech login URL. For example, if you log in at `https://yourorg.navexone.com/content/dotNet/noAuth/login.aspx`, then your base URL is `https://yourorg.navexone.com`.

Set this as `POLICYTECH_BASE_URL` in your `.env` file (no trailing slash).

## Step 2: Enable the API Keys Add-on

The OpenSearch API requires the "API Keys" add-on to be activated. This is included with your PolicyTech license but must be turned on by NAVEX Support.

1. Contact NAVEX Support:
   - **Phone:** 888-359-8123
   - **Portal:** https://support.navex.com/s/contactsupport
2. Request: "Please enable the API Keys add-on for our PolicyTech instance"
3. They will provide a **registration code**

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

The add-on hasn't been enabled yet. Contact NAVEX Support (Step 2).

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
    &SearchField={ALL|TITLE|BODY|NUMBER}
    &itemsPerPage={count}
    &startIndex={offset}
    &SearchTerms={query}
```

The response is RSS or Atom XML containing matching published documents with title, description, link, publication date, and optionally a download URL for attached files.

For full API documentation, see the PolicyTech help files:
https://helpfiles.policytech.com/en/18-5-0-0/HelpCenter/Content/IT_Stgs/API_Keys.htm
