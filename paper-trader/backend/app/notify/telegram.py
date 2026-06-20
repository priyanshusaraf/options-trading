"""Telegram Bot API sender.

Credentials come from TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (via .env / env vars,
loaded by Settings). If either is missing, `send` is a no-op returning False — the
feature is simply off. Network errors are caught and logged, never raised, so a
flaky network can never take down the engine.

Setup: message @BotFather to create a bot and get the token; message your new bot
once, then GET https://api.telegram.org/bot<token>/getUpdates to read your chat id.
"""
from __future__ import annotations

import os

import httpx

from app.core.config import get_settings
from app.core.logging import log


def _creds() -> tuple[str, str]:
    s = get_settings()
    token = s.telegram_bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = s.telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    return token, chat_id


def configured() -> bool:
    token, chat_id = _creds()
    return bool(token and chat_id)


def send(text: str) -> bool:
    token, chat_id = _creds()
    if not (token and chat_id):
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=5.0,
        )
        if r.status_code != 200:
            log.warn(f"telegram send non-200: {r.status_code}")
        return r.status_code == 200
    except Exception as e:  # network/DNS/timeout — never propagate
        log.warn(f"telegram send failed: {e}")
        return False
