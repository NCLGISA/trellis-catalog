#!/usr/bin/env python3
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
Proactive Send -- send messages to Teams users/channels via the bot server.

Requires: Webhook mode with bot_server.py running. Messages are sent as the
bot identity (TEAMS_BOT_NAME) to conversations where the bot is installed.

Usage:
  python3 proactive_send.py list                          List known conversations
  python3 proactive_send.py send <conversation_id> <msg>  Send a message
  python3 proactive_send.py broadcast <msg>               Send to all conversations
  python3 proactive_send.py status                        Bot server status
"""

import json
import os
import sys

from teams_client import TeamsClient


def list_conversations(client: TeamsClient) -> dict:
    convs = client.bot_conversations()
    if "error" in convs:
        return {"error": convs["error"], "hint": "Is bot_server.py running? (webhook mode only)"}

    results = {}
    for conv_id, ref in convs.items():
        results[conv_id] = {
            "user_name": ref.get("user_name"),
            "channel_id": ref.get("channel_id"),
            "updated_at": ref.get("updated_at"),
        }
    return {"conversations": results, "total": len(results)}


def send_message(client: TeamsClient, conversation_id: str, message: str) -> dict:
    return client.bot_send(conversation_id, message)


def broadcast(client: TeamsClient, message: str) -> dict:
    convs = client.bot_conversations()
    if "error" in convs:
        return {"error": convs["error"]}

    results = []
    for conv_id in convs:
        result = client.bot_send(conv_id, message)
        results.append({"conversation_id": conv_id, **result})

    sent = sum(1 for r in results if r.get("ok"))
    return {"total": len(results), "sent": sent, "results": results}


def status(client: TeamsClient) -> dict:
    health = client.bot_health()
    convs = client.bot_conversations()
    conv_count = len(convs) if "error" not in convs else 0

    return {
        "bot_server": health,
        "conversations_tracked": conv_count,
        "mode": client.bot_mode,
        "bot_name": client.bot_name,
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    mode = os.environ.get("TEAMS_BOT_MODE", "webhook")
    if mode != "webhook":
        print("ERROR: Proactive messaging requires webhook mode (TEAMS_BOT_MODE=webhook)")
        sys.exit(1)

    cmd = sys.argv[1]
    client = TeamsClient()

    if cmd == "list":
        result = list_conversations(client)
    elif cmd == "send":
        if len(sys.argv) < 4:
            print("Usage: proactive_send.py send <conversation_id> <message>")
            sys.exit(1)
        result = send_message(client, sys.argv[2], " ".join(sys.argv[3:]))
    elif cmd == "broadcast":
        if len(sys.argv) < 3:
            print("Usage: proactive_send.py broadcast <message>")
            sys.exit(1)
        result = broadcast(client, " ".join(sys.argv[2:]))
    elif cmd == "status":
        result = status(client)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
