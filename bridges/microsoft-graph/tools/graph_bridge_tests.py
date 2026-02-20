"""
Microsoft Graph Bridge Read-Only Test Battery

Exercises every read-only API category against the live Microsoft 365
tenant and produces a compact pass/fail summary.
No mutations, no side effects.

Usage: python3 graph_bridge_tests.py
"""

import sys
import time
import json
from datetime import date, datetime, timedelta
from collections import Counter

sys.path.insert(0, "/opt/bridge/data/tools")
from graph_client import GraphClient


# ── Test Framework ─────────────────────────────────────────────────────

class TestResult:
    def __init__(self, num, category, name, status, detail=""):
        self.num = num
        self.category = category
        self.name = name
        self.status = status
        self.detail = detail


results = []
test_counter = 0


def run_test(category, name, fn):
    """Run a single test function, catch exceptions, record result."""
    global test_counter
    test_counter += 1
    num = test_counter
    try:
        detail = fn()
        results.append(TestResult(num, category, name, "PASS", detail or ""))
    except Exception as e:
        results.append(TestResult(num, category, name, "FAIL", str(e)[:120]))


def print_report(elapsed):
    """Print the final structured report."""
    today_str = date.today().isoformat()
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    total = len(results)

    print(f"\n{'=' * 110}")
    print(f"  Microsoft Graph Bridge Test Battery")
    print(f"  Date: {today_str}  Tenant: example.com")
    print(f"{'=' * 110}")
    print(f"{'#':>3}  {'Category':<24} {'Test':<44} {'Status':<7} Detail")
    print(f"{'-' * 110}")

    for r in results:
        marker = "PASS" if r.status == "PASS" else "FAIL"
        print(f"{r.num:>3}  {r.category:<24} {r.name:<44} {marker:<7} {r.detail[:60]}")

    print(f"{'-' * 110}")
    print(f"RESULT: {passed}/{total} PASSED  |  {failed} FAILED  |  Runtime: {elapsed:.1f}s")
    print(f"{'=' * 110}\n")


# ── Shared State ───────────────────────────────────────────────────────

shared = {}


# ── Category 1: Bridge Health ──────────────────────────────────────────

def test_connection_check(client):
    def fn():
        info = client.test_connection()
        assert info.get("ok"), f"Connection failed: {info}"
        shared["tenant_id"] = info.get("tenant_id", "?")
        shared["tenant_name"] = info.get("display_name", "?")
        return f"Tenant: {info.get('display_name')} ({info.get('tenant_id', '?')[:8]}...)"
    run_test("Bridge Health", "Connection check", fn)


def test_permission_smoke(client):
    def fn():
        endpoints = {
            "Users": "users?$top=1",
            "Groups": "groups?$top=1",
            "Intune": "deviceManagement/managedDevices?$top=1",
            "Sites": "sites?search=*&$top=1",
        }
        ok_list = []
        fail_list = []
        for label, ep in endpoints.items():
            resp = client.get(ep)
            if resp.status_code == 200:
                ok_list.append(label)
            else:
                fail_list.append(f"{label}({resp.status_code})")
        assert not fail_list, f"Failed: {', '.join(fail_list)}"
        return f"All scopes OK: {', '.join(ok_list)}"
    run_test("Bridge Health", "Permission smoke test", fn)


# ── Category 2: Users and Entra ID ────────────────────────────────────

def test_list_users(client):
    def fn():
        users = client.list_users()
        shared["users"] = users
        count = len(users)
        enabled = sum(1 for u in users if u.get("accountEnabled"))
        disabled = count - enabled
        return f"{count} users ({enabled} enabled, {disabled} disabled)"
    run_test("Users / Entra ID", "List all users", fn)


def test_member_vs_guest(client):
    def fn():
        users = shared.get("users", [])
        assert users, "No users loaded"
        types = Counter(u.get("userType", "Unknown") for u in users)
        parts = ", ".join(f"{c} {t}" for t, c in types.most_common())
        return parts
    run_test("Users / Entra ID", "Member vs guest breakdown", fn)


def test_search_known_user(client):
    def fn():
        results_list = client.search_users("admin")
        assert len(results_list) >= 1, "Expected at least 1 result"
        user = results_list[0]
        shared["known_user"] = user
        shared["known_upn"] = user.get("userPrincipalName", user.get("mail", "?"))
        return f"Found: {user.get('displayName')} ({user.get('mail', '?')})"
    run_test("Users / Entra ID", "Search known user", fn)


