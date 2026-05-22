#!/usr/bin/env python3
"""Bot Telegram langsung — tanpa Hermes / Gemini."""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from tracker.env import load_env_local
from tracker.router import is_tracker_message, route_message
from tracker import users

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("telegram_bot")

_API = "https://api.telegram.org/bot{token}/{method}"
_BOT_USERNAME: str | None = None
_BOT_ID: int | None = None


def _token() -> str:
    t = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not t:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN di .env.local")
    return t


def _api(method: str, payload: dict) -> dict:
    url = _API.format(token=_token(), method=method)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(body.get("description", "Telegram API error"))
    return body


def _bot_me() -> dict:
    global _BOT_USERNAME, _BOT_ID
    if _BOT_USERNAME is None:
        me = _api("getMe", {}).get("result", {})
        _BOT_USERNAME = (me.get("username") or "").lower()
        _BOT_ID = me.get("id")
    return {"username": _BOT_USERNAME or "", "id": _BOT_ID}


def _bot_username() -> str:
    return _bot_me()["username"]


def _is_group_chat(chat: dict) -> bool:
    return chat.get("type") in ("group", "supergroup")


def _group_mention_required() -> bool:
    return os.environ.get("TELEGRAM_GROUP_REQUIRE_MENTION", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _is_reply_to_this_bot(msg: dict) -> bool:
    reply = msg.get("reply_to_message") or {}
    sender = reply.get("from") or {}
    bot_id = _bot_me()["id"]
    if bot_id and sender.get("id") == bot_id:
        return True
    return bool(sender.get("is_bot") and not bot_id)


def _should_handle_in_group(msg: dict, text: str) -> bool:
    if _group_mention_required():
        if text.startswith("/"):
            return True
        bot = _bot_username()
        if bot and f"@{bot}" in text.lower():
            return True
    if _is_reply_to_this_bot(msg):
        return True
    return is_tracker_message(text)


def _sender_user_id(msg: dict) -> int | None:
    sender = msg.get("from") or {}
    uid = sender.get("id")
    if uid is not None:
        return int(uid)
    return None


def _strip_bot_mention(text: str) -> str:
    bot = _bot_username()
    if not bot:
        return text.strip()
    return re.sub(rf"@{re.escape(bot)}\s*", "", text, flags=re.IGNORECASE).strip()


def send_message(chat_id: int, text: str) -> None:
    # Telegram limit 4096 chars
    chunk = text[:4000]
    _api("sendMessage", {"chat_id": chat_id, "text": chunk})


def _ensure_polling() -> None:
    wh = _api("getWebhookInfo", {}).get("result", {})
    if wh.get("url"):
        _api("deleteWebhook", {"drop_pending_updates": False})
        logger.warning("Webhook dihapus agar polling lokal jalan.")


def run_polling() -> None:
    _ensure_polling()
    me = _bot_me()
    logger.info(
        "Bot aktif @%s (tanpa Gemini). Grup: matikan Group Privacy di @BotFather.",
        me["username"] or "?",
    )
    offset = 0
    while True:
        try:
            body = _api("getUpdates", {"timeout": 30, "offset": offset, "allowed_updates": ["message"]})
        except urllib.error.HTTPError as exc:
            logger.error("Telegram HTTP %s — retry 5s", exc.code)
            time.sleep(5)
            continue
        except Exception as exc:
            logger.error("Poll error: %s — retry 5s", exc)
            time.sleep(5)
            continue

        for upd in body.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or {}
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            if chat_id is None:
                continue
            user_id = _sender_user_id(msg)
            if user_id is None:
                continue
            text = msg.get("text") or msg.get("caption") or ""
            if not text:
                continue

            in_group = _is_group_chat(chat)
            text = _strip_bot_mention(text)
            if not text:
                continue

            if in_group and not _should_handle_in_group(msg, text):
                logger.debug("Grup abaikan: %r", text[:60])
                continue

            admin_reply = users.handle_admin_command(text, user_id)
            if admin_reply is not None:
                if users.is_admin(user_id):
                    send_message(chat_id, admin_reply)
                continue

            if not users.is_allowed(user_id):
                if in_group and not is_tracker_message(text):
                    continue
                logger.info("Blocked user_id=%s chat=%s", user_id, chat_id)
                try:
                    send_message(
                        chat_id,
                        f"⛔ User {user_id} belum terdaftar. Minta admin: tambah user {user_id}",
                    )
                except Exception:
                    pass
                continue

            logger.info("user=%s chat=%s text=%r", user_id, chat_id, text[:80])
            try:
                reply = route_message(text, user_id)
                send_message(chat_id, reply)
            except Exception as exc:
                logger.exception("handle failed")
                try:
                    send_message(chat_id, f"❌ Error internal: {exc}")
                except Exception:
                    pass


def main() -> None:
    load_env_local()
    users.ensure_loaded()
    run_polling()


if __name__ == "__main__":
    main()
