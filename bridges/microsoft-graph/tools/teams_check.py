"""
Microsoft Teams Inventory Tool

Query Teams, channels, and membership across the tenant.

Usage:
    python3 teams_check.py list                     # List all teams
    python3 teams_check.py info <team-name>          # Team details and channels
    python3 teams_check.py members <team-name>       # Team membership
    python3 teams_check.py search <query>            # Search teams by name
    python3 teams_check.py summary                   # Tenant-wide Teams summary
"""

import sys
import json
from collections import Counter

sys.path.insert(0, "/opt/bridge/data/tools")
from graph_client import GraphClient


def list_teams(client: GraphClient):
    """List all teams in the tenant."""
    teams = client.list_teams()

    print(f"Microsoft Teams: {len(teams)}")
    print()
    print(f"{'Team Name':<50} {'Visibility':<14} {'Description'}")
    print("-" * 100)

    for t in sorted(teams, key=lambda x: (x.get("displayName") or "").lower()):
        name = (t.get("displayName") or "?")[:49]
        visibility = (t.get("visibility") or "?")[:13]
        desc = (t.get("description") or "")[:40]
        print(f"{name:<50} {visibility:<14} {desc}")


def team_info(client: GraphClient, team_name: str):
    """Show team details and channels."""
    teams = client.list_teams()
    matches = [t for t in teams if team_name.lower() in (t.get("displayName") or "").lower()]

    if not matches:
        print(f"No team matching '{team_name}' found ({len(teams)} teams searched)")
        sys.exit(1)

    team = matches[0]
    team_id = team["id"]

    print(f"Team: {team.get('displayName')}")
    print(f"  ID:          {team_id}")
    print(f"  Visibility:  {team.get('visibility', '?')}")
    print(f"  Description: {team.get('description') or '(none)'}")
    print()

    # Channels
    try:
        channels = client.list_team_channels(team_id)
        print(f"Channels ({len(channels)}):")
        for ch in channels:
            name = ch.get("displayName", "?")
            membership = ch.get("membershipType", "?")
            print(f"  {name:<40} [{membership}]")
    except Exception as e:
        print(f"Channels: error ({str(e)[:40]})")

    if len(matches) > 1:
        print(f"\nNote: {len(matches)} teams matched '{team_name}', showing first")


def team_members(client: GraphClient, team_name: str):
    """Show team membership."""
    teams = client.list_teams()
    matches = [t for t in teams if team_name.lower() in (t.get("displayName") or "").lower()]

    if not matches:
        print(f"No team matching '{team_name}' found")
        sys.exit(1)

    team = matches[0]
    team_id = team["id"]
    members = client.list_team_members(team_id)

    owners = [m for m in members if "owner" in (m.get("roles") or [])]
    regular = [m for m in members if "owner" not in (m.get("roles") or [])]

    print(f"Team: {team.get('displayName')} - {len(members)} members ({len(owners)} owners)")
    print()

    if owners:
        print(f"Owners ({len(owners)}):")
        for m in owners:
            name = m.get("displayName", "?")
            email = m.get("email", "?")
            print(f"  {name:<35} {email}")

    print(f"\nMembers ({len(regular)}):")
    for m in sorted(regular, key=lambda x: (x.get("displayName") or "").lower()):
        name = m.get("displayName", "?")
        email = m.get("email", "?")
        print(f"  {name:<35} {email}")


def search_teams(client: GraphClient, query: str):
    """Search teams by name."""
    teams = client.list_teams()
    matches = [t for t in teams if query.lower() in (t.get("displayName") or "").lower()]

    print(f"Teams matching '{query}': {len(matches)}")
    print()

    for t in matches:
        name = t.get("displayName", "?")
        visibility = t.get("visibility", "?")
        desc = (t.get("description") or "")[:50]
        print(f"  {name}")
        print(f"    Visibility: {visibility}, ID: {t['id'][:8]}...")
        if desc:
            print(f"    Description: {desc}")
        print()


def summary(client: GraphClient):
    """Tenant-wide Teams summary."""
    teams = client.list_teams()

    visibility = Counter(t.get("visibility", "unknown") for t in teams)

    print(f"Microsoft Teams Summary")
    print(f"=" * 50)
    print(f"Total teams: {len(teams)}")
    print(f"Visibility: {', '.join(f'{c} {v}' for v, c in visibility.most_common())}")
    print()

    # Sample channel counts for first 20 teams
    print("Channel counts (sample of 20 teams):")
    sample = teams[:20]
    for t in sample:
        try:
            channels = client.list_team_channels(t["id"])
            name = (t.get("displayName") or "?")[:40]
            print(f"  {name:<42} {len(channels)} channels")
        except Exception:
            name = (t.get("displayName") or "?")[:40]
            print(f"  {name:<42} (error)")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = GraphClient()
    command = sys.argv[1].lower()

    if command == "list":
        list_teams(client)
    elif command == "info":
        if len(sys.argv) < 3:
            print("Usage: teams_check.py info <team-name>")
            sys.exit(1)
        team_info(client, " ".join(sys.argv[2:]))
    elif command == "members":
        if len(sys.argv) < 3:
            print("Usage: teams_check.py members <team-name>")
            sys.exit(1)
        team_members(client, " ".join(sys.argv[2:]))
    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: teams_check.py search <query>")
            sys.exit(1)
        search_teams(client, " ".join(sys.argv[2:]))
    elif command == "summary":
        summary(client)
    else:
        print(f"Unknown command: {command}")
        print("Commands: list, info, members, search, summary")
        sys.exit(1)


if __name__ == "__main__":
    main()
