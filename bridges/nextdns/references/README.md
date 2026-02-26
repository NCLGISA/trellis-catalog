# NextDNS Bridge -- Deployment Requirements

## Prerequisites

### 1. Obtain an API Key

1. Log in to the NextDNS dashboard at https://my.nextdns.io
2. Navigate to the **Account** page
3. Scroll to the bottom to find your API key
4. Copy the key into the `.env` file as `NEXTDNS_API_KEY`

The API key grants access to all profiles owned by the account. There are no per-profile keys.

### 2. Identify Your Profile ID (Optional)

If you want profile-scoped commands to work without the `--profile` flag:

1. Open the NextDNS dashboard
2. Select a profile -- the profile ID is the alphanumeric string in the URL (e.g. `https://my.nextdns.io/abc123/...`)
3. Set `NEXTDNS_PROFILE=abc123` in the `.env` file

Alternatively, deploy without a default profile and use `python3 nextdns.py profiles list` to discover profile IDs.

## Authentication Model

This bridge uses a **shared API key**. The NextDNS API authenticates via the `X-Api-Key` header and does not support per-user or per-profile keys. The `NEXTDNS_API_KEY` credential is scoped as `shared` in the bridge manifest, meaning all operators share the same account-level access.

## API Notes

- The NextDNS API is officially in beta but has been stable for production use
- Rate limits are not documented; the bridge uses reasonable request patterns
- All responses follow a `{ "data": ..., "meta": ... }` envelope format
- Paginated endpoints use cursor-based pagination (handled automatically by the client)

## Deployment

Once prerequisites are met:

```bash
cp .env.example .env
# Fill in TENDRIL_INSTALL_KEY, TENDRIL_DOWNLOAD_URL, NEXTDNS_API_KEY
# Optionally set NEXTDNS_PROFILE
docker compose up -d --build
```

The bridge registers as `bridge-nextdns` on Tendril Root. Verify with the health check:

```bash
docker exec bridge-nextdns python3 /opt/bridge/data/tools/nextdns_check.py
```

## References

Place institutional knowledge documents here (DNS policies, blocklist standards, incident response procedures, etc.).
Files in this directory are available to the bridge at `/opt/bridge/data/references/`.
