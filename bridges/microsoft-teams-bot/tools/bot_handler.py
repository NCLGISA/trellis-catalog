"""
Teams Bot Activity Handler -- processes incoming Bot Framework activities,
stores conversation references for proactive messaging, and handles
Teams-specific events (installs, message reactions, etc.).
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Dict

from botbuilder.core import TurnContext
from botbuilder.core.teams import TeamsActivityHandler
from botbuilder.schema import (
    Activity,
    ActivityTypes,
    ChannelAccount,
    ConversationReference,
)

logger = logging.getLogger("teams-bot")

CONV_STORE_PATH = os.environ.get(
    "TEAMS_BOT_CONV_STORE", "/opt/bridge/data/conversations.json"
)
MSG_LOG_PATH = os.environ.get(
    "TEAMS_BOT_MSG_LOG", "/opt/bridge/data/message_log.jsonl"
)
BOT_NAME = os.environ.get("TEAMS_BOT_NAME", "Tendril Bot")
BOT_VERSION = os.environ.get("TEAMS_BOT_VERSION", "unknown")


class ConversationStore:
    """Thread-safe persistent store for conversation references."""

    def __init__(self, path: str = CONV_STORE_PATH):
        self.path = path
        self._refs: Dict[str, dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    self._refs = json.load(f)
                logger.info("Loaded %d conversation references", len(self._refs))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load conversation store: %s", exc)
                self._refs = {}

    def _save(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(self._refs, f, indent=2, default=str)
            os.replace(tmp, self.path)
        except OSError as exc:
            logger.error("Failed to save conversation store: %s", exc)

    def upsert(self, key: str, ref: ConversationReference):
        self._refs[key] = {
            "conversation_id": ref.conversation.id if ref.conversation else None,
            "user_id": ref.user.id if ref.user else None,
            "user_name": ref.user.name if ref.user else None,
            "channel_id": ref.channel_id,
            "service_url": ref.service_url,
            "bot_id": ref.bot.id if ref.bot else None,
            "bot_name": ref.bot.name if ref.bot else None,
            "activity_id": ref.activity_id,
            "locale": ref.locale,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "_raw": TurnContext.get_conversation_reference(
                Activity(
                    id=ref.activity_id,
                    channel_id=ref.channel_id,
                    service_url=ref.service_url,
                    conversation=ref.conversation,
                    from_property=ref.user,
                    recipient=ref.bot,
                    locale=ref.locale,
                )
            ).__dict__
            if ref.conversation
            else {},
        }
        self._save()

    def get_all(self) -> Dict[str, dict]:
        return dict(self._refs)

    def get(self, key: str) -> dict | None:
        return self._refs.get(key)

    @property
    def count(self) -> int:
        return len(self._refs)


STORE = ConversationStore()


def get_store() -> ConversationStore:
    return STORE


class TeamsBotHandler(TeamsActivityHandler):
    """Handles Bot Framework activities for the Teams channel."""

    def __init__(self):
        super().__init__()
        self.store = STORE

    async def on_message_activity(self, turn_context: TurnContext):
        self._save_conversation_reference(turn_context.activity)

        text = (turn_context.activity.text or "").strip()
        if not text:
            return

        user_name = (
            turn_context.activity.from_property.name
            if turn_context.activity.from_property
            else "unknown"
        )
        user_id = (
            turn_context.activity.from_property.id
            if turn_context.activity.from_property
            else None
        )

        logger.info("Message from %s: %s", user_name, text[:100])
        self._log_message("in", user_name, user_id, text)

        lower = text.lower()
        if lower in ("hello", "hi", "hey"):
            reply = (
                f"Hi, I'm **{BOT_NAME}** -- A bridge for Rowan County IT "
                f"to send notifications via MS Teams. Type **help** for more info."
            )
            await turn_context.send_activity(reply)
            self._log_message("out", BOT_NAME, None, reply)
        elif lower == "help":
            reply = (
                f"**{BOT_NAME}**\n\n"
                "I deliver notifications and updates from the Rowan County "
                "IT team directly to your Teams.\n\n"
                "Commands:\n"
                "- **hello** -- greeting\n"
                "- **help** -- this message\n"
                "- **status** -- check if I'm operational\n"
            )
            await turn_context.send_activity(reply)
            self._log_message("out", BOT_NAME, None, reply)
        elif lower == "status":
            reply = f"**{BOT_NAME}** is operational (v{BOT_VERSION})."
            await turn_context.send_activity(reply)
            self._log_message("out", BOT_NAME, None, reply)
        else:
            reply = "I didn't understand that. Type **help** for available commands."
            await turn_context.send_activity(reply)
            self._log_message("out", BOT_NAME, None, reply)

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ):
        self._save_conversation_reference(turn_context.activity)
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    f"Hi, I'm **{BOT_NAME}** -- A bridge for Rowan County IT "
                    f"to send notifications via MS Teams. Type **help** for more info."
                )

    async def on_conversation_update_activity(self, turn_context: TurnContext):
        self._save_conversation_reference(turn_context.activity)
        await super().on_conversation_update_activity(turn_context)

    async def on_teams_channel_created(self, channel_info, team_info, turn_context):
        logger.info("Channel created: %s in team %s", channel_info, team_info)
        self._save_conversation_reference(turn_context.activity)

    async def on_installation_update_activity(self, turn_context: TurnContext):
        action = turn_context.activity.action
        logger.info("Installation update: %s", action)
        if action == "add":
            self._save_conversation_reference(turn_context.activity)
            await turn_context.send_activity(
                f"Hi, I'm **{BOT_NAME}** -- A bridge for Rowan County IT "
                f"to send notifications via MS Teams. Type **help** for more info."
            )
        elif action == "remove":
            key = self._make_key(turn_context.activity)
            if key and key in self.store._refs:
                del self.store._refs[key]
                self.store._save()
                logger.info("Removed conversation reference: %s", key)

    @staticmethod
    def _log_message(direction: str, user_name: str, user_id: str | None, text: str):
        try:
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "dir": direction,
                "user_name": user_name,
                "user_id": user_id,
                "text": text[:500],
            }
            with open(MSG_LOG_PATH, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def _save_conversation_reference(self, activity: Activity):
        ref = TurnContext.get_conversation_reference(activity)
        key = self._make_key(activity)
        if key:
            self.store.upsert(key, ref)

    @staticmethod
    def _make_key(activity: Activity) -> str | None:
        if activity.conversation:
            return activity.conversation.id
        return None
