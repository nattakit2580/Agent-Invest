"""Generate price chart PNG bytes (with trend) for the Telegram bot."""
from __future__ import annotations

import io

import matplotlib
matplotlib.use("Agg")  # headless — no display needed
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import yfinance as yf


# currency symbol by yfinance suffix — HK dollar / China yuan / default USD
_SUFFIX_CURRENCY = {
    ".HK": "HK$",
    ".SS": "¥",   # Shanghai (CNY)
    ".SZ": "¥",   # Shenzhen (CNY)
    ".SH": "¥",
    ".TW": "NT$",
    ".T": "¥",    # Tokyo (JPY)
    ".BK": "฿",   # Thailand
}


def _currency_for(symbol: str) -> str:
    up = symbol.upper()
    for suffix, cur in _SUFFIX_CURRENCY.items():
        if up.endswith(suffix):
            return cur
    return "$"


def _linear_trend(y: list[float]) -> tuple[list[float], float]:
    """Least-squares line over y (x = 0..n-1). Returns (fitted_values, slope_pct)
    where slope_pct is the % change from the fitted start to the fitted end."""
    n = len(y)
    if n < 2:
        return list(y), 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(y) / n
    denom = sum((x - mean_x) ** 2 for x in xs) or 1e-9
    slope = sum((xs[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / denom
    intercept = mean_y - slope * mean_x
    fitted = [slope * x + intercept for x in xs]
    start, end = fitted[0], fitted[-1]
    slope_pct = ((end - start) / start * 100) if start else 0.0
    return fitted, slope_pct


def _trend_label(slope_pct: float) -> tuple[str, str, str, str]:
    """Return (thai_label, english_label, arrow, hex_color) from the trend slope.
    English is used on the PNG (matplotlib's default font has no Thai glyphs);
    Thai is used in the Telegram caption, which renders Thai fine."""
    if slope_pct > 1.5:
        return "ขาขึ้น", "UPTREND", "▲", "#10b981"
    if slope_pct < -1.5:
        return "ขาลง", "DOWNTREND", "▼", "#ef4444"
    return "ไซด์เวย์", "SIDEWAYS", "▬", "#f59e0b"


def generate_price_chart(symbol: str, days: int = 7) -> tuple[bytes, dict]:
    """Download OHLCV via yfinance and render a dark-themed price chart with a
    linear trend line. Returns (png_bytes, meta) where meta describes the trend
    so the caller can build a caption.
    """
    ticker = yf.Ticker(symbol)
    interval = "1h" if days <= 7 else "1d"
    hist = ticker.history(period=f"{days}d", interval=interval)

    if hist.empty:
        raise ValueError(f"ไม่พบข้อมูลราคาสำหรับ {symbol}")

    prices = hist["Close"]
    dates = hist.index
    close_vals = [float(p) for p in prices]
    first, last = close_vals[0], close_vals[-1]
    change_pct = (last - first) / first * 100 if first else 0.0
    is_up = last >= first
    cur = _currency_for(symbol)

    fitted, slope_pct = _linear_trend(close_vals)
    trend_th, trend_en, arrow, trend_color = _trend_label(slope_pct)

    line_color = "#10b981" if is_up else "#ef4444"

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#1e293b")

    ax.plot(dates, prices, color=line_color, linewidth=2, zorder=3, label="Price")
    ax.fill_between(dates, prices, min(close_vals) * 0.999, alpha=0.12, color=line_color)
    # trend line (dashed) over the same window
    ax.plot(dates, fitted, color=trend_color, linewidth=1.6, linestyle="--", alpha=0.9,
            zorder=4, label=f"Trend: {trend_en}")

    ax.grid(color="#334155", linewidth=0.5, alpha=0.6, zorder=0)
    for spine in ax.spines.values():
        spine.set_color("#334155")

    ax.tick_params(colors="#94a3b8", labelsize=9)
    fmt = mdates.DateFormatter("%d/%m %H:%M" if days <= 2 else "%d/%m")
    ax.xaxis.set_major_formatter(fmt)
    fig.autofmt_xdate(rotation=30, ha="right")

    sign = "+" if is_up else ""
    ax.set_title(
        f"{symbol}   {cur}{last:,.2f}   ({sign}{change_pct:.1f}%)   {arrow} {trend_en}",
        color="white", fontsize=13, fontweight="bold", pad=12,
    )
    ax.set_xlabel(f"{days}-day chart", color="#64748b", fontsize=9)
    leg = ax.legend(loc="upper left", fontsize=8, framealpha=0.15)
    for txt in leg.get_texts():
        txt.set_color("#cbd5e1")

    ax.annotate(
        f"{cur}{last:,.2f}",
        xy=(dates[-1], last),
        xytext=(-55, 10),
        textcoords="offset points",
        color=line_color,
        fontsize=10,
        fontweight="bold",
    )

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=110, facecolor="#0f172a")
    plt.close(fig)
    buf.seek(0)

    meta = {
        "symbol": symbol,
        "currency": cur,
        "last_price": last,
        "change_pct": change_pct,
        "slope_pct": slope_pct,
        "trend_th": trend_th,
        "arrow": arrow,
        "days": days,
        "recent_high": max(close_vals),
        "recent_low": min(close_vals),
    }
    return buf.read(), meta


_SERIES_COLORS = ["#38bdf8", "#f59e0b", "#10b981", "#ef4444", "#a78bfa", "#f472b6"]


def _style_dark(fig, ax):
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#1e293b")
    ax.grid(color="#334155", linewidth=0.5, alpha=0.6, zorder=0)
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.tick_params(colors="#94a3b8", labelsize=9)


def generate_compare_chart(symbols: list[str], days: int = 30) -> tuple[bytes, dict]:
    """Overlay 2–4 symbols on one chart, each normalized to % change from the
    window start (so different price scales are comparable). Returns (png, meta)
    where meta['changes'] maps symbol -> final % change."""
    symbols = [s for s in symbols if s][:4]
    if len(symbols) < 2:
        raise ValueError("ต้องมีอย่างน้อย 2 สัญลักษณ์เพื่อเปรียบเทียบ")

    interval = "1h" if days <= 7 else "1d"
    fig, ax = plt.subplots(figsize=(10, 5))
    _style_dark(fig, ax)

    changes: dict[str, float] = {}
    plotted = 0
    for i, sym in enumerate(symbols):
        try:
            hist = yf.Ticker(sym).history(period=f"{days}d", interval=interval)
        except Exception:
            continue
        if hist.empty:
            continue
        closes = [float(p) for p in hist["Close"]]
        base = closes[0] if closes and closes[0] else None
        if not base:
            continue
        pct_series = [(p - base) / base * 100 for p in closes]
        color = _SERIES_COLORS[i % len(_SERIES_COLORS)]
        final = pct_series[-1]
        changes[sym] = final
        sign = "+" if final >= 0 else ""
        ax.plot(hist.index, pct_series, color=color, linewidth=2, zorder=3,
                label=f"{sym}  {sign}{final:.1f}%")
        plotted += 1

    if plotted < 2:
        plt.close(fig)
        raise ValueError("ดึงข้อมูลเปรียบเทียบไม่พอ (ต้องได้อย่างน้อย 2 ตัว)")

    ax.axhline(0, color="#64748b", linewidth=0.8, linestyle=":", zorder=1)
    fmt = mdates.DateFormatter("%d/%m %H:%M" if days <= 2 else "%d/%m")
    ax.xaxis.set_major_formatter(fmt)
    fig.autofmt_xdate(rotation=30, ha="right")
    ax.set_title(f"Compare ({days}d)  —  % change", color="white", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("% change", color="#64748b", fontsize=9)
    leg = ax.legend(loc="upper left", fontsize=9, framealpha=0.15)
    for txt in leg.get_texts():
        txt.set_color("#e2e8f0")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=110, facecolor="#0f172a")
    plt.close(fig)
    buf.seek(0)
    return buf.read(), {"symbols": list(changes.keys()), "days": days, "changes": changes}


def generate_portfolio_chart(holdings: list[dict]) -> tuple[bytes, dict]:
    """Pie of holdings by current market value + totals in the title.
    `holdings`: list of {symbol, value, cost, pnl}. Returns (png, meta)."""
    holdings = [h for h in holdings if (h.get("value") or 0) > 0]
    if not holdings:
        raise ValueError("พอร์ตว่างเปล่า")

    holdings = sorted(holdings, key=lambda h: h["value"], reverse=True)
    total_value = sum(h["value"] for h in holdings)
    total_cost = sum(h.get("cost") or 0 for h in holdings)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0.0

    labels = [f"{h['symbol']}  {h['value'] / total_value * 100:.0f}%" for h in holdings]
    values = [h["value"] for h in holdings]
    colors = [_SERIES_COLORS[i % len(_SERIES_COLORS)] for i in range(len(holdings))]

    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor("#0f172a")
    wedges, _ = ax.pie(values, colors=colors, startangle=90, counterclock=False,
                       wedgeprops={"width": 0.42, "edgecolor": "#0f172a", "linewidth": 2})
    ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5),
              fontsize=10, framealpha=0, labelcolor="#e2e8f0")

    sign = "+" if total_pnl >= 0 else ""
    pnl_color = "#10b981" if total_pnl >= 0 else "#ef4444"
    ax.text(0, 0.12, f"${total_value:,.0f}", ha="center", va="center",
            color="white", fontsize=17, fontweight="bold")
    ax.text(0, -0.12, f"{sign}${total_pnl:,.0f} ({sign}{total_pnl_pct:.1f}%)",
            ha="center", va="center", color=pnl_color, fontsize=12, fontweight="bold")
    ax.set_title("Portfolio Allocation & P&L", color="white", fontsize=14, fontweight="bold", pad=14)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=110, facecolor="#0f172a", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read(), {
        "total_value": total_value, "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct, "holdings": len(holdings),
    }
