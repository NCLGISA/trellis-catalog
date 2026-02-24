# Splunk Bridge -- Deployment Requirements

## Prerequisites

### Splunk Cloud

Two settings must be configured before deploying:

#### 1. Enable Token Authentication

1. Log in to Splunk Web (`https://yourorg.splunkcloud.com`)
2. Go to **Settings** > **Tokens** (under Users and Authentication)
3. If token auth is not enabled, go to **Settings** > **Server settings** > **General settings**, scroll to **Token Authentication**, set to **Enabled**, and save
4. Return to **Settings** > **Tokens** > **New Token**
5. Select the user, set an audience (e.g. "Tendril Bridge"), set expiration, and click **Create**
6. Copy the token value into the `.env` file as `SPLUNK_TOKEN`

#### 2. IP Allow List for Search API (Port 8089)

Splunk Cloud blocks REST API access on port 8089 by default. The Docker host's public IP must be added to the `search-api` IP allow list.

1. Log in to Splunk Web
2. Go to the **Admin Config Service** panel or use the ACS API
3. Add the Docker host's public IP as a `/32` subnet to the **search-api** feature allow list
4. Allow several minutes for the change to propagate

Alternatively, use the ACS API directly:

```bash
curl -X POST 'https://admin.splunk.com/<stack>/adminconfig/v2/access/search-api/ipallowlists' \
  --header 'Content-Type: application/json' \
  --header 'Authorization: Bearer <your-acs-token>' \
  --data '{ "subnets": ["<your-public-ip>/32"] }'
```

### Splunk Enterprise (On-Prem)

#### 1. Enable Token Authentication

Token authentication requires Splunk Enterprise 7.3 or later.

1. Log in to Splunk Web (`https://splunk.internal`)
2. Go to **Settings** > **Tokens** (under Users and Authentication)
3. If token auth is not enabled, go to **Settings** > **Server settings** > **General settings**, scroll to **Token Authentication**, set to **Enabled**, and save
4. Create a token the same way as Splunk Cloud (above)

#### 2. Network Access

Ensure the Docker host running the bridge can reach the Splunk search head on port **8089** (the management/REST API port). This may require firewall rules depending on your network.

#### 3. Self-Signed Certificates

If the search head uses a self-signed TLS certificate (common in on-prem deployments), set `SPLUNK_VERIFY_TLS=false` in the `.env` file. This disables certificate verification for API calls.

## Authentication Model

This bridge uses **per-user tokens**. Each Splunk token is tied to an individual user's account and inherits that user's roles and index permissions. The `SPLUNK_TOKEN` credential is scoped as `operator` in the bridge manifest, meaning each Tendril operator should store their own token via the Tendril bridge credentials system rather than sharing a single token.

The `.env` file token is used as the default for the container's health check. Operator-specific tokens stored via `bridge_credentials` are injected at runtime and take precedence.

## Deployment

Once prerequisites are met:

```bash
cp .env.example .env
# Fill in TENDRIL_INSTALL_KEY, TENDRIL_DOWNLOAD_URL, SPLUNK_URL, SPLUNK_TOKEN
# For on-prem with self-signed certs: set SPLUNK_VERIFY_TLS=false
docker compose up -d --build
```

The bridge registers as `bridge-splunk` on Tendril Root. Verify with the health check:

```bash
docker exec bridge-splunk python3 /opt/bridge/data/tools/splunk_check.py
```

## References

Place institutional knowledge documents here (runbooks, SOPs, index schemas, etc.).
Files in this directory are available to the bridge at `/opt/bridge/data/references/`.
