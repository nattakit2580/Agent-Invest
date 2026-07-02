from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.prediction import Prediction, MarketSnapshot
from models.schemas import AnalyzeRequest, PredictionResponse
from fetchers.market_fetcher import fetch_market_data
from fetchers.news_fetcher import fetch_all_news
from agents.orchestrator import Orchestrator
from services import rag as rag_service

router = APIRouter(prefix="/analyze", tags=["analyze"])
orchestrator = Orchestrator()


@router.post("", response_model=PredictionResponse)
def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)):
    try:
        market_data = fetch_market_data(req.symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch market data: {str(e)}")

    news = fetch_all_news(req.symbol.upper())

    # RAG retrieval uses market_data only (agents haven't run yet).
    # We pass agent_outputs=None intentionally — market context alone is sufficient
    # for finding structurally similar past cases before agents produce their output.
    similar_cases = rag_service.get_similar_cases(
        req.symbol.upper(), market_data, None, db
    )

    result = orchestrator.analyze(req.symbol.upper(), market_data, news, req.timeframe, similar_cases)

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

    rag_service.index_prediction(prediction, market_data, db)

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
