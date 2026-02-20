"""
Azure Resource Manager REST API Client (MSAL client_credentials)

Provides authenticated access to the Azure ARM API for your Azure subscription
with automatic token refresh, pagination, and rate-limit handling.

Authentication uses MSAL client_credentials flow:
  - POST to Entra ID token endpoint with client_id + client_secret
  - Scope: https://management.azure.com/.default
  - Tokens are valid for ~1 hour
  - Tokens are cached and auto-refreshed 5 minutes before expiry

Environment variables (set in docker-compose.yml):
  AZURE_TENANT_ID        - Entra ID tenant ID
  ARM_CLIENT_ID          - App registration client ID
  ARM_CLIENT_SECRET      - App registration client secret
  AZURE_SUBSCRIPTION_ID  - Azure subscription ID
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
CLIENT_ID = os.getenv("ARM_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("ARM_CLIENT_SECRET", "")
SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID", "")

TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
ARM_BASE = "https://management.azure.com"
ARM_SCOPE = "https://management.azure.com/.default"
DEFAULT_API_VERSION = "2024-03-01"

TOKEN_REFRESH_BUFFER_SECS = 300


class ArmClient:
    """Azure Resource Manager REST API client with MSAL token management."""

    def __init__(
        self,
        tenant_id: str = None,
        client_id: str = None,
        client_secret: str = None,
        subscription_id: str = None,
    ):
        self.tenant_id = tenant_id or TENANT_ID
        self.client_id = client_id or CLIENT_ID
        self.client_secret = client_secret or CLIENT_SECRET
        self.subscription_id = subscription_id or SUBSCRIPTION_ID

        if not all([self.tenant_id, self.client_id, self.client_secret, self.subscription_id]):
            print(
                "ERROR: Missing Azure ARM credentials.\n"
                "\n"
                "Required environment variables:\n"
                "  AZURE_TENANT_ID\n"
                "  ARM_CLIENT_ID\n"
                "  ARM_CLIENT_SECRET\n"
                "  AZURE_SUBSCRIPTION_ID\n"
                "\n"
                "Create an App Registration in Entra ID with RBAC roles\n"
                "on the target subscription.\n",
                file=sys.stderr,
            )
            sys.exit(1)

        self._access_token = None
        self._token_expires_at = 0
        self.session = requests.Session()

    @property
    def sub_path(self) -> str:
        """ARM subscription path prefix."""
        return f"/subscriptions/{self.subscription_id}"

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
                "scope": ARM_SCOPE,
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
        }

    # ── Core HTTP Methods ──────────────────────────────────────────────

    def _request(
        self, method: str, path: str, api_version: str = None, **kwargs
    ) -> requests.Response:
        """Make an ARM API request with auth, rate-limit retry, and token refresh."""
        if path.startswith("http"):
            url = path
        else:
            url = f"{ARM_BASE}{path}"

        if "params" not in kwargs or kwargs["params"] is None:
            kwargs["params"] = {}
        if api_version and "api-version" not in kwargs["params"]:
            kwargs["params"]["api-version"] = api_version

        max_retries = 3
        for attempt in range(max_retries):
            kwargs["headers"] = self._auth_headers()
            resp = self.session.request(method, url, timeout=60, **kwargs)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 10))
                print(f"  Rate limited. Waiting {retry_after}s...", file=sys.stderr)
                time.sleep(retry_after)
                continue

            if resp.status_code == 401:
                self._access_token = None
                self._token_expires_at = 0
                continue

            return resp

        return resp

    def get(self, path: str, api_version: str = None, params: dict = None) -> requests.Response:
        return self._request("GET", path, api_version=api_version, params=params)

    def post(self, path: str, api_version: str = None, json_data: dict = None) -> requests.Response:
        return self._request("POST", path, api_version=api_version, json=json_data)

    def put(self, path: str, api_version: str = None, json_data: dict = None) -> requests.Response:
        return self._request("PUT", path, api_version=api_version, json=json_data)

    def delete(self, path: str, api_version: str = None) -> requests.Response:
        return self._request("DELETE", path, api_version=api_version)

    # ── Pagination Helper ──────────────────────────────────────────────

    def get_all(
        self, path: str, api_version: str = None, params: dict = None, max_pages: int = 50
    ) -> list:
        """Paginate through ARM list results using nextLink."""
        results = []
        url = path

        for _ in range(max_pages):
            resp = self.get(url, api_version=api_version, params=params)
            if resp.status_code != 200:
                print(f"  Error fetching {url}: {resp.status_code} {resp.text}", file=sys.stderr)
                break

            data = resp.json()
            results.extend(data.get("value", []))

            next_link = data.get("nextLink")
            if not next_link:
                break
            url = next_link
            params = None
            api_version = None

        return results

    # ── Resource Groups ────────────────────────────────────────────────

    def list_resource_groups(self) -> list:
        """List all resource groups in the subscription."""
        return self.get_all(
            f"{self.sub_path}/resourcegroups",
            api_version="2024-03-01",
        )

    # ── Virtual Machines ───────────────────────────────────────────────

    def list_vms(self, resource_group: str = None) -> list:
        """List VMs. Optionally filter by resource group."""
        if resource_group:
            path = f"{self.sub_path}/resourceGroups/{resource_group}/providers/Microsoft.Compute/virtualMachines"
        else:
            path = f"{self.sub_path}/providers/Microsoft.Compute/virtualMachines"
        return self.get_all(path, api_version="2024-03-01")

    def get_vm(self, resource_group: str, vm_name: str, instance_view: bool = False) -> dict:
        """Get a VM by name. Set instance_view=True for power state."""
        expand = "$expand=instanceView" if instance_view else ""
        path = (
            f"{self.sub_path}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.Compute/virtualMachines/{vm_name}"
        )
        params = {}
        if instance_view:
            params["$expand"] = "instanceView"
        resp = self.get(path, api_version="2024-03-01", params=params)
        resp.raise_for_status()
        return resp.json()

    def list_vm_statuses(self, resource_group: str = None) -> list:
        """List all VMs with their power state (instance view)."""
        vms = self.list_vms(resource_group)
        results = []
        for vm in vms:
            vm_id = vm["id"]
            resp = self.get(
                f"{vm_id}/instanceView",
                api_version="2024-03-01",
            )
            power_state = "unknown"
            if resp.status_code == 200:
                statuses = resp.json().get("statuses", [])
                for s in statuses:
                    if s.get("code", "").startswith("PowerState/"):
                        power_state = s["code"].replace("PowerState/", "")
                        break

            rg = vm_id.split("/resourceGroups/")[1].split("/")[0] if "/resourceGroups/" in vm_id else "?"
            results.append({
                "name": vm["name"],
                "resourceGroup": rg,
                "location": vm.get("location"),
                "vmSize": vm.get("properties", {}).get("hardwareProfile", {}).get("vmSize"),
                "powerState": power_state,
                "osType": vm.get("properties", {}).get("storageProfile", {}).get("osDisk", {}).get("osType"),
            })
        return results

    def vm_power_action(self, resource_group: str, vm_name: str, action: str) -> dict:
        """Perform a power action on a VM: start, deallocate, restart, powerOff."""
        valid_actions = {"start", "deallocate", "restart", "powerOff"}
        if action not in valid_actions:
            return {"error": f"Invalid action '{action}'. Valid: {valid_actions}"}

        path = (
            f"{self.sub_path}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.Compute/virtualMachines/{vm_name}/{action}"
        )
        resp = self.post(path, api_version="2024-03-01")
        if resp.status_code == 202:
            return {"ok": True, "action": action, "vm": vm_name, "status": "accepted"}
        return {"error": resp.status_code, "body": resp.text}

    # ── Network Security Groups ────────────────────────────────────────

    def list_nsgs(self, resource_group: str = None) -> list:
        """List NSGs. Optionally filter by resource group."""
        if resource_group:
            path = f"{self.sub_path}/resourceGroups/{resource_group}/providers/Microsoft.Network/networkSecurityGroups"
        else:
            path = f"{self.sub_path}/providers/Microsoft.Network/networkSecurityGroups"
        return self.get_all(path, api_version="2024-01-01")

    def get_nsg(self, resource_group: str, nsg_name: str) -> dict:
        """Get an NSG with all its rules."""
        path = (
            f"{self.sub_path}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.Network/networkSecurityGroups/{nsg_name}"
        )
        resp = self.get(path, api_version="2024-01-01")
        resp.raise_for_status()
        return resp.json()

    def list_nsg_rules(self, resource_group: str, nsg_name: str) -> list:
        """List all rules (default + custom) for an NSG."""
        nsg = self.get_nsg(resource_group, nsg_name)
        props = nsg.get("properties", {})
        rules = props.get("securityRules", [])
        default_rules = props.get("defaultSecurityRules", [])
        return {"custom": rules, "default": default_rules}

    # ── Virtual Networks ───────────────────────────────────────────────

    def list_vnets(self, resource_group: str = None) -> list:
        """List virtual networks."""
        if resource_group:
            path = f"{self.sub_path}/resourceGroups/{resource_group}/providers/Microsoft.Network/virtualNetworks"
        else:
            path = f"{self.sub_path}/providers/Microsoft.Network/virtualNetworks"
        return self.get_all(path, api_version="2024-01-01")

    # ── Storage Accounts ───────────────────────────────────────────────

    def list_storage_accounts(self, resource_group: str = None) -> list:
        """List storage accounts."""
        if resource_group:
            path = f"{self.sub_path}/resourceGroups/{resource_group}/providers/Microsoft.Storage/storageAccounts"
        else:
            path = f"{self.sub_path}/providers/Microsoft.Storage/storageAccounts"
        return self.get_all(path, api_version="2023-05-01")

    def get_storage_account(self, resource_group: str, account_name: str) -> dict:
        """Get a storage account by name."""
        path = (
            f"{self.sub_path}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.Storage/storageAccounts/{account_name}"
        )
        resp = self.get(path, api_version="2023-05-01")
        resp.raise_for_status()
        return resp.json()

    # ── Azure Virtual Desktop (AVD) ───────────────────────────────────

    def list_host_pools(self, resource_group: str = None) -> list:
        """List AVD host pools."""
        if resource_group:
            path = f"{self.sub_path}/resourceGroups/{resource_group}/providers/Microsoft.DesktopVirtualization/hostPools"
        else:
            path = f"{self.sub_path}/providers/Microsoft.DesktopVirtualization/hostPools"
        return self.get_all(path, api_version="2024-04-03")

    def get_host_pool(self, resource_group: str, pool_name: str) -> dict:
        """Get an AVD host pool by name."""
        path = (
            f"{self.sub_path}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.DesktopVirtualization/hostPools/{pool_name}"
        )
        resp = self.get(path, api_version="2024-04-03")
        resp.raise_for_status()
        return resp.json()

    def list_session_hosts(self, resource_group: str, pool_name: str) -> list:
        """List session hosts in an AVD host pool."""
        path = (
            f"{self.sub_path}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.DesktopVirtualization/hostPools/{pool_name}/sessionHosts"
        )
        return self.get_all(path, api_version="2024-04-03")

    def list_user_sessions(self, resource_group: str, pool_name: str, session_host: str) -> list:
        """List active user sessions on an AVD session host."""
        path = (
            f"{self.sub_path}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.DesktopVirtualization/hostPools/{pool_name}"
            f"/sessionHosts/{session_host}/userSessions"
        )
        return self.get_all(path, api_version="2024-04-03")

    def list_app_groups(self, resource_group: str = None) -> list:
        """List AVD application groups."""
        if resource_group:
            path = f"{self.sub_path}/resourceGroups/{resource_group}/providers/Microsoft.DesktopVirtualization/applicationGroups"
        else:
            path = f"{self.sub_path}/providers/Microsoft.DesktopVirtualization/applicationGroups"
        return self.get_all(path, api_version="2024-04-03")

    # ── Azure Monitor ──────────────────────────────────────────────────

    def get_metrics(
        self,
        resource_id: str,
        metric_names: str,
        timespan: str = "PT1H",
        interval: str = "PT5M",
    ) -> dict:
        """
        Get Azure Monitor metrics for a resource.

        metric_names: comma-separated (e.g. "Percentage CPU,Network In Total")
        timespan: ISO 8601 duration (e.g. "PT1H" for last hour, "P1D" for last day)
        interval: ISO 8601 duration (e.g. "PT5M" for 5-minute granularity)
        """
        path = f"{resource_id}/providers/microsoft.insights/metrics"
        params = {
            "metricnames": metric_names,
            "timespan": timespan,
            "interval": interval,
            "aggregation": "Average,Maximum",
        }
        resp = self.get(path, api_version="2024-02-01", params=params)
        resp.raise_for_status()
        return resp.json()

    # ── Cost Management ────────────────────────────────────────────────

    def get_cost_summary(self, timeframe: str = "MonthToDate") -> dict:
        """
        Get cost summary for the subscription.

        timeframe: MonthToDate, BillingMonthToDate, TheLastMonth,
                   TheLastBillingMonth, WeekToDate, Custom
        """
        path = f"{self.sub_path}/providers/Microsoft.CostManagement/query"
        body = {
            "type": "ActualCost",
            "timeframe": timeframe,
            "dataset": {
                "granularity": "None",
                "aggregation": {
                    "totalCost": {"name": "Cost", "function": "Sum"},
                },
                "grouping": [
                    {"type": "Dimension", "name": "ResourceGroup"},
                ],
            },
        }
        resp = self.post(path, api_version="2023-11-01", json_data=body)
        if resp.status_code != 200:
            return {"error": resp.status_code, "body": resp.text}
        return resp.json()

    # ── Utility ────────────────────────────────────────────────────────

    def test_connection(self) -> dict:
        """Health check: fetch subscription info to validate credentials."""
        try:
            resp = self.get(self.sub_path, api_version="2024-03-01")
            if resp.status_code != 200:
                return {"ok": False, "status": resp.status_code, "body": resp.text}
            sub = resp.json()
            rgs = self.list_resource_groups()
            return {
                "ok": True,
                "subscription_id": sub.get("subscriptionId"),
                "display_name": sub.get("displayName"),
                "state": sub.get("state"),
                "resource_groups": len(rgs),
            }
        except requests.HTTPError as e:
            return {
                "ok": False,
                "error": str(e),
                "status": getattr(e.response, "status_code", None),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── CLI Entrypoint ─────────────────────────────────────────────────────

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "test"
    client = ArmClient()

    if action == "test":
        result = client.test_connection()
        print(json.dumps(result, indent=2))

    elif action == "vms":
        vms = client.list_vms()
        print(f"Total VMs: {len(vms)}")
        for vm in vms:
            rg = vm["id"].split("/resourceGroups/")[1].split("/")[0] if "/resourceGroups/" in vm["id"] else "?"
            size = vm.get("properties", {}).get("hardwareProfile", {}).get("vmSize", "?")
            print(f"  {vm['name']:30s}  {rg:30s}  {size:20s}  {vm.get('location', '?')}")

    elif action == "rgs":
        rgs = client.list_resource_groups()
        print(f"Resource groups: {len(rgs)}")
        for rg in rgs:
            print(f"  {rg['name']:40s}  {rg.get('location', '?')}")

    elif action == "nsgs":
        nsgs = client.list_nsgs()
        print(f"NSGs: {len(nsgs)}")
        for nsg in nsgs:
            rule_count = len(nsg.get("properties", {}).get("securityRules", []))
            print(f"  {nsg['name']:40s}  rules={rule_count}")

    elif action == "storage":
        accounts = client.list_storage_accounts()
        print(f"Storage accounts: {len(accounts)}")
        for a in accounts:
            kind = a.get("kind", "?")
            print(f"  {a['name']:30s}  {kind:20s}  {a.get('location', '?')}")

    elif action == "avd":
        pools = client.list_host_pools()
        print(f"AVD Host Pools: {len(pools)}")
        for p in pools:
            props = p.get("properties", {})
            print(f"  {p['name']:30s}  type={props.get('hostPoolType', '?')}  lb={props.get('loadBalancerType', '?')}")

    else:
        print(f"Unknown action: {action}")
        print("Usage: python3 arm_client.py [test|vms|rgs|nsgs|storage|avd]")
        sys.exit(1)