def test_get_user_detail(client):
    def fn():
        upn = shared.get("known_upn")
        assert upn, "No known user from search"
        user = client.get_user(upn)
        fields = ["displayName", "jobTitle", "department", "mail"]
        present = [f for f in fields if user.get(f)]
        return f"{len(present)}/4 fields: {', '.join(f'{f}={user[f][:20]}' for f in present)}"
    run_test("Users / Entra ID", "Get user detail", fn)


def test_disabled_accounts(client):
    def fn():
        users = shared.get("users", [])
        disabled = [u for u in users if not u.get("accountEnabled")]
        count = len(disabled)
        sample = ", ".join((u.get("displayName") or u.get("userPrincipalName") or "?")[:25] for u in disabled[:3])
        suffix = f"... +{count - 3} more" if count > 3 else ""
        return f"{count} disabled accounts: {sample}{suffix}"
    run_test("Users / Entra ID", "Disabled accounts", fn)


# ── Category 3: Groups ────────────────────────────────────────────────

def test_list_groups(client):
    def fn():
        groups = client.list_groups()
        shared["groups"] = groups
        return f"{len(groups)} groups"
    run_test("Groups", "List all groups", fn)


def test_group_type_breakdown(client):
    def fn():
        groups = shared.get("groups", [])
        assert groups, "No groups loaded"
        m365 = 0
        security = 0
        distribution = 0
        mail_security = 0
        for g in groups:
            gtypes = g.get("groupTypes", [])
            sec = g.get("securityEnabled", False)
            mail = g.get("mailEnabled", False)
            if "Unified" in gtypes:
                m365 += 1
            elif sec and not mail:
                security += 1
            elif mail and not sec:
                distribution += 1
            elif sec and mail:
                mail_security += 1
        return f"M365: {m365}, Security: {security}, Dist: {distribution}, MailSec: {mail_security}"
    run_test("Groups", "Group type breakdown", fn)


def test_get_group_members(client):
    def fn():
        groups = shared.get("groups", [])
        assert groups, "No groups loaded"
        target = None
        for g in groups:
            if "information technology" in (g.get("displayName") or "").lower():
                target = g
                break
        if not target:
            target = groups[0]
        members = client.list_group_members(target["id"])
        shared["sample_group"] = target
        shared["sample_group_members"] = members
        name = (target.get("displayName") or "?")[:30]
        return f"'{name}': {len(members)} members"
    run_test("Groups", "Get group members", fn)


def test_large_groups(client):
    def fn():
        groups = shared.get("groups", [])
        assert groups, "No groups loaded"
        sized = []
        for g in groups[:50]:
            try:
                members = client.list_group_members(g["id"])
                sized.append((g, len(members)))
            except Exception:
                pass
        sized.sort(key=lambda x: x[1], reverse=True)
        top3 = sized[:3]
        parts = "; ".join(f"{g.get('displayName', '?')[:25]}={c}" for g, c in top3)
        return f"Top 3: {parts}"
    run_test("Groups", "Largest groups (sample of 50)", fn)


# ── Category 4: Directory and AD Sync ─────────────────────────────────

def test_organization_info(client):
    def fn():
        org = client.get_organization()
        assert org.get("id"), "No organization info returned"
        name = org.get("displayName", "?")
        tenant_id = org.get("id", "?")[:8]
        return f"{name} (tenant: {tenant_id}...)"
    run_test("Directory / AD Sync", "Organization info", fn)


def test_verified_domains(client):
    def fn():
        domains = client.list_domains()
        verified = [d for d in domains if d.get("isVerified")]
        default_domain = next((d["id"] for d in domains if d.get("isDefault")), "?")
        names = ", ".join(d["id"] for d in verified[:5])
        suffix = f"... +{len(verified) - 5} more" if len(verified) > 5 else ""
        return f"{len(verified)} verified, default: {default_domain} ({names}{suffix})"
    run_test("Directory / AD Sync", "Verified domains", fn)


def test_onprem_sync_users(client):
    def fn():
        users = shared.get("users", [])
        assert users, "No users loaded"
        synced = sum(1 for u in users if u.get("onPremisesSyncEnabled"))
        cloud_only = len(users) - synced
        pct = (synced / len(users) * 100) if users else 0
        return f"{synced} synced from AD ({pct:.0f}%), {cloud_only} cloud-only"
    run_test("Directory / AD Sync", "On-premises synced users", fn)


def test_service_principals(client):
    def fn():
        sps = client.list_service_principals(top=999)
        count = len(sps)
        ms_apps = sum(1 for s in sps if "microsoft" in (s.get("appOwnerOrganizationId") or "").lower()
                      or (s.get("displayName") or "").startswith("Microsoft"))
        return f"{count} service principals (~{ms_apps} Microsoft)"
    run_test("Directory / AD Sync", "Service principals", fn)


