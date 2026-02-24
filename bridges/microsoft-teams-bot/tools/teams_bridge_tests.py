#!/usr/bin/env python3
"""
Teams Bot Bridge Battery Tests -- read-only validation of Graph API access,
bot server functionality, and conversation store operations.

Usage:
  python3 teams_bridge_tests.py          Run all tests
  python3 teams_bridge_tests.py graph    Graph API tests only
  python3 teams_bridge_tests.py bot      Bot server tests only
"""

import json
import os
import sys
import time

try:
    from dotenv import load_dotenv

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


def run_test(name: str, fn, *args) -> dict:
    start = time.time()
    try:
        result = fn(*args)
        elapsed = round(time.time() - start, 2)
        return {"test": name, "status": result.get("status", PASS), "elapsed_s": elapsed, **result}
    except Exception as exc:
        elapsed = round(time.time() - start, 2)
        return {"test": name, "status": FAIL, "elapsed_s": elapsed, "error": str(exc)}


# ── Graph API Tests ───────────────────────────────────────────────

def test_token_acquisition():
    from teams_client import TeamsClient
    client = TeamsClient()
    token = client._get_token()
    if token and len(token) > 50:
        return {"status": PASS, "token_length": len(token)}
    return {"status": FAIL, "error": "Token too short or empty"}


def test_list_teams():
    from teams_client import TeamsClient
    client = TeamsClient()
    resp = client.get("teams", params={"$top": 5})
    if resp.status_code == 200:
        teams = resp.json().get("value", [])
        return {"status": PASS, "teams_returned": len(teams)}
    return {"status": FAIL, "http_status": resp.status_code, "body": resp.text[:200]}


def test_list_channels():
    from teams_client import TeamsClient
    client = TeamsClient()
    teams = client.list_teams(top=1)
    if not teams:
        return {"status": SKIP, "reason": "No teams found"}
    team_id = teams[0]["id"]
    channels = client.list_channels(team_id)
    return {
        "status": PASS,
        "team": teams[0].get("displayName"),
        "channels_returned": len(channels),
    }


def test_channel_messages():
    from teams_client import TeamsClient
    client = TeamsClient()
    teams = client.list_teams(top=1)
    if not teams:
        return {"status": SKIP, "reason": "No teams found"}

    team_id = teams[0]["id"]
    channels = client.list_channels(team_id)
    if not channels:
        return {"status": SKIP, "reason": "No channels found"}

    channel_id = channels[0]["id"]
    msgs = client.list_channel_messages(team_id, channel_id, top=5)
    return {
        "status": PASS,
        "team": teams[0].get("displayName"),
        "channel": channels[0].get("displayName"),
        "messages_returned": len(msgs),
    }


def test_user_chats():
    """Test listing chats for a user (app-only: Chat.Read.All + User.Read.All)."""
    from teams_client import TeamsClient
    client = TeamsClient()
    users = client.list_users(top=5)
    if not users:
        return {"status": SKIP, "reason": "No users found"}

    for user in users:
        try:
            chats = client.list_user_chats(user["id"], top=5)
            return {
                "status": PASS,
                "user": user.get("displayName"),
                "chats_returned": len(chats),
            }
        except Exception:
            continue
    return {"status": SKIP, "reason": "No accessible user chats found"}


def test_chat_messages():
    """Test reading messages from a user's chat (ChatMessage.Read.All)."""
    from teams_client import TeamsClient
    client = TeamsClient()
    users = client.list_users(top=5)
    if not users:
        return {"status": SKIP, "reason": "No users found"}

    for user in users:
        try:
            chats = client.list_user_chats(user["id"], top=3)
            for chat in chats:
                msgs = client.list_chat_messages(chat["id"], top=5)
                return {
                    "status": PASS,
                    "user": user.get("displayName"),
                    "chat_type": chat.get("chatType"),
                    "messages_returned": len(msgs),
                }
        except Exception:
            continue
    return {"status": SKIP, "reason": "No accessible chat messages found"}


# ── Bot Server Tests ─────────────────────────────────────────────

def test_bot_health():
    from teams_client import TeamsClient
    client = TeamsClient()
    health = client.bot_health()
    if health.get("status") == "ok":
        return {"status": PASS, **health}
    return {"status": FAIL, **health}


def test_bot_conversations():
    from teams_client import TeamsClient
    client = TeamsClient()
    convs = client.bot_conversations()
    if "error" in convs:
        return {"status": FAIL, **convs}
    return {"status": PASS, "conversation_count": len(convs)}


# ── Runner ────────────────────────────────────────────────────────

GRAPH_TESTS = [
    ("Graph: Token Acquisition", test_token_acquisition),
    ("Graph: List Teams", test_list_teams),
    ("Graph: List Channels", test_list_channels),
    ("Graph: Channel Messages", test_channel_messages),
    ("Graph: User Chats", test_user_chats),
    ("Graph: Chat Messages", test_chat_messages),
]

BOT_TESTS = [
    ("Bot Server: Health", test_bot_health),
    ("Bot Server: Conversations", test_bot_conversations),
]


def main():
    subset = sys.argv[1] if len(sys.argv) > 1 else "all"
    mode = os.environ.get("TEAMS_BOT_MODE", "webhook")

    tests = []
    if subset in ("all", "graph"):
        tests.extend(GRAPH_TESTS)
    if subset in ("all", "bot") and mode == "webhook":
        tests.extend(BOT_TESTS)

    results = []
    for name, fn in tests:
        result = run_test(name, fn)
        status_icon = {"PASS": "+", "FAIL": "!", "SKIP": "~"}.get(result["status"], "?")
        print(f"  [{status_icon}] {name}: {result['status']} ({result['elapsed_s']}s)")
        results.append(result)

    passed = sum(1 for r in results if r["status"] == PASS)
    failed = sum(1 for r in results if r["status"] == FAIL)
    skipped = sum(1 for r in results if r["status"] == SKIP)

    print(f"\nResults: {passed} passed, {failed} failed, {skipped} skipped out of {len(results)} tests")

    summary = {
        "bridge": "microsoft-teams-bot",
        "mode": mode,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "tests": results,
    }
    print(json.dumps(summary, indent=2))
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
