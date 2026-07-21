from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from config import get_settings
from fetchers.agenda_fetcher import fetch_agenda_categories, split_csv
from fetchers.market_fetcher import fetch_market_data
from models.prediction import TelegramChat, TelegramMessage, TelegramUser
from services.monitor_report import build_daily_monitor_report, build_ipo_agenda, build_watchlist_summary
from services.telegram_client import TelegramClient, TelegramSendError


@dataclass
class TelegramReply:
    text: str | None = None
    keyboard: list[list[dict[str, Any]]] | None = None
    photo_bytes: bytes | None = None   # PNG — triggers sendPhoto instead of sendMessage
    caption: str | None = None         # caption shown below photo

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
    "analyze_symbol": "analysis",
    "chart_symbol": "chart",
    "portfolio": "portfolio",
    "watch": "watch",
    "compare": "compare",
    "earnings": "calendar",
    "menu": "help",
    "ai_chat": "chat",
    "set_tier": "admin",
    "my_status": "status",
    "alert": "alert",
    "ignored_command": "other",
    "unknown": "other",
    "non_text": "other",
}

# ในกลุ่ม บอททำหน้าที่ "รายงาน" เท่านั้น (ข่าว / งบไตรมาส / IPO) — intent อื่น
# เช่น AI chat, portfolio, analyze ใช้ได้เฉพาะแชทส่วนตัว จะตอบ redirect ไป DM แทน
GROUP_ALLOWED_INTENTS = {
    "news", "ipo", "ipo_hk", "earnings", "daily_report", "watchlist",
    "help", "start", "menu",
}
# intent เหล่านี้ในกลุ่มให้เงียบไปเลย (กันสแปมจากคำสั่งของบอทตัวอื่น/ข้อความทั่วไป)
GROUP_SILENT_INTENTS = {"unknown", "ignored_command", "non_text"}


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


# หุ้นเอเชียเป็นรหัสตัวเลข + suffix ตลาด เช่น 0700.HK (ฮ่องกง), 600519.SS (เซี่ยงไฮ้),
# 000001.SZ (เซินเจิ้น) — yfinance ใช้ฟอร์แมตนี้
CN_HK_RE = re.compile(r"\b(\d{1,6})\.(HK|SS|SZ|SH|TW|BK)\b", re.IGNORECASE)
_CRYPTO_ALIASES = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT"}


def _resolve_symbol(raw: str | None) -> str | None:
    """Normalize a user-typed ticker to a yfinance symbol. Handles crypto
    shortcuts and Chinese/HK numeric tickers (pads HK codes to 4 digits,
    maps Shanghai SH->SS)."""
    if not raw:
        return None
    s = raw.strip().upper()
    if not s:
        return None
    if s in _CRYPTO_ALIASES:
        return f"{s}-USD"
    m = re.fullmatch(r"(\d{1,6})\.(HK|SS|SZ|SH|TW|BK)", s)
    if m:
        num, suf = m.group(1), m.group(2)
        if suf == "SH":
            suf = "SS"
        if suf == "HK":
            num = num.zfill(4)   # เช่น 700 -> 0700
        return f"{num}.{suf}"
    return s


def _extract_symbol(text: str) -> str | None:
    ignored = {
        "IPO", "HK", "HKEX", "NEWS", "WATCHLIST", "REPORT", "USD", "THE", "AND",
        "GRAPH", "CHART", "PRICE", "ANALYZE", "AI", "MENU",
    }
    up = text.upper()
    # หุ้นจีน/ฮ่องกงแบบรหัสตัวเลข + suffix ตลาด (ตรวจก่อนเพราะ regex ทั่วไปจับไม่ได้)
    m = CN_HK_RE.search(up)
    if m:
        return _resolve_symbol(m.group(0))
    for match in SYMBOL_RE.findall(up):
        if match in ignored:
            continue
        return _resolve_symbol(match)
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
    elif command in {"start"} and args.strip() in {"portfolio", "watch"}:
        # Deep-link payload from the "open in private chat" button shown when a
        # personal command was blocked in a group (t.me/<bot>?start=portfolio).
        intent = args.strip()
        args = ""
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
    elif command in {"analyze", "ai", "วิเคราะห์"}:
        intent = "analyze_symbol"
    elif command in {"chart", "price", "กราฟ", "กราฟราคา", "graph", "graphs"}:
        intent = "chart_symbol"
    elif command in {"portfolio", "port", "holdings", "port"}:
        intent = "portfolio"
    elif command in {"watch", "mywatch", "mylist"}:
        intent = "watch"
    elif command in {"compare", "vs"}:
        intent = "compare"
    elif command in {"earnings", "quarter", "quarterly"}:
        intent = "earnings"
    elif command in {"menu", "shortcuts"}:
        intent = "menu"
    elif command in {"alert", "alerts", "แจ้งเตือน"}:
        intent = "alert"
    elif command in {"settier"}:
        intent = "set_tier"
    elif command in {"me", "status", "tier", "myplan", "plan"}:
        intent = "my_status"
    elif command:
        intent = "unknown"
    elif _extract_wallet_addresses(text):
        intent = "wallet_check"
    elif any(word in normalized for word in ["ipohk", "hk ipo", "hkex", "hong kong ipo", "ipo ฮ่องกง", "ไอพีโอฮ่องกง", "หุ้น ipo ฮ่องกง"]):
        intent = "ipo_hk"
    elif any(word in normalized for word in ["ipo", "ไอพีโอ", "หุ้นเข้าใหม่", "ตารางจอง", "ตาราง ipo"]):
        intent = "ipo"
    elif any(word in normalized for word in ["งบไตรมาส", "ประกาศงบ", "งบการเงิน", "earnings"]):
        intent = "earnings"
    elif any(word in normalized for word in ["ข่าว", "news", "น่าจับตา", "จับตา", "headline", "update"]):
        intent = "news"
    elif any(word in normalized for word in ["watchlist", "list หุ้น", "ลิสต์หุ้น", "หุ้นที่ควรติดตาม", "หุ้นน่าติดตาม", "ติดตามหุ้น"]):
        intent = "watchlist"
    elif any(word in normalized for word in ["กระเป๋า", "คริปโต", "wallet", "address", "ตรวจ address", "เช็ค address"]):
        intent = "wallet_check"
    elif any(word in normalized for word in ["สรุปตลาด", "daily report", "รายงาน", "ภาพรวมตลาด", "summary"]):
        intent = "daily_report"
    elif any(word in normalized for word in ["graph", "chart", "กราฟ", "ตีกราฟ"]) and _extract_symbol(text):
        intent = "chart_symbol"
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


# ---------------------------------------------------------------------------
# Inline keyboard helpers
# ---------------------------------------------------------------------------

def _market_keyboard(symbol: str) -> list[list[dict[str, Any]]]:
    return [
        [
            {"text": "📊 วิเคราะห์ AI", "callback_data": f"analyze:{symbol}"},
            {"text": "📈 Chart 7d",     "callback_data": f"chart:{symbol}"},
        ],
        [
            {"text": "➕ เพิ่ม Port",   "callback_data": f"port_add:{symbol}"},
            {"text": "💼 Port ของฉัน", "callback_data": "port_view"},
        ],
    ]


def _bot_dm_url() -> str | None:
    username = get_settings().telegram_bot_username.strip("@")
    return f"https://t.me/{username}" if username else None


def _menu_reply(chat_type: str) -> TelegramReply:
    """เมนูคีย์ลัดแบบปุ่มกด — ชุดปุ่มต่างกันตามประเภทแชท:
    private = ครบทุกฟีเจอร์, group = เฉพาะรายงาน (ข่าว/งบ/IPO) + ปุ่มลิงก์ไป DM."""
    if chat_type == "private":
        keyboard: list[list[dict[str, Any]]] = [
            [
                {"text": "💬 คุยกับ AI", "callback_data": "askai"},
            ],
            [
                {"text": "💼 พอร์ตของฉัน", "callback_data": "port_view"},
                {"text": "📋 Watchlist",    "callback_data": "watch_view"},
            ],
            [
                {"text": "📰 ข่าววันนี้",   "callback_data": "news"},
                {"text": "🗓 IPO",          "callback_data": "ipo"},
            ],
            [
                {"text": "📅 งบไตรมาส",     "callback_data": "earnings"},
                {"text": "📊 รายงานเต็ม",   "callback_data": "report"},
            ],
            [
                {"text": "👤 แพ็กเกจ/สิทธิ์", "callback_data": "me"},
                {"text": "❓ วิธีใช้",       "callback_data": "help"},
            ],
        ]
        text = (
            "⚡ เมนูคีย์ลัด — กดปุ่มได้เลย\n\n"
            "หรือพิมพ์คุยกับ AI ได้ตรงนี้เลย เช่น\n"
            "“พอร์ตฉันเป็นยังไงบ้าง” “NVDA ยังน่าถือไหม”"
        )
    else:
        keyboard = [
            [
                {"text": "📰 ข่าววันนี้",   "callback_data": "news"},
                {"text": "🗓 IPO",          "callback_data": "ipo"},
            ],
            [
                {"text": "📅 งบไตรมาส",     "callback_data": "earnings"},
                {"text": "📊 รายงานเต็ม",   "callback_data": "report"},
            ],
        ]
        dm_url = _bot_dm_url()
        if dm_url:
            keyboard.append([{"text": "💬 แชทกับ AI ส่วนตัว", "url": dm_url}])
        text = "⚡ เมนูรายงาน (ในกลุ่มใช้ได้เฉพาะรายงาน — แชท AI/พอร์ต ทักส่วนตัว)"
    return TelegramReply(text=text, keyboard=keyboard)