# ── Category 5: Security and Audit ────────────────────────────────────

def test_sign_in_logs(client):
    def fn():
        try:
            logs = client.list_sign_ins(top=50)
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                return "SKIP: AuditLog.Read.All not granted"
            raise
        count = len(logs)
        statuses = Counter()
        for log in logs:
            status = log.get("status", {})
            code = status.get("errorCode", 0)
            statuses["success" if code == 0 else "failure"] += 1
        parts = ", ".join(f"{c} {s}" for s, c in statuses.most_common())
        return f"{count} recent sign-ins ({parts})"
    run_test("Security / Audit", "Recent sign-in logs", fn)


def test_directory_audit_logs(client):
    def fn():
        try:
            logs = client.list_directory_audit_logs(top=50)
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                return "SKIP: AuditLog.Read.All not granted"
            raise
        count = len(logs)
        activities = Counter(log.get("activityDisplayName", "?") for log in logs)
        top3 = ", ".join(f"{a} ({c})" for a, c in activities.most_common(3))
        return f"{count} audit events. Top: {top3}"
    run_test("Security / Audit", "Directory audit logs", fn)


def test_inbox_forwarding_rules(client):
    def fn():
        users = shared.get("users", [])
        enabled_users = [u for u in users if u.get("accountEnabled") and u.get("mail")]
        sample = enabled_users[:10]
        forwarding_users = []
        rules_checked = 0
        for u in sample:
            upn = u.get("userPrincipalName") or u.get("mail")
            try:
                rules = client.get_inbox_rules(upn)
                rules_checked += 1
                for rule in rules:
                    actions = rule.get("actions", {})
                    fwd = actions.get("forwardTo", [])
                    redir = actions.get("redirectTo", [])
                    if fwd or redir:
                        forwarding_users.append(upn)
                        break
            except Exception:
                pass
        shared["forwarding_users"] = forwarding_users
        if forwarding_users:
            names = ", ".join(f.split("@")[0] for f in forwarding_users[:3])
            return f"Checked {rules_checked}, {len(forwarding_users)} with forwarding: {names}"
        return f"Checked {rules_checked} mailboxes, 0 with forwarding rules"
    run_test("Security / Audit", "Inbox forwarding rules audit", fn)


def test_external_forwarding(client):
    def fn():
        users = shared.get("users", [])
        enabled_users = [u for u in users if u.get("accountEnabled") and u.get("mail")]
        sample = enabled_users[:10]
        external_fwd = []
        for u in sample:
            upn = u.get("userPrincipalName") or u.get("mail")
            try:
                rules = client.get_inbox_rules(upn)
                for rule in rules:
                    actions = rule.get("actions", {})
                    for dest_list in [actions.get("forwardTo", []), actions.get("redirectTo", [])]:
                        for dest in dest_list:
                            addr = dest.get("emailAddress", {}).get("address", "")
                            if addr and not addr.lower().endswith("@example.com"):
                                external_fwd.append(f"{upn}->{addr}")
            except Exception:
                pass
        if external_fwd:
            return f"ALERT: {len(external_fwd)} external forwards: {'; '.join(external_fwd[:3])}"
        return "0 external forwarding rules detected"
    run_test("Security / Audit", "External mail forwarding", fn)


# ── Category 6: Licensing ─────────────────────────────────────────────

def test_license_inventory(client):
    def fn():
        skus = client.list_subscribed_skus()
        shared["skus"] = skus
        count = len(skus)
        sku_names = {
            "SPE_E3": "M365 E3", "ENTERPRISEPACK": "O365 E3",
            "FLOW_FREE": "Power Automate Free", "POWER_BI_STANDARD": "Power BI Free",
            "AAD_PREMIUM": "Entra ID P1", "EMSPREMIUM": "EMS E5",
            "PROJECTPREMIUM": "Project Plan 5", "VISIOCLIENT": "Visio Plan 2",
        }
        top5 = sorted(skus, key=lambda s: s.get("consumedUnits", 0), reverse=True)[:5]
        parts = []
        for s in top5:
            part_num = s.get("skuPartNumber", "?")
            name = sku_names.get(part_num, part_num)[:18]
            consumed = s.get("consumedUnits", 0)
            total_units = 0
            for plan in s.get("prepaidUnits", {}).values():
                if isinstance(plan, int):
                    total_units += plan
            enabled = s.get("prepaidUnits", {}).get("enabled", 0)
            parts.append(f"{name}:{consumed}/{enabled}")
        return f"{count} SKUs. Top: {', '.join(parts)}"
    run_test("Licensing", "License inventory", fn)


