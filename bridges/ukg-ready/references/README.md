# UKG Ready Bridge -- Setup Guide

## Prerequisites

Before deploying the bridge, you need three things from your UKG Ready instance:

1. A **Service Account** (username + password)
2. A **REST API Key**
3. Your **Company Short Name** (7-digit identifier)

---

## Step 1: Add the Service Accounts and API Keys Widgets

If the **Service Accounts** or **API Keys** widgets are not visible on your Login Config tab:

1. Log into UKG Ready as a Company Administrator
2. Navigate to **Global Setup > Company Setup**
3. Open the **Login Config** tab
4. Click **Edit Tabs** (pencil icon)
5. In the **Tabs Configuration** screen, scroll down in **Available Windows** on the right side until you see **Service Accounts**
6. Click and drag **Service Accounts** into an empty column (Column #2 or #3)
7. Also drag **API Keys** into the same column for convenience
8. Click **SAVE**, then click **BACK** to return to Company Setup

> **Tip:** The Tabs Configuration layout shows Service Accounts and API Keys being added to the Login Config tab columns.

---

## Step 2: Create a Service Account

1. Return to the **Login Config** tab
2. In the **Service Accounts** widget, click **Add Service Account**
3. Fill in the fields:
   - **Username:** `Tendril` (or your preferred name)
   - **Password:** Use a strong passphrase
4. **Security Profile:** Select **Company Administrator** for full API scope access
5. **Account Access > Account Groups:** Select **All Company Employees**
6. Click **Save**

> **Important:** The service account's Security Profile determines which API endpoints are accessible. Company Administrator grants full access to all modules.

---

## Step 3: Generate the REST API Key

1. In the **Login Config** tab, locate the **API Keys** widget
2. Click **GENERATE**
3. Click the **eye icon** to reveal the masked API key
4. Copy the key and store it securely

> **WARNING:** Pressing GENERATE creates a **new** key and **invalidates** the previous one. If existing integrations use the current key, do not generate a new one unless you plan to update all consumers.

---

## Step 4: Find Your Company Short Name

The Company Short Name is a 7-digit number required for authentication.

**Option A -- From Company Setup:**
1. Go to **Global Setup > Company Setup > Company Info**
2. Under **Company Address**, find the **Company Short Name** field

**Option B -- From your login URL:**
- Your UKG Ready login URL looks like: `https://secureN.saashr.com/ta/XXXXXXX.login`
- The 7 digits (`XXXXXXX`) are your Company Short Name

---

## Step 5: Determine Your API Endpoint URL

UKG Ready hosts tenants across multiple regional clusters. Each cluster has its
own hostname. You must identify which cluster hosts your tenant so the bridge
can reach the correct API endpoint.

### How to find your host

**Option A -- From your login URL (fastest):**

When you log into UKG Ready, look at the browser address bar. The URL will be
in the format:

```
https://secureN.saashr.com/ta/XXXXXXX.login
```

The `secureN` portion is your host. Known clusters include `secure3`, `secure4`,
`secure5`, `secure6`, and `secure7`, though others may exist.

**Option B -- From the REST API documentation page:**

UKG Ready publishes interactive API docs at each cluster. Navigate to:

```
https://secureN.saashr.com/ta/docs/rest/public/
```

Replace `N` with the number from your login URL. If the page loads and shows
the REST API documentation, you have the correct host.

**Option C -- Ask your UKG administrator:**

Your UKG account representative or system administrator will know which
regional cluster your tenant is provisioned on.

### Setting the URL

Set `UKG_BASE_URL` to the **root URL only** -- no trailing slash and no path:

| Correct | Incorrect |
|---------|-----------|
| `https://secure3.saashr.com` | `https://secure3.saashr.com/` |
| `https://secure6.saashr.com` | `https://secure6.saashr.com/ta/rest/v2` |

The bridge appends the appropriate API paths automatically.

---

## Step 6: Identify Your Host (summary)

Your UKG Ready host is the domain from your login URL:

- `https://secure3.saashr.com` -- host is `secure3`
- `https://secure5.saashr.com` -- host is `secure5`
- `https://secure7.saashr.com` -- host is `secure7`

Use the full URL (e.g. `https://secureN.saashr.com`) as the value for `UKG_BASE_URL`.

---

## Step 7: Configure the Bridge

Set these environment variables (or store via `trellis credentials set`):

| Variable | Example | Description |
|----------|---------|-------------|
| `UKG_BASE_URL` | `https://secureN.saashr.com` | Your UKG Ready host URL (see Step 5) |
| `UKG_COMPANY_SHORT_NAME` | `1234567` | 7-digit company identifier |
| `UKG_API_KEY` | *(your API key)* | REST API key from Step 3 |
| `UKG_USERNAME` | `Tendril` | Service account username |
| `UKG_PASSWORD` | *(your password)* | Service account password |

---

## Step 8: Verify

Run the health check to confirm everything is working:

```bash
python3 /opt/bridge/data/tools/ukg_check.py
```

Expected output:
```json
{
  "bridge": "ukg-ready",
  "checks": [
    {"name": "auth", "status": "pass", "company_id": "..."},
    {"name": "employees", "status": "pass", "employee_count": "..."}
  ],
  "summary": "2/2 checks passed",
  "healthy": true
}
```

---

## Authentication Flow

The bridge uses a two-step token-based authentication:

1. **Login:** POST to `/ta/rest/v1/login` with `Api-Key` header and service account credentials
2. **Token:** Receives a JWT (1-hour TTL) containing the company ID (`cid`)
3. **API Calls:** All subsequent requests include `Authentication: Bearer {token}` and `Api-Key` headers

The client automatically refreshes the token before expiry.

---

## API Reference

- **REST API Documentation:** `https://secureN.saashr.com/ta/docs/rest/public/` (replace N with your cluster number)
- **V1 Endpoints:** `/ta/rest/v1/company/{cid}/...`
- **V2 Endpoints:** `/ta/rest/v2/companies/{cid}/...`

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `API key is required` (403) | Missing `Api-Key` header | Verify `UKG_API_KEY` is set |
| `Invalid login` (403) | Wrong credentials | Check username, password, and company short name |
| `Company not found` (404) | Wrong company ID in URL path | The bridge extracts company ID from JWT automatically |
| `Authentication is required` (401) | Token expired or missing | The bridge auto-refreshes; check credentials if persistent |
| `Method Not Allowed` (405) | Wrong HTTP method | Verify you're using POST for login, GET for queries |
| Connection timeout | Wrong host | Verify `UKG_BASE_URL` matches your login URL cluster (see Step 5) |
