"""
Microsoft 365 Security Posture Tool

Query Defender alerts/incidents, Secure Score, Identity Protection
(risky users, risk events), and Conditional Access policies.

Usage:
    python3 security_check.py dashboard              # Security overview dashboard
    python3 security_check.py alerts [--severity high]  # Defender alerts
    python3 security_check.py incidents               # Defender incidents
    python3 security_check.py score                   # Microsoft Secure Score
    python3 security_check.py risky-users             # Risky users (Identity Protection)
    python3 security_check.py risk-detections         # Risk detection events
    python3 security_check.py ca-policies             # Conditional Access policies
    python3 security_check.py named-locations          # CA named locations
    python3 security_check.py sign-ins [user@...]      # Recent sign-in logs
"""

import sys
import json
from datetime import date, datetime
from collections import Counter

sys.path.insert(0, "/opt/bridge/data/tools")
from graph_client import GraphClient


def dashboard(client: GraphClient):
    """Security overview dashboard."""
    print(f"Microsoft 365 Security Dashboard - {date.today().isoformat()}")
    print("=" * 80)

    # Secure Score
    try:
        scores = client.get_secure_scores(top=1)
        if scores:
            s = scores[0]
            current = s.get("currentScore", 0)
            max_score = s.get("maxScore", 0)
            pct = (current / max_score * 100) if max_score else 0
            print(f"\nSecure Score: {current:.1f} / {max_score:.1f} ({pct:.0f}%)")
    except Exception as e:
        print(f"\nSecure Score: unavailable ({str(e)[:40]})")

    # Defender Alerts
    try:
        alerts = client.list_security_alerts(top=100)
        severities = Counter(a.get("severity", "?") for a in alerts)
        active = [a for a in alerts if a.get("status") != "resolved"]
        print(f"\nDefender Alerts (recent 100): {len(alerts)} total, {len(active)} active")
        if severities:
            parts = ", ".join(f"{c} {s}" for s, c in severities.most_common())
            print(f"  Severity: {parts}")
    except Exception as e:
        print(f"\nDefender Alerts: unavailable ({str(e)[:40]})")

    # Defender Incidents
    try:
        incidents = client.list_security_incidents(top=50)
        active_inc = [i for i in incidents if i.get("status") != "resolved"]
        print(f"\nDefender Incidents (recent 50): {len(incidents)} total, {len(active_inc)} active")
    except Exception as e:
        print(f"\nDefender Incidents: unavailable ({str(e)[:40]})")

    # Risky Users
    try:
        risky = client.list_risky_users()
        at_risk = [u for u in risky if u.get("riskState") == "atRisk"]
        risk_levels = Counter(u.get("riskLevel", "?") for u in at_risk)
        print(f"\nRisky Users: {len(at_risk)} at risk (of {len(risky)} total flagged)")
        if risk_levels:
            parts = ", ".join(f"{c} {l}" for l, c in risk_levels.most_common())
            print(f"  Risk levels: {parts}")
    except Exception as e:
        print(f"\nRisky Users: unavailable ({str(e)[:40]})")

    # Conditional Access
    try:
        policies = client.list_conditional_access_policies()
        enabled = [p for p in policies if p.get("state") == "enabled"]
        report_only = [p for p in policies if p.get("state") == "enabledForReportingButNotEnforced"]
        disabled = [p for p in policies if p.get("state") == "disabled"]
        print(f"\nConditional Access: {len(policies)} policies ({len(enabled)} enabled, {len(report_only)} report-only, {len(disabled)} disabled)")
    except Exception as e:
        print(f"\nConditional Access: unavailable ({str(e)[:40]})")

    # Sign-in summary
    try:
        sign_ins = client.list_sign_ins(top=100)
        failures = [s for s in sign_ins if s.get("status", {}).get("errorCode", 0) != 0]
        print(f"\nRecent Sign-ins (100): {len(failures)} failures, {len(sign_ins) - len(failures)} success")
    except Exception as e:
        print(f"\nSign-in Logs: unavailable ({str(e)[:40]})")

    print("\n" + "=" * 80)