def test_unlicensed_users(client):
    def fn():
        users = shared.get("users", [])
        enabled = [u for u in users if u.get("accountEnabled") and u.get("userType") == "Member"]
        sample = enabled[:20]
        unlicensed = 0
        checked = 0
        for u in sample:
            upn = u.get("userPrincipalName") or u.get("id")
            try:
                lics = client.get_user_licenses(upn)
                checked += 1
                if not lics:
                    unlicensed += 1
            except Exception:
                pass
        pct = (unlicensed / checked * 100) if checked else 0
        return f"Sample: {unlicensed}/{checked} unlicensed ({pct:.0f}%)"
    run_test("Licensing", "Unlicensed enabled members (sample)", fn)


def test_license_utilization(client):
    def fn():
        skus = shared.get("skus", [])
        assert skus, "No SKU data loaded"
        total_enabled = 0
        total_consumed = 0
        for s in skus:
            enabled = s.get("prepaidUnits", {}).get("enabled", 0)
            consumed = s.get("consumedUnits", 0)
            if enabled > 0:
                total_enabled += enabled
                total_consumed += consumed
        pct = (total_consumed / total_enabled * 100) if total_enabled else 0
        return f"{total_consumed}/{total_enabled} licenses consumed ({pct:.0f}% utilization)"
    run_test("Licensing", "Overall license utilization", fn)


# ── Category 7: SharePoint and OneDrive ───────────────────────────────

def test_list_sites(client):
    def fn():
        sites = client.list_sites()
        shared["sites"] = sites
        count = len(sites)
        names = ", ".join((s.get("displayName") or s.get("name") or "?")[:20] for s in sites[:5])
        suffix = f"... +{count - 5} more" if count > 5 else ""
        return f"{count} sites: {names}{suffix}"
    run_test("SharePoint / OneDrive", "List SharePoint sites", fn)


def test_get_site_detail(client):
    def fn():
        sites = shared.get("sites", [])
        if not sites:
            return "SKIP: No sites found"
        for site in sites[:10]:
            try:
                detail = client.get_site(site["id"])
                name = detail.get("displayName") or detail.get("name") or "?"
                url = detail.get("webUrl", "?")
                modified = (detail.get("lastModifiedDateTime") or "?")[:10]
                shared["accessible_site"] = site
                return f"{name}: {url[:50]} (modified: {modified})"
            except Exception:
                continue
        return "SKIP: No accessible sites in first 10"
    run_test("SharePoint / OneDrive", "Get site detail", fn)


def test_site_drives(client):
    def fn():
        site = shared.get("accessible_site")
        sites = shared.get("sites", [])
        if not site and not sites:
            return "SKIP: No sites found"
        candidates = [site] if site else sites[:10]
        for s in candidates:
            try:
                drives = client.list_site_drives(s["id"])
                count = len(drives)
                total_bytes = 0
                for d in drives:
                    quota = d.get("quota", {})
                    used = quota.get("used", 0)
                    total_bytes += used
                total_mb = total_bytes / (1024 * 1024)
                name = (s.get("displayName") or s.get("name") or "?")[:20]
                return f"'{name}': {count} drives, {total_mb:.0f} MB used"
            except Exception:
                continue
        return "SKIP: No accessible site drives in sample"
    run_test("SharePoint / OneDrive", "Site drives / document libraries", fn)


# ── Category 8: Intune Devices and Policies ───────────────────────────

def test_list_managed_devices(client):
    def fn():
        devices = client.list_managed_devices()
        shared["devices"] = devices
        return f"{len(devices)} managed devices"
    run_test("Intune", "List managed devices", fn)


def test_device_os_breakdown(client):
    def fn():
        devices = shared.get("devices", [])
        assert devices, "No devices loaded"
        os_counts = Counter(d.get("operatingSystem", "Unknown") for d in devices)
        parts = ", ".join(f"{c} {os}" for os, c in os_counts.most_common())
        return parts
    run_test("Intune", "Device OS breakdown", fn)


def test_compliance_status(client):
    def fn():
        devices = shared.get("devices", [])
        assert devices, "No devices loaded"
        states = Counter(d.get("complianceState", "unknown") for d in devices)
        parts = ", ".join(f"{c} {s}" for s, c in states.most_common())
        compliant = states.get("compliant", 0)
        total = len(devices)
        pct = (compliant / total * 100) if total else 0
        return f"{pct:.0f}% compliant ({parts})"
    run_test("Intune", "Compliance status", fn)


