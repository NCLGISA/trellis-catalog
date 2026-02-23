"""
Teams Bot Server -- persistent aiohttp web server for Bot Framework webhook.

Endpoints:
  POST /api/messages      Bot Framework webhook (Azure Bot Service routes here)
  GET  /api/health        Health check (Docker healthcheck, tools)
  GET  /api/conversations List stored conversation references (localhost)
  POST /api/send          Send proactive message (localhost, used by Tendril tools)
"""

import json
import logging
import os
import sys
import traceback
from http import HTTPStatus

from aiohttp import web
from aiohttp.web import Request, Response
from botbuilder.core import TurnContext
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.integration.aiohttp import (
    CloudAdapter,
    ConfigurationBotFrameworkAuthentication,
)
from botbuilder.schema import Activity, ActivityTypes

logging.basicConfig(
    level=logging.INFO,
    format="[teams-bot] %(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("teams-bot-server")

try:
    from dotenv import load_dotenv

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass


class BotConfig:
    PORT = int(os.environ.get("TEAMS_BOT_PORT", 3978))
    APP_ID = os.environ.get("TEAMS_BOT_APP_ID", "")
    APP_PASSWORD = os.environ.get("TEAMS_BOT_APP_SECRET", "")
    APP_TENANTID = os.environ.get("TEAMS_BOT_TENANT_ID", "")
    APP_TYPE = "SingleTenant"


CONFIG = BotConfig()

ADAPTER = CloudAdapter(ConfigurationBotFrameworkAuthentication(CONFIG))


async def on_error(context: TurnContext, error: Exception):
    logger.error("Unhandled error: %s", error)
    traceback.print_exc()
    await context.send_activity("The bot encountered an error. Check bridge logs.")


ADAPTER.on_turn_error = on_error

from bot_handler import TeamsBotHandler, get_store  # noqa: E402

BOT = TeamsBotHandler()


async def handle_messages(req: Request) -> Response:
    return await ADAPTER.process(req, BOT)


async def handle_health(req: Request) -> Response:
    store = get_store()
    return web.json_response(
        {
            "status": "ok",
            "mode": "webhook",
            "bot_name": os.environ.get("TEAMS_BOT_NAME", "Tendril Bot"),
            "conversations_tracked": store.count,
            "app_id_configured": bool(CONFIG.APP_ID),
        },
        status=HTTPStatus.OK,
    )


async def handle_conversations(req: Request) -> Response:
    if not _is_localhost(req):
        return Response(status=HTTPStatus.FORBIDDEN, text="localhost only")
    store = get_store()
    return web.json_response(store.get_all(), status=HTTPStatus.OK)


async def handle_send(req: Request) -> Response:
    """Send a proactive message. Body: {"conversation_id": "...", "message": "..."}"""
    if not _is_localhost(req):
        return Response(status=HTTPStatus.FORBIDDEN, text="localhost only")

    try:
        body = await req.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"error": "Invalid JSON"}, status=HTTPStatus.BAD_REQUEST
        )

    conversation_id = body.get("conversation_id")
    message = body.get("message", "")
    if not conversation_id or not message:
        return web.json_response(
            {"error": "conversation_id and message required"},
            status=HTTPStatus.BAD_REQUEST,
        )

    store = get_store()
    ref_data = store.get(conversation_id)
    if not ref_data or "_raw" not in ref_data:
        return web.json_response(
            {"error": f"No conversation reference for {conversation_id}"},
            status=HTTPStatus.NOT_FOUND,
        )

    from botbuilder.schema import ConversationReference

    raw = ref_data["_raw"]
    conv_ref = ConversationReference(**raw)

    sent = False

    async def _send_callback(turn_context: TurnContext):
        nonlocal sent
        await turn_context.send_activity(Activity(type=ActivityTypes.message, text=message))
        sent = True

    try:
        await ADAPTER.continue_conversation(conv_ref, _send_callback, CONFIG.APP_ID)
    except Exception as exc:
        logger.error("Proactive send failed: %s", exc)
        return web.json_response(
            {"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

    return web.json_response({"ok": sent, "conversation_id": conversation_id})


def _is_localhost(req: Request) -> bool:
    peer = req.remote
    return peer in ("127.0.0.1", "::1", "localhost", None)


APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/messages", handle_messages)
APP.router.add_get("/api/health", handle_health)
APP.router.add_get("/api/conversations", handle_conversations)
APP.router.add_post("/api/send", handle_send)

if __name__ == "__main__":
    logger.info("Starting bot server on port %d", CONFIG.PORT)
    web.run_app(APP, host="0.0.0.0", port=CONFIG.PORT)
