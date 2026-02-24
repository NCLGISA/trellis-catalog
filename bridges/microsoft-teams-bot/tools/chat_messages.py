#!/usr/bin/env python3
"""
Chat Messages -- read/search 1:1 and group chat messages via Graph API.

Requires: Chat.Read.All, ChatMessage.Read.All, User.Read.All (application)

App-only access to chats uses user-scoped endpoints:
  /users/{user-id}/chats -> /chats/{chat-id}/messages

Usage:
  python3 chat_messages.py chats <user>                     List chats for a user
  python3 chat_messages.py messages <chat_id> [--top N]     Read messages from a chat
  python3 chat_messages.py members <chat_id>                List chat members
  python3 chat_messages.py search <user> <query> [--top N]  Search a user's chats
  python3 chat_messages.py summary <user>                   Chat summary for a user

  <user> accepts displayName (substring match), UPN, or user ID (GUID).
"""

import json
import sys

from teams_client import TeamsClient


def _resolve_user(client: TeamsClient, name_or_id: str) -> dict | None:
    if len(name_or_id) == 36 and "-" in name_or_id:
        try:
            resp = client.get(f"users/{name_or_id}")
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass

    if "@" in name_or_id:
        try:
            resp = client.get(f"users/{name_or_id}")
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass

    users = client.list_users(top=999)
    name_lower = name_or_id.lower()
    for u in users:
        dn = u.get("displayName", "")
        upn = u.get("userPrincipalName", "")
        if name_lower in dn.lower() or name_lower in upn.lower():
            return u
    return None


def list_chats(client: TeamsClient, user_ref: str, top: int = 25) -> list[dict]:
    user = _resolve_user(client, user_ref)
    if not user:
        return [{"error": f"User not found: {user_ref}"}]

    chats = client.list_user_chats(user["id"], top=top)
    results = []
    for c in chats:
        results.append({
            "id": c["id"],
            "topic": c.get("topic") or "(no topic)",
            "chatType": c.get("chatType"),
            "createdDateTime": c.get("createdDateTime"),
            "lastUpdatedDateTime": c.get("lastUpdatedDateTime"),
        })
    return results


def read_messages(client: TeamsClient, chat_id: str, top: int = 25) -> list[dict]:
    messages = client.list_chat_messages(chat_id, top=top)
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
            "importance": m.get("importance"),
            "messageType": m.get("messageType"),
        })
    return results


def list_members(client: TeamsClient, chat_id: str) -> list[dict]:
    members = client.list_chat_members(chat_id)
    return [
        {
            "displayName": m.get("displayName"),
            "userId": m.get("userId"),
            "email": m.get("email"),
            "roles": m.get("roles", []),
        }
        for m in members
    ]


def search_chats(client: TeamsClient, user_ref: str, query: str, top: int = 10) -> list[dict]:
    user = _resolve_user(client, user_ref)
    if not user:
        return [{"error": f"User not found: {user_ref}"}]

    chats = client.list_user_chats(user["id"], top=top)
    hits = []
    query_lower = query.lower()

    for c in chats:
        try:
            messages = client.list_chat_messages(c["id"], top=20)
            for m in messages:
                body = m.get("body", {}).get("content", "")
                if query_lower in body.lower():
                    sender = m.get("from", {})
                    user_info = sender.get("user", {}) if sender else {}
                    hits.append({
                        "chat_id": c["id"],
                        "chat_topic": c.get("topic") or "(no topic)",
                        "message_id": m.get("id"),
                        "from": user_info.get("displayName", "system"),
                        "createdDateTime": m.get("createdDateTime"),
                        "snippet": body[:300],
                    })
        except Exception:
            continue

    return hits


def summary(client: TeamsClient, user_ref: str) -> dict:
    user = _resolve_user(client, user_ref)
    if not user:
        return {"error": f"User not found: {user_ref}"}

    chats = client.list_user_chats(user["id"], top=100)
    by_type = {}
    for c in chats:
        ct = c.get("chatType", "unknown")
        by_type[ct] = by_type.get(ct, 0) + 1

    return {
        "user": user.get("displayName"),
        "total_chats": len(chats),
        "by_type": by_type,
        "note": "Showing up to 100 most recent chats",
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

    if cmd == "chats":
        if len(sys.argv) < 3:
            print("Usage: chat_messages.py chats <user>")
            sys.exit(1)
        result = list_chats(client, sys.argv[2], top=top)
    elif cmd == "messages":
        if len(sys.argv) < 3:
            print("Usage: chat_messages.py messages <chat_id>")
            sys.exit(1)
        result = read_messages(client, sys.argv[2], top=top)
    elif cmd == "members":
        if len(sys.argv) < 3:
            print("Usage: chat_messages.py members <chat_id>")
            sys.exit(1)
        result = list_members(client, sys.argv[2])
    elif cmd == "search":
        if len(sys.argv) < 4:
            print("Usage: chat_messages.py search <user> <query>")
            sys.exit(1)
        result = search_chats(client, sys.argv[2], sys.argv[3], top=top)
    elif cmd == "summary":
        if len(sys.argv) < 3:
            print("Usage: chat_messages.py summary <user>")
            sys.exit(1)
        result = summary(client, sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
