from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from config import get_settings


class TelegramNotConfiguredError(RuntimeError):
    pass


class TelegramSendError(RuntimeError):
    pass


@dataclass(frozen=True)
class TelegramStatus:
    configured: bool
    bot_configured: bool
    channel_id: str | None
    community_chat_id: str | None
    paid_chat_id: str | None
    bot2_configured: bool
    bot2_channel_id: str | None
    daily_report_enabled: bool
    community_report_enabled: bool
    paid_report_enabled: bool


def _chunk_message(text: str, limit: int = 3900) -> list[str]:
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    while len(text) > limit:
        split_at = text.rfind("\n\n", 0, limit)
        if split_at < int(limit * 0.5):
            split_at = text.rfind("\n", 0, limit)
        if split_at < int(limit * 0.5):
            split_at = limit
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        chunks.append(text)
    return chunks


def normalize_chat_id(chat_id: str | None) -> str | None:
    """Telegram supergroup/channel ids have the form '-100' + digits. A common
    config mistake is storing them as a positive number (the leading '-' dropped),
    which makes every send fail with 'Bad Request: chat not found'. Restore the
    sign for that specific signature so a fat-fingered env var still works.

    Leaves @usernames, already-signed ids, and ordinary numbers untouched. Apply
    ONLY to configured broadcast targets (channels/groups) — never to per-user
    reply chat ids, whose positive sign is correct.
    """
    if not chat_id:
        return chat_id
    s = str(chat_id).strip()
    if s.startswith("-") or s.startswith("@"):
        return s
    # '-100' + 10-digit internal id => 13-digit positive form starting with '100'
    if s.isdigit() and s.startswith("100") and len(s) >= 13:
        return "-" + s
    return s


def _mask_channel(channel_id: str | None) -> str | None:
    if not channel_id:
        return None
    if len(channel_id) <= 8:
        return "***"
    return f"{channel_id[:4]}...{channel_id[-4:]}"