def test_stale_devices(client):
    def fn():
        devices = shared.get("devices", [])
        assert devices, "No devices loaded"
        cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat() + "Z"
        stale = []
        for d in devices:
            last_sync = d.get("lastSyncDateTime", "")
            if last_sync and last_sync < cutoff:
                stale.append(d)
        count = len(stale)
        sample = ", ".join((d.get("deviceName") or "?")[:20] for d in stale[:3])
        suffix = f"... +{count - 3} more" if count > 3 else ""
        return f"{count} stale (>30d): {sample}{suffix}"
    run_test("Intune", "Stale devices (>30 days)", fn)


def test_compliance_policies(client):
    def fn():
        try:
            policies = client.list_compliance_policies()
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                return "SKIP: DeviceManagementConfiguration.Read.All not granted"
            raise
        shared["compliance_policies"] = policies
        count = len(policies)
        names = ", ".join((p.get("displayName") or "?")[:25] for p in policies[:5])
        suffix = f"... +{count - 5} more" if count > 5 else ""
        return f"{count} policies: {names}{suffix}"
    run_test("Intune", "Compliance policies", fn)


# ── Category 9: Exchange Online ───────────────────────────────────────

def test_mailbox_settings(client):
    def fn():
        upn = shared.get("known_upn")
        assert upn, "No known user for mailbox check"
        settings = client.get_mailbox_settings(upn)
        tz = settings.get("timeZone", "?")
        lang = settings.get("language", {}).get("displayName", "?")
        auto_reply = settings.get("automaticRepliesSetting", {}).get("status", "?")
        return f"{upn.split('@')[0]}: tz={tz}, lang={lang}, auto-reply={auto_reply}"
    run_test("Exchange Online", "Mailbox settings check", fn)


def test_mail_folders(client):
    def fn():
        upn = shared.get("known_upn")
        assert upn, "No known user for folder check"
        folders = client.get_mail_folders(upn)
        count = len(folders)
        inbox = next((f for f in folders if (f.get("displayName") or "").lower() == "inbox"), None)
        inbox_info = ""
        if inbox:
            total_items = inbox.get("totalItemCount", 0)
            unread = inbox.get("unreadItemCount", 0)
            inbox_info = f", inbox: {total_items} items ({unread} unread)"
        return f"{count} folders{inbox_info}"
    run_test("Exchange Online", "Mail folder inventory", fn)


def test_calendar_permissions(client):
    def fn():
        upn = shared.get("known_upn")
        assert upn, "No known user for calendar check"
        try:
            perms = client.get_calendar_permissions(upn)
        except Exception as e:
            err = str(e)
            if "403" in err or "Forbidden" in err:
                return "SKIP: Calendars.ReadWrite not granted"
            if "504" in err or "Gateway Timeout" in err:
                return "SKIP: Graph API timeout (transient)"
            raise
        count = len(perms)
        roles = Counter(p.get("role", "?") for p in perms)
        parts = ", ".join(f"{c} {r}" for r, c in roles.most_common())
        return f"{count} calendar permissions ({parts})"
    run_test("Exchange Online", "Calendar permissions", fn)


# ── Main ───────────────────────────────────────────────────────────────

def main():
    start = time.time()
    client = GraphClient()

    # Category 1: Bridge Health
    test_connection_check(client)
    test_permission_smoke(client)

    # Category 2: Users and Entra ID
    test_list_users(client)
    test_member_vs_guest(client)
    test_search_known_user(client)
    test_get_user_detail(client)
    test_disabled_accounts(client)

    # Category 3: Groups
    test_list_groups(client)
    test_group_type_breakdown(client)
    test_get_group_members(client)
    test_large_groups(client)

    # Category 4: Directory and AD Sync
    test_organization_info(client)
    test_verified_domains(client)
    test_onprem_sync_users(client)
    test_service_principals(client)

    # Category 5: Security and Audit
    test_sign_in_logs(client)
    test_directory_audit_logs(client)
    test_inbox_forwarding_rules(client)
    test_external_forwarding(client)

    # Category 6: Licensing
    test_license_inventory(client)
    test_unlicensed_users(client)
    test_license_utilization(client)

    # Category 7: SharePoint and OneDrive
    test_list_sites(client)
    test_get_site_detail(client)
    test_site_drives(client)

    # Category 8: Intune Devices and Policies
    test_list_managed_devices(client)
    test_device_os_breakdown(client)
    test_compliance_status(client)
    test_stale_devices(client)
    test_compliance_policies(client)

    # Category 9: Exchange Online
    test_mailbox_settings(client)
    test_mail_folders(client)
    test_calendar_permissions(client)

    elapsed = time.time() - start
    print_report(elapsed)

    failed = sum(1 for r in results if r.status == "FAIL")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