def show_alerts(client: GraphClient, severity_filter: str = None):
    """Show Defender security alerts."""
    alerts = client.list_security_alerts(top=50)

    if severity_filter:
        alerts = [a for a in alerts if a.get("severity", "").lower() == severity_filter.lower()]

    print(f"Defender Security Alerts: {len(alerts)}")
    print()
    print(f"{'Severity':<12} {'Status':<12} {'Title':<50} {'Created'}")
    print("-" * 95)

    for a in alerts:
        sev = (a.get("severity") or "?")[:11]
        status = (a.get("status") or "?")[:11]
        title = (a.get("title") or "?")[:49]
        created = (a.get("createdDateTime") or "?")[:19]
        print(f"{sev:<12} {status:<12} {title:<50} {created}")


def show_incidents(client: GraphClient):
    """Show Defender security incidents."""
    incidents = client.list_security_incidents(top=50)

    print(f"Defender Security Incidents: {len(incidents)}")
    print()
    print(f"{'Severity':<12} {'Status':<14} {'Title':<48} {'Alerts':>6} {'Created'}")
    print("-" * 100)

    for i in incidents:
        sev = (i.get("severity") or "?")[:11]
        status = (i.get("status") or "?")[:13]
        title = (i.get("displayName") or "?")[:47]
        alert_count = len(i.get("alerts", []))
        created = (i.get("createdDateTime") or "?")[:19]
        print(f"{sev:<12} {status:<14} {title:<48} {alert_count:>6} {created}")


def show_secure_score(client: GraphClient):
    """Show Microsoft Secure Score details."""
    scores = client.get_secure_scores(top=1)
    if not scores:
        print("No Secure Score data available")
        return

    s = scores[0]
    current = s.get("currentScore", 0)
    max_score = s.get("maxScore", 0)
    pct = (current / max_score * 100) if max_score else 0
    created = (s.get("createdDateTime") or "?")[:19]

    print(f"Microsoft Secure Score")
    print(f"  Score: {current:.1f} / {max_score:.1f} ({pct:.0f}%)")
    print(f"  Date:  {created}")
    print()

    controls = s.get("controlScores", [])
    if controls:
        controls.sort(key=lambda c: c.get("score", 0), reverse=True)
        print(f"{'Control':<55} {'Score':>6} {'Max':>6}")
        print("-" * 70)
        for c in controls[:20]:
            name = (c.get("controlName") or "?")[:54]
            score = c.get("score", 0)
            max_val = c.get("maxScore", 0) if "maxScore" in c else ""
            print(f"{name:<55} {score:>6.1f} {str(max_val):>6}")


def show_risky_users(client: GraphClient):
    """Show risky users from Identity Protection."""
    risky = client.list_risky_users()
    at_risk = [u for u in risky if u.get("riskState") in ("atRisk", "confirmedCompromised")]

    print(f"Identity Protection - Risky Users: {len(at_risk)} at risk / {len(risky)} total")
    print()

    if not at_risk:
        print("No users currently at risk.")
        return

    print(f"{'User':<40} {'Risk Level':<12} {'Risk State':<20} {'Last Updated'}")
    print("-" * 95)

    for u in at_risk:
        name = (u.get("userDisplayName") or u.get("userPrincipalName") or "?")[:39]
        level = (u.get("riskLevel") or "?")[:11]
        state = (u.get("riskState") or "?")[:19]
        updated = (u.get("riskLastUpdatedDateTime") or "?")[:19]
        print(f"{name:<40} {level:<12} {state:<20} {updated}")


def show_risk_detections(client: GraphClient):
    """Show risk detection events."""
    events = client.list_risk_detections(top=50)

    print(f"Identity Protection - Risk Detections: {len(events)}")
    print()
    print(f"{'Risk Level':<12} {'Type':<35} {'User':<30} {'Detected'}")
    print("-" * 95)

    for e in events:
        level = (e.get("riskLevel") or "?")[:11]
        risk_type = (e.get("riskEventType") or "?")[:34]
        user = (e.get("userDisplayName") or e.get("userPrincipalName") or "?")[:29]
        detected = (e.get("activityDateTime") or "?")[:19]
        print(f"{level:<12} {risk_type:<35} {user:<30} {detected}")


