#!/usr/bin/env python3
"""
Channel Messages -- read/search channel messages via Graph API.

Requires: ChannelMessage.Read.All, Team.ReadBasic.All, Channel.ReadBasic.All

Usage:
  python3 channel_messages.py teams                                   List teams
  python3 channel_messages.py channels <team>                         List channels
  python3 channel_messages.py messages <team> <channel> [--top N]     Read messages
  python3 channel_messages.py replies <team> <channel> <msg_id>       Read replies
  python3 channel_messages.py search <team> <query> [--top N]         Search channels
  python3 channel_messages.py summary                                 Tenant summary

  <team> and <channel> accept display names (substring match) or IDs.
"""

import json
import sys

from teams_client import TeamsClient


def _resolve_team(client: TeamsClient, name_or_id: str) -> dict | None:
    if len(name_or_id) == 36 and "-" in name_or_id:
        try:
            return client.get_team(name_or_id)
        except Exception:
            pass

    teams = client.list_teams()
    name_lower = name_or_id.lower()
    for t in teams:
        if name_lower in t.get("displayName", "").lower():
            return t
    return None


def _resolve_channel(
    client: TeamsClient, team_id: str, name_or_id: str
) -> dict | None:
    if ":" in name_or_id or len(name_or_id) > 50:
        try:
            return client.get_channel(team_id, name_or_id)
        except Exception:
            pass

    channels = client.list_channels(team_id)
    name_lower = name_or_id.lower()
    for ch in channels:
        if name_lower in ch.get("displayName", "").lower():
            return ch
    return None


def list_teams(client: TeamsClient) -> list[dict]:
    teams = client.list_teams()
    return [
        {
            "id": t["id"],
            "displayName": t.get("displayName"),
            "description": (t.get("description") or "")[:100],
            "visibility": t.get("visibility"),
        }
        for t in teams
    ]


def list_channels(client: TeamsClient, team_name: str) -> list[dict]:
    team = _resolve_team(client, team_name)
    if not team:
        return [{"error": f"Team not found: {team_name}"}]

    channels = client.list_channels(team["id"])
    return [
        {
            "id": ch["id"],
            "displayName": ch.get("displayName"),
            "membershipType": ch.get("membershipType"),
            "description": (ch.get("description") or "")[:100],
        }
        for ch in channels
    ]


def read_messages(
    client: TeamsClient, team_name: str, channel_name: str, top: int = 25
) -> list[dict]:
    team = _resolve_team(client, team_name)
    if not team:
        return [{"error": f"Team not found: {team_name}"}]

    channel = _resolve_channel(client, team["id"], channel_name)
    if not channel:
        return [{"error": f"Channel not found: {channel_name}"}]

    messages = client.list_channel_messages(team["id"], channel["id"], top=top)
    results = []
    for m in messages:
        sender = m.get("from", {})
        user = sender.get("user", {}) if sender else {}
        body = m.get("body", {})
        results.append({
            "id": m.get("id"),
            "from": user.get("displayName", "system"),
            "createdDateTime": m.get("createdDateTime"),
            "contentType": body.get("contentType"),
            "content": body.get("content", "")[:500],
            "replyCount": m.get("replyCount", 0) if "replies@odata.context" not in m else None,
            "importance": m.get("importance"),
        })
    return results


def read_replies(
    client: TeamsClient, team_name: str, channel_name: str, message_id: str
) -> list[dict]:
    team = _resolve_team(client, team_name)
    if not team:
        return [{"error": f"Team not found: {team_name}"}]

    channel = _resolve_channel(client, team["id"], channel_name)
    if not channel:
        return [{"error": f"Channel not found: {channel_name}"}]

    replies = client.list_message_replies(team["id"], channel["id"], message_id)
    results = []
    for r in replies:
        sender = r.get("from", {})
        user = sender.get("user", {}) if sender else {}
        body = r.get("body", {})
        results.append({
            "id": r.get("id"),
            "from": user.get("displayName", "system"),
            "createdDateTime": r.get("createdDateTime"),
            "content": body.get("content", "")[:500],
        })
    return results


def search_channels(
    client: TeamsClient, team_name: str, query: str, top: int = 10
) -> list[dict]:
    team = _resolve_team(client, team_name)
    if not team:
        return [{"error": f"Team not found: {team_name}"}]

    channels = client.list_channels(team["id"])
    query_lower = query.lower()
    hits = []

    for ch in channels:
        try:
            messages = client.list_channel_messages(team["id"], ch["id"], top=top)
            for m in messages:
                body = m.get("body", {}).get("content", "")
                if query_lower in body.lower():
                    sender = m.get("from", {})
                    user = sender.get("user", {}) if sender else {}
                    hits.append({
                        "channel": ch.get("displayName"),
                        "message_id": m.get("id"),
                        "from": user.get("displayName", "system"),
                        "createdDateTime": m.get("createdDateTime"),
                        "snippet": body[:300],
                    })
        except Exception:
            continue

    return hits


def team_summary(client: TeamsClient) -> dict:
    teams = client.list_teams()
    total_channels = 0
    samples = []
    for t in teams[:5]:
        channels = client.list_channels(t["id"])
        total_channels += len(channels)
        samples.append({
            "team": t.get("displayName"),
            "channels": len(channels),
            "visibility": t.get("visibility"),
        })

    return {
        "total_teams": len(teams),
        "channels_sampled": total_channels,
        "samples": samples,
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    client = TeamsClient()
    top = 25

    for i, arg in enumerate(sys.argv):
        if arg == "--top" and i + 1 < len(sys.argv):
            top = int(sys.argv[i + 1])

    if cmd == "teams":
        result = list_teams(client)
    elif cmd == "channels":
        if len(sys.argv) < 3:
            print("Usage: channel_messages.py channels <team>")
            sys.exit(1)
        result = list_channels(client, sys.argv[2])
    elif cmd == "messages":
        if len(sys.argv) < 4:
            print("Usage: channel_messages.py messages <team> <channel>")
            sys.exit(1)
        result = read_messages(client, sys.argv[2], sys.argv[3], top=top)
    elif cmd == "replies":
        if len(sys.argv) < 5:
            print("Usage: channel_messages.py replies <team> <channel> <msg_id>")
            sys.exit(1)
        result = read_replies(client, sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "search":
        if len(sys.argv) < 4:
            print("Usage: channel_messages.py search <team> <query>")
            sys.exit(1)
        result = search_channels(client, sys.argv[2], sys.argv[3], top=top)
    elif cmd == "summary":
        result = team_summary(client)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
