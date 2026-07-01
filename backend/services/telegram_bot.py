from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from config import get_settings
from fetchers.agenda_fetcher import fetch_agenda_categories, split_csv
from fetchers.market_fetcher import fetch_market_data
from models.prediction import TelegramChat, TelegramMessage, TelegramUser
from services.monitor_report import build_daily_monitor_report, build_ipo_agenda, build_watchlist_summary
from services.telegram_client import TelegramClient, TelegramSendError

COMMAND_RE = re.compile(r"^/([A-Za-z0-9_]+)(?:@([A-Za-z0-9_]+))?(?:\s+(.*))?$", re.DOTALL)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
SYMBOL_RE = re.compile(r"\b[A-Z]{1,8}(?:[-.][A-Z]{1,6})?\b")
ADDRESS_PATTERNS: dict[str, re.Pattern[str]] = {
    "evm": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    "bitcoin": re.compile(r"\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}\b"),
    "tron": re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b"),
    "solana": re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b"),
}
STOP_WORDS = {
    "the", "and", "for", "with", "from", "this", "that", "please", "want", "check",
    "อยาก", "ขอ", "ช่วย", "ดู", "เช็ค", "ตรวจ", "หน่อย", "ครับ", "ค่ะ", "คะ", "ได้ไหม",
    "ข้อมูล", "อัปเดต", "อัพเดต", "บอท", "bot", "agent", "invest",
}
INTENT_TOPICS = {
    "start": "help",
    "help": "help",
    "ipo": "ipo",
    "ipo_hk": "ipo",
    "news": "news",
    "watchlist": "watchlist",
    "wallet_check": "wallet",
    "daily_report": "report",
    "market_symbol": "market",
    "ignored_command": "other",
    "unknown": "other",
    "non_text": "other",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def _extract_keywords(text: str | None) -> list[str]:
    if not text:
        return []
    cleaned = URL_RE.sub(" ", text)
    for pattern in ADDRESS_PATTERNS.values():
        cleaned = pattern.sub(" ", cleaned)
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9._-]{1,24}|[0-9]{2,8}|[\u0E00-\u0E7F]{2,}", cleaned)
    keywords: list[str] = []
    for token in tokens:
        value = token.strip("/.,!?;:()[]{}'\"").lower()
        if not value or value in STOP_WORDS or len(value) < 2:
            continue
        if value not in keywords:
            keywords.append(value)
    return keywords[:12]


def _command_parts(text: str) -> tuple[str | None, str | None, str]:
    match = COMMAND_RE.match(text.strip())
    if not match:
        return None, None, ""
    return match.group(1).lower(), (match.group(2) or "").lower() or None, (match.group(3) or "").strip()


