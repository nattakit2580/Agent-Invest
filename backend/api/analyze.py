from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.prediction import Prediction, MarketSnapshot
from models.schemas import AnalyzeRequest, PredictionResponse
from fetchers.market_fetcher import fetch_market_data
from fetchers.news_fetcher import fetch_all_news
from agents.orchestrator import Orchestrator, DIRECTION_WEIGHTS
from utils.learning import (
    adjust_weights,
    get_agent_accuracy,
    get_symbol_history,
    summarize_history_for_prompt,
)

router = APIRouter(prefix="/analyze", tags=["analyze"])
orchestrator = Orchestrator()


@router.post("", response_model=PredictionResponse)
def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)):
    try:
        market_data = fetch_market_data(req.symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch market data: {str(e)}")

    news = fetch_all_news(req.symbol.upper())

    # Memory: recall this symbol's realized track record and feed it into the analysis.
    symbol = req.symbol.upper()
    history = get_symbol_history(db, symbol, limit=5)
    history_summary = summarize_history_for_prompt(history, symbol)
    # Learning: shift blend weights toward agents that have been more accurate.
    agent_accuracy = get_agent_accuracy(db, symbol=symbol)
    weights = adjust_weights(DIRECTION_WEIGHTS, agent_accuracy)

    result = orchestrator.analyze(
        symbol,
        market_data,
        news,
        req.timeframe,
        history_summary=history_summary,
        weights=weights,
    )

    snapshot = MarketSnapshot(
        symbol=req.symbol.upper(),
        price=market_data["price"],
        volume=market_data["volume"],
        market_cap=market_data.get("market_cap"),
        pe_ratio=market_data.get("pe_ratio"),
        rsi_14=market_data.get("rsi_14"),
        macd=market_data.get("macd"),
        macd_signal=market_data.get("macd_signal"),
        sma_20=market_data.get("sma_20"),
        sma_50=market_data.get("sma_50"),
        extra={"news_count": len(news), "price_change_pct": market_data.get("price_change_pct")},
    )
    db.add(snapshot)

    prediction = Prediction(
        symbol=req.symbol.upper(),
        timeframe=req.timeframe,
        direction=result["direction"],
        current_price=result["current_price"],
        target_price=result.get("target_price"),
        confidence=result["confidence"],
        reasoning=result["reasoning"],
        agent_outputs=result["agent_outputs"],
        status="pending",
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


@router.get("/market/{symbol}")
def get_market_data(symbol: str):
    try:
        return fetch_market_data(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/news/{symbol}")
def get_news(symbol: str):
    return {"symbol": symbol.upper(), "news": fetch_all_news(symbol.upper())}
