"""Generate price chart PNG bytes for Telegram bot."""
from __future__ import annotations

import io

import matplotlib
matplotlib.use("Agg")  # headless — no display needed
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import yfinance as yf


def generate_price_chart(symbol: str, days: int = 7) -> bytes:
    """
    Download OHLCV via yfinance and render a dark-themed price chart.
    Returns PNG bytes ready to send via Telegram sendPhoto.
    """
    ticker = yf.Ticker(symbol)
    interval = "1h" if days <= 7 else "1d"
    hist = ticker.history(period=f"{days}d", interval=interval)

    if hist.empty:
        raise ValueError(f"ไม่พบข้อมูลราคาสำหรับ {symbol}")

    prices = hist["Close"]
    dates = hist.index
    first, last = float(prices.iloc[0]), float(prices.iloc[-1])
    change_pct = (last - first) / first * 100
    is_up = last >= first

    line_color = "#10b981" if is_up else "#ef4444"
    fill_color = line_color

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#1e293b")

    ax.plot(dates, prices, color=line_color, linewidth=2, zorder=3)
    ax.fill_between(dates, prices, prices.min() * 0.999, alpha=0.12, color=fill_color)

    ax.grid(color="#334155", linewidth=0.5, alpha=0.6, zorder=0)
    for spine in ax.spines.values():
        spine.set_color("#334155")

    ax.tick_params(colors="#94a3b8", labelsize=9)
    fmt = mdates.DateFormatter("%d/%m %H:%M" if days <= 2 else "%d/%m")
    ax.xaxis.set_major_formatter(fmt)
    fig.autofmt_xdate(rotation=30, ha="right")

    sign = "+" if is_up else ""
    ax.set_title(
        f"{symbol}   ${last:,.2f}   ({sign}{change_pct:.1f}%)",
        color="white", fontsize=13, fontweight="bold", pad=12,
    )
    ax.set_xlabel(f"{days}-day chart", color="#64748b", fontsize=9)

    # Annotate last price point
    ax.annotate(
        f"${last:,.2f}",
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
    return buf.read()