def _extract_wallet_addresses(text: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for chain, pattern in ADDRESS_PATTERNS.items():
        for match in pattern.findall(text):
            if match in seen:
                continue
            if chain == "solana" and (match.startswith("0x") or match.startswith(("bc1", "1", "3", "T"))):
                continue
            seen.add(match)
            found.append({"chain": chain, "address": match})
    return found[:5]


def _extract_symbol(text: str) -> str | None:
    ignored = {"IPO", "HK", "HKEX", "NEWS", "WATCHLIST", "REPORT", "USD", "THE", "AND"}
    for match in SYMBOL_RE.findall(text.upper()):
        if match in ignored:
            continue
        if match == "BTC":
            return "BTC-USD"
        if match == "ETH":
            return "ETH-USD"
        return match
    return None


def resolve_telegram_intent(text: str | None) -> dict[str, Any]:
    text = text or ""
    normalized = _normalize_text(text)
    command, target_username, args = _command_parts(text)
    settings = get_settings()
    bot_username = settings.telegram_bot_username.strip("@").lower()
    keywords = _extract_keywords(text)

    if command and target_username and bot_username and target_username != bot_username:
        intent = "ignored_command"
    elif command in {"start"}:
        intent = "start"
    elif command in {"help"}:
        intent = "help"
    elif command in {"ipohk", "hkipo", "ipohongkong"}:
        intent = "ipo_hk"
    elif command in {"ipo", "ipos"}:
        intent = "ipo"
    elif command in {"news", "update", "updates"}:
        intent = "news"
    elif command in {"watchlist", "stocks", "list"}:
        intent = "watchlist"
    elif command in {"checkaddress", "wallet", "address"}:
        intent = "wallet_check"
    elif command in {"report", "summary", "daily"}:
        intent = "daily_report"
    elif command:
        intent = "unknown"
    elif _extract_wallet_addresses(text):
        intent = "wallet_check"
    elif any(word in normalized for word in ["ipohk", "hk ipo", "hkex", "hong kong ipo", "ipo ฮ่องกง", "ไอพีโอฮ่องกง", "หุ้น ipo ฮ่องกง"]):
        intent = "ipo_hk"
    elif any(word in normalized for word in ["ipo", "ไอพีโอ", "หุ้นเข้าใหม่", "ตารางจอง", "ตาราง ipo"]):
        intent = "ipo"
    elif any(word in normalized for word in ["ข่าว", "news", "น่าจับตา", "จับตา", "headline", "update"]):
        intent = "news"
    elif any(word in normalized for word in ["watchlist", "list หุ้น", "ลิสต์หุ้น", "หุ้นที่ควรติดตาม", "หุ้นน่าติดตาม", "ติดตามหุ้น"]):
        intent = "watchlist"
    elif any(word in normalized for word in ["กระเป๋า", "คริปโต", "wallet", "address", "ตรวจ address", "เช็ค address"]):
        intent = "wallet_check"
    elif any(word in normalized for word in ["สรุปตลาด", "daily report", "รายงาน", "ภาพรวมตลาด", "summary"]):
        intent = "daily_report"
    elif _extract_symbol(text):
        intent = "market_symbol"
    else:
        intent = "unknown"

    return {
        "intent": intent,
        "topic": INTENT_TOPICS.get(intent, "other"),
        "command": command,
        "args": args,
        "keywords": keywords,
    }


def _fmt_price(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if numeric >= 1000:
        return f"{numeric:,.2f}"
    if numeric >= 1:
        return f"{numeric:.2f}"
    return f"{numeric:.6f}"


def _fmt_pct(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/a"
    sign = "+" if numeric > 0 else ""
    return f"{sign}{numeric:.2f}%"


def _format_help() -> str:
    return "\n".join([
        "Agent Invest bot commands",
        "",
        "/news - noteworthy market news",
        "/watchlist - assets to monitor",
        "/ipo - IPO agenda",
        "/ipohk - Hong Kong IPO agenda",
        "/checkaddress <wallet> - identify crypto wallet and open explorers",
        "/report - full daily monitor",
        "",
        "Natural language works too, for example: 'อยากดู IPO ฮ่องกง', 'หุ้นที่ควรติดตาม', or 'อยากตรวจกระเป๋าคริปโต 0x...'.",
        "",
        "Disclaimer: automated monitoring only, not financial advice.",
    ])


def _format_ipo_reply(hk_only: bool = False) -> str:
    settings = get_settings()
    categories = fetch_agenda_categories(max_items=settings.telegram_private_report_max_news_items)
    items = build_ipo_agenda(categories)
    if hk_only:
        hk_items = []
        for item in items:
            haystack = " ".join(str(item.get(key) or "") for key in ["exchange", "source", "summary", "company", "link"]).lower()
            if "hk" in haystack or "hong kong" in haystack:
                hk_items.append(item)
        items = hk_items

    title = "HK IPO agenda" if hk_only else "IPO agenda"
    if not items:
        return f"{title}\n- No matching IPO items found from configured sources. Add guaranteed items in data/ipo_watchlist.json."

    lines = [title]
    for item in items[:8]:
        company = item.get("company") or "IPO update"
        exchange = item.get("exchange") or "exchange n/a"
        expected_date = item.get("expected_date") or "date n/a"
        status = item.get("status") or "watching"
        line = f"- {company} | {exchange} | {expected_date} | {status}"
        if item.get("link"):
            line += f"\n  {item['link']}"
        lines.append(line)
    return "\n".join(lines)


def _format_news_reply() -> str:
    settings = get_settings()
    categories = fetch_agenda_categories(max_items=settings.telegram_private_report_max_news_items)
    sections = [
        ("News to watch", "noteworthy_news"),
        ("Economic agenda", "economic_agenda"),
        ("Geopolitic risk", "geopolitic_prediction"),
    ]
    lines = ["Market news monitor"]
    found = False
    for label, key in sections:
        items = categories.get(key, [])[:4]
        if not items:
            continue
        found = True
        lines.extend(["", label])
        for item in items:
            title = item.get("title") or "Untitled"
            source = item.get("source") or "source n/a"
            line = f"- {title} ({source})"
            if item.get("link"):
                line += f"\n  {item['link']}"
            lines.append(line)
    if not found:
        lines.append("- No matching news detected from configured RSS sources.")
    return "\n".join(lines)


def _format_watchlist_reply() -> str:
    settings = get_settings()
    symbols = split_csv(settings.monitor_watchlist_symbols)
    items = build_watchlist_summary(symbols, max_assets=settings.telegram_private_report_max_assets)
    if not items:
        return "Watchlist\n- No watchlist assets configured."

    lines = ["Watchlist assets"]
    for item in items[: settings.telegram_private_report_max_assets]:
        symbol = item.get("symbol", "-")
        bias = item.get("bias", "watch")
        price = _fmt_price(item.get("price"))
        change = _fmt_pct(item.get("price_change_pct"))
        reasons = "; ".join(item.get("reasons", [])[:2])
        lines.append(f"- {symbol}: {price} ({change}) | {bias} | {reasons}")
    return "\n".join(lines)


def _format_market_symbol_reply(text: str) -> str:
    symbol = _extract_symbol(text)
    if not symbol:
        return "Send a symbol such as AAPL, NVDA, BTC, or ETH."
    data = fetch_market_data(symbol)
    lines = [f"{symbol} market snapshot"]
    lines.append(f"- Price: {_fmt_price(data.get('price'))}")
    lines.append(f"- Change: {_fmt_pct(data.get('price_change_pct'))}")
    if data.get("rsi_14") is not None:
        lines.append(f"- RSI 14: {data['rsi_14']}")
    if data.get("macd") is not None and data.get("macd_signal") is not None:
        lines.append(f"- MACD: {data['macd']} / signal {data['macd_signal']}")
    return "\n".join(lines)


def _format_wallet_reply(text: str) -> str:
    addresses = _extract_wallet_addresses(text)
    if not addresses:
        return "Send /checkaddress <wallet address>. I can identify EVM, Bitcoin, Tron, and Solana-style addresses and return explorer links."

    explorer_urls = {
        "evm": "https://etherscan.io/address/{address}",
        "bitcoin": "https://blockstream.info/address/{address}",
        "tron": "https://tronscan.org/#/address/{address}",
        "solana": "https://solscan.io/account/{address}",
    }
    labels = {
        "evm": "EVM-compatible address",
        "bitcoin": "Bitcoin address",
        "tron": "Tron address",
        "solana": "Solana-style address",
    }

    lines = ["Wallet check"]
    for item in addresses:
        chain = item["chain"]
        address = item["address"]
        lines.append(f"- {labels.get(chain, chain)}: {address}")
        lines.append(f"  {explorer_urls[chain].format(address=address)}")
    lines.append("Balance/risk scoring can be connected later with chain explorer APIs; this response is explorer-based.")
    return "\n".join(lines)


def build_telegram_reply(intent_info: dict[str, Any], text: str) -> str | None:
    intent = intent_info.get("intent", "unknown")
    try:
        if intent in {"start", "help", "unknown"}:
            return _format_help()
        if intent == "ipo_hk":
            return _format_ipo_reply(hk_only=True)
        if intent == "ipo":
            return _format_ipo_reply(hk_only=False)
        if intent == "news":
            return _format_news_reply()
        if intent == "watchlist":
            return _format_watchlist_reply()
        if intent == "wallet_check":
            return _format_wallet_reply(text)
        if intent == "daily_report":
            settings = get_settings()
            return build_daily_monitor_report(
                max_assets=settings.telegram_private_report_max_assets,
                max_news_items=settings.telegram_private_report_max_news_items,
            )["message"]
        if intent == "market_symbol":
            return _format_market_symbol_reply(text)
    except Exception as exc:
        return f"Could not fetch that data right now: {str(exc)[:180]}"
    return None


def _display_name(user: TelegramUser | None) -> str | None:
    if not user:
        return None
    if user.username:
        return f"@{user.username}"
    name = " ".join(part for part in [user.first_name, user.last_name] if part)
    return name or user.telegram_user_id


def _upsert_user(db: Session, raw_user: dict[str, Any] | None, now: datetime) -> TelegramUser | None:
    if not raw_user or raw_user.get("id") is None:
        return None
    telegram_user_id = str(raw_user.get("id"))
    user = db.query(TelegramUser).filter(TelegramUser.telegram_user_id == telegram_user_id).first()
    if not user:
        user = TelegramUser(telegram_user_id=telegram_user_id, first_seen_at=now)
        db.add(user)
    user.username = raw_user.get("username")
    user.first_name = raw_user.get("first_name")
    user.last_name = raw_user.get("last_name")
    user.language_code = raw_user.get("language_code")
    user.is_bot = bool(raw_user.get("is_bot", False))
    user.last_seen_at = now
    user.message_count = (user.message_count or 0) + 1
    return user


def _upsert_chat(db: Session, raw_chat: dict[str, Any], now: datetime) -> TelegramChat:
    telegram_chat_id = str(raw_chat.get("id"))
    chat = db.query(TelegramChat).filter(TelegramChat.telegram_chat_id == telegram_chat_id).first()
    if not chat:
        chat = TelegramChat(telegram_chat_id=telegram_chat_id, first_seen_at=now)
        db.add(chat)
    chat.chat_type = raw_chat.get("type") or "unknown"
    chat.title = raw_chat.get("title")
    chat.username = raw_chat.get("username")
    chat.last_seen_at = now
    chat.message_count = (chat.message_count or 0) + 1
    return chat


def _message_from_update(update: dict[str, Any]) -> dict[str, Any] | None:
    for key in ["message", "edited_message", "channel_post"]:
        value = update.get(key)
        if isinstance(value, dict):
            return value
    return None


def _should_reply(chat_type: str, text: str, intent_info: dict[str, Any]) -> bool:
    if chat_type == "private":
        return True
    if intent_info.get("intent") == "ignored_command":
        return False
    if intent_info.get("command"):
        return True
    username = get_settings().telegram_bot_username.strip("@").lower()
    return bool(username and f"@{username}" in text.lower())


def handle_telegram_update(update: dict[str, Any], db: Session) -> dict[str, Any]:
    message = _message_from_update(update)
    if not message:
        return {"ok": True, "handled": False, "reason": "unsupported_update"}

    update_id = str(update.get("update_id")) if update.get("update_id") is not None else None
    if update_id:
        existing = db.query(TelegramMessage).filter(TelegramMessage.telegram_update_id == update_id).first()
        if existing:
            return {"ok": True, "handled": True, "duplicate": True, "message_id": existing.id}

    now = _now()
    raw_chat = message.get("chat") or {}
    raw_user = message.get("from")
    text = message.get("text") or message.get("caption") or ""
    intent_info = resolve_telegram_intent(text) if text else {
        "intent": "non_text",
        "topic": "other",
        "command": None,
        "args": "",
        "keywords": [],
    }

    message_date = None
    if message.get("date") is not None:
        try:
            message_date = datetime.fromtimestamp(int(message["date"]), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            message_date = None

    user = _upsert_user(db, raw_user, now)
    chat = _upsert_chat(db, raw_chat, now)
    row = TelegramMessage(
        telegram_update_id=update_id,
        telegram_message_id=str(message.get("message_id")) if message.get("message_id") is not None else None,
        telegram_chat_id=chat.telegram_chat_id,
        telegram_user_id=user.telegram_user_id if user else None,
        chat_type=chat.chat_type,
        text=text or None,
        normalized_text=_normalize_text(text) if text else None,
        command=intent_info.get("command"),
        intent=intent_info.get("intent", "unknown"),
        topic=intent_info.get("topic", "other"),
        keywords=intent_info.get("keywords") or [],
        message_date=message_date,
        created_at=now,
        raw_update=update,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    if text and _should_reply(chat.chat_type, text, intent_info):
        reply = build_telegram_reply(intent_info, text)
        if reply:
            try:
                TelegramClient(channel_id=chat.telegram_chat_id).send_message(reply, chat_id=chat.telegram_chat_id)
                row.reply_status = "sent"
            except TelegramSendError as exc:
                row.reply_status = f"failed: {str(exc)[:120]}"
            except Exception as exc:
                row.reply_status = f"failed: {str(exc)[:120]}"
            db.commit()

    return {
        "ok": True,
        "handled": True,
        "message_id": row.id,
        "intent": row.intent,
        "topic": row.topic,
        "reply_status": row.reply_status,
    }


def build_telegram_analytics(
    db: Session,
    *,
    days: int = 7,
    chat_id: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    days = max(1, min(days, 365))
    limit = max(1, min(limit, 50))
    cutoff = _now() - timedelta(days=days)

    query = db.query(TelegramMessage).filter(TelegramMessage.created_at >= cutoff)
    if chat_id:
        query = query.filter(TelegramMessage.telegram_chat_id == chat_id)

    messages = query.order_by(TelegramMessage.created_at.asc()).all()
    total = len(messages)
    private_messages = sum(1 for msg in messages if msg.chat_type == "private")
    group_messages = sum(1 for msg in messages if msg.chat_type in {"group", "supergroup"})
    unique_users = len({msg.telegram_user_id for msg in messages if msg.telegram_user_id})
    active_chats = len({msg.telegram_chat_id for msg in messages if msg.telegram_chat_id})

    topic_counter = Counter(msg.topic or "unknown" for msg in messages)
    intent_counter = Counter(msg.intent or "unknown" for msg in messages)
    keyword_counter: Counter[str] = Counter()
    for msg in messages:
        for keyword in msg.keywords or []:
            keyword_counter[str(keyword)] += 1

    start_date = (_now().date() - timedelta(days=days - 1))
    daily = {
        (start_date + timedelta(days=offset)).isoformat(): {
            "date": (start_date + timedelta(days=offset)).isoformat(),
            "total": 0,
            "private": 0,
            "group": 0,
        }
        for offset in range(days)
    }
    for msg in messages:
        key = msg.created_at.date().isoformat()
        bucket = daily.setdefault(key, {"date": key, "total": 0, "private": 0, "group": 0})
        bucket["total"] += 1
        if msg.chat_type == "private":
            bucket["private"] += 1
        elif msg.chat_type in {"group", "supergroup"}:
            bucket["group"] += 1

    recent_rows = query.order_by(TelegramMessage.created_at.desc()).limit(limit).all()
    user_ids = {row.telegram_user_id for row in recent_rows if row.telegram_user_id}
    users = {}
    if user_ids:
        users = {
            user.telegram_user_id: user
            for user in db.query(TelegramUser).filter(TelegramUser.telegram_user_id.in_(user_ids)).all()
        }

    return {
        "days": days,
        "total_messages": total,
        "private_messages": private_messages,
        "group_messages": group_messages,
        "unique_users": unique_users,
        "active_chats": active_chats,
        "top_topics": [{"name": name, "count": count} for name, count in topic_counter.most_common(limit)],
        "top_intents": [{"name": name, "count": count} for name, count in intent_counter.most_common(limit)],
        "top_keywords": [{"name": name, "count": count} for name, count in keyword_counter.most_common(limit)],
        "daily_messages": list(daily.values()),
        "recent_messages": [
            {
                "created_at": row.created_at,
                "chat_id": row.telegram_chat_id,
                "chat_type": row.chat_type,
                "user_id": row.telegram_user_id,
                "display_name": _display_name(users.get(row.telegram_user_id)) if row.telegram_user_id else None,
                "text": (row.text[:180] + "...") if row.text and len(row.text) > 180 else row.text,
                "intent": row.intent,
                "topic": row.topic,
            }
            for row in recent_rows
        ],
    }
