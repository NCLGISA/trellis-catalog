"""
Verizon MyBusiness Bridge -- ForgeRock REST Authentication

Pure httpx client for the ForgeRock callback-based authentication tree.
Drives the multi-step login flow without requiring a browser:

  Step 1: VBGUserValidateService -- NameCallback (username)
  Step 2: VBGUserValidateService -- DeviceProfileCallback (device fingerprint)
  Step 3: VBGUserValidateService -> redirect -> VBGUserLoginService
          NameCallback (username) + PasswordCallback (password)
  Step 4: VBGUserLoginService -- DeviceProfileCallback (device fingerprint again)
  Step 5: If MFA requested -- submit SMS OTP code
  Final:  Receive tokenId + session cookies

The operator only needs to provide the SMS code; everything else is automated.
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

AUTH_BASE = "https://mblogin.verizonwireless.com"
VALIDATE_URL = (
    f"{AUTH_BASE}/vzauth/json/realms/root/realms/vzwmb/authenticate"
    "?authIndexType=service&client_id=pwll"
    "&authIndexValue=VBGUserValidateService"
    "&goto=http://mb.verizonwireless.com/mbt/secure/index?appName=esm"
)
LOGIN_URL = (
    f"{AUTH_BASE}/vzauth/json/realms/root/realms/vzwmb/authenticate"
    "?authIndexType=service"
    "&authIndexValue=VBGUserLoginService"
    "&goto=http://mb.verizonwireless.com/mbt/secure/index?appName=esm"
)
SSO_URL = "https://sso.verizonenterprise.com/account/business/addsession"
PORTAL_URL = "https://mb.verizonwireless.com/mbt/secure/index?appName=esm"
LOGIN_PAGE_URL = f"{AUTH_BASE}/account/business/login/unifiedlogin"

DEVICE_FINGERPRINT = json.dumps({
    "identifier": {
        "screen": {"screenWidth": 1280, "screenHeight": 900, "screenColourDepth": 30},
        "timezone": {"timezone": 300},
        "plugins": {
            "installedPlugins": (
                "internal-pdf-viewer;internal-pdf-viewer;internal-pdf-viewer;"
                "internal-pdf-viewer;internal-pdf-viewer;"
            )
        },
        "fonts": {
            "installedFonts": (
                "cursive;monospace;serif;sans-serif;fantasy;default;"
                "Arial;Arial Black;Arial Narrow;Arial Rounded MT Bold;"
                "Comic Sans MS;Courier;Courier New;Georgia;Impact;"
                "Papyrus;Tahoma;Times;Times New Roman;Trebuchet MS;Verdana;"
            )
        },
        "userAgent": {
            "browserInfo": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        },
        "appName": "Netscape",
        "appCodeName": "Mozilla",
        "appVersion": (
            "5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "platform": "MacIntel",
        "product": "Gecko",
        "productSub": "20030107",
        "vendor": "Google Inc.",
        "language": "en-US",
        "version": "1.0.0",
    }
})

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/json",
    "Origin": AUTH_BASE,
    "Referer": f"{AUTH_BASE}/account/business/login/unifiedlogin",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "X-Requested-With": "XMLHttpRequest",
}


class ForgeRockAuthError(Exception):
    """Raised when the ForgeRock auth flow encounters an error."""
    pass


class MFARequiredError(Exception):
    """Raised when the flow pauses for SMS MFA code entry."""

    def __init__(self, message: str, auth_state: dict):
        super().__init__(message)
        self.auth_state = auth_state


@dataclass
class AuthState:
    """Tracks state across the multi-step auth flow."""
    auth_id: str = ""
    cookies: dict = field(default_factory=dict)
    token_id: str = ""
    mfa_phone: str = ""
    current_step: str = ""
    service: str = ""

    def to_dict(self) -> dict:
        return {
            "auth_id": self.auth_id,
            "cookies": self.cookies,
            "token_id": self.token_id,
            "mfa_phone": self.mfa_phone,
            "current_step": self.current_step,
            "service": self.service,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AuthState":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class ForgeRockAuth:
    """Drives the ForgeRock callback authentication tree via REST."""

    def __init__(self):
        self._client = httpx.Client(
            headers=BROWSER_HEADERS,
            follow_redirects=False,
            timeout=30.0,
        )

    def close(self):
        if not self._client.is_closed:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _acquire_akamai_cookies(self):
        """Load the login page to pick up Akamai bot-management cookies."""
        resp = self._client.get(
            LOGIN_PAGE_URL,
            headers={**BROWSER_HEADERS, "Accept": "text/html,application/xhtml+xml,*/*"},
            follow_redirects=True,
        )
        return resp

    def _post_auth(self, url: str, body: dict) -> httpx.Response:
        """POST to a ForgeRock auth endpoint."""
        resp = self._client.post(url, json=body)
        return resp

    def _find_callback(self, callbacks: list, cb_type: str) -> dict | None:
        for cb in callbacks:
            if cb.get("type") == cb_type:
                return cb
        return None

    def _build_callback_response(self, auth_id: str, callbacks: list) -> dict:
        return {"authId": auth_id, "callbacks": callbacks}

    def authenticate(self, username: str, password: str, mfa_code: str | None = None) -> dict:
        """
        Run the full ForgeRock auth flow.

        Returns a dict with session cookies on success.
        Raises MFARequiredError if an SMS code is needed and mfa_code is None.
        """
        # Load the login page to get Akamai cookies
        self._acquire_akamai_cookies()

        # Phase 1: VBGUserValidateService
        # Step 1a: Initial request to get the authId
        resp = self._client.post(VALIDATE_URL, json={})
        if resp.status_code != 200:
            raise ForgeRockAuthError(f"Initial auth request failed: {resp.status_code}")

        data = resp.json()
        auth_id = data.get("authId", "")
        callbacks = data.get("callbacks", [])

        # Step 1b: Submit username via NameCallback
        name_cb = self._find_callback(callbacks, "NameCallback")
        if not name_cb:
            raise ForgeRockAuthError("Expected NameCallback in step 1, not found")

        for inp in name_cb.get("input", []):
            if inp["name"] == "IDToken1":
                inp["value"] = username

        body = self._build_callback_response(auth_id, callbacks)
        resp = self._post_auth(VALIDATE_URL, body)
        if resp.status_code != 200:
            raise ForgeRockAuthError(f"Username submission failed: {resp.status_code}")

        data = resp.json()
        auth_id = data.get("authId", "")
        callbacks = data.get("callbacks", [])

        # Step 2: DeviceProfileCallback -- send device fingerprint
        device_cb = self._find_callback(callbacks, "DeviceProfileCallback")
        if not device_cb:
            raise ForgeRockAuthError("Expected DeviceProfileCallback in step 2, not found")

        for inp in device_cb.get("input", []):
            if inp["name"] == "IDToken1":
                inp["value"] = DEVICE_FINGERPRINT

        body = self._build_callback_response(auth_id, callbacks)
        resp = self._post_auth(VALIDATE_URL, body)
        if resp.status_code != 200:
            raise ForgeRockAuthError(f"Device profile submission failed: {resp.status_code}")

        data = resp.json()

        # Check for SEGP_NLBE or similar redirect to VBGUserLoginService
        # The response may contain a TextOutputCallback with "SEGP_NLBE" indicating
        # a redirect to the login service, OR we may get a successUrl/tokenId.
        text_cb = self._find_callback(data.get("callbacks", []), "TextOutputCallback")
        if text_cb:
            msg = ""
            for out in text_cb.get("output", []):
                if out["name"] == "message":
                    msg = out["value"]
            if msg:
                pass  # Expected: SEGP_NLBE means redirect to LoginService

        # Phase 2: VBGUserLoginService
        # Step 3: Submit username + password
        resp = self._client.post(LOGIN_URL, json={})
        if resp.status_code != 200:
            raise ForgeRockAuthError(f"Login service init failed: {resp.status_code}")

        data = resp.json()
        auth_id = data.get("authId", "")
        callbacks = data.get("callbacks", [])

        name_cb = self._find_callback(callbacks, "NameCallback")
        pass_cb = self._find_callback(callbacks, "PasswordCallback")

        if not name_cb or not pass_cb:
            raise ForgeRockAuthError(
                "Expected NameCallback + PasswordCallback in login step, "
                f"got: {[c['type'] for c in callbacks]}"
            )

        for inp in name_cb.get("input", []):
            if inp["name"] == "IDToken1":
                inp["value"] = username
        for inp in pass_cb.get("input", []):
            if inp["name"] == "IDToken2":
                inp["value"] = password

        body = self._build_callback_response(auth_id, callbacks)
        body["path"] = "vzpllgn"
        resp = self._post_auth(LOGIN_URL, body)
        if resp.status_code != 200:
            raise ForgeRockAuthError(f"Credential submission failed: {resp.status_code}")

        data = resp.json()

        # Check for errors
        if "code" in data and data.get("code") != 200:
            raise ForgeRockAuthError(f"Auth error: {data.get('message', data)}")

        # If tokenId present, auth completed without MFA
        if "tokenId" in data:
            return self._finalize_session(data)

        auth_id = data.get("authId", "")
        callbacks = data.get("callbacks", [])

        # Step 4: DeviceProfileCallback again
        device_cb = self._find_callback(callbacks, "DeviceProfileCallback")
        if device_cb:
            for inp in device_cb.get("input", []):
                if inp["name"] == "IDToken1":
                    inp["value"] = DEVICE_FINGERPRINT

            body = self._build_callback_response(auth_id, callbacks)
            resp = self._post_auth(LOGIN_URL, body)
            if resp.status_code != 200:
                raise ForgeRockAuthError(
                    f"Login device profile submission failed: {resp.status_code}"
                )

            data = resp.json()

            if "tokenId" in data:
                return self._finalize_session(data)

            auth_id = data.get("authId", "")
            callbacks = data.get("callbacks", [])

        # Step 5: MFA callback (SMS OTP)
        # At this point we expect some form of OTP callback
        if mfa_code:
            return self._submit_mfa(auth_id, callbacks, mfa_code)
        else:
            mfa_phone = self._extract_mfa_phone(callbacks)
            state = AuthState(
                auth_id=auth_id,
                cookies=dict(self._client.cookies),
                mfa_phone=mfa_phone,
                current_step="mfa_pending",
                service="VBGUserLoginService",
            )
            raise MFARequiredError(
                f"SMS code sent to {mfa_phone or '(unknown)'}. "
                "Provide the code to complete authentication.",
                auth_state=state.to_dict(),
            )

    def complete_mfa(self, auth_state: dict, mfa_code: str) -> dict:
        """
        Complete authentication by submitting the MFA code.

        auth_state is the dict from a previous MFARequiredError.
        """
        state = AuthState.from_dict(auth_state)

        # Restore cookies from state
        for name, value in state.cookies.items():
            self._client.cookies.set(name, value)

        # Re-initiate the login service to get a fresh callback with the MFA prompt
        resp = self._client.post(LOGIN_URL, json={})
        if resp.status_code != 200:
            raise ForgeRockAuthError(f"MFA re-init failed: {resp.status_code}")

        data = resp.json()
        auth_id = data.get("authId", state.auth_id)
        callbacks = data.get("callbacks", [])

        return self._submit_mfa(auth_id, callbacks, mfa_code)

    def _submit_mfa(self, auth_id: str, callbacks: list, code: str) -> dict:
        """Submit the MFA OTP code through whatever callback is pending."""
        # Look for any callback that takes a code input
        for cb in callbacks:
            for inp in cb.get("input", []):
                if "IDToken" in inp.get("name", ""):
                    inp["value"] = code
                    break

        body = self._build_callback_response(auth_id, callbacks)
        resp = self._post_auth(LOGIN_URL, body)
        if resp.status_code != 200:
            raise ForgeRockAuthError(f"MFA submission failed: {resp.status_code}")

        data = resp.json()

        if "tokenId" in data:
            return self._finalize_session(data)

        # May need more steps (device profile again after MFA)
        auth_id = data.get("authId", "")
        callbacks = data.get("callbacks", [])

        device_cb = self._find_callback(callbacks, "DeviceProfileCallback")
        if device_cb:
            for inp in device_cb.get("input", []):
                if inp["name"] == "IDToken1":
                    inp["value"] = DEVICE_FINGERPRINT

            body = self._build_callback_response(auth_id, callbacks)
            resp = self._post_auth(LOGIN_URL, body)
            data = resp.json()

            if "tokenId" in data:
                return self._finalize_session(data)

        if "code" in data and data.get("code") != 200:
            raise ForgeRockAuthError(f"MFA auth error: {data.get('message', data)}")

        raise ForgeRockAuthError(
            f"Unexpected response after MFA: {list(data.keys())}"
        )

    def _extract_mfa_phone(self, callbacks: list) -> str:
        """Try to extract the masked phone number from MFA callbacks."""
        for cb in callbacks:
            for out in cb.get("output", []):
                val = str(out.get("value", ""))
                if "XXX" in val or "xxx" in val:
                    return val
                if "phone" in val.lower() or "sms" in val.lower():
                    return val
        return ""

    def _finalize_session(self, auth_data: dict) -> dict:
        """
        After receiving tokenId, establish the full portal session by
        visiting the SSO and portal URLs to collect all session cookies.
        """
        token_id = auth_data["tokenId"]
        realm = auth_data.get("realm", "/vzwmb")

        # Follow the SSO session establishment
        try:
            resp = self._client.get(
                PORTAL_URL,
                headers={
                    **BROWSER_HEADERS,
                    "Accept": "text/html,application/xhtml+xml,*/*",
                },
                follow_redirects=True,
            )
        except httpx.HTTPError:
            pass  # Some redirects may fail but cookies are still set

        cookies = []
        for cookie in self._client.cookies.jar:
            cookies.append({
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
            })

        return {
            "success": True,
            "token_id": token_id,
            "realm": realm,
            "cookies": cookies,
            "cookie_count": len(cookies),
        }
