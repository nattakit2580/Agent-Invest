from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from agents.base_agent import BaseAgent
from config import get_settings
from fetchers.agenda_fetcher import fetch_agenda_categories, load_ipo_watchlist, split_csv
from fetchers.calendar_fetcher import get_upcoming_events
from fetchers.economic_fetcher import fetch_economic_indicators
from fetchers.market_fetcher import fetch_market_data


DEFAULT_TIMEZONE = "Asia/Bangkok"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt_pct(value: Any) -> str:
    numeric = _safe_float(value)
    sign = "+" if numeric > 0 else ""
    return f"{sign}{numeric:.2f}%"


def _fmt_price(value: Any) -> str:
    if value is None:
        return "n/a"
    numeric = _safe_float(value)
    if numeric >= 1000:
        return f"{numeric:,.2f}"
    if numeric >= 1:
        return f"{numeric:.2f}"
    return f"{numeric:.6f}"


def _local_now() -> datetime:
    settings = get_settings()
    try:
        tz = ZoneInfo(settings.telegram_timezone or DEFAULT_TIMEZONE)
    except Exception:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime.now(tz)


def _article_text(article: dict[str, Any]) -> str:
    return f"{article.get('title', '')} {article.get('summary', '')}".lower()


def _count_symbol_mentions(symbol: str, categories: dict[str, list[dict[str, Any]]]) -> int:
    plain = symbol.replace("-USD", "").replace(".BK", "").lower()
    if not plain:
        return 0
    count = 0
    for articles in categories.values():
        for article in articles:
            if plain in _article_text(article):
                count += 1
    return count


BIAS_TH = {
    "bullish_watch": "ขาขึ้น 🟢",
    "risk_watch": "เฝ้าระวัง 🔴",
    "neutral_watch": "ทรงตัว 🟡",
    "unavailable": "ข้อมูลไม่พร้อม ⚪",
}


def _watch_signal(market_data: dict[str, Any], news_mentions: int) -> tuple[str, float, list[str]]:
    change = _safe_float(market_data.get("price_change_pct"))
    rsi = market_data.get("rsi_14")
    macd = market_data.get("macd")
    macd_signal = market_data.get("macd_signal")

    score = abs(change)
    bias_score = 0.0
    reasons: list[str] = []

    if change >= 2:
        bias_score += 1
        score += 2
        reasons.append("momentum ขาขึ้นแข็งแกร่ง")
    elif change <= -2:
        bias_score -= 1
        score += 2
        reasons.append("ราคาดิ่งลงแรง")

    if rsi is not None:
        rsi_value = _safe_float(rsi)
        if rsi_value >= 70:
            bias_score -= 0.5
            score += 1.5
            reasons.append(f"RSI overbought {rsi_value:.1f}")
        elif rsi_value <= 35:
            bias_score += 0.5
            score += 1.5
            reasons.append(f"RSI oversold {rsi_value:.1f}")

    if macd is not None and macd_signal is not None:
        macd_value = _safe_float(macd)
        signal_value = _safe_float(macd_signal)
        if macd_value > signal_value:
            bias_score += 0.4
            score += 0.7
            reasons.append("MACD อยู่เหนือ signal line")
        elif macd_value < signal_value:
            bias_score -= 0.4
            score += 0.7
            reasons.append("MACD อยู่ต่ำกว่า signal line")

    if news_mentions:
        score += min(news_mentions, 5) * 0.4
        reasons.append(f"ถูกกล่าวถึงใน {news_mentions} รายการข่าว")

    if not reasons:
        reasons.append("ราคาทรงตัว รอ catalyst ใหม่")

    if bias_score > 0.35:
        bias = "bullish_watch"
    elif bias_score < -0.35:
        bias = "risk_watch"
    else:
        bias = "neutral_watch"

    return bias, round(score, 3), reasons[:4]


