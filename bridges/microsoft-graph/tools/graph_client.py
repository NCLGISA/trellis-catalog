"""
Microsoft Graph REST API v1.0 Client (MSAL client_credentials)

Provides authenticated access to the Microsoft Graph API for the tenant
(example.com) with automatic token refresh, pagination, and
rate-limit handling.

Authentication uses MSAL client_credentials flow:
  - POST to Entra ID token endpoint with client_id + client_secret
  - Tokens are valid for ~1 hour
  - Tokens are cached and auto-refreshed 5 minutes before expiry

Environment variables (set in docker-compose.yml):
  AZURE_TENANT_ID      - Entra ID tenant ID
  GRAPH_CLIENT_ID      - App registration client ID
  GRAPH_CLIENT_SECRET  - App registration client secret
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID = os.getenv("GRAPH_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET", "")

TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
API_BASE = "https://graph.microsoft.com/v1.0"
BETA_BASE = "https://graph.microsoft.com/beta"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"

TOKEN_REFRESH_BUFFER_SECS = 300


class GraphClient:
    """Microsoft Graph REST API v1.0 client with MSAL token management."""

    def __init__(
        self,
        tenant_id: str = None,
        client_id: str = None,
        client_secret: str = None,
    ):
        self.tenant_id = tenant_id or TENANT_ID
        self.client_id = client_id or CLIENT_ID
        self.client_secret = client_secret or CLIENT_SECRET

        if not all([self.tenant_id, self.client_id, self.client_secret]):
            print(
                "ERROR: Missing Microsoft Graph credentials.\n"
                "\n"
                "Required environment variables:\n"
                "  AZURE_TENANT_ID\n"
                "  GRAPH_CLIENT_ID\n"
                "  GRAPH_CLIENT_SECRET\n"
                "\n"
                "Create an App Registration in Entra ID with application\n"
                "permissions for Microsoft Graph.\n",
                file=sys.stderr,
            )
            sys.exit(1)

        self._access_token = None
        self._token_expires_at = 0
        self.session = requests.Session()

    # ── OAuth Token Management ─────────────────────────────────────────

    def _get_token(self) -> str:
        """Obtain or refresh the MSAL client_credentials token."""
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        token_url = TOKEN_URL_TEMPLATE.format(tenant=self.tenant_id)
        resp = requests.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": GRAPH_SCOPE,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            print(
                f"ERROR: Token request failed ({resp.status_code}): {resp.text}",
                file=sys.stderr,
            )
            sys.exit(1)

        token_data = resp.json()
        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        self._token_expires_at = now + expires_in - TOKEN_REFRESH_BUFFER_SECS

        return self._access_token

    def _auth_headers(self) -> dict:
        """Return headers with a valid Bearer token."""
        token = self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "ConsistencyLevel": "eventual",
        }

    # ── Core HTTP Methods ──────────────────────────────────────────────

    def _request(
        self, method: str, endpoint: str, **kwargs
    ) -> requests.Response:
        """Make an API request with auth, rate-limit retry, and token refresh."""
        url = endpoint if endpoint.startswith("http") else f"{API_BASE}/{endpoint.lstrip('/')}"
        max_retries = 3

        for attempt in range(max_retries):
            kwargs["headers"] = self._auth_headers()
            resp = self.session.request(method, url, timeout=60, **kwargs)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                print(f"  Rate limited. Waiting {retry_after}s...", file=sys.stderr)
                time.sleep(retry_after)
                continue

            if resp.status_code == 401:
                self._access_token = None
                self._token_expires_at = 0
                continue

            return resp

        return resp

    def get(self, endpoint: str, params: dict = None) -> requests.Response:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("POST", endpoint, json=json_data)

    def patch(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("PATCH", endpoint, json=json_data)

    def put(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("PUT", endpoint, json=json_data)

    def delete(self, endpoint: str, params: dict = None) -> requests.Response:
        return self._request("DELETE", endpoint, params=params)

    # ── Pagination Helper ──────────────────────────────────────────────

    def get_all(
        self,
        endpoint: str,
        key: str = "value",
        params: dict = None,
        top: int = 100,
        max_pages: int = 100,
    ) -> list:
        """
        Paginate through all results for a list endpoint.

        Graph uses @odata.nextLink for cursor-based pagination.
        `key` is the JSON key containing the array (usually 'value').
        """
        params = dict(params or {})
        if "$top" not in params and top:
            params["$top"] = top
        results = []
        url = endpoint

        for _ in range(max_pages):
            resp = self.get(url, params=params if not url.startswith("http") else None)
            if resp.status_code != 200:
                print(f"  Error fetching {url}: {resp.status_code} {resp.text}", file=sys.stderr)
                break

            data = resp.json()
            items = data.get(key, [])
            results.extend(items)

            next_link = data.get("@odata.nextLink")
            if not next_link:
                break

            url = next_link
            params = None

        return results

    # ── Users ──────────────────────────────────────────────────────────

    def list_users(self, select: str = None, filter_expr: str = None, top: int = 100) -> list:
        """List all users in the tenant."""
        params = {}
        if select:
            params["$select"] = select
        else:
            params["$select"] = (
                "id,displayName,mail,userPrincipalName,accountEnabled,"
                "jobTitle,department,userType,onPremisesSyncEnabled"
            )
        if filter_expr:
            params["$filter"] = filter_expr
        return self.get_all("users", params=params, top=top)

    def get_user(self, user_id: str, select: str = None) -> dict:
        """Get a single user by ID, UPN, or email."""
        params = {}
        if select:
            params["$select"] = select
        resp = self.get(f"users/{user_id}", params=params)
        resp.raise_for_status()
        return resp.json()

    def search_users(self, query: str, select: str = None) -> list:
        """Search users by displayName or mail (contains match)."""
        params = {
            "$search": f'"displayName:{query}" OR "mail:{query}"',
            "$orderby": "displayName",
        }
        if select:
            params["$select"] = select
        return self.get_all("users", params=params)

    def update_user(self, user_id: str, properties: dict) -> dict:
        """Update user properties (displayName, jobTitle, department, etc.)."""
        resp = self.patch(f"users/{user_id}", json_data=properties)
        if resp.status_code == 204:
            return {"ok": True}
        return {"error": resp.status_code, "body": resp.text}

    def disable_user(self, user_id: str) -> dict:
        """Disable a user's sign-in."""
        return self.update_user(user_id, {"accountEnabled": False})

    def enable_user(self, user_id: str) -> dict:
        """Enable a user's sign-in."""
        return self.update_user(user_id, {"accountEnabled": True})

    # ── Groups ─────────────────────────────────────────────────────────

    def list_groups(self, filter_expr: str = None, top: int = 100) -> list:
        """List all groups in the tenant."""
        params = {}
        if filter_expr:
            params["$filter"] = filter_expr
        return self.get_all("groups", params=params, top=top)

    def get_group(self, group_id: str) -> dict:
        resp = self.get(f"groups/{group_id}")
        resp.raise_for_status()
        return resp.json()

    def list_group_members(self, group_id: str, select: str = None) -> list:
        """List members of a group."""
        params = {}
        if select:
            params["$select"] = select
        return self.get_all(f"groups/{group_id}/members", params=params or None)

    def add_group_member(self, group_id: str, user_id: str) -> dict:
        """Add a user to a group."""
        body = {"@odata.id": f"{API_BASE}/directoryObjects/{user_id}"}
        resp = self.post(f"groups/{group_id}/members/$ref", json_data=body)
        if resp.status_code == 204:
            return {"ok": True}
        return {"error": resp.status_code, "body": resp.text}

    def remove_group_member(self, group_id: str, user_id: str) -> dict:
        """Remove a user from a group."""
        resp = self.delete(f"groups/{group_id}/members/{user_id}/$ref")
        if resp.status_code == 204:
            return {"ok": True}
        return {"error": resp.status_code, "body": resp.text}

    # ── Licenses ───────────────────────────────────────────────────────

    def list_subscribed_skus(self) -> list:
        """List all subscribed license SKUs."""
        resp = self.get("subscribedSkus")
        resp.raise_for_status()
        return resp.json().get("value", [])

    def get_user_licenses(self, user_id: str) -> list:
        """Get licenses assigned to a user."""
        resp = self.get(f"users/{user_id}/licenseDetails")
        resp.raise_for_status()
        return resp.json().get("value", [])

    def assign_license(self, user_id: str, sku_id: str, disabled_plans: list = None) -> dict:
        """Assign a license to a user."""
        body = {
            "addLicenses": [{"skuId": sku_id, "disabledPlans": disabled_plans or []}],
            "removeLicenses": [],
        }
        resp = self.post(f"users/{user_id}/assignLicense", json_data=body)
        if resp.status_code == 200:
            return {"ok": True}
        return {"error": resp.status_code, "body": resp.text}

    def remove_license(self, user_id: str, sku_id: str) -> dict:
        """Remove a license from a user."""
        body = {"addLicenses": [], "removeLicenses": [sku_id]}
        resp = self.post(f"users/{user_id}/assignLicense", json_data=body)
        if resp.status_code == 200:
            return {"ok": True}
        return {"error": resp.status_code, "body": resp.text}

    # ── Mailbox (Exchange Online) ──────────────────────────────────────

    def get_mailbox_settings(self, user_id: str) -> dict:
        """Get a user's mailbox settings (auto-reply, timezone, forwarding, etc.)."""
        resp = self.get(f"users/{user_id}/mailboxSettings")
        resp.raise_for_status()
        return resp.json()

    def get_mail_folders(self, user_id: str) -> list:
        """Get a user's mail folders (Inbox, Sent, etc.) with unread counts."""
        return self.get_all(f"users/{user_id}/mailFolders")

    def get_inbox_rules(self, user_id: str) -> list:
        """Get a user's inbox rules (forwarding, auto-move, etc.)."""
        resp = self.get(f"users/{user_id}/mailFolders/inbox/messageRules")
        resp.raise_for_status()
        return resp.json().get("value", [])

    def list_messages(self, user_id: str, folder: str = "inbox", top: int = 25, filter_expr: str = None) -> list:
        """List messages in a user's mail folder."""
        params = {"$top": top, "$orderby": "receivedDateTime desc"}
        if filter_expr:
            params["$filter"] = filter_expr
        return self.get_all(
            f"users/{user_id}/mailFolders/{folder}/messages",
            params=params,
            top=top,
            max_pages=1,
        )

    def send_mail(self, user_id: str, subject: str, body: str, to_recipients: list) -> dict:
        """Send an email as a user."""
        message = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [
                    {"emailAddress": {"address": addr}} for addr in to_recipients
                ],
            }
        }
        resp = self.post(f"users/{user_id}/sendMail", json_data=message)
        if resp.status_code == 202:
            return {"ok": True}
        return {"error": resp.status_code, "body": resp.text}

    # ── Shared Mailboxes ───────────────────────────────────────────────

    def list_shared_mailboxes(self) -> list:
        """List shared mailboxes (users with recipientType 'SharedMailbox')."""
        params = {
            "$filter": "userType eq 'Member'",
            "$select": "id,displayName,mail,userPrincipalName,accountEnabled,userType",
        }
        users = self.get_all("users", params=params)
        shared = []
        for u in users:
            upn = u.get("userPrincipalName", "")
            if "#EXT#" not in upn and not u.get("accountEnabled", True):
                shared.append(u)
        return shared

    # ── Mailbox Delegation ──────────────────────────────────────────────

    def grant_mailbox_delegate(self, mailbox: str, delegate_email: str, role: str = "editor") -> dict:
        """Grant a user delegate (full) access to another user's mailbox.

        Uses calendarPermissions as a proxy since Graph does not expose
        Exchange mailbox permissions directly. For full mailbox delegation,
        use Exchange Online PowerShell via Tendril.

        For read-only shared access, the delegate can access via:
            /users/{mailbox}/messages
        if the application has Mail.ReadWrite permission.

        Args:
            mailbox: UPN or ID of the mailbox owner
            delegate_email: email of the user to grant access
            role: 'read' or 'editor' (default: editor = full access)
        """
        delegate = self.get_user(delegate_email, select="id,displayName")
        perm_body = {
            "emailAddress": {"address": delegate_email, "name": delegate.get("displayName", "")},
            "role": role,
            "allowedRoles": ["read", "write", "delegateWithPrivateEventAccess", "delegateWithoutPrivateEventAccess"],
        }
        resp = self.post(f"users/{mailbox}/calendar/calendarPermissions", json_data=perm_body)
        if resp.status_code in (200, 201):
            return {"ok": True, "delegate": delegate_email, "mailbox": mailbox, "role": role}
        return {"error": resp.status_code, "body": resp.text}

    def list_mailbox_permissions(self, mailbox: str) -> list:
        """List all delegate permissions on a mailbox (via calendar permissions)."""
        resp = self.get(f"users/{mailbox}/calendar/calendarPermissions")
        resp.raise_for_status()
        return resp.json().get("value", [])

    # ── Distribution Lists (Mail-Enabled Groups) ─────────────────────

    def list_distribution_groups(self, top: int = 999) -> list:
        """List mail-enabled distribution groups."""
        params = {
            "$filter": "mailEnabled eq true and securityEnabled eq false",
            "$select": "id,displayName,mail,proxyAddresses,memberCount",
        }
        return self.get_all("groups", params=params, top=top)

    def search_distribution_groups(self, query: str) -> list:
        """Search distribution groups by display name."""
        params = {
            "$search": f'"displayName:{query}"',
            "$filter": "mailEnabled eq true",
            "$select": "id,displayName,mail,memberCount",
        }
        return self.get_all("groups", params=params)

    def list_distribution_group_members(self, group_id: str) -> list:
        """List members of a distribution group."""
        return self.get_all(f"groups/{group_id}/members",
                            params={"$select": "id,displayName,mail,userPrincipalName"})

    def remove_distribution_group_member(self, group_id: str, member_id: str) -> dict:
        """Remove a member from a distribution group."""
        resp = self.delete(f"groups/{group_id}/members/{member_id}/$ref")
        if resp.status_code == 204:
            return {"ok": True}
        return {"error": resp.status_code, "body": resp.text}

    def add_distribution_group_member(self, group_id: str, user_id: str) -> dict:
        """Add a member to a distribution group."""
        body = {"@odata.id": f"{API_BASE}/directoryObjects/{user_id}"}
        resp = self.post(f"groups/{group_id}/members/$ref", json_data=body)
        if resp.status_code == 204:
            return {"ok": True}
        return {"error": resp.status_code, "body": resp.text}

    # ── Room Calendars (Resource Mailboxes) ──────────────────────────

    def list_room_lists(self) -> list:
        """List room lists (room categories/buildings)."""
        resp = self.get("places/microsoft.graph.roomList")
        resp.raise_for_status()
        return resp.json().get("value", [])

    def list_rooms(self) -> list:
        """List all room resources (conference rooms)."""
        resp = self.get("places/microsoft.graph.room")
        resp.raise_for_status()
        return resp.json().get("value", [])

    def get_room_calendar(self, room_email: str, start: str = None, end: str = None) -> list:
        """Get calendar events for a room mailbox.

        Args:
            room_email: the room resource email (e.g., 'admin-conf-101@example.com')
            start: ISO 8601 start datetime (defaults to today)
            end: ISO 8601 end datetime (defaults to 7 days from start)
        """
        from datetime import datetime, timedelta
        if not start:
            start = datetime.utcnow().strftime("%Y-%m-%dT00:00:00Z")
        if not end:
            end = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT23:59:59Z")

        params = {
            "startDateTime": start,
            "endDateTime": end,
            "$select": "subject,organizer,start,end,location",
            "$orderby": "start/dateTime",
        }
        return self.get_all(f"users/{room_email}/calendarView", params=params)

    # ── Calendar ───────────────────────────────────────────────────────

    def get_calendar_permissions(self, user_id: str) -> list:
        """Get calendar sharing permissions for a user."""
        resp = self.get(f"users/{user_id}/calendar/calendarPermissions")
        resp.raise_for_status()
        return resp.json().get("value", [])

    # ── Intune / Device Management ─────────────────────────────────────

    def list_managed_devices(self, filter_expr: str = None, top: int = 100) -> list:
        """List Intune managed devices."""
        params = {}
        if filter_expr:
            params["$filter"] = filter_expr
        return self.get_all("deviceManagement/managedDevices", params=params, top=top)

    def get_managed_device(self, device_id: str) -> dict:
        resp = self.get(f"deviceManagement/managedDevices/{device_id}")
        resp.raise_for_status()
        return resp.json()

    def list_compliance_policies(self) -> list:
        """List Intune device compliance policies."""
        return self.get_all("deviceManagement/deviceCompliancePolicies")

    # ── SharePoint ─────────────────────────────────────────────────────

    def list_sites(self, search: str = None) -> list:
        """List SharePoint sites. Optional search filter."""
        if search:
            params = {"search": search}
            return self.get_all("sites", params=params)
        return self.get_all("sites?search=*")

    def get_site(self, site_id: str) -> dict:
        resp = self.get(f"sites/{site_id}")
        resp.raise_for_status()
        return resp.json()

    def list_site_drives(self, site_id: str) -> list:
        """List document libraries for a SharePoint site."""
        return self.get_all(f"sites/{site_id}/drives")

    # ── Directory / Organization ───────────────────────────────────────

    def get_organization(self) -> dict:
        """Get the organization (tenant) details."""
        resp = self.get("organization")
        resp.raise_for_status()
        orgs = resp.json().get("value", [])
        return orgs[0] if orgs else {}

    def list_domains(self) -> list:
        """List verified domains for the tenant."""
        resp = self.get("domains")
        resp.raise_for_status()
        return resp.json().get("value", [])

    def list_service_principals(self, filter_expr: str = None, top: int = 100) -> list:
        """List service principals (app registrations) in the tenant."""
        params = {}
        if filter_expr:
            params["$filter"] = filter_expr
        return self.get_all("servicePrincipals", params=params, top=top)

    def list_app_role_assignments(self, service_principal_id: str) -> list:
        """List users/groups assigned to an enterprise application."""
        return self.get_all(f"servicePrincipals/{service_principal_id}/appRoleAssignedTo")

    # ── Audit / Sign-in Logs ──────────────────────────────────────────

    def list_sign_ins(self, user_id: str = None, top: int = 50) -> list:
        """List sign-in logs. Optionally filter by user."""
        params = {"$top": top, "$orderby": "createdDateTime desc"}
        if user_id:
            params["$filter"] = f"userId eq '{user_id}'"
        return self.get_all("auditLogs/signIns", params=params, top=top, max_pages=1)

    def list_directory_audit_logs(self, top: int = 50) -> list:
        """List directory audit logs."""
        params = {"$top": top, "$orderby": "activityDateTime desc"}
        return self.get_all("auditLogs/directoryAudits", params=params, top=top, max_pages=1)

    # ── LAPS (Local Admin Password Solution) ──────────────────────────

    def get_device_laps(self, device_id: str) -> dict:
        """Get LAPS credentials for a device by its Entra device ID."""
        resp = self.get(f"directory/deviceLocalCredentials/{device_id}?$select=credentials")
        resp.raise_for_status()
        return resp.json()

    def list_laps_devices(self, top: int = 999) -> list:
        """List all devices that have LAPS credentials backed up."""
        return self.get_all("directory/deviceLocalCredentials", top=top)

    # ── Teams ─────────────────────────────────────────────────────────

    def list_teams(self, top: int = 999) -> list:
        """List all teams in the tenant."""
        return self.get_all("teams", top=top)

    def get_team(self, team_id: str) -> dict:
        resp = self.get(f"teams/{team_id}")
        resp.raise_for_status()
        return resp.json()

    def list_team_channels(self, team_id: str) -> list:
        """List channels for a team (no pagination -- channels API rejects $top)."""
        resp = self.get(f"teams/{team_id}/channels")
        resp.raise_for_status()
        return resp.json().get("value", [])

    def list_team_members(self, team_id: str) -> list:
        """List members of a team (no pagination -- members API rejects $top)."""
        resp = self.get(f"teams/{team_id}/members")
        resp.raise_for_status()
        return resp.json().get("value", [])

    # ── Security / Defender ───────────────────────────────────────────

    def list_security_alerts(self, top: int = 50) -> list:
        """List Microsoft Defender security alerts."""
        params = {"$top": top, "$orderby": "createdDateTime desc"}
        return self.get_all("security/alerts_v2", params=params, top=top, max_pages=1)

    def list_security_incidents(self, top: int = 50) -> list:
        """List Microsoft Defender security incidents."""
        params = {"$top": top, "$orderby": "createdDateTime desc"}
        return self.get_all("security/incidents", params=params, top=top, max_pages=1)

    def get_secure_scores(self, top: int = 1) -> list:
        """Get Microsoft Secure Score (most recent by default)."""
        params = {"$top": top, "$orderby": "createdDateTime desc"}
        return self.get_all("security/secureScores", params=params, top=top, max_pages=1)

    # ── Identity Protection (Entra ID P2) ─────────────────────────────

    def list_risky_users(self, top: int = 100) -> list:
        """List users flagged as risky by Identity Protection."""
        return self.get_all("identityProtection/riskyUsers", top=top)

    def list_risk_detections(self, top: int = 50) -> list:
        """List risk detection events."""
        params = {"$top": top, "$orderby": "activityDateTime desc"}
        return self.get_all("identityProtection/riskDetections", params=params, top=top, max_pages=1)

    # ── Conditional Access ────────────────────────────────────────────

    def list_conditional_access_policies(self) -> list:
        """List all Conditional Access policies."""
        return self.get_all("identity/conditionalAccess/policies")

    def list_named_locations(self) -> list:
        """List Conditional Access named locations."""
        return self.get_all("identity/conditionalAccess/namedLocations")

    # ── Global Secure Access (beta) ──────────────────────────────────
    # Requires NetworkAccess.Read.All permission (add via Entra portal).
    # These endpoints use the beta API and may change without notice.

    def list_forwarding_profiles(self) -> list:
        """List Global Secure Access forwarding profiles (beta).

        Returns Private Access, Internet Access, and M365 traffic profiles.
        Requires NetworkAccess.Read.All permission.
        """
        return self.get_all(f"{BETA_BASE}/networkAccess/forwardingProfiles")

    def get_forwarding_profile(self, profile_id: str) -> dict:
        """Get a single forwarding profile with its policies (beta)."""
        resp = self.get(f"{BETA_BASE}/networkAccess/forwardingProfiles/{profile_id}?$expand=policies($expand=rules)")
        resp.raise_for_status()
        return resp.json()

    def list_filtering_policies(self) -> list:
        """List Global Secure Access filtering policies (beta)."""
        return self.get_all(f"{BETA_BASE}/networkAccess/filteringPolicies")

    def list_remote_networks(self) -> list:
        """List Global Secure Access remote networks / branch offices (beta)."""
        return self.get_all(f"{BETA_BASE}/networkAccess/connectivity/branches")

    # ── Extended Intune ───────────────────────────────────────────────

    def list_intune_apps(self, top: int = 100) -> list:
        """List Intune mobile/managed apps."""
        return self.get_all("deviceAppManagement/mobileApps", top=top)

    def list_device_configurations(self) -> list:
        """List Intune device configuration profiles."""
        return self.get_all("deviceManagement/deviceConfigurations")

    def get_managed_device_overview(self) -> dict:
        """Get Intune managed device overview (counts by OS, compliance, etc.)."""
        resp = self.get("deviceManagement/managedDeviceOverview")
        resp.raise_for_status()
        return resp.json()

    def list_intune_role_definitions(self) -> list:
        """List Intune RBAC role definitions."""
        return self.get_all("deviceManagement/roleDefinitions")

    # ── Reports ───────────────────────────────────────────────────────

    def get_office365_active_users(self, period: str = "D7") -> str:
        """Get Office 365 active user report (returns CSV)."""
        resp = self.get(f"reports/getOffice365ActiveUserDetail(period='{period}')")
        resp.raise_for_status()
        return resp.text

    def get_auth_methods_registration(self, top: int = 999) -> list:
        """Get authentication methods registration details."""
        return self.get_all("reports/authenticationMethods/userRegistrationDetails", top=top)

    # ── Utility ────────────────────────────────────────────────────────

    def test_connection(self) -> dict:
        """Health check: validate credentials and basic API access."""
        try:
            # Use /users?$top=1 as the primary check (requires User.Read.All,
            # which is always granted). /organization requires Organization.Read.All
            # which may not be available in all tenants.
            users = self.list_users(select="id,displayName", top=1)
            result = {"ok": True, "users_accessible": True}

            # Try organization info (may fail with 403 if Organization.Read.All not granted)
            try:
                org = self.get_organization()
                result["tenant_id"] = org.get("id")
                result["display_name"] = org.get("displayName")
            except Exception:
                result["organization_info"] = "not accessible (Organization.Read.All may not be granted)"

            # Try domains
            try:
                domains = self.list_domains()
                result["verified_domains"] = [d["id"] for d in domains if d.get("isVerified")]
                result["default_domain"] = next(
                    (d["id"] for d in domains if d.get("isDefault")), None
                )
            except Exception:
                result["domains"] = "not accessible"

            return result
        except requests.HTTPError as e:
            return {
                "ok": False,
                "error": str(e),
                "status": getattr(e.response, "status_code", None),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── CLI Entrypoint ─────────────────────────────────────────────────────
# Allows quick testing: python3 graph_client.py test

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "test"
    client = GraphClient()

    if action == "test":
        result = client.test_connection()
        print(json.dumps(result, indent=2))

    elif action == "users":
        users = client.list_users(
            select="id,displayName,mail,userPrincipalName,accountEnabled,jobTitle,department"
        )
        print(f"Total users: {len(users)}")
        for u in users:
            enabled = "enabled" if u.get("accountEnabled") else "disabled"
            name = u.get('displayName') or '?'
            mail = u.get('mail') or ''
            print(f"  {name:40s}  {mail:40s}  {enabled}")

    elif action == "groups":
        groups = client.list_groups()
        print(f"Total groups: {len(groups)}")
        for g in groups:
            print(f"  {g.get('displayName', '?'):40s}  members={g.get('memberCount', '?')}")

    elif action == "licenses":
        skus = client.list_subscribed_skus()
        print(f"Subscribed SKUs: {len(skus)}")
        for s in skus:
            consumed = s.get("consumedUnits", 0)
            total = s.get("prepaidUnits", {}).get("enabled", 0)
            print(f"  {s.get('skuPartNumber', '?'):40s}  {consumed}/{total} consumed")

    elif action == "domains":
        domains = client.list_domains()
        for d in domains:
            default = " (default)" if d.get("isDefault") else ""
            verified = " [verified]" if d.get("isVerified") else ""
            print(f"  {d['id']}{default}{verified}")

    else:
        print(f"Unknown action: {action}")
        print("Usage: python3 graph_client.py [test|users|groups|licenses|domains]")
        sys.exit(1)
