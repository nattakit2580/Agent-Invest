"""TradingView-style chart PNGs for the Telegram bot: candlesticks + moving
averages + support/resistance + volume, plus multi-symbol compare and a
portfolio donut."""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import matplotlib
matplotlib.use("Agg")  # headless — no display needed
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import yfinance as yf


# currency symbol by yfinance suffix — HK dollar / China yuan / default USD
_SUFFIX_CURRENCY = {
    ".HK": "HK$", ".SS": "¥", ".SZ": "¥", ".SH": "¥",
    ".TW": "NT$", ".T": "¥", ".BK": "฿",
}


def _currency_for(symbol: str) -> str:
    up = symbol.upper()
    for suffix, cur in _SUFFIX_CURRENCY.items():
        if up.endswith(suffix):
            return cur
    return "$"


# timeframe key -> (lookback days, interval, thai label). We download by
# start/end date (yfinance's `period` doesn't accept 3y/4y). Weekly candles for
# the multi-year views so they stay readable.
TF_SPEC: dict[str, tuple[int, str, str]] = {
    "1w": (7, "1h", "1 สัปดาห์"),
    "1m": (30, "1d", "1 เดือน"),
    "3m": (90, "1d", "3 เดือน"),
    "6m": (180, "1d", "6 เดือน"),
    "1y": (365, "1d", "1 ปี"),
    "2y": (730, "1d", "2 ปี"),
    "3y": (1095, "1wk", "3 ปี"),
    "4y": (1460, "1wk", "4 ปี"),
    "5y": (1825, "1wk", "5 ปี"),
}
DEFAULT_TF = "1y"


def _download(symbol: str, days: int, interval: str) -> pd.DataFrame:
    """OHLCV via yfinance by date range (works for any lookback, incl. 3y/4y)."""
    end = datetime.now(timezone.utc) + timedelta(days=1)
    start = end - timedelta(days=days + 6)
    return yf.Ticker(symbol).history(
        start=start.date().isoformat(), end=end.date().isoformat(), interval=interval
    )

_UP = "#26a69a"     # TradingView green
_DOWN = "#ef5350"   # TradingView red
_BG = "#0f172a"


def _mav_lengths(timeframe: str, interval: str, n: int) -> tuple[int, ...]:
    """Moving-average window lengths appropriate to the candle interval, filtered
    to what the data actually supports."""
    if interval == "1wk":
        candidates = (10, 30)      # ~ MA50 / MA150 in daily terms
    elif timeframe in ("1w", "1m"):
        candidates = (9, 21)       # short-term
    else:
        candidates = (50, 200)     # classic daily MAs
    return tuple(m for m in candidates if m < n)


def _support_resistance(df: pd.DataFrame, k: int = 5, max_each: int = 2) -> tuple[list[float], list[float]]:
    """Pivot-based support/resistance: local swing highs above the current price
    (resistance) and swing lows below it (support), nearest first."""
    highs = df["High"].values
    lows = df["Low"].values
    n = len(df)
    last = float(df["Close"].values[-1])
    piv_high: list[float] = []
    piv_low: list[float] = []
    for i in range(k, n - k):
        if highs[i] == highs[i - k:i + k + 1].max():
            piv_high.append(float(highs[i]))
        if lows[i] == lows[i - k:i + k + 1].min():
            piv_low.append(float(lows[i]))
    res = sorted({round(h, 2) for h in piv_high if h > last})[:max_each]
    sup = sorted({round(l, 2) for l in piv_low if l < last}, reverse=True)[:max_each]
    return res, sup


def _trend_from_ma(df: pd.DataFrame, long_len: int) -> tuple[str, str, str]:
    """Trend from price vs its long moving average — clearer and more meaningful
    than a raw regression slope. Returns (thai, english, hex_color)."""
    close = df["Close"]
    last = float(close.iloc[-1])
    if len(close) >= long_len:
        ma = float(close.rolling(long_len).mean().iloc[-1])
    else:
        ma = float(close.mean())
    if last > ma * 1.01:
        return "ขาขึ้น", "UPTREND", _UP
    if last < ma * 0.99:
        return "ขาลง", "DOWNTREND", _DOWN
    return "ไซด์เวย์", "SIDEWAYS", "#f59e0b"


def _dark_style(mav_colors: list[str]):
    mc = mpf.make_marketcolors(
        up=_UP, down=_DOWN,
        edge={"up": _UP, "down": _DOWN},
        wick={"up": _UP, "down": _DOWN},
        volume={"up": _UP, "down": _DOWN},
    )
    return mpf.make_mpf_style(
        base_mpf_style="nightclouds",
        marketcolors=mc,
        mavcolors=mav_colors,
        facecolor=_BG, edgecolor="#334155", gridcolor="#1e293b",
        gridstyle="--", figcolor=_BG,
        rc={
            "axes.labelcolor": "#94a3b8", "xtick.color": "#94a3b8",
            "ytick.color": "#94a3b8", "text.color": "#e2e8f0",
            "axes.titlecolor": "#ffffff",
        },
    )


