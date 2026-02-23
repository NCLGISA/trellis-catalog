"""
Microsoft Purview PowerShell Client (Certificate-Based Authentication)

Python wrapper for Security & Compliance PowerShell cmdlets via Connect-IPPSSession.
Covers DLP policies, retention policies/labels, sensitivity labels, alert policies,
eDiscovery (read-only), and information barriers.

Uses the same ExchangeOnlineManagement module as the Exchange bridge, but connects
to the compliance endpoint (compliance.protection.outlook.com) instead of Exchange.

Environment variables:
  PURVIEW_TENANT_ID       - Entra ID tenant ID
  PURVIEW_APP_ID          - App registration client ID
  PURVIEW_CERT_THUMBPRINT - SHA1 thumbprint of the uploaded certificate
  PURVIEW_ORGANIZATION    - Tenant onmicrosoft.com domain
"""

import os
import sys
import json
import subprocess
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

TENANT_ID = os.getenv("PURVIEW_TENANT_ID", "")
APP_ID = os.getenv("PURVIEW_APP_ID", "")
CERT_THUMBPRINT = os.getenv("PURVIEW_CERT_THUMBPRINT", "")
ORGANIZATION = os.getenv("PURVIEW_ORGANIZATION", "")
CERT_DIR = os.getenv("PURVIEW_CERT_DIR", "/opt/bridge/certs")
CERT_FILENAME = os.getenv("PURVIEW_CERT_FILENAME", "purview-bridge.pfx")


class PurviewClient:
    """Security & Compliance PowerShell client via pwsh subprocess."""

    def __init__(
        self,
        tenant_id: str = None,
        app_id: str = None,
        cert_thumbprint: str = None,
        organization: str = None,
    ):
        self.tenant_id = tenant_id or TENANT_ID
        self.app_id = app_id or APP_ID
        self.cert_thumbprint = cert_thumbprint or CERT_THUMBPRINT
        self.organization = organization or ORGANIZATION

        if not all([self.app_id, self.organization]):
            print(
                "ERROR: Missing Purview credentials.\n"
                "\n"
                "Required environment variables:\n"
                "  PURVIEW_TENANT_ID\n"
                "  PURVIEW_APP_ID\n"
                "  PURVIEW_CERT_THUMBPRINT\n"
                "  PURVIEW_ORGANIZATION\n",
                file=sys.stderr,
            )
            sys.exit(1)

    def _build_connect_script(self) -> str:
        """Build the PowerShell Connect-IPPSSession preamble."""
        pfx_path = f"{CERT_DIR}/{CERT_FILENAME}"
        return (
            f"$cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new('{pfx_path}', '', "
            f"[System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::MachineKeySet)\n"
            f"Connect-IPPSSession -Certificate $cert "
            f"-AppId '{self.app_id}' "
            f"-Organization '{self.organization}' "
            f"-ShowBanner:$false\n"
        )

    def run_cmdlet(
        self,
        cmdlet: str,
        params: dict = None,
        raw: bool = False,
        timeout: int = 120,
    ) -> dict:
        """
        Execute a Security & Compliance PowerShell cmdlet.

        Args:
            cmdlet: The cmdlet name (e.g., 'Get-DlpCompliancePolicy')
            params: Dict of parameter names to values
            raw: If True, return raw text output instead of JSON
            timeout: Command timeout in seconds

        Returns:
            dict with 'ok', 'data' (list or str), and optionally 'error'
        """
        script = self._build_connect_script()

        param_str = ""
        if params:
            for key, value in params.items():
                if value is True:
                    param_str += f" -{key}"
                elif value is False:
                    continue
                elif isinstance(value, (list, tuple)):
                    quoted = ",".join(f"'{v}'" for v in value)
                    param_str += f" -{key} @({quoted})"
                else:
                    param_str += f" -{key} '{value}'"

        if raw:
            script += f"{cmdlet}{param_str}\n"
        else:
            script += f"$results = {cmdlet}{param_str}\n"
            script += "$results | ConvertTo-Json -Depth 10 -Compress\n"

        script += "Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue\n"

        try:
            result = subprocess.run(
                ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                if "AADSTS" in stderr:
                    return {"ok": False, "error": f"Authentication failed: {stderr[:200]}"}
                if "not recognized" in stderr.lower():
                    return {"ok": False, "error": f"Cmdlet not available via Connect-IPPSSession: {stderr[:200]}"}
                return {"ok": False, "error": stderr[:500]}

            stdout = result.stdout.strip()

            if raw:
                return {"ok": True, "data": stdout}

            if not stdout:
                return {"ok": True, "data": []}

            try:
                parsed = json.loads(stdout)
                if isinstance(parsed, dict):
                    parsed = [parsed]
                return {"ok": True, "data": parsed}
            except json.JSONDecodeError:
                return {"ok": True, "data": stdout}

        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Command timed out after {timeout} seconds"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def test_connection(self) -> dict:
        """Health check: validate certificate auth and basic SCC access."""
        script = self._build_connect_script()
        script += (
            "$policies = Get-DlpCompliancePolicy | Measure-Object | Select-Object Count\n"
            "$labels = Get-Label | Measure-Object | Select-Object Count\n"
            "@{DlpPolicies=$policies.Count; SensitivityLabels=$labels.Count} | ConvertTo-Json -Compress\n"
            "Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue\n"
        )

        try:
            result = subprocess.run(
                ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return {"ok": False, "error": result.stderr.strip()[:500]}

            stdout = result.stdout.strip()
            try:
                counts = json.loads(stdout)
                return {
                    "ok": True,
                    "dlp_policies": counts.get("DlpPolicies", 0),
                    "sensitivity_labels": counts.get("SensitivityLabels", 0),
                    "auth": "certificate",
                    "endpoint": "compliance.protection.outlook.com",
                    "app_id": self.app_id,
                    "thumbprint": self.cert_thumbprint[:8] + "...",
                }
            except json.JSONDecodeError:
                return {"ok": True, "raw_output": stdout[:200]}

        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Connection timed out after 60 seconds"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "test"
    client = PurviewClient()

    if action == "test":
        result = client.test_connection()
        print(json.dumps(result, indent=2))
    else:
        print(f"Unknown action: {action}")
        print("Usage: python3 purview_client.py test")
        sys.exit(1)
