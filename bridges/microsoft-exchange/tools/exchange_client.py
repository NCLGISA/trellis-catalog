# Copyright 2026 The Tendril Project Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Exchange Online PowerShell Client (Certificate-Based Authentication)

Provides a Python wrapper for Exchange Online PowerShell cmdlets via pwsh.
All cmdlets are executed through Connect-ExchangeOnline with certificate-based
app-only authentication -- no interactive login, no WinRM, runs on Linux.

Environment variables (set in docker-compose.yml):
  EXO_TENANT_ID       - Entra ID tenant ID
  EXO_APP_ID          - App registration client ID
  EXO_CERT_THUMBPRINT - SHA1 thumbprint of the uploaded certificate
  EXO_ORGANIZATION    - Tenant onmicrosoft.com domain

The ExchangeOnlineManagement module v3+ uses REST under the hood (not WinRM),
so all connections are outbound HTTPS to outlook.office365.com.
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

TENANT_ID = os.getenv("EXO_TENANT_ID", "")
APP_ID = os.getenv("EXO_APP_ID", "")
CERT_THUMBPRINT = os.getenv("EXO_CERT_THUMBPRINT", "")
ORGANIZATION = os.getenv("EXO_ORGANIZATION", "")
CERT_DIR = os.getenv("EXO_CERT_DIR", "/opt/bridge/certs")
CERT_FILENAME = os.getenv("EXO_CERT_FILENAME", "exchange-bridge.pfx")


class ExchangeClient:
    """Exchange Online PowerShell client via pwsh subprocess."""

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
                "ERROR: Missing Exchange Online credentials.\n"
                "\n"
                "Required environment variables:\n"
                "  EXO_TENANT_ID\n"
                "  EXO_APP_ID\n"
                "  EXO_CERT_THUMBPRINT\n"
                "  EXO_ORGANIZATION\n",
                file=sys.stderr,
            )
            sys.exit(1)

    def _build_connect_script(self, use_ipps: bool = False) -> str:
        """Build the PowerShell connect preamble."""
        pfx_path = f"{CERT_DIR}/{CERT_FILENAME}"
        connect_cmd = "Connect-IPPSSession" if use_ipps else "Connect-ExchangeOnline"

        return (
            f"$cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new('{pfx_path}', '', "
            f"[System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::MachineKeySet)\n"
            f"{connect_cmd} -Certificate $cert "
            f"-AppId '{self.app_id}' "
            f"-Organization '{self.organization}' "
            f"-ShowBanner:$false\n"
        )

    def run_cmdlet(
        self,
        cmdlet: str,
        params: dict = None,
        use_ipps: bool = False,
        raw: bool = False,
    ) -> dict:
        """
        Execute an Exchange Online PowerShell cmdlet and return parsed results.

        Args:
            cmdlet: The cmdlet name (e.g., 'Get-QuarantineMessage')
            params: Dict of parameter names to values
            use_ipps: If True, use Connect-IPPSSession (Security & Compliance)
            raw: If True, return raw text output instead of JSON

        Returns:
            dict with 'ok', 'data' (list or str), and optionally 'error'
        """
        script = self._build_connect_script(use_ipps=use_ipps)

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
                timeout=120,
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                if "AADSTS" in stderr:
                    return {"ok": False, "error": f"Authentication failed: {stderr[:200]}"}
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
            return {"ok": False, "error": "Command timed out after 120 seconds"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def test_connection(self) -> dict:
        """Health check: validate certificate auth and basic EXO access."""
        script = self._build_connect_script()
        script += (
            "$org = Get-OrganizationConfig | Select-Object Name, DisplayName, IsDehydrated\n"
            "$org | ConvertTo-Json -Compress\n"
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
                org = json.loads(stdout)
                return {
                    "ok": True,
                    "organization": org.get("Name") or org.get("DisplayName"),
                    "auth": "certificate",
                    "app_id": self.app_id,
                    "thumbprint": self.cert_thumbprint[:8] + "...",
                }
            except json.JSONDecodeError:
                return {"ok": True, "raw_output": stdout[:200]}

        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Connection timed out after 60 seconds"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── CLI Entrypoint ─────────────────────────────────────────────────────

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "test"
    client = ExchangeClient()

    if action == "test":
        result = client.test_connection()
        print(json.dumps(result, indent=2))
    else:
        print(f"Unknown action: {action}")
        print("Usage: python3 exchange_client.py test")
        sys.exit(1)