def _group_redirect_reply() -> TelegramReply:
    """ตอบในกลุ่มเมื่อมีคนเรียกฟีเจอร์ที่เปิดเฉพาะแชทส่วนตัว (AI chat / พอร์ต / วิเคราะห์)."""
    keyboard = None
    dm_url = _bot_dm_url()
    if dm_url:
        keyboard = [[{"text": "💬 เปิดแชทส่วนตัวกับบอท", "url": dm_url}]]
    return TelegramReply(
        text=(
            "ฟีเจอร์นี้ใช้ได้เฉพาะแชทส่วนตัวกับบอทครับ 🙏\n"
            "ในกลุ่มผมรายงานได้เฉพาะ: /news ข่าว · /earnings งบไตรมาส · /ipo ตาราง IPO · /report สรุปตลาด"
        ),
        keyboard=keyboard,
    )


def _format_earnings_reply() -> str:
    """ปฏิทินงบรายไตรมาส (earnings) + ex-dividend ที่กำลังมาถึง จาก CalendarEvent ใน DB."""
    from fetchers.calendar_fetcher import get_upcoming_events
    events = get_upcoming_events(days_ahead=30)
    earnings = [e for e in events if e.get("event_type") == "earnings"]
    dividends = [e for e in events if e.get("event_type") == "dividend"]

    if not earnings and not dividends:
        return (
            "📅 งบรายไตรมาส\n"
            "- ยังไม่มีกำหนดการงบใน 30 วันข้างหน้า (หรือระบบยังไม่ได้ refresh ปฏิทิน)\n"
            "ระบบอัปเดตปฏิทินอัตโนมัติทุกวัน — ลองใหม่ภายหลัง"
        )

    lines = ["📅 งบรายไตรมาส 30 วันข้างหน้า"]
    for e in earnings[:10]:
        days = e.get("days_until", 0)
        when = "วันนี้" if days == 0 else f"อีก {days} วัน"
        lines.append(f"- {e.get('symbol') or '-'}: {e['event_date']} ({when})")
    if dividends:
        lines.append("")
        lines.append("💰 Ex-dividend")
        for e in dividends[:5]:
            lines.append(f"- {e.get('symbol') or '-'}: {e['event_date']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AI chat (private เท่านั้น) — คุยกับ LLM โดยรู้ portfolio/watchlist ของผู้ใช้
# ---------------------------------------------------------------------------

AI_CHAT_SYSTEM_PROMPT = """คุณคือ Agent Invest ผู้ช่วยการลงทุนส่วนตัวใน Telegram ตอบเป็นภาษาไทย
กติกา:
- ตอบกระชับ ตรงคำถาม เหมาะกับหน้าจอมือถือ (ไม่เกิน ~10 บรรทัด) ไม่ใช้ markdown
- คุณเห็นข้อมูล portfolio และ watchlist ของผู้ใช้ (แนบมาใน context) — ใช้อ้างอิงเมื่อเกี่ยวข้อง
- ถ้าถูกถามความเห็นเรื่องหุ้น ให้วิเคราะห์จากข้อมูลที่มีอย่างระมัดระวัง และเตือนว่าไม่ใช่คำแนะนำการลงทุน
- ถ้าคำถามต้องใช้ข้อมูลสดที่ไม่มีใน context แนะนำคำสั่งที่เหมาะ เช่น /analyze SYMBOL, /chart SYMBOL, /news, /earnings
- ห้ามแต่งตัวเลขราคา/ข้อมูลที่ไม่มีใน context เด็ดขาด"""


# ── Few-shot ที่เรียนรู้จาก feedback: ดึงคำตอบที่ผู้ใช้กด 👍 มาเป็นตัวอย่างน้ำเสียง/รูปแบบ
# แคชไว้ (TTL) เพื่อไม่ต้อง query DB ทุกครั้งที่แชท ระบบยิ่งใช้ยิ่งปรับตัวตามที่ผู้ใช้ชอบ
_FEWSHOT_CACHE: dict[str, Any] = {"text": "", "ts": 0.0}
_FEWSHOT_TTL_SEC = 900        # รีเฟรชทุก 15 นาที
_FEWSHOT_MAX = 3              # จำนวนตัวอย่างสูงสุด


def _chat_system_prompt(db: Session | None) -> str:
    """ระบบ prompt พื้นฐาน + few-shot จากคำตอบที่ได้ 👍 บ่อย (auto-improve)."""
    if db is None:
        return AI_CHAT_SYSTEM_PROMPT
    import time
    now_ts = time.monotonic()
    if now_ts - _FEWSHOT_CACHE["ts"] > _FEWSHOT_TTL_SEC:
        _FEWSHOT_CACHE["text"] = _build_few_shot(db)
        _FEWSHOT_CACHE["ts"] = now_ts
    block = _FEWSHOT_CACHE["text"]
    return AI_CHAT_SYSTEM_PROMPT + block


def _build_few_shot(db: Session) -> str:
    try:
        from models.chat_feedback import AiChatInteraction
        rows = (
            db.query(AiChatInteraction)
            .filter(AiChatInteraction.rating == 1)
            .order_by(AiChatInteraction.rated_at.desc())
            .limit(_FEWSHOT_MAX * 3)
            .all()
        )
    except Exception:
        return ""
    seen: set[str] = set()
    examples: list[str] = []
    for r in rows:
        q = (r.question or "").strip().replace("\n", " ")[:120]
        a = (r.answer or "").strip().replace("\n", " ")[:240]
        key = q.lower()
        if not q or not a or key in seen:
            continue
        seen.add(key)
        examples.append(f"ผู้ใช้: {q}\nตอบที่ดี: {a}")
        if len(examples) >= _FEWSHOT_MAX:
            break
    if not examples:
        return ""
    return ("\n\nตัวอย่างคำตอบที่ผู้ใช้พอใจ (ใช้เป็นแนวทางน้ำเสียง ความยาว และรูปแบบ "
            "ไม่ต้องลอกเนื้อหา):\n" + "\n---\n".join(examples))


def _is_bare_symbol(text: str) -> bool:
    """True เมื่อข้อความเป็นแค่ ticker เดี่ยวๆ ที่ตั้งใจพิมพ์เป็น ticker — ตอบ snapshot เร็ว
    เงื่อนไข: พิมพ์ตัวใหญ่ทั้งหมด ("NVDA") หรือเป็น alias คริปโตที่คนพิมพ์เล็กจนชิน ("btc")
    คำอังกฤษพิมพ์เล็กทั่วไป ("hello", "nvda") ให้ AI ตอบแทน — AI เห็นราคาสดใน context อยู่แล้ว
    ส่วนประโยคที่มี ticker ปนอยู่ (เช่น "ควรขาย NVDA ไหม") ให้ AI ตอบเช่นกัน."""
    stripped = text.strip()
    if not re.fullmatch(r"[A-Za-z]{1,8}(?:[-.][A-Za-z]{1,6})?", stripped):
        return False
    return stripped.isupper() or stripped.lower() in {"btc", "eth", "btc-usd", "eth-usd"}


def _ai_chat_context(telegram_user_id: str | None, db: Session | None, text: str = "") -> str:
    """รวบรวม context ส่วนตัว (portfolio + watchlist + ราคาหุ้นที่ถามถึง + ข้อความล่าสุด) ให้ LLM."""
    parts: list[str] = []
    symbol = (_extract_symbol(text) if text else None) or _get_context_symbol(telegram_user_id, db)
    if symbol:
        try:
            data = fetch_market_data(symbol)
            parts.append(
                f"=== ราคาล่าสุด {symbol} (หัวข้อที่กำลังคุย) ===\n"
                f"ราคา {_fmt_price(data.get('price'))} | เปลี่ยนแปลง {_fmt_pct(data.get('price_change_pct'))}"
                + (f" | RSI14 {data['rsi_14']}" if data.get("rsi_14") is not None else "")
            )
        except Exception:
            pass
    if telegram_user_id and db:
        try:
            parts.append("=== Portfolio ของผู้ใช้ (ราคาปัจจุบัน + P&L) ===\n" + _portfolio_view(telegram_user_id, db))
        except Exception:
            pass
        try:
            from models.watchlist import UserWatchlist
            symbols = [
                r.symbol for r in db.query(UserWatchlist)
                .filter(UserWatchlist.telegram_user_id == telegram_user_id).all()
            ]
            if symbols:
                parts.append("=== Watchlist ส่วนตัว ===\n" + ", ".join(symbols))
        except Exception:
            pass
        try:
            # ข้อความล่าสุดของผู้ใช้ (ตัวล่าสุดสุดคือข้อความปัจจุบัน — ข้าม)
            recent = (
                db.query(TelegramMessage)
                .filter(
                    TelegramMessage.telegram_user_id == telegram_user_id,
                    TelegramMessage.chat_type == "private",
                    TelegramMessage.text.isnot(None),
                )
                .order_by(TelegramMessage.created_at.desc())
                .limit(7)
                .all()
            )
            previous = [r.text for r in recent[1:] if r.text]
            if previous:
                parts.append(
                    "=== ข้อความก่อนหน้าของผู้ใช้ (ใหม่→เก่า ใช้เข้าใจบริบทการสนทนา) ===\n"
                    + "\n".join(f"- {t[:150]}" for t in previous[:6])
                )
        except Exception:
            pass
    return "\n\n".join(parts) if parts else "(ผู้ใช้ยังไม่มี portfolio/watchlist)"


# throttle ต่อ user กันสแปมเผาโควตา LLM — in-memory พอ (โปรเซสเดียว, รีเซ็ตตอน restart ไม่เป็นไร)
_AI_CHAT_LAST_CALL: dict[str, float] = {}
_AI_CHAT_MIN_INTERVAL_SEC = 3.0


def _ai_chat_throttled(telegram_user_id: str | None) -> bool:
    """True = ถามถี่เกินไป (และบันทึกเวลาเรียกล่าสุดเมื่อผ่าน)."""
    if not telegram_user_id:
        return False
    import time
    now_ts = time.monotonic()
    last = _AI_CHAT_LAST_CALL.get(telegram_user_id, 0.0)
    if now_ts - last < _AI_CHAT_MIN_INTERVAL_SEC:
        return True
    _AI_CHAT_LAST_CALL[telegram_user_id] = now_ts
    return False


# timeframe tokens ที่รับได้ — ตรงกับ TF_SPEC ใน telegram_chart (1w..5y)
# รองรับพิมพ์แบบไทยด้วย เช่น "5ปี", "1 ปี"
GRAPH_TF_TOKENS = ["1w", "1m", "3m", "6m", "1y", "2y", "3y", "4y", "5y"]
_TF_THAI = {"1ปี": "1y", "2ปี": "2y", "3ปี": "3y", "4ปี": "4y", "5ปี": "5y",
            "6เดือน": "6m", "3เดือน": "3m", "1เดือน": "1m"}


def _parse_graph_timeframe(text: str, default: str = "1y") -> str:
    """หา timeframe token ในข้อความ เช่น '1y', '5y', '6m' หรือ '5ปี' คืนคีย์ของ TF_SPEC
    (default = 1 ปี ตามที่ผู้ใช้อยากเห็นภาพรวมระยะยาว)."""
    low = text.lower()
    for tok in GRAPH_TF_TOKENS:
        if re.search(rf"\b{tok}\b", low):
            return tok
    compact = low.replace(" ", "")
    for th, key in _TF_THAI.items():
        if th in compact:
            return key
    return default


def _extract_symbols(text: str, limit: int = 4) -> list[str]:
    """ดึงหลาย ticker จากข้อความ (คั่นด้วย vs / , / เว้นวรรค) สำหรับโหมดเปรียบเทียบ."""
    out: list[str] = []
    for tok in re.split(r"\s+|,|\bvs\b|\bกับ\b", text, flags=re.IGNORECASE):
        if not tok.strip():
            continue
        sym = _extract_symbol(tok)
        if sym and sym not in out:
            out.append(sym)
        if len(out) >= limit:
            break
    return out


def _is_admin(telegram_user_id: str | None) -> bool:
    """แอดมิน = user id ที่อยู่ใน TELEGRAM_UNLIMITED_USER_IDS (เจ้าของ/ผู้ดูแล)."""
    if not telegram_user_id:
        return False
    ids = {s.strip() for s in split_csv(get_settings().telegram_unlimited_user_ids)}
    return telegram_user_id in ids


def _my_status_reply(telegram_user_id: str | None, db: Session | None) -> TelegramReply:
    """แสดง tier + สิทธิ์คงเหลือของวันนี้ให้ผู้ใช้ (customer-facing)."""
    if not telegram_user_id or not db:
        return TelegramReply(text="ดูสถานะได้เฉพาะในแชทส่วนตัวกับบอทครับ")
    from services.tiers import get_user_tier, quota_for, TIER_LABELS
    from services.usage import peek_quota

    tier = get_user_tier(db, telegram_user_id)
    unlimited_wl = _is_admin(telegram_user_id)
    lines = [f"👤 แพ็กเกจของคุณ: {TIER_LABELS.get(tier, tier)}" + ("  (unlimited)" if unlimited_wl else "")]
    lines.append("")
    lines.append("สิทธิ์คงเหลือวันนี้:")
    feature_labels = [("analyze", "🧠 วิเคราะห์ AI"), ("graph", "📈 ตีกราฟ"), ("chat", "💬 แชท AI")]
    for feature, label in feature_labels:
        limit = quota_for(db, telegram_user_id, feature)
        if limit <= 0 or unlimited_wl:
            lines.append(f"• {label}: ไม่จำกัด")
        else:
            q = peek_quota(db, telegram_user_id, feature, limit)
            remaining = max(0, limit - q.used)
            lines.append(f"• {label}: เหลือ {remaining}/{limit} ครั้ง")
    lines.append("")
    lines.append("สิทธิ์รีเซ็ตทุกเที่ยงคืน (เวลาไทย) — อยากอัปเกรดแพ็กเกจแจ้งแอดมินได้ครับ")
    return TelegramReply(text="\n".join(lines), keyboard=[[{"text": "⚡ เมนู", "callback_data": "menu"}]])


def _set_tier_reply(args: str, caller_id: str | None, db: Session | None) -> TelegramReply:
    """/settier <user_id> <tier> — เฉพาะแอดมิน (TELEGRAM_UNLIMITED_USER_IDS)."""
    if not _is_admin(caller_id) or not db:
        return TelegramReply(text="คำสั่งนี้ใช้ได้เฉพาะแอดมินครับ")
    from services.tiers import set_user_tier, TIERS, TIER_LABELS
    parts = args.split()
    if len(parts) < 2:
        return TelegramReply(
            text=f"รูปแบบ: /settier <user_id> <tier>\ntier ที่ใช้ได้: {', '.join(TIERS)}\nตัวอย่าง: /settier 123456789 pro"
        )
    target_id, tier = parts[0], parts[1]
    try:
        new_tier = set_user_tier(db, target_id, tier)
    except ValueError as e:
        return TelegramReply(text=str(e))
    return TelegramReply(text=f"✅ ตั้ง user {target_id} เป็นแพ็กเกจ {TIER_LABELS.get(new_tier, new_tier)} แล้ว")


def _portfolio_data(telegram_user_id: str, db: Session) -> list[dict]:
    """โครงสร้างพอร์ตพร้อมมูลค่าปัจจุบัน/ทุน/PnL ต่อรายการ (ใช้ทำกราฟวงกลม)."""
    from models.portfolio import UserPortfolio
    holdings = (
        db.query(UserPortfolio)
        .filter(UserPortfolio.telegram_user_id == telegram_user_id)
        .all()
    )
    rows: list[dict] = []
    for h in holdings:
        try:
            data = fetch_market_data(h.symbol)
            current = float(data.get("price") or h.buy_price)
        except Exception:
            current = h.buy_price
        cost = h.quantity * h.buy_price
        value = h.quantity * current
        rows.append({"symbol": h.symbol, "value": value, "cost": cost, "pnl": value - cost})
    return rows


def _portfolio_chart_reply(telegram_user_id: str | None, db: Session | None) -> TelegramReply:
    if not telegram_user_id or not db:
        return TelegramReply(text="ดูพอร์ตได้เฉพาะในแชทส่วนตัวกับบอทครับ")
    rows = _portfolio_data(telegram_user_id, db)
    if not rows:
        return TelegramReply(text="💼 Portfolio ว่างเปล่า\nเพิ่มหุ้น: /portfolio add AAPL 10 180.50")
    from services.telegram_chart import generate_portfolio_chart
    photo, meta = generate_portfolio_chart(rows)
    sign = "+" if meta["total_pnl"] >= 0 else ""
    caption = (
        f"💼 พอร์ตของคุณ — {meta['holdings']} รายการ\n"
        f"มูลค่ารวม ${meta['total_value']:,.2f} | P&L {sign}${meta['total_pnl']:,.2f} ({sign}{meta['total_pnl_pct']:.1f}%)"
    )
    return TelegramReply(
        photo_bytes=photo, caption=caption,
        keyboard=[[{"text": "🔄 รีเฟรช", "callback_data": "port_chart"},
                   {"text": "💼 รายการ", "callback_data": "port_view"}]],
    )


def _format_alert_command(args: str, telegram_user_id: str | None, db: Session | None) -> TelegramReply:
    """/alert SYMBOL PRICE (ตั้ง) · /alert list · /alert remove SYMBOL."""
    if not telegram_user_id or not db:
        return TelegramReply(text="ตั้งแจ้งเตือนราคาได้เฉพาะในแชทส่วนตัวกับบอทครับ")
    from services import alerts as alert_svc

    parts = args.split()
    sub = parts[0].lower() if parts else "list"

    if sub in {"list", "ls", ""} or not parts:
        rows = alert_svc.list_alerts(db, telegram_user_id, active_only=True)
        if not rows:
            return TelegramReply(text="🔔 ยังไม่มีแจ้งเตือนราคาที่ตั้งไว้\nตั้งด้วย: /alert AAPL 250")
        lines = ["🔔 แจ้งเตือนราคาที่ใช้งานอยู่"]
        for a in rows:
            op = "≥" if a.direction == "above" else "≤"
            lines.append(f"• {a.symbol}  {op} ${a.target_price:,.2f}")
        lines.append("\nลบ: /alert remove SYMBOL")
        return TelegramReply(text="\n".join(lines))

    if sub in {"remove", "rm", "del", "delete", "cancel"}:
        sym = _extract_symbol(" ".join(parts[1:])) if len(parts) > 1 else None
        if not sym:
            return TelegramReply(text="รูปแบบ: /alert remove SYMBOL")
        n = alert_svc.remove_alerts_for_symbol(db, telegram_user_id, sym)
        return TelegramReply(text=f"✅ ลบแจ้งเตือน {sym} แล้ว ({n} รายการ)" if n else f"ไม่พบแจ้งเตือน {sym}")

    # create: /alert SYMBOL PRICE
    symbol = _extract_symbol(parts[0])
    if not symbol or len(parts) < 2:
        return TelegramReply(text="รูปแบบ: /alert SYMBOL PRICE\nตัวอย่าง: /alert AAPL 250  หรือ  /alert 0700.HK 400")
    try:
        target = float(parts[1].replace(",", ""))
    except ValueError:
        return TelegramReply(text="ราคาต้องเป็นตัวเลข เช่น /alert AAPL 250")
    if target <= 0:
        return TelegramReply(text="ราคาต้องมากกว่า 0")

    # cap จำนวน alert ต่อคน (vip / whitelist ไม่จำกัด)
    from services.tiers import get_user_tier
    unlimited = _is_admin(telegram_user_id) or get_user_tier(db, telegram_user_id) == "vip"
    cap = get_settings().telegram_max_alerts_per_user
    if not unlimited and cap > 0 and alert_svc.count_active(db, telegram_user_id) >= cap:
        return TelegramReply(text=f"⏳ ตั้งแจ้งเตือนได้สูงสุด {cap} รายการ — ลบของเก่าก่อน (/alert remove SYMBOL)")

    ref = None
    try:
        ref = float(fetch_market_data(symbol).get("price"))
    except Exception:
        pass
    row = alert_svc.create_alert(db, telegram_user_id, symbol, target, ref)
    op = "ขึ้นถึง" if row.direction == "above" else "ลงถึง"
    now_txt = f" (ตอนนี้ ${ref:,.2f})" if ref else ""
    return TelegramReply(
        text=f"🔔 ตั้งแจ้งเตือน {symbol} เมื่อราคา{op} ${target:,.2f}{now_txt}\nจะเตือนอัตโนมัติเมื่อถึงเป้า",
        keyboard=[[{"text": "🔔 ดูทั้งหมด", "callback_data": "alert_list"}]],
    )


_ANALYZE_HEARTBEAT_SEC = 10   # อัปเดตความคืบหน้าทุกกี่วินาที


def _analyze_result_text_kb(symbol: str, market_data: dict, result: dict) -> tuple[str, list]:
    direction = result["direction"]
    confidence = result["confidence"]
    icon = "🟢" if direction == "bullish" else "🔴" if direction == "bearish" else "🟡"
    text = (
        f"{icon} {symbol} — AI วิเคราะห์\n"
        f"ทิศทาง: {direction.upper()}  ความเชื่อมั่น: {confidence:.0%}\n"
        f"ราคา: ${market_data.get('price', 0):,.2f}\n\n"
        + (result.get("reasoning") or "")[:300]
    )
    kb = [
        [{"text": f"💬 คุยกับ AI ต่อเรื่อง {symbol}", "callback_data": f"askai:{symbol}"}],
        [
            {"text": "📈 Chart 7d",   "callback_data": f"chart:{symbol}"},
            {"text": "💼 Portfolio",  "callback_data": "port_view"},
        ],
    ]
    return text, kb


def _analyze_with_progress(symbol: str, chat_id: str, telegram_user_id: str | None) -> None:
    """รัน /analyze แบบ background + อัปเดตสถานะทุก ~10 วิ (แก้ข้อความเดิม) เพื่อไม่ให้เงียบ."""
    import threading
    import time
    from database import SessionLocal

    client = TelegramClient(channel_id=chat_id)
    db = SessionLocal()
    msg_id: Any = None
    state = {"stage": "กำลังเริ่ม...", "start": time.time()}
    stop = threading.Event()

    def _fmt(stage: str) -> str:
        el = int(time.time() - state["start"])
        return f"🔄 กำลังวิเคราะห์ {symbol} ด้วย AI… ({el} วินาที)\n⏳ {stage}"

    def heartbeat():
        # อัปเดตทุก N วิ จนกว่างานจะเสร็จ (stop ถูก set)
        while not stop.wait(_ANALYZE_HEARTBEAT_SEC):
            if msg_id is None:
                continue
            try:
                client.edit_message_text(_fmt(state["stage"]), chat_id, msg_id)
            except Exception:
                pass

    try:
        res = client.send_message(_fmt(state["stage"]), chat_id=chat_id)
        msg_id = (res[0].get("message_id") if res else None)
        hb = threading.Thread(target=heartbeat, daemon=True)
        hb.start()

        # 1) ตรวจ symbol (ผิด → ไม่หักโควตา)
        state["stage"] = "ดึงข้อมูลตลาด…"
        try:
            market_data = fetch_market_data(symbol)
        except Exception:
            stop.set()
            if msg_id:
                client.edit_message_text(f"❌ ไม่พบข้อมูลของ {symbol} — ลองตรวจสัญลักษณ์อีกครั้ง", chat_id, msg_id)
            return

        # 2) โควตา
        if telegram_user_id:
            from services.usage import try_consume
            from services.tiers import quota_for
            q = try_consume(db, telegram_user_id, "analyze", quota_for(db, telegram_user_id, "analyze"))
            if not q.allowed:
                stop.set()
                if msg_id:
                    client.edit_message_text(
                        f"⏳ วันนี้ใช้สิทธิ์วิเคราะห์ AI ครบแล้ว ({q.used}/{q.limit})\nสิทธิ์รีเซ็ตพรุ่งนี้ครับ",
                        chat_id, msg_id,
                    )
                return

        # 3) ข่าว + AI
        from agents.orchestrator import Orchestrator
        from fetchers.news_fetcher import fetch_all_news
        state["stage"] = "ดึงข่าวล่าสุด…"
        news = fetch_all_news(symbol)
        state["stage"] = "AI 4 ตัวกำลังวิเคราะห์ + ตรวจทานความเสี่ยง…"
        result = Orchestrator().analyze(symbol, market_data, news)

        stop.set()
        _set_context_symbol(telegram_user_id, symbol, db)
        text, kb = _analyze_result_text_kb(symbol, market_data, result)
        if msg_id:
            try:
                client.edit_message_text(text, chat_id, msg_id, keyboard=kb)
            except Exception:
                client.send_message_with_keyboard(text, chat_id=chat_id, keyboard=kb)
        else:
            client.send_message_with_keyboard(text, chat_id=chat_id, keyboard=kb)
    except Exception as exc:
        stop.set()
        try:
            if msg_id:
                client.edit_message_text(f"❌ วิเคราะห์ {symbol} ไม่สำเร็จ: {str(exc)[:150]}", chat_id, msg_id)
            else:
                client.send_message(f"❌ วิเคราะห์ {symbol} ไม่สำเร็จ: {str(exc)[:150]}", chat_id=chat_id)
        except Exception:
            pass
    finally:
        stop.set()
        db.close()


def _start_async_analyze(symbol: str, chat_id: str, telegram_user_id: str | None) -> None:
    import threading
    threading.Thread(
        target=_analyze_with_progress, args=(symbol, chat_id, telegram_user_id), daemon=True
    ).start()


def _quota_reached_reply(feature_th: str, used: int, limit: int) -> TelegramReply:
    return TelegramReply(
        text=(
            f"⏳ วันนี้คุณใช้สิทธิ์ {feature_th} ครบแล้ว ({used}/{limit} ครั้ง)\n"
            f"สิทธิ์จะรีเซ็ตใหม่พรุ่งนี้ครับ — ถ้าต้องการเพิ่มสิทธิ์แจ้งแอดมินได้"
        ),
        keyboard=[[{"text": "⚡ เมนู", "callback_data": "menu"}]],
    )


def _chart_caption(meta: dict) -> str:
    cur = meta["currency"]
    sign = "+" if meta["change_pct"] >= 0 else ""
    ma = meta.get("ma") or []
    unit = meta.get("ma_unit", "วัน")
    trend_reason = ""
    if ma:
        long_ma = ma[-1]
        above = meta["trend_th"] == "ขาขึ้น"
        rel = "เหนือ" if above else ("ใต้" if meta["trend_th"] == "ขาลง" else "ใกล้")
        trend_reason = f" (ราคาอยู่{rel}เส้น MA{long_ma}{unit})"
    lines = [
        f"📈 {meta['symbol']} — {meta.get('tf_label', '')}   แนวโน้ม{meta['trend_th']}{trend_reason}",
        f"ราคา {cur}{meta['last_price']:,.2f} ({sign}{meta['change_pct']:.1f}%)",
    ]
    res = meta.get("resistance") or []
    sup = meta.get("support") or []
    if res:
        lines.append("🔴 แนวต้าน: " + " · ".join(f"{cur}{r:,.2f}" for r in res))
    if sup:
        lines.append("🟢 แนวรับ: " + " · ".join(f"{cur}{s:,.2f}" for s in sup))
    if ma:
        lines.append(f"เส้นค่าเฉลี่ย: " + " / ".join(f"MA{m}{unit}" for m in ma) + " · แท่งเทียน + Volume")
    lines.append("เปลี่ยนช่วงเวลา: /graph " + meta['symbol'] + " 5y (1w/1m/3m/6m/1y/2y/3y/4y/5y)")
    lines.append("(ข้อมูลดิบ ไม่ใช่คำแนะนำการลงทุน)")
    return "\n".join(lines)


# บริบทหัวข้อสนทนาล่าสุดต่อ user — ให้คำถามต่อเนื่องอย่าง "ทำไมถึงขึ้น" รู้ว่าหมายถึง
# หุ้นตัวไหนโดยไม่ต้องพิมพ์ ticker ซ้ำ เก็บทั้งใน memory (เร็ว) และ DB (จำข้าม restart)
_LAST_CONTEXT: dict[str, str] = {}


def _set_context_symbol(telegram_user_id: str | None, symbol: str | None,
                        db: Session | None = None) -> None:
    if not telegram_user_id or not symbol:
        return
    _LAST_CONTEXT[telegram_user_id] = symbol
    if db is not None:
        try:
            user = db.query(TelegramUser).filter(
                TelegramUser.telegram_user_id == telegram_user_id
            ).first()
            if user is None:
                user = TelegramUser(telegram_user_id=telegram_user_id, first_seen_at=_now())
                db.add(user)
            user.last_context_symbol = symbol
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass


def _get_context_symbol(telegram_user_id: str | None, db: Session | None = None) -> str | None:
    """หัวข้อล่าสุด: จาก memory ก่อน ถ้าไม่มี (เช่นหลัง restart) ดึงจาก DB."""
    if not telegram_user_id:
        return None
    cached = _LAST_CONTEXT.get(telegram_user_id)
    if cached:
        return cached
    if db is not None:
        try:
            user = db.query(TelegramUser).filter(
                TelegramUser.telegram_user_id == telegram_user_id
            ).first()
            if user and user.last_context_symbol:
                _LAST_CONTEXT[telegram_user_id] = user.last_context_symbol
                return user.last_context_symbol
        except Exception:
            pass
    return None


def _log_ai_interaction(db: Session | None, telegram_user_id: str | None,
                        question: str, answer: str, symbol: str | None) -> str | None:
    """เก็บ Q&A ของ AI chat เป็นสถิติ (ใช้ปรับปรุงโลจิก + เป็นข้อมูลฝึกภายหลัง)."""
    if not db or not telegram_user_id:
        return None
    try:
        from models.chat_feedback import AiChatInteraction
        row = AiChatInteraction(
            telegram_user_id=telegram_user_id,
            symbol=symbol, question=question[:2000], answer=answer[:4000],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    except Exception as exc:
        print(f"[ai_chat] log error: {exc}")
        try:
            db.rollback()
        except Exception:
            pass
        return None


def _ai_chat_reply(text: str, telegram_user_id: str | None, db: Session | None) -> TelegramReply:
    from agents.base_agent import BaseAgent
    if _ai_chat_throttled(telegram_user_id):
        return TelegramReply(text="ส่งข้อความถี่เกินไปครับ รอสักครู่แล้วถามใหม่ 🙏")
    context = _ai_chat_context(telegram_user_id, db, text)
    user_prompt = f"{context}\n\n=== คำถามของผู้ใช้ ===\n{text[:1500]}"
    try:
        agent = BaseAgent()
        agent.name = "telegram_chat"
        answer = (agent._call_llm(_chat_system_prompt(db), user_prompt, max_tokens=700) or "").strip()
    except Exception as exc:
        return TelegramReply(
            text=f"ตอนนี้ AI ตอบไม่ได้ชั่วคราว ({str(exc)[:120]})\nลองใช้เมนูคำสั่งแทน: /menu"
        )
    if not answer:
        return TelegramReply(text="AI ไม่มีคำตอบสำหรับข้อความนี้ ลอง /menu ดูคำสั่งที่ใช้ได้")

    # context symbol: จากข้อความปัจจุบัน หรือหัวข้อล่าสุด
    cur_sym = _extract_symbol(text)
    symbol = cur_sym or _get_context_symbol(telegram_user_id, db)
    _set_context_symbol(telegram_user_id, cur_sym, db)
    interaction_id = _log_ai_interaction(db, telegram_user_id, text, answer, symbol)

    # ปุ่มให้คะแนน (เก็บสถิติ→ปรับปรุงโลจิก) + ปุ่มถามต่อ
    keyboard: list[list[dict[str, Any]]] = []
    if interaction_id:
        keyboard.append([
            {"text": "👍 ตรงใจ", "callback_data": f"chatfb:{interaction_id}:up"},
            {"text": "👎 ยังไม่ใช่", "callback_data": f"chatfb:{interaction_id}:down"},
        ])
    keyboard.append([
        {"text": "💬 ถามต่อ", "callback_data": "askai"},
        {"text": "⚡ เมนู", "callback_data": "menu"},
    ])
    return TelegramReply(text=answer[:3900], keyboard=keyboard)


# ---------------------------------------------------------------------------
# Portfolio helpers
# ---------------------------------------------------------------------------

def _portfolio_view(telegram_user_id: str, db: Session) -> str:
    from models.portfolio import UserPortfolio
    holdings = (
        db.query(UserPortfolio)
        .filter(UserPortfolio.telegram_user_id == telegram_user_id)
        .all()
    )
    if not holdings:
        return (
            "💼 Portfolio ของคุณว่างเปล่า\n"
            "เพิ่มหุ้น: /portfolio add AAPL 10 180.50"
        )
    lines = ["💼 Portfolio ของคุณ\n"]
    total_cost = total_value = 0.0
    for h in holdings:
        try:
            data = fetch_market_data(h.symbol)
            current = float(data.get("price") or h.buy_price)
        except Exception:
            current = h.buy_price
        cost = h.quantity * h.buy_price
        value = h.quantity * current
        pnl = value - cost
        pnl_pct = (pnl / cost * 100) if cost else 0
        total_cost += cost
        total_value += value
        sign = "+" if pnl >= 0 else ""
        icon = "🟢" if pnl >= 0 else "🔴"
        lines.append(
            f"{icon} {h.symbol}: {h.quantity:.4g} หุ้น @ ${h.buy_price:.2f}\n"
            f"   ราคาปัจจุบัน ${current:.2f} | P&L {sign}${pnl:.2f} ({sign}{pnl_pct:.1f}%)"
        )
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
    sign = "+" if total_pnl >= 0 else ""
    lines.append(
        f"\n📊 มูลค่ารวม ${total_value:,.2f} | {sign}${total_pnl:.2f} ({sign}{total_pnl_pct:.1f}%)"
    )
    return "\n".join(lines)


def _portfolio_add(telegram_user_id: str, args: str, db: Session) -> str:
    from models.portfolio import UserPortfolio
    parts = args.strip().split()
    if len(parts) < 3:
        return (
            "รูปแบบ: /portfolio add SYMBOL จำนวน ราคาซื้อ\n"
            "ตัวอย่าง: /portfolio add AAPL 10 180.50"
        )
    symbol = parts[0].upper()
    try:
        qty = float(parts[1])
        price = float(parts[2])
    except ValueError:
        return "จำนวนและราคาต้องเป็นตัวเลข"
    if qty <= 0 or price <= 0:
        return "จำนวนและราคาต้องมากกว่า 0"
    existing = (
        db.query(UserPortfolio)
        .filter(
            UserPortfolio.telegram_user_id == telegram_user_id,
            UserPortfolio.symbol == symbol,
        )
        .first()
    )
    if existing:
        total_qty = existing.quantity + qty
        avg_price = (existing.quantity * existing.buy_price + qty * price) / total_qty
        existing.quantity = total_qty
        existing.buy_price = round(avg_price, 4)
    else:
        from models.portfolio import UserPortfolio as UP
        db.add(UP(telegram_user_id=telegram_user_id, symbol=symbol, quantity=qty, buy_price=price))
    db.commit()
    return f"✅ เพิ่ม {symbol} {qty:.4g} หุ้น @ ${price:.2f} ใน Portfolio แล้ว"


def _portfolio_remove(telegram_user_id: str, symbol: str, db: Session) -> str:
    from models.portfolio import UserPortfolio
    row = (
        db.query(UserPortfolio)
        .filter(
            UserPortfolio.telegram_user_id == telegram_user_id,
            UserPortfolio.symbol == symbol.upper(),
        )
        .first()
    )
    if not row:
        return f"ไม่พบ {symbol.upper()} ใน Portfolio ของคุณ"
    db.delete(row)
    db.commit()
    return f"✅ ลบ {symbol.upper()} ออกจาก Portfolio แล้ว"


def _format_portfolio_command(args: str, telegram_user_id: str | None, db: Session | None) -> str:
    """Parse /portfolio [add|remove|view] ..."""
    if not telegram_user_id or not db:
        return "Portfolio ใช้ได้เฉพาะใน private chat กับบอท"
    parts = args.strip().split(None, 1)
    sub = parts[0].lower() if parts else "view"
    sub_args = parts[1] if len(parts) > 1 else ""
    if sub == "add":
        return _portfolio_add(telegram_user_id, sub_args, db)
    if sub in {"remove", "rm", "del", "delete"}:
        return _portfolio_remove(telegram_user_id, sub_args or "", db)
    return _portfolio_view(telegram_user_id, db)


def _watch_add(telegram_user_id: str, args: str, db: Session) -> str:
    from models.watchlist import UserWatchlist
    symbol = (args.strip().split() or [""])[0].upper()
    if not symbol:
        return "รูปแบบ: /watch add SYMBOL\nตัวอย่าง: /watch add TSLA"
    existing = (
        db.query(UserWatchlist)
        .filter(
            UserWatchlist.telegram_user_id == telegram_user_id,
            UserWatchlist.symbol == symbol,
        )
        .first()
    )
    if existing:
        return f"{symbol} อยู่ใน watchlist ของคุณอยู่แล้ว"
    db.add(UserWatchlist(telegram_user_id=telegram_user_id, symbol=symbol))
    db.commit()
    return f"✅ เพิ่ม {symbol} ใน watchlist ส่วนตัวแล้ว"


def _watch_remove(telegram_user_id: str, symbol: str, db: Session) -> str:
    from models.watchlist import UserWatchlist
    row = (
        db.query(UserWatchlist)
        .filter(
            UserWatchlist.telegram_user_id == telegram_user_id,
            UserWatchlist.symbol == symbol.upper(),
        )
        .first()
    )
    if not row:
        return f"ไม่พบ {symbol.upper()} ใน watchlist ของคุณ"
    db.delete(row)
    db.commit()
    return f"✅ ลบ {symbol.upper()} ออกจาก watchlist แล้ว"


def _watch_view(telegram_user_id: str, db: Session) -> str:
    from models.watchlist import UserWatchlist
    rows = (
        db.query(UserWatchlist)
        .filter(UserWatchlist.telegram_user_id == telegram_user_id)
        .order_by(UserWatchlist.created_at.asc())
        .all()
    )
    if not rows:
        return "Watchlist ส่วนตัวของคุณว่างอยู่\nเพิ่มด้วย /watch add SYMBOL เช่น /watch add TSLA"

    lines = ["📋 Watchlist ส่วนตัวของคุณ"]
    for row in rows:
        try:
            data = fetch_market_data(row.symbol)
            price = _fmt_price(data.get("price"))
            pct = _fmt_pct(data.get("price_change_pct"))
            icon = "🟢" if (data.get("price_change_pct") or 0) >= 0 else "🔴"
        except Exception:
            price, pct, icon = "n/a", "n/a", "⚪"
        lines.append(f"{icon} {row.symbol}: {price} ({pct})")
    return "\n".join(lines)


def _format_watch_command(args: str, telegram_user_id: str | None, db: Session | None) -> str:
    """Parse /watch [add|remove|view] ... — personal watchlist, distinct from /watchlist (global config list)."""
    if not telegram_user_id or not db:
        return "Watchlist ส่วนตัวใช้ได้เฉพาะใน private chat กับบอท"
    parts = args.strip().split(None, 1)
    sub = parts[0].lower() if parts else "view"
    sub_args = parts[1] if len(parts) > 1 else ""
    if sub == "add":
        return _watch_add(telegram_user_id, sub_args, db)
    if sub in {"remove", "rm", "del", "delete"}:
        return _watch_remove(telegram_user_id, sub_args or "", db)
    return _watch_view(telegram_user_id, db)


def _format_compare_reply(args: str) -> TelegramReply:
    """Parse /compare SYMBOL1 SYMBOL2 — side-by-side snapshot, no LLM call (fast)."""
    tokens = [t.upper() for t in re.split(r"\s+|,|\bvs\b|\bกับ\b", args, flags=re.IGNORECASE) if t.strip()]
    if len(tokens) < 2:
        return TelegramReply(text="รูปแบบ: /compare SYMBOL1 SYMBOL2\nตัวอย่าง: /compare AAPL MSFT")
    sym_a, sym_b = tokens[0], tokens[1]

    try:
        data_a = fetch_market_data(sym_a)
    except Exception as e:
        return TelegramReply(text=f"ดึงข้อมูล {sym_a} ไม่สำเร็จ: {e}")
    try:
        data_b = fetch_market_data(sym_b)
    except Exception as e:
        return TelegramReply(text=f"ดึงข้อมูล {sym_b} ไม่สำเร็จ: {e}")

    def row(label: str, a: Any, b: Any) -> str:
        return f"{label:<10}: {a}  vs  {b}"

    lines = [f"⚖️ {sym_a} vs {sym_b}", ""]
    lines.append(row("ราคา", _fmt_price(data_a.get("price")), _fmt_price(data_b.get("price"))))
    lines.append(row("1D", _fmt_pct(data_a.get("price_change_pct")), _fmt_pct(data_b.get("price_change_pct"))))
    if data_a.get("pe_ratio") is not None or data_b.get("pe_ratio") is not None:
        pe_a = data_a.get("pe_ratio")
        pe_b = data_b.get("pe_ratio")
        lines.append(row("P/E", f"{pe_a:.1f}" if pe_a is not None else "n/a", f"{pe_b:.1f}" if pe_b is not None else "n/a"))
    if data_a.get("market_cap") or data_b.get("market_cap"):
        def fmt_cap(v):
            if not v:
                return "n/a"
            if v >= 1e12:
                return f"${v/1e12:.2f}T"
            if v >= 1e9:
                return f"${v/1e9:.2f}B"
            return f"${v:,.0f}"
        lines.append(row("Market Cap", fmt_cap(data_a.get("market_cap")), fmt_cap(data_b.get("market_cap"))))
    if data_a.get("rsi_14") is not None or data_b.get("rsi_14") is not None:
        lines.append(row("RSI 14", data_a.get("rsi_14") or "n/a", data_b.get("rsi_14") or "n/a"))

    # simple heuristic verdict — valuation + momentum, not a full AI call
    notes = []
    pe_a, pe_b = data_a.get("pe_ratio"), data_b.get("pe_ratio")
    if pe_a is not None and pe_b is not None:
        cheaper = sym_a if pe_a < pe_b else sym_b
        notes.append(f"{cheaper} valuation ถูกกว่า (P/E ต่ำกว่า)")
    chg_a, chg_b = data_a.get("price_change_pct") or 0, data_b.get("price_change_pct") or 0
    stronger = sym_a if chg_a > chg_b else sym_b
    notes.append(f"{stronger} momentum วันนี้ดีกว่า")
    if notes:
        lines.append("")
        lines.append("💡 " + " | ".join(notes))
        lines.append("(ข้อมูลดิบ ไม่ใช่คำแนะนำการลงทุน — ใช้ /analyze เพื่อดูวิเคราะห์เต็มจาก AI)")

    return TelegramReply(
        text="\n".join(lines),
        keyboard=[[
            {"text": f"📊 วิเคราะห์ {sym_a}", "callback_data": f"analyze:{sym_a}"},
            {"text": f"📊 วิเคราะห์ {sym_b}", "callback_data": f"analyze:{sym_b}"},
        ]],
    )


# ---------------------------------------------------------------------------
# "/" command menu (Telegram setMyCommands) — shown in both private chats and
# groups once registered. Names must be lowercase [a-z0-9_], no leading slash.
# ---------------------------------------------------------------------------

BOT_COMMANDS: list[dict[str, str]] = [
    {"command": "menu", "description": "เมนูคีย์ลัดแบบปุ่มกด"},
    {"command": "analyze", "description": "วิเคราะห์หุ้นด้วย AI (จำกัดต่อวัน)"},
    {"command": "graph", "description": "กราฟแท่งเทียน + MA + แนวรับแนวต้าน (เช่น /graph AAPL 5y)"},
    {"command": "chart", "description": "กราฟราคาย้อนหลัง 7 วัน"},
    {"command": "alert", "description": "แจ้งเตือนราคา เช่น /alert AAPL 250"},
    {"command": "me", "description": "ดูแพ็กเกจ + สิทธิ์คงเหลือวันนี้"},
    {"command": "compare", "description": "เทียบหุ้น 2 ตัวแบบเคียงข้าง"},
    {"command": "portfolio", "description": "พอร์ตของคุณ (add/remove/view + P&L)"},
    {"command": "watch", "description": "Watchlist ส่วนตัว (add/remove/view)"},
    {"command": "watchlist", "description": "หุ้นที่ระบบติดตามอยู่ (global)"},
    {"command": "news", "description": "ข่าวเด่นประจำวัน"},
    {"command": "report", "description": "รายงานตลาดประจำวันแบบเต็ม"},
    {"command": "ipo", "description": "ตาราง IPO"},
    {"command": "ipohk", "description": "ตาราง IPO ฮ่องกง"},
    {"command": "earnings", "description": "ปฏิทินงบรายไตรมาส"},
    {"command": "checkaddress", "description": "ตรวจสอบ wallet address คริปโต"},
    {"command": "help", "description": "วิธีใช้งานบอท"},
]

# เมนู "/" สำหรับ "กลุ่ม" — เฉพาะคำสั่งที่ทำงานในกลุ่มได้จริง (ที่เหลือเด้งไป DM
# อยู่แล้ว จึงไม่ใส่เพื่อไม่ให้สมาชิกกลุ่มสับสน) เรียงตามความถี่ใช้งาน
_GROUP_COMMAND_NAMES = ["menu", "news", "earnings", "ipo", "ipohk", "report", "watchlist", "help"]
GROUP_COMMANDS: list[dict[str, str]] = [
    c for name in _GROUP_COMMAND_NAMES
    for c in BOT_COMMANDS if c["command"] == name
]


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

def _format_help() -> str:
    return "\n".join([
        "Agent Invest bot commands",
        "",
        "/menu - shortcut button menu",
        "/news - noteworthy market news",
        "/earnings - upcoming quarterly earnings calendar",
        "/watchlist - assets to monitor (global)",
        "/ipo - IPO agenda",
        "/ipohk - Hong Kong IPO agenda",
        "/checkaddress <wallet> - identify crypto wallet and open explorers",
        "/report - full daily monitor",
        "/analyze SYMBOL - run AI analysis (daily quota per user)",
        "/graph SYMBOL [tf] - candlestick + MA + support/resistance (tf: 1w/1m/3m/6m/1y/2y/3y/4y/5y, e.g. /graph AAPL 5y). Compare: /graph AAPL vs MSFT",
        "/chart SYMBOL - 7-day price chart",
        "/portfolio chart - your holdings as a pie chart with total P&L",
        "/alert SYMBOL PRICE - alert when price is reached (e.g. /alert AAPL 250). /alert list, /alert remove SYMBOL",
        "/me - your plan + remaining quota today",
        "/portfolio [add|remove] SYMBOL QTY PRICE - track your holdings + live P&L",
        "/watch [add|remove] SYMBOL - your personal watchlist (price only, no P&L)",
        "/compare SYMBOL1 SYMBOL2 - side-by-side snapshot",
        "",
        "Natural language works too, for example: 'อยากดู IPO ฮ่องกง', 'หุ้นที่ควรติดตาม', or 'อยากตรวจกระเป๋าคริปโต 0x...'.",
        "",
        "ในแชทส่วนตัว พิมพ์คุยกับ AI ได้เลย (รู้จัก portfolio ของคุณ) — ในกลุ่มใช้ได้เฉพาะคำสั่งรายงาน (/news /earnings /ipo /report)",
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


def _format_market_symbol_reply(text: str) -> TelegramReply:
    symbol = _extract_symbol(text)
    if not symbol:
        return TelegramReply(text="ส่ง symbol เช่น AAPL, NVDA, BTC, ETH")
    data = fetch_market_data(symbol)
    lines = [f"📊 {symbol} — snapshot"]
    lines.append(f"💰 ราคา: {_fmt_price(data.get('price'))}")
    lines.append(f"📉 เปลี่ยนแปลง: {_fmt_pct(data.get('price_change_pct'))}")
    if data.get("rsi_14") is not None:
        lines.append(f"📈 RSI 14: {data['rsi_14']}")
    if data.get("macd") is not None and data.get("macd_signal") is not None:
        lines.append(f"⚡ MACD: {data['macd']} / signal {data['macd_signal']}")
    return TelegramReply(text="\n".join(lines), keyboard=_market_keyboard(symbol))


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


def build_telegram_reply(
    intent_info: dict[str, Any],
    text: str,
    db: Session | None = None,
    telegram_user_id: str | None = None,
    chat_type: str = "private",
) -> TelegramReply | None:
    intent = intent_info.get("intent", "unknown")
    args = intent_info.get("args", "")
    try:
        if intent in {"start", "menu"}:
            return _menu_reply(chat_type)
        if intent in {"help", "unknown"}:
            return TelegramReply(text=_format_help())
        if intent == "earnings":
            return TelegramReply(text=_format_earnings_reply())
        if intent == "my_status":
            return _my_status_reply(telegram_user_id, db)
        if intent == "set_tier":
            return _set_tier_reply(args, telegram_user_id, db)
        if intent == "alert":
            return _format_alert_command(args, telegram_user_id, db)
        if intent == "ai_chat":
            if telegram_user_id and db:
                from services.usage import try_consume
                from services.tiers import quota_for
                q = try_consume(db, telegram_user_id, "chat", quota_for(db, telegram_user_id, "chat"))
                if not q.allowed:
                    return _quota_reached_reply("แชท AI", q.used, q.limit)
            return _ai_chat_reply(text, telegram_user_id, db)
        if intent == "ipo_hk":
            return TelegramReply(text=_format_ipo_reply(hk_only=True))
        if intent == "ipo":
            return TelegramReply(text=_format_ipo_reply(hk_only=False))
        if intent == "news":
            return TelegramReply(text=_format_news_reply())
        if intent == "watchlist":
            return TelegramReply(text=_format_watchlist_reply())
        if intent == "wallet_check":
            return TelegramReply(text=_format_wallet_reply(text))
        if intent == "daily_report":
            settings = get_settings()
            msg = build_daily_monitor_report(
                max_assets=settings.telegram_private_report_max_assets,
                max_news_items=settings.telegram_private_report_max_news_items,
            )["message"]
            return TelegramReply(text=msg)
        if intent == "market_symbol":
            return _format_market_symbol_reply(text)

        # ── New features ───────────────────────────────────────────────────
        if intent == "analyze_symbol":
            symbol = _extract_symbol(args) or _extract_symbol(text)
            if not symbol:
                return TelegramReply(text="ส่ง symbol เช่น /analyze AAPL หรือ /analyze 0700.HK")
            from agents.orchestrator import Orchestrator
            from fetchers.news_fetcher import fetch_all_news
            market_data = fetch_market_data(symbol)   # ตรวจ symbol ก่อน (ผิดจะ raise ไม่หักโควตา)
            # โควตา: หักหลังยืนยัน symbol ใช้ได้ แต่ก่อนเรียก LLM (ส่วนที่แพง)
            if telegram_user_id and db:
                from services.usage import try_consume
                from services.tiers import quota_for
                q = try_consume(db, telegram_user_id, "analyze", quota_for(db, telegram_user_id, "analyze"))
                if not q.allowed:
                    return _quota_reached_reply("วิเคราะห์ AI", q.used, q.limit)
            news = fetch_all_news(symbol)
            result = Orchestrator().analyze(symbol, market_data, news)
            direction = result["direction"]
            confidence = result["confidence"]
            icon = "🟢" if direction == "bullish" else "🔴" if direction == "bearish" else "🟡"
            reply_text = (
                f"{icon} {symbol} — AI วิเคราะห์\n"
                f"ทิศทาง: {direction.upper()}  ความเชื่อมั่น: {confidence:.0%}\n"
                f"ราคา: ${market_data.get('price', 0):,.2f}\n\n"
                + (result.get("reasoning") or "")[:300]
            )
            # จำหัวข้อไว้ ให้กด "คุยกับ AI ต่อ" แล้วถามต่อเนื่องได้เลย
            _set_context_symbol(telegram_user_id, symbol, db)
            return TelegramReply(
                text=reply_text,
                keyboard=[
                    [{"text": f"💬 คุยกับ AI ต่อเรื่อง {symbol}", "callback_data": f"askai:{symbol}"}],
                    [
                        {"text": "📈 Chart 7d",   "callback_data": f"chart:{symbol}"},
                        {"text": "💼 Portfolio",  "callback_data": "port_view"},
                    ],
                ],
            )

        if intent == "chart_symbol":
            source = args or text
            multi = _extract_symbols(source)
            is_compare = len(multi) >= 2
            symbol = None if is_compare else (_extract_symbol(args) or _extract_symbol(text))
            if not is_compare and not symbol:
                return TelegramReply(text="ส่ง symbol เช่น /graph AAPL, /graph 0700.HK หรือ /graph 600519.SS\nเปรียบเทียบ: /graph AAPL vs MSFT · ช่วงเวลา: /graph AAPL 5y (1w–5y)")
            # โควตา: เช็คก่อนเรนเดอร์ (กันเรนเดอร์ทิ้งเมื่อเกินสิทธิ์)
            if telegram_user_id and db:
                from services.usage import peek_quota
                from services.tiers import quota_for
                pq = peek_quota(db, telegram_user_id, "graph", quota_for(db, telegram_user_id, "graph"))
                if not pq.allowed:
                    return _quota_reached_reply("ตีกราฟ", pq.used, pq.limit)

            tf = _parse_graph_timeframe(source, default="1y")
            if is_compare:
                from services.telegram_chart import generate_compare_chart
                photo, meta = generate_compare_chart(multi, timeframe=tf)
                ranked = sorted(meta["changes"].items(), key=lambda kv: kv[1], reverse=True)
                lines = [f"⚖️ เปรียบเทียบ {meta.get('tf_label', tf)} (% เปลี่ยนแปลง)"]
                for i, (sym, pct) in enumerate(ranked):
                    medal = "🥇" if i == 0 else ("🥈" if i == 1 else "•")
                    sign = "+" if pct >= 0 else ""
                    lines.append(f"{medal} {sym}: {sign}{pct:.1f}%")
                caption = "\n".join(lines)
                keyboard = [[{"text": f"📊 วิเคราะห์ {multi[0]}", "callback_data": f"analyze:{multi[0]}"}]]
            else:
                from services.telegram_chart import generate_price_chart
                photo, meta = generate_price_chart(symbol, timeframe=tf)
                caption = _chart_caption(meta)
                keyboard = [[
                    {"text": "📊 วิเคราะห์ AI",  "callback_data": f"analyze:{symbol}"},
                    {"text": "➕ เพิ่ม Port",     "callback_data": f"port_add:{symbol}"},
                ]]

            # เรนเดอร์สำเร็จ (symbol ใช้ได้) แล้วค่อยหักโควตา
            if telegram_user_id and db:
                from services.usage import try_consume
                from services.tiers import quota_for
                try_consume(db, telegram_user_id, "graph", quota_for(db, telegram_user_id, "graph"))
            return TelegramReply(photo_bytes=photo, caption=caption, keyboard=keyboard)

        if intent == "portfolio":
            sub = args.strip().lower()
            if sub.startswith("chart") or sub.startswith("pie") or sub in {"กราฟ", "รูป"}:
                return _portfolio_chart_reply(telegram_user_id, db)
            reply_text = _format_portfolio_command(args, telegram_user_id, db)
            keyboard = None
            if telegram_user_id and db and not args.strip().startswith("add"):
                keyboard = [[
                    {"text": "🔄 Refresh", "callback_data": "port_view"},
                    {"text": "📊 กราฟพอร์ต", "callback_data": "port_chart"},
                ]]
            return TelegramReply(text=reply_text, keyboard=keyboard)

        if intent == "watch":
            reply_text = _format_watch_command(args, telegram_user_id, db)
            keyboard = None
            if telegram_user_id and db and not args.strip().startswith("add"):
                keyboard = [[{"text": "🔄 Refresh", "callback_data": "watch_view"}]]
            return TelegramReply(text=reply_text, keyboard=keyboard)

        if intent == "compare":
            return _format_compare_reply(args)

    except Exception as exc:
        return TelegramReply(text=f"ขณะนี้ไม่สามารถดึงข้อมูลได้: {str(exc)[:180]}")
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


def _dispatch_reply(
    reply: TelegramReply,
    client: TelegramClient,
    chat_id: str,
) -> str:
    """Send the TelegramReply via the appropriate Telegram method. Returns status string."""
    try:
        if reply.photo_bytes:
            client.send_photo(
                reply.photo_bytes,
                chat_id=chat_id,
                caption=reply.caption,
                keyboard=reply.keyboard,
            )
        elif reply.text:
            if reply.keyboard:
                client.send_message_with_keyboard(
                    reply.text, chat_id=chat_id, keyboard=reply.keyboard
                )
            else:
                client.send_message(reply.text, chat_id=chat_id)
        return "sent"
    except TelegramSendError as exc:
        return f"failed: {str(exc)[:120]}"
    except Exception as exc:
        return f"failed: {str(exc)[:120]}"


def _handle_callback_query(callback_query: dict[str, Any], db: Session) -> dict[str, Any]:
    """Handle inline keyboard button presses."""
    callback_id = str(callback_query.get("id", ""))
    data = str(callback_query.get("data", ""))
    from_user = callback_query.get("from") or {}
    telegram_user_id = str(from_user.get("id", ""))
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))

    if not chat_id:
        return {"ok": True, "handled": False, "reason": "no_chat_id"}

    # Parse "action:arg"
    parts = data.split(":", 1)
    action = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    client = TelegramClient(channel_id=chat_id)

    # ── AI-chat feedback (👍/👎) — เก็บสถิติเพื่อปรับปรุงโลจิก ──
    if action == "chatfb":
        fb_parts = arg.split(":")
        inter_id = fb_parts[0] if fb_parts else ""
        vote = fb_parts[1] if len(fb_parts) > 1 else ""
        rating = 1 if vote == "up" else (-1 if vote == "down" else None)
        saved = False
        if inter_id and rating is not None:
            try:
                from models.chat_feedback import AiChatInteraction
                row = db.query(AiChatInteraction).filter(AiChatInteraction.id == inter_id).first()
                if row:
                    row.rating = rating
                    row.rated_at = _now()
                    db.commit()
                    saved = True
                    if rating == 1:
                        _FEWSHOT_CACHE["ts"] = 0.0   # ให้ few-shot รีเฟรชทันทีเมื่อมีตัวอย่างที่ดีใหม่
            except Exception as exc:
                print(f"[ai_chat] feedback save error: {exc}")
                db.rollback()
        ack = "ขอบคุณสำหรับ feedback 🙏 เราจะเอาไปปรับปรุงให้ดีขึ้น" if saved else "บันทึกแล้ว"
        try:
            client.answer_callback_query(callback_id, text=ack)
        except Exception:
            pass
        return {"ok": True, "handled": True, "action": "chatfb", "rating": rating, "saved": saved}

    # ── "คุยกับ AI ต่อ" — ตั้งหัวข้อแล้วชวนให้พิมพ์คำถามต่อ ──
    if action == "askai":
        if arg:
            _set_context_symbol(telegram_user_id, _extract_symbol(arg) or arg.upper(), db)
        try:
            client.answer_callback_query(callback_id)
        except Exception:
            pass
        topic = _get_context_symbol(telegram_user_id, db) or ""
        prompt = (f"💬 ถามต่อได้เลยครับ — พิมพ์คำถามเกี่ยวกับ {topic} หรือเรื่องอื่นก็ได้\n"
                  "เช่น \"ทำไมถึงมองว่าขึ้น\", \"ความเสี่ยงคืออะไร\", \"ควรถือหรือขาย\"") if topic else (
                  "💬 ถามอะไรก็ได้เลยครับ พิมพ์คำถามด้านล่าง\nเช่น \"ตลาดช่วงนี้เป็นยังไง\", \"NVDA ยังน่าถือไหม\"")
        try:
            client.send_message(prompt, chat_id=chat_id)
        except Exception:
            pass
        return {"ok": True, "handled": True, "action": "askai", "topic": topic}

    # Map callback actions to synthetic intent_info
    action_intent_map = {
        "analyze":    "analyze_symbol",
        "chart":      "chart_symbol",
        "port_view":  "portfolio",
        "port_add":   "portfolio",
        "port_chart": "portfolio",
        "watch_view": "watch",
        "news":       "news",
        "ipo":        "ipo",
        "ipohk":      "ipo_hk",
        "earnings":   "earnings",
        "report":     "daily_report",
        "watchlist":  "watchlist",
        "menu":       "menu",
        "help":       "help",
        "me":         "my_status",
        "alert_list": "alert",
    }
    intent = action_intent_map.get(action, "unknown")

    # Synthesize args for buttons that map onto a subcommand
    if action == "port_add":
        args_str = f"add {arg}" if arg else ""
    elif action == "port_chart":
        args_str = "chart"
    elif action == "alert_list":
        args_str = "list"
    else:
        args_str = arg

    intent_info = {"intent": intent, "command": action, "args": args_str, "keywords": []}

    chat_type = str(chat.get("type") or "unknown")

    # ปุ่มที่กดในกลุ่มต้องเป็น intent ฝั่งรายงานเท่านั้น (กันปุ่มเก่า/ปุ่มส่งต่อ)
    # channel = แอดมินเท่านั้น จึงอนุญาตเต็ม เหมือน private
    if chat_type in {"group", "supergroup"} and intent not in GROUP_ALLOWED_INTENTS:
        try:
            client.answer_callback_query(callback_id, text="ฟีเจอร์นี้ใช้ในแชทส่วนตัวกับบอทครับ")
        except Exception:
            pass
        return {"ok": True, "handled": True, "action": action, "status": "blocked_in_group"}

    # Acknowledge button press first (removes loading spinner)
    try:
        client.answer_callback_query(callback_id)
    except Exception:
        pass

    # ปุ่ม "วิเคราะห์ AI" → รันแบบ background + แจ้งความคืบหน้าทุก 10 วิ (ไม่เงียบ)
    if intent == "analyze_symbol":
        sym = _extract_symbol(arg)
        if sym:
            _start_async_analyze(sym, chat_id, telegram_user_id)
            return {"ok": True, "handled": True, "action": action, "status": "analyze_async"}

    reply = build_telegram_reply(intent_info, arg, db, telegram_user_id, chat_type=chat_type)
    if not reply:
        return {"ok": True, "handled": False}

    status = _dispatch_reply(reply, client, chat_id)
    return {"ok": True, "handled": True, "action": action, "status": status}


def handle_telegram_update(update: dict[str, Any], db: Session) -> dict[str, Any]:
    # Inline keyboard button press
    if "callback_query" in update:
        return _handle_callback_query(update["callback_query"], db)

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

    # private chat: ข้อความ free-text → คุยกับ AI
    # ครอบทั้ง intent "unknown" และประโยคที่มี ticker ปน (market_symbol) —
    # ยกเว้นพิมพ์ ticker เดี่ยวๆ ("NVDA") ที่ตอบ snapshot เร็วเหมาะกว่า
    chat_type_raw = (raw_chat.get("type") or "unknown") if isinstance(raw_chat, dict) else "unknown"
    if (
        chat_type_raw == "private"
        and not intent_info.get("command")
        and get_settings().telegram_private_ai_chat
        and (
            intent_info.get("intent") == "unknown"
            or (intent_info.get("intent") == "market_symbol" and not _is_bare_symbol(text))
        )
    ):
        intent_info["intent"] = "ai_chat"
        intent_info["topic"] = INTENT_TOPICS["ai_chat"]

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
        command=(intent_info.get("command") or "")[:80] or None,
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
        intent = intent_info.get("intent", "unknown")
        # กลุ่ม/ซูเปอร์กรุ๊ป = report-only (คำสั่งอื่นชี้ไป DM) เพราะสมาชิกทั่วไปพิมพ์ได้
        # channel = โพสต์ได้เฉพาะแอดมิน จึงให้รันคำสั่งได้เต็มแล้วโพสต์ผลลงช่องเลย
        # (เช่น /graph AAPL โพสต์กราฟเข้าช่อง) — private ก็รันเต็มเช่นกัน
        is_group = chat.chat_type in {"group", "supergroup"}
        # /analyze (private/channel): รันแบบ background + แจ้งความคืบหน้าทุก 10 วิ
        # (กันเงียบระหว่างประมวลผลหลายวินาที) แทนที่จะบล็อกรอในนี้
        if (not is_group and intent == "analyze_symbol"
                and (_extract_symbol(intent_info.get("args", "")) or _extract_symbol(text))):
            sym = _extract_symbol(intent_info.get("args", "")) or _extract_symbol(text)
            _start_async_analyze(sym, chat.telegram_chat_id, user.telegram_user_id if user else None)
            row.reply_status = "analyze_async"
            db.commit()
            reply = None
        elif is_group and intent not in GROUP_ALLOWED_INTENTS:
            # ในกลุ่ม: intent ที่เปิดเฉพาะส่วนตัว → ชี้ไป DM, intent ขยะ → เงียบ
            # ยกเว้น unknown: ตอบเฉพาะเมื่อ @mention บอทตรงๆ (ไม่ใช่คำสั่งหลงมาของบอทอื่น)
            bot_username = get_settings().telegram_bot_username.strip("@").lower()
            mentioned = bool(bot_username and f"@{bot_username}" in text.lower())
            if intent in GROUP_SILENT_INTENTS and not mentioned:
                reply = None
            else:
                reply = _group_redirect_reply()
        else:
            reply = build_telegram_reply(
                intent_info, text, db,
                user.telegram_user_id if user else None,
                chat_type=chat.chat_type,
            )
        if reply:
            client = TelegramClient(channel_id=chat.telegram_chat_id)
            row.reply_status = _dispatch_reply(reply, client, chat.telegram_chat_id)[:200]
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