class TelegramClient:
    def __init__(self, bot_token: str | None = None, channel_id: str | None = None):
        settings = get_settings()
        self.bot_token = bot_token if bot_token is not None else settings.telegram_bot_token
        # Only the configured-channel fallback is normalized (a broadcast target);
        # an explicitly-passed channel_id may be a per-user reply id and is left as-is.
        self.channel_id = channel_id if channel_id is not None else normalize_chat_id(settings.telegram_channel_id)

    @property
    def bot_configured(self) -> bool:
        return bool(self.bot_token)

    @property
    def configured(self) -> bool:
        return bool(self.bot_token and self.channel_id)

    def status(self) -> TelegramStatus:
        settings = get_settings()
        return TelegramStatus(
            configured=self.configured,
            bot_configured=self.bot_configured,
            channel_id=_mask_channel(self.channel_id),
            community_chat_id=_mask_channel(settings.telegram_community_chat_id),
            paid_chat_id=_mask_channel(settings.telegram_paid_chat_id),
            bot2_configured=bool(settings.telegram_bot2_token and settings.telegram_bot2_channel_id),
            bot2_channel_id=_mask_channel(settings.telegram_bot2_channel_id),
            daily_report_enabled=settings.telegram_daily_report_enabled,
            community_report_enabled=settings.telegram_community_report_enabled,
            paid_report_enabled=settings.telegram_paid_report_enabled,
        )

    def _request(self, method: str, payload: dict[str, Any] | None = None, *, timeout: int = 15) -> dict[str, Any]:
        if not self.bot_configured:
            raise TelegramNotConfiguredError("TELEGRAM_BOT_TOKEN must be configured.")

        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        response = requests.post(url, json=payload or {}, timeout=timeout)
        try:
            body = response.json()
        except ValueError:
            body = {"description": response.text[:500]}

        if response.status_code >= 400 or not body.get("ok", False):
            description = body.get("description") or response.text[:500]
            raise TelegramSendError(f"Telegram {method} failed: {description}")
        return body

    def send_message_with_keyboard(
        self,
        text: str,
        *,
        chat_id: str | None = None,
        keyboard: list[list[dict[str, Any]]] | None = None,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        """Send a single message with an optional inline keyboard."""
        target = chat_id or self.channel_id
        if not self.bot_configured or not target:
            raise TelegramNotConfiguredError("Bot token and chat id required.")
        payload: dict[str, Any] = {
            "chat_id": target,
            "text": text[:3900],
            "disable_web_page_preview": True,
        }
        if keyboard:
            payload["reply_markup"] = {"inline_keyboard": keyboard}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return self._request("sendMessage", payload).get("result", {})

    def send_photo(
        self,
        photo_bytes: bytes,
        *,
        chat_id: str | None = None,
        caption: str | None = None,
        keyboard: list[list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        """Send a photo via multipart/form-data (sendPhoto)."""
        import json as _json
        target = chat_id or self.channel_id
        if not self.bot_configured or not target:
            raise TelegramNotConfiguredError("Bot token and chat id required.")
        url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        data: dict[str, str] = {"chat_id": str(target)}
        if caption:
            data["caption"] = caption[:1024]
        if keyboard:
            data["reply_markup"] = _json.dumps({"inline_keyboard": keyboard})
        resp = requests.post(
            url,
            data=data,
            files={"photo": ("chart.png", photo_bytes, "image/png")},
            timeout=30,
        )
        try:
            body = resp.json()
        except ValueError:
            body = {"description": resp.text[:500]}
        if resp.status_code >= 400 or not body.get("ok", False):
            raise TelegramSendError(f"sendPhoto failed: {body.get('description', '')}")
        return body.get("result", {})

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: str = "",
    ) -> dict[str, Any]:
        """Acknowledge an inline keyboard button press."""
        return self._request("answerCallbackQuery", {
            "callback_query_id": callback_query_id,
            "text": text[:200],
        })

    def send_message(
        self,
        text: str,
        *,
        chat_id: str | None = None,
        disable_web_page_preview: bool = True,
        parse_mode: str | None = None,
    ) -> list[dict[str, Any]]:
        target_chat_id = chat_id or self.channel_id
        if not self.bot_configured or not target_chat_id:
            raise TelegramNotConfiguredError(
                "TELEGRAM_BOT_TOKEN and a target chat id must be configured."
            )

        chunks = _chunk_message(text)
        if not chunks:
            return []

        results: list[dict[str, Any]] = []
        for chunk in chunks:
            payload: dict[str, Any] = {
                "chat_id": target_chat_id,
                "text": chunk,
                "disable_web_page_preview": disable_web_page_preview,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            results.append(self._request("sendMessage", payload).get("result", {}))
        return results

    @classmethod
    def all_configured_bots(cls) -> list["TelegramClient"]:
        """Return list of all configured bots (bot1 + bot2 if set)."""
        settings = get_settings()
        bots = []
        if settings.telegram_bot_token:
            bots.append(cls(bot_token=settings.telegram_bot_token,
                            channel_id=settings.telegram_channel_id))
        if settings.telegram_bot2_token and settings.telegram_bot2_channel_id:
            bots.append(cls(bot_token=settings.telegram_bot2_token,
                            channel_id=settings.telegram_bot2_channel_id))
        return bots

    def set_webhook(
        self,
        webhook_url: str,
        *,
        secret_token: str | None = None,
        drop_pending_updates: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "url": webhook_url,
            "drop_pending_updates": drop_pending_updates,
            "allowed_updates": ["message", "edited_message", "channel_post", "callback_query"],
        }
        if secret_token:
            payload["secret_token"] = secret_token
        return self._request("setWebhook", payload, timeout=20)

    def delete_webhook(self, *, drop_pending_updates: bool = False) -> dict[str, Any]:
        return self._request(
            "deleteWebhook",
            {"drop_pending_updates": drop_pending_updates},
            timeout=20,
        )

    def get_webhook_info(self) -> dict[str, Any]:
        return self._request("getWebhookInfo", timeout=20)

    def set_my_commands(self, commands: list[dict[str, str]], *,
                        scope: dict[str, Any] | None = None,
                        language_code: str | None = None) -> dict[str, Any]:
        """Register the "/" command menu. Without a scope this sets the DEFAULT
        scope; a more specific scope (e.g. all_private_chats) or a language-specific
        list overrides it, so we set several scopes explicitly to avoid a stale
        empty scope hiding the menu."""
        payload: dict[str, Any] = {"commands": commands}
        if scope:
            payload["scope"] = scope
        if language_code:
            payload["language_code"] = language_code
        return self._request("setMyCommands", payload, timeout=20)

    def delete_my_commands(self, *, scope: dict[str, Any] | None = None,
                           language_code: str | None = None) -> dict[str, Any]:
        """Clear commands for a scope/language so it falls back to the default set
        (used to remove a stale empty override)."""
        payload: dict[str, Any] = {}
        if scope:
            payload["scope"] = scope
        if language_code:
            payload["language_code"] = language_code
        return self._request("deleteMyCommands", payload, timeout=20)

    def set_chat_menu_button(self) -> dict[str, Any]:
        """Show the clickable "Menu" button next to the message input, which opens
        the command list on tap. Private chats only — Telegram's Bot API does not
        support a menu button in groups/supergroups; there, "/" autocomplete
        (set_my_commands) is the only entry point."""
        return self._request("setChatMenuButton", {"menu_button": {"type": "commands"}}, timeout=20)

    def get_my_commands(self, *, scope: dict[str, Any] | None = None,
                        language_code: str | None = None) -> dict[str, Any]:
        """Read the registered "/" command menu for a scope/language (verification)."""
        payload: dict[str, Any] = {}
        if scope:
            payload["scope"] = scope
        if language_code:
            payload["language_code"] = language_code
        return self._request("getMyCommands", payload, timeout=20)

    def get_me(self) -> dict[str, Any]:
        """getMe — identify which bot this token is (username, id) to rule out a
        wrong-bot mismatch."""
        return self._request("getMe", {}, timeout=20)


def broadcast_parallel(
    message: str,
    *,
    parse_mode: str | None = None,
    extra_targets: list[tuple[str, str]] | None = None,
) -> dict[str, str]:
    """
    Fire-and-forget: ส่งจาก bot1 (+ extra_targets ถ้ามี) พร้อมกัน ไม่ log DB

    bot2 ไม่รวมอัตโนมัติ — จัดการแยกผ่าน _log_and_send_bot2 ในฝั่งที่ต้องการ log

    Returns dict: {label: "ok" | error_message}
    """
    settings = get_settings()

    targets: list[tuple[str, str, str]] = []  # (label, token, chat_id)

    if settings.telegram_bot_token and settings.telegram_channel_id:
        targets.append(("bot1", settings.telegram_bot_token, normalize_chat_id(settings.telegram_channel_id)))

    for i, (token, chat_id) in enumerate(extra_targets or [], start=2):
        targets.append((f"extra{i}", token, normalize_chat_id(chat_id)))

    if not targets:
        return {}

    def _send(label: str, token: str, chat_id: str) -> tuple[str, str]:
        try:
            client = TelegramClient(bot_token=token, channel_id=chat_id)
            client.send_message(message, parse_mode=parse_mode)
            return label, "ok"
        except Exception as e:
            return label, str(e)

    results = {}
    with ThreadPoolExecutor(max_workers=len(targets)) as executor:
        futures = {executor.submit(_send, label, token, chat_id): label
                   for label, token, chat_id in targets}
        for future in as_completed(futures):
            label, status = future.result()
            results[label] = status

    return results