def generate_price_chart(symbol: str, timeframe: str = DEFAULT_TF) -> tuple[bytes, dict]:
    """Candlestick chart with moving averages, support/resistance and volume,
    TradingView-style. `timeframe` is a key of TF_SPEC (1w..5y).
    Returns (png_bytes, meta)."""
    tf = timeframe if timeframe in TF_SPEC else DEFAULT_TF
    days, interval, tf_label = TF_SPEC[tf]

    df = _download(symbol, days, interval)
    if df.empty:
        raise ValueError(f"ไม่พบข้อมูลราคาสำหรับ {symbol}")
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if len(df) < 2:
        raise ValueError(f"ข้อมูลราคา {symbol} ไม่พอวาดกราฟ")

    cur = _currency_for(symbol)
    closes = df["Close"]
    first, last = float(closes.iloc[0]), float(closes.iloc[-1])
    change_pct = (last - first) / first * 100 if first else 0.0

    mav = _mav_lengths(tf, interval, len(df))
    mav_colors = ["#f59e0b", "#3b82f6", "#a78bfa"][:len(mav)] or ["#f59e0b"]
    long_len = mav[-1] if mav else len(df)
    trend_th, trend_en, _ = _trend_from_ma(df, long_len)

    res, sup = _support_resistance(df)
    levels = res + sup
    level_colors = [_DOWN] * len(res) + [_UP] * len(sup)

    sign = "+" if change_pct >= 0 else ""
    title = f"{symbol}   {cur}{last:,.2f}   ({sign}{change_pct:.1f}%)   {trend_en}   [{tf}]"

    plot_kwargs = dict(
        type="candle",
        style=_dark_style(mav_colors),
        volume=True,
        figsize=(12, 7.5),
        title=title,
        ylabel="Price",
        ylabel_lower="Volume",
        returnfig=True,
        tight_layout=True,
        xrotation=12,
        scale_padding={"left": 0.4, "right": 0.9, "top": 0.9, "bottom": 0.6},
    )
    if mav:
        plot_kwargs["mav"] = mav
    if levels:
        plot_kwargs["hlines"] = dict(
            hlines=levels, colors=level_colors,
            linestyle="--", linewidths=0.9, alpha=0.65,
        )

    fig, axes = mpf.plot(df, **plot_kwargs)

    # label each support/resistance line with its price, on the right edge
    ax = axes[0]
    xr = ax.get_xlim()[1]
    for lvl, col in zip(levels, level_colors):
        ax.text(xr, lvl, f" {cur}{lvl:,.2f}", color=col, fontsize=8,
                va="center", ha="left", fontweight="bold")
    # legend for the moving averages
    if mav:
        handles = [plt.Line2D([0], [0], color=mav_colors[i], lw=1.6) for i in range(len(mav))]
        unit = "wk" if interval == "1wk" else "d"
        ax.legend(handles, [f"MA{m}{unit}" for m in mav], loc="upper left",
                  fontsize=8, framealpha=0.15, labelcolor="#e2e8f0")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, facecolor=_BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    return buf.read(), {
        "symbol": symbol, "currency": cur, "timeframe": tf, "tf_label": tf_label,
        "last_price": last, "change_pct": change_pct,
        "trend_th": trend_th, "trend_en": trend_en,
        "resistance": res, "support": sup,
        "ma": [int(m) for m in mav], "ma_unit": ("สัปดาห์" if interval == "1wk" else "วัน"),
    }


_SERIES_COLORS = ["#38bdf8", "#f59e0b", "#10b981", "#ef4444", "#a78bfa", "#f472b6"]


def _style_dark(fig, ax):
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor("#1e293b")
    ax.grid(color="#334155", linewidth=0.5, alpha=0.6, zorder=0)
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.tick_params(colors="#94a3b8", labelsize=9)


def generate_compare_chart(symbols: list[str], timeframe: str = "6m") -> tuple[bytes, dict]:
    """Overlay 2–4 symbols, each normalized to % change from the window start
    (so different price scales compare). Returns (png, meta)."""
    symbols = [s for s in symbols if s][:4]
    if len(symbols) < 2:
        raise ValueError("ต้องมีอย่างน้อย 2 สัญลักษณ์เพื่อเปรียบเทียบ")
    tf = timeframe if timeframe in TF_SPEC else "6m"
    days, interval, tf_label = TF_SPEC[tf]

    fig, ax = plt.subplots(figsize=(11, 6))
    _style_dark(fig, ax)

    changes: dict[str, float] = {}
    plotted = 0
    for i, sym in enumerate(symbols):
        try:
            hist = _download(sym, days, interval)
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
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m" if interval != "1wk" else "%b %y"))
    fig.autofmt_xdate(rotation=30, ha="right")
    ax.set_title(f"Compare — % change [{tf}]", color="white", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("% change", color="#64748b", fontsize=9)
    leg = ax.legend(loc="upper left", fontsize=9, framealpha=0.15)
    for txt in leg.get_texts():
        txt.set_color("#e2e8f0")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=110, facecolor=_BG)
    plt.close(fig)
    buf.seek(0)
    return buf.read(), {"symbols": list(changes.keys()), "timeframe": tf, "tf_label": tf_label, "changes": changes}


def generate_portfolio_chart(holdings: list[dict]) -> tuple[bytes, dict]:
    """Donut of holdings by current market value + totals in the center."""
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
    fig.patch.set_facecolor(_BG)
    wedges, _ = ax.pie(values, colors=colors, startangle=90, counterclock=False,
                       wedgeprops={"width": 0.42, "edgecolor": _BG, "linewidth": 2})
    ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5),
              fontsize=10, framealpha=0, labelcolor="#e2e8f0")

    sign = "+" if total_pnl >= 0 else ""
    pnl_color = _UP if total_pnl >= 0 else _DOWN
    ax.text(0, 0.12, f"${total_value:,.0f}", ha="center", va="center",
            color="white", fontsize=17, fontweight="bold")
    ax.text(0, -0.12, f"{sign}${total_pnl:,.0f} ({sign}{total_pnl_pct:.1f}%)",
            ha="center", va="center", color=pnl_color, fontsize=12, fontweight="bold")
    ax.set_title("Portfolio Allocation & P&L", color="white", fontsize=14, fontweight="bold", pad=14)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=110, facecolor=_BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read(), {
        "total_value": total_value, "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct, "holdings": len(holdings),
    }