def show_ca_policies(client: GraphClient):
    """Show Conditional Access policies."""
    policies = client.list_conditional_access_policies()

    print(f"Conditional Access Policies: {len(policies)}")
    print()
    print(f"{'State':<12} {'Policy Name':<55} {'Created'}")
    print("-" * 85)

    for p in sorted(policies, key=lambda x: x.get("state", "")):
        state = (p.get("state") or "?")[:11]
        name = (p.get("displayName") or "?")[:54]
        created = (p.get("createdDateTime") or "?")[:19]
        print(f"{state:<12} {name:<55} {created}")


def show_named_locations(client: GraphClient):
    """Show Conditional Access named locations."""
    locations = client.list_named_locations()

    print(f"Named Locations: {len(locations)}")
    print()
    for loc in locations:
        name = loc.get("displayName", "?")
        loc_type = loc.get("@odata.type", "?").split(".")[-1]
        trusted = "trusted" if loc.get("isTrusted") else "untrusted"
        print(f"  {name}")
        print(f"    Type: {loc_type}, {trusted}")

        if "ipRanges" in loc:
            ranges = loc.get("ipRanges", [])
            for r in ranges[:5]:
                print(f"    Range: {r.get('cidrAddress', '?')}")
            if len(ranges) > 5:
                print(f"    ... +{len(ranges) - 5} more ranges")

        if "countriesAndRegions" in loc:
            countries = loc.get("countriesAndRegions", [])
            print(f"    Countries: {', '.join(countries[:10])}")
        print()


def show_sign_ins(client: GraphClient, user: str = None):
    """Show recent sign-in logs."""
    if user:
        # Look up user ID first
        u = client.get_user(user, select="id,displayName,userPrincipalName")
        user_id = u.get("id")
        sign_ins = client.list_sign_ins(user_id=user_id, top=20)
        print(f"Recent sign-ins for {u.get('displayName', user)}: {len(sign_ins)}")
    else:
        sign_ins = client.list_sign_ins(top=50)
        print(f"Recent sign-ins (all users): {len(sign_ins)}")

    print()
    print(f"{'User':<30} {'App':<25} {'Status':<10} {'IP':<16} {'Date'}")
    print("-" * 100)

    for s in sign_ins:
        upn = (s.get("userPrincipalName") or "?").split("@")[0][:29]
        app = (s.get("appDisplayName") or "?")[:24]
        error = s.get("status", {}).get("errorCode", 0)
        status = "OK" if error == 0 else f"ERR:{error}"
        ip = (s.get("ipAddress") or "?")[:15]
        created = (s.get("createdDateTime") or "?")[:19]
        print(f"{upn:<30} {app:<25} {status:<10} {ip:<16} {created}")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = GraphClient()
    command = sys.argv[1].lower()

    if command == "dashboard":
        dashboard(client)
    elif command == "alerts":
        severity = None
        if "--severity" in sys.argv:
            idx = sys.argv.index("--severity")
            severity = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        show_alerts(client, severity)
    elif command == "incidents":
        show_incidents(client)
    elif command == "score":
        show_secure_score(client)
    elif command in ("risky-users", "riskyusers"):
        show_risky_users(client)
    elif command in ("risk-detections", "riskdetections"):
        show_risk_detections(client)
    elif command in ("ca-policies", "capolicies", "ca"):
        show_ca_policies(client)
    elif command in ("named-locations", "namedlocations", "locations"):
        show_named_locations(client)
    elif command in ("sign-ins", "signins", "logins"):
        user = sys.argv[2] if len(sys.argv) > 2 else None
        show_sign_ins(client, user)
    else:
        print(f"Unknown command: {command}")
        print("Commands: dashboard, alerts, incidents, score, risky-users, risk-detections, ca-policies, named-locations, sign-ins")
        sys.exit(1)


if __name__ == "__main__":
    main()
