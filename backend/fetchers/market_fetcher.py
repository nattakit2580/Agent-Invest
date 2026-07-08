import time
import threading
import yfinance as yf
import pandas as pd
import ta
from typing import Optional
from datetime import datetime, timezone

_cache: dict[str, tuple[dict, float]] = {}
_cache_lock = threading.Lock()
_MARKET_TTL = 300  # 5 minutes


def fetch_market_data(symbol: str) -> dict:
    key = symbol.upper()
    with _cache_lock:
        if key in _cache:
            data, ts = _cache[key]
            if time.time() - ts < _MARKET_TTL:
                return data

    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="3mo", interval="1d")

    if hist.empty:
        raise ValueError(f"No market data found for symbol: {symbol}")

    info = {}
    try:
        info = ticker.info
    except Exception:
        pass

    close = hist["Close"]
    volume = hist["Volume"]

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    macd_obj = ta.trend.MACD(close)
    sma_20 = ta.trend.SMAIndicator(close, window=20).sma_indicator()
    sma_50 = ta.trend.SMAIndicator(close, window=50).sma_indicator()
    bb = ta.volatility.BollingerBands(close, window=20)

    latest_price = float(close.iloc[-1])
    prev_close = float(close.iloc[-2]) if len(close) > 1 else latest_price
    price_change_pct = ((latest_price - prev_close) / prev_close) * 100

    result = {
        "symbol": symbol,
        "price": latest_price,
        "prev_close": prev_close,
        "price_change_pct": round(price_change_pct, 2),
        "volume": float(volume.iloc[-1]),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "eps": info.get("trailingEps"),
        "revenue": info.get("totalRevenue"),
        "debt_to_equity": info.get("debtToEquity"),
        "profit_margins": info.get("profitMargins"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "company_name": info.get("longName", symbol),
        "rsi_14": round(float(rsi.iloc[-1]), 2) if not pd.isna(rsi.iloc[-1]) else None,
        "macd": round(float(macd_obj.macd().iloc[-1]), 4) if not pd.isna(macd_obj.macd().iloc[-1]) else None,
        "macd_signal": round(float(macd_obj.macd_signal().iloc[-1]), 4) if not pd.isna(macd_obj.macd_signal().iloc[-1]) else None,
        "macd_diff": round(float(macd_obj.macd_diff().iloc[-1]), 4) if not pd.isna(macd_obj.macd_diff().iloc[-1]) else None,
        "sma_20": round(float(sma_20.iloc[-1]), 4) if not pd.isna(sma_20.iloc[-1]) else None,
        "sma_50": round(float(sma_50.iloc[-1]), 4) if not pd.isna(sma_50.iloc[-1]) else None,
        "bb_upper": round(float(bb.bollinger_hband().iloc[-1]), 4) if not pd.isna(bb.bollinger_hband().iloc[-1]) else None,
        "bb_lower": round(float(bb.bollinger_lband().iloc[-1]), 4) if not pd.isna(bb.bollinger_lband().iloc[-1]) else None,
        "high_52w": info.get("fiftyTwoWeekHigh"),
        "low_52w": info.get("fiftyTwoWeekLow"),
        "price_history": [
            {"date": str(d.date()), "close": round(float(p), 4), "volume": int(v)}
            for d, p, v in zip(hist.index[-30:], close.iloc[-30:], volume.iloc[-30:])
        ],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    with _cache_lock:
        _cache[key] = (result, time.time())
    return result


def fetch_actual_price(symbol: str) -> Optional[float]:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None