def build_watchlist_summary(
    symbols: list[str] | None = None,
    *,
    categories: dict[str, list[dict[str, Any]]] | None = None,
    max_assets: int | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    requested_symbols = symbols or split_csv(settings.monitor_watchlist_symbols)
    limit = max_assets or settings.monitor_report_max_watchlist_assets
    category_data = categories or {}

    items: list[dict[str, Any]] = []
    for raw_symbol in requested_symbols[:limit]:
        symbol = raw_symbol.strip().upper()
        if not symbol:
            continue
        try:
            market_data = fetch_market_data(symbol)
            news_mentions = _count_symbol_mentions(symbol, category_data)
            bias, priority, reasons = _watch_signal(market_data, news_mentions)
            items.append(
                {
                    "symbol": symbol,
                    "company_name": market_data.get("company_name", symbol),
                    "price": market_data.get("price"),
                    "price_change_pct": market_data.get("price_change_pct"),
                    "volume": market_data.get("volume"),
                    "rsi_14": market_data.get("rsi_14"),
                    "macd": market_data.get("macd"),
                    "macd_signal": market_data.get("macd_signal"),
                    "bias": bias,
                    "watch_priority": priority,
                    "reasons": reasons,
                    "fetched_at": market_data.get("fetched_at"),
                    "error": None,
                }
            )
        except Exception as exc:
            items.append(
                {
                    "symbol": symbol,
                    "company_name": symbol,
                    "price": None,
                    "price_change_pct": None,
                    "bias": "unavailable",
                    "watch_priority": 0,
                    "reasons": [f"market data unavailable: {str(exc)[:160]}"],
                    "error": str(exc),
                }
            )

    return sorted(items, key=lambda item: item.get("watch_priority", 0), reverse=True)


def build_ipo_agenda(categories: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    items = load_ipo_watchlist()
    for article in categories.get("ipo_agenda", [])[:8]:
        items.append(
            {
                "company": article.get("title", "IPO update"),
                "symbol": None,
                "exchange": None,
                "expected_date": article.get("published", ""),
                "status": "news_detected",
                "summary": article.get("summary", ""),
                "link": article.get("link", ""),
                "source": article.get("source", "news"),
            }
        )
    return items[:12]


def _fallback_brief(categories: dict[str, list[dict[str, Any]]], watchlist: list[dict[str, Any]]) -> dict[str, Any]:
    top_watch = [item for item in watchlist if not item.get("error")][:3]
    focus = [f"{item['symbol']}: {BIAS_TH.get(item.get('bias', ''), item.get('bias', 'watch'))}" for item in top_watch]
    if not focus:
        focus = ["ยังไม่มีข้อมูลตลาดที่น่าเชื่อถือ"]

    risks = []
    if categories.get("geopolitic_prediction"):
        risks.append("พาดหัวข่าวภูมิรัฐศาสตร์อาจกระทบความต้องการรับความเสี่ยง")
    if categories.get("economic_agenda"):
        risks.append("ข้อมูลมหภาคที่กำลังจะมาถึงอาจเพิ่มความผันผวน")
    if not risks:
        risks.append("สภาพคล่องตลาดและความพร้อมของข้อมูลยังเป็นความเสี่ยงหลักในระยะใกล้")

    return {
        "headline": "รายงานประจำวันสร้างจากข้อมูลตลาดและข่าวที่จัดหมวดหมู่",
        "daily_focus": focus,
        "risks": risks[:3],
        "action_items": [
            "ตรวจสอบ Watchlist ที่มีความสำคัญสูงก่อนตลาดเปิด",
            "ตรวจสอบวันที่และแหล่งข้อมูลหลักก่อนดำเนินการตาม IPO หรือวาระเศรษฐกิจ",
        ],
    }


def _generate_ai_brief(
    categories: dict[str, list[dict[str, Any]]],
    watchlist: list[dict[str, Any]],
    economic_indicators: list[dict[str, Any]] | None = None,
    use_ai: bool | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    economic_indicators = economic_indicators or []
    effective_use_ai = settings.telegram_use_ai_summary if use_ai is None else use_ai
    if not effective_use_ai or not settings.openrouter_api_key:
        return _fallback_brief(categories, watchlist)

    compact_categories = {
        category: [
            {
                "title": item.get("title"),
                "summary": item.get("summary"),
                "source": item.get("source"),
                "published": item.get("published"),
            }
            for item in items[:5]
        ]
        for category, items in categories.items()
    }
    compact_watchlist = [
        {
            "symbol": item.get("symbol"),
            "price_change_pct": item.get("price_change_pct"),
            "bias": item.get("bias"),
            "reasons": item.get("reasons"),
        }
        for item in watchlist[:8]
    ]
    compact_economics = [
        {
            "label": item.get("label"),
            "value": item.get("value"),
            "change": item.get("change"),
            "change_pct": item.get("change_pct"),
            "date": item.get("observation_date"),
        }
        for item in economic_indicators[:15]
    ]

    system = (
        "You are an institutional markets editor. Return ONLY valid JSON, no markdown. "
        "Write ALL text fields (headline, daily_focus, risks, action_items) in Thai language. "
        "Be concise and do not provide personalized financial advice."
    )
    user = f"""สร้างสรุปรายงานตลาดประจำวันสำหรับ Telegram จากข้อมูลด้านล่าง

DATA:
{json.dumps({"categories": compact_categories, "watchlist": compact_watchlist, "economic_indicators": compact_economics}, ensure_ascii=False)}

Return this exact JSON (all text values must be in Thai):
{{
  "headline": "<หนึ่งประโยคสรุปภาพรวมตลาดวันนี้>",
  "daily_focus": ["<ประเด็นที่ 1>", "<ประเด็นที่ 2>", "<ประเด็นที่ 3>"],
  "risks": ["<ความเสี่ยง 1>", "<ความเสี่ยง 2>"],
  "action_items": ["<สิ่งที่ควรทำ 1>", "<สิ่งที่ควรทำ 2>"]
}}"""

    try:
        agent = BaseAgent()
        result = agent._parse_json(agent._call_llm(system, user, max_tokens=800))
        return {
            "headline": str(result.get("headline", "")).strip() or "Daily monitor generated.",
            "daily_focus": list(result.get("daily_focus") or [])[:4],
            "risks": list(result.get("risks") or [])[:4],
            "action_items": list(result.get("action_items") or [])[:4],
        }
    except Exception:
        return _fallback_brief(categories, watchlist)


def _translate_categories_th(categories: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """แปล title/summary ของข่าวที่จะแสดงในรายงานเป็นภาษาไทย (LLM call เดียว).

    ลิงก์ต้นฉบับคงไว้เสมอ — ผู้อ่านกดเข้าไปอ่านฉบับเต็มได้
    แปลไม่สำเร็จ = คืนต้นฉบับเดิม ไม่ทำให้รายงานล้ม
    """
    settings = get_settings()
    if not settings.telegram_translate_news or not settings.openrouter_api_key:
        return categories

    # เก็บเฉพาะรายการที่จะถูก render จริง (5 ต่อหมวด) เพื่อไม่เปลือง token
    to_translate: list[dict[str, str]] = []
    index_map: list[tuple[str, int]] = []   # (category, item_index)
    for category, items in categories.items():
        for i, item in enumerate(items[:5]):
            to_translate.append({
                "title": item.get("title", "")[:240],
                "summary": item.get("summary", "")[:400],
            })
            index_map.append((category, i))

    if not to_translate:
        return categories

    system = (
        "You are a professional Thai financial news translator. "
        "Translate each news title and summary into natural Thai suitable for investors. "
        "Keep ticker symbols, company names, numbers, and financial terms like RSI/MACD/IPO/FOMC in English. "
        "Return ONLY valid JSON, no markdown."
    )
    user = f"""แปลข่าวการเงินต่อไปนี้เป็นภาษาไทย

INPUT (JSON array):
{json.dumps(to_translate, ensure_ascii=False)}

Return this exact JSON — array เดียวกัน ลำดับเดิม จำนวนเท่าเดิม ({len(to_translate)} รายการ):
{{"translations": [{{"title_th": "<หัวข้อภาษาไทย>", "summary_th": "<สรุปภาษาไทย 1-2 ประโยค>"}}]}}"""

    try:
        agent = BaseAgent()
        agent.name = "news_translator"
        result = agent._parse_json(agent._call_llm(system, user, max_tokens=3000))
        translations = result.get("translations", [])
        if len(translations) != len(index_map):
            return categories

        for (category, i), tr in zip(index_map, translations):
            title_th = str(tr.get("title_th", "")).strip()
            summary_th = str(tr.get("summary_th", "")).strip()
            if title_th:
                categories[category][i]["title"] = title_th
            if summary_th:
                categories[category][i]["summary"] = summary_th
        return categories
    except Exception as e:
        print(f"[monitor_report] translate error (ใช้ต้นฉบับแทน): {e}")
        return categories


def _format_article(article: dict[str, Any]) -> str:
    title = article.get("title", "Untitled")
    source = article.get("source", "unknown")
    published = article.get("published", "")
    link = article.get("link", "")
    suffix = f" ({source})" if source else ""
    date_part = f" [{published}]" if published else ""
    line = f"- {title}{suffix}{date_part}"
    if link:
        line += f"\n  {link}"
    return line


def _format_ipo(item: dict[str, Any]) -> str:
    company = item.get("company") or "IPO update"
    exchange = item.get("exchange") or "exchange n/a"
    expected_date = item.get("expected_date") or "date n/a"
    status = item.get("status") or "watching"
    link = item.get("link") or ""
    line = f"- {company} | {exchange} | {expected_date} | {status}"
    if link:
        line += f"\n  {link}"
    return line


_EVENT_TYPE_LABELS = {
    "earnings": "Earnings",
    "dividend": "Ex-Dividend",
    "ipo": "IPO",
    "economic": "Economic release",
}


def _format_calendar_event(item: dict[str, Any]) -> str:
    label = _EVENT_TYPE_LABELS.get(item.get("event_type"), item.get("event_type", "event"))
    title = item.get("title", "event")
    event_date = item.get("event_date", "")
    days_until = item.get("days_until")
    if days_until == 0:
        when = "today"
    elif days_until == 1:
        when = "in 1 day"
    elif isinstance(days_until, int):
        when = f"in {days_until} days"
    else:
        when = ""
    when_text = f" ({when})" if when else ""
    return f"- [{label}] {title} — {event_date}{when_text}"


def _format_indicator(item: dict[str, Any]) -> str:
    label = item.get("label", item.get("series_id", "indicator"))
    value = item.get("value")
    unit = item.get("unit") or ""
    unit_suffix = f" {unit}" if unit else ""
    date = item.get("observation_date") or ""
    value_text = _fmt_price(value) if value is not None else "n/a"

    change = item.get("change")
    change_pct = item.get("change_pct")
    if change is not None:
        arrow = "up" if change > 0 else ("down" if change < 0 else "flat")
        pct_text = f" ({_fmt_pct(change_pct)})" if change_pct is not None else ""
        change_text = f" | {arrow} {change:+.2f}{pct_text} vs prev"
    else:
        change_text = ""

    date_text = f" [{date}]" if date else ""
    return f"- {label}: {value_text}{unit_suffix}{change_text}{date_text}"


def render_daily_monitor_message(report: dict[str, Any]) -> str:
    categories = report["categories"]
    watchlist = report["watchlist"]
    ipo_agenda = report["ipo_agenda"]
    brief = report["brief"]
    generated_at = report["generated_at"]

    lines: list[str] = [
        "🗓 ภาพรวมตลาดประจำวัน — Agent Invest",
        f"สร้างเมื่อ: {generated_at}",
        "",
        "── สรุปภาพรวม ──",
        f"• {brief.get('headline', 'รายงานประจำวันสร้างจากข้อมูลตลาด')}",
    ]

    for item in brief.get("daily_focus", [])[:4]:
        lines.append(f"• {item}")

    settings = get_settings()
    watchlist_limit = settings.telegram_private_report_max_assets
    lines.extend(["", "── Watchlist ──"])
    for item in watchlist[:watchlist_limit]:
        symbol = item.get("symbol", "-")
        bias_raw = item.get("bias", "watch")
        bias = BIAS_TH.get(bias_raw, bias_raw)
        price = _fmt_price(item.get("price"))
        change = _fmt_pct(item.get("price_change_pct")) if item.get("price_change_pct") is not None else "n/a"
        rsi = item.get("rsi_14")
        rsi_text = f" | RSI {rsi}" if rsi is not None else ""
        reasons = "; ".join(item.get("reasons", [])[:2])
        lines.append(f"• {symbol}: {price} ({change}) | {bias}{rsi_text}")
        if reasons:
            lines.append(f"   {reasons}")

    lines.extend(["", "── ปฏิทินล่วงหน้า (แจ้งเตือน) ──"])
    upcoming_events = report.get("upcoming_events", [])
    if upcoming_events:
        lines.extend(_format_calendar_event(item) for item in upcoming_events[:12])
    else:
        lines.append("• ไม่มีกำหนดการ earnings / ปันผล / IPO ในช่วงที่ตั้งค่าไว้")

    lines.extend(["", "── IPO ที่น่าจับตา ──"])
    if ipo_agenda:
        lines.extend(_format_ipo(item) for item in ipo_agenda[:6])
    else:
        lines.append("• ไม่พบ IPO agenda จากแหล่งข้อมูลที่ตั้งค่าไว้")

    lines.extend(["", "── ตัวเลขเศรษฐกิจ (ล่าสุด) ──"])
    economic_indicators = report.get("economic_indicators", [])
    if economic_indicators:
        lines.extend(_format_indicator(item) for item in economic_indicators)
    else:
        lines.append("• ไม่มีข้อมูลตัวเลขเศรษฐกิจ (ตั้งค่า FRED_API_KEY เพื่อเปิดใช้งาน)")

    lines.extend(["", "── วาระเศรษฐกิจ ──"])
    economic_items = categories.get("economic_agenda", [])
    if economic_items:
        lines.extend(_format_article(item) for item in economic_items[:5])
    else:
        lines.append("• ไม่พบวาระเศรษฐกิจจากแหล่งข้อมูลที่ตั้งค่าไว้")

    lines.extend(["", "── ความเสี่ยงภูมิรัฐศาสตร์ ──"])
    geopolitic_items = categories.get("geopolitic_prediction", [])
    if geopolitic_items:
        lines.extend(_format_article(item) for item in geopolitic_items[:5])
    else:
        lines.append("• ไม่พบรายการความเสี่ยงภูมิรัฐศาสตร์จากแหล่งข้อมูลที่ตั้งค่าไว้")

    lines.extend(["", "── ข่าวที่น่าติดตาม ──"])
    news_items = categories.get("noteworthy_news", [])
    if news_items:
        lines.extend(_format_article(item) for item in news_items[:5])
    else:
        lines.append("• ไม่พบข่าวสำคัญจากแหล่งข้อมูลที่ตั้งค่าไว้")

    risks = brief.get("risks", [])
    if risks:
        lines.extend(["", "⚠️ ความเสี่ยง"])
        lines.extend(f"• {risk}" for risk in risks[:4])

    actions = brief.get("action_items", [])
    if actions:
        lines.extend(["", "📋 สิ่งที่ควรทำวันนี้"])
        lines.extend(f"• {action}" for action in actions[:4])

    lines.extend([
        "",
        "⚠️ ข้อมูลนี้สร้างโดยระบบอัตโนมัติ ไม่ใช่คำแนะนำทางการเงิน กรุณาตรวจสอบแหล่งข้อมูลก่อนตัดสินใจ",
    ])
    return "\n".join(lines)

def render_public_monitor_message(
    report: dict[str, Any],
    *,
    max_watchlist_assets: int | None = None,
    max_news_items: int | None = None,
) -> str:
    settings = get_settings()
    watchlist_limit = max_watchlist_assets or settings.telegram_public_watchlist_limit
    news_limit = max_news_items or settings.telegram_public_news_limit
    categories = report["categories"]
    watchlist = report["watchlist"]
    ipo_agenda = report["ipo_agenda"]
    brief = report["brief"]

    lines: list[str] = [
        "🗓 อัปเดตตลาดประจำวัน — Agent Invest",
        f"สร้างเมื่อ: {report['generated_at']}",
        "",
        "── โฟกัสตลาดวันนี้ ──",
        f"• {brief.get('headline', 'รายงานประจำวันสร้างจากข้อมูลตลาด')}",
    ]

    lines.extend(["", "── ภาพรวม Watchlist ──"])
    for item in watchlist[:watchlist_limit]:
        symbol = item.get("symbol", "-")
        bias_raw = item.get("bias", "watch")
        bias = BIAS_TH.get(bias_raw, bias_raw)
        price = _fmt_price(item.get("price"))
        change = _fmt_pct(item.get("price_change_pct")) if item.get("price_change_pct") is not None else "n/a"
        lines.append(f"• {symbol}: {price} ({change}) | {bias}")

    lines.extend(["", "── ข่าวที่น่าติดตาม ──"])
    news_items = categories.get("noteworthy_news", [])
    if news_items:
        lines.extend(_format_article(item) for item in news_items[:news_limit])
    else:
        lines.append("• ไม่พบข่าวสำคัญจากแหล่งข้อมูลที่ตั้งค่าไว้")

    lines.extend(["", "── IPO ที่น่าจับตา ──"])
    if ipo_agenda:
        lines.extend(_format_ipo(item) for item in ipo_agenda[: max(1, min(news_limit, 2))])
    else:
        lines.append("• ไม่พบ IPO agenda จากแหล่งข้อมูลที่ตั้งค่าไว้")

    lines.extend([
        "",
        "สมาชิก Premium รับ Watchlist เต็ม, IPO agenda, วาระเศรษฐกิจ และการวิเคราะห์เพิ่มเติม",
        "⚠️ ข้อมูลนี้สร้างโดยระบบอัตโนมัติ ไม่ใช่คำแนะนำทางการเงิน",
    ])
    return "\n".join(lines)

def build_daily_monitor_report(
    *,
    symbols: list[str] | None = None,
    max_news_items: int | None = None,
    max_assets: int | None = None,
    use_ai: bool | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    now = _local_now()
    categories = fetch_agenda_categories(max_items=max_news_items or settings.monitor_report_max_news_items)
    categories = _translate_categories_th(categories)
    watchlist = build_watchlist_summary(symbols, categories=categories, max_assets=max_assets)
    ipo_agenda = build_ipo_agenda(categories)
    try:
        economic_indicators = fetch_economic_indicators()[: settings.monitor_economic_report_limit]
    except Exception as exc:
        print(f"[monitor_report] economic indicators unavailable: {exc}")
        economic_indicators = []
    try:
        upcoming_events = get_upcoming_events()
    except Exception as exc:
        print(f"[monitor_report] upcoming events unavailable: {exc}")
        upcoming_events = []
    brief = _generate_ai_brief(categories, watchlist, economic_indicators, use_ai=use_ai)

    report = {
        "title": "ภาพรวมตลาดประจำวัน — Agent Invest",
        "report_date": now.date().isoformat(),
        "generated_at": now.strftime("%Y-%m-%d %H:%M %Z"),
        "categories": categories,
        "watchlist": watchlist,
        "ipo_agenda": ipo_agenda,
        "economic_indicators": economic_indicators,
        "upcoming_events": upcoming_events,
        "brief": brief,
    }
    report["message"] = render_daily_monitor_message(report)
    return report
