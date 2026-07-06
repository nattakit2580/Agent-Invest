import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models.prediction import Prediction, MarketSnapshot
from models.schemas import AnalyzeRequest, PredictionResponse
from fetchers.market_fetcher import fetch_market_data
from fetchers.news_fetcher import fetch_all_news
from agents.orchestrator import Orchestrator
from services import rag as rag_service
from services.agent_feedback import get_agent_feedback
from services.market_regime import detect_regime
from config import get_settings

router = APIRouter(prefix="/analyze", tags=["analyze"])
orchestrator = Orchestrator()


def _prediction_to_dict(p: Prediction) -> dict:
    return {
        "id": p.id,
        "symbol": p.symbol,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "timeframe": p.timeframe,
        "direction": p.direction,
        "current_price": p.current_price,
        "target_price": p.target_price,
        "confidence": p.confidence,
        "reasoning": p.reasoning,
        "agent_outputs": p.agent_outputs,
        "actual_price": p.actual_price,
        "actual_direction": p.actual_direction,
        "accuracy_score": p.accuracy_score,
        "compared_at": p.compared_at.isoformat() if p.compared_at else None,
        "status": p.status,
    }


@router.post("", response_model=PredictionResponse)
def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.use_local_model and not settings.openrouter_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENROUTER_API_KEY is not configured. Set it in backend/.env or enable USE_LOCAL_MODEL.",
        )
    try:
        market_data = fetch_market_data(req.symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch market data: {str(e)}")

    news = fetch_all_news(req.symbol.upper())

    regime = detect_regime(market_data, news)

    # RAG retrieval uses market_data only (agents haven't run yet).
    # We pass agent_outputs=None intentionally — market context alone is sufficient
    # for finding structurally similar past cases before agents produce their output.
    similar_cases = rag_service.get_similar_cases(
        req.symbol.upper(), market_data, None, db
    )

    agent_fb = get_agent_feedback(db, regime=regime)
    result = orchestrator.analyze(req.symbol.upper(), market_data, news, req.timeframe, similar_cases, agent_fb, regime=regime)

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
        market_regime=result.get("market_regime"),
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    rag_service.index_prediction(prediction, market_data, db)

    return prediction


@router.post("/stream")
def analyze_stream(req: AnalyzeRequest):
    """Same analysis as POST /analyze, but streamed as newline-delimited JSON so the
    UI can reveal each agent as it finishes. Event shapes (one JSON object per line):
      {"type":"status","stage":"market|news|agents|synthesis|critic|saving"}
      {"type":"agent","name":"news","output":{...}}
      {"type":"synthesis","direction":..,"confidence":..,"reasoning":..,"key_risks":[..],
       "catalysts":[..],"recommendation":..,"target_price":..,"current_price":..}
      {"type":"critic","output":{...}}
      {"type":"final","prediction":{...}}
      {"type":"error","detail":"..."}
    """
    symbol = req.symbol.upper()
    timeframe = req.timeframe

    def gen():
        def emit(obj: dict) -> str:
            return json.dumps(obj, ensure_ascii=False) + "\n"

        settings = get_settings()
        if not settings.use_local_model and not settings.openrouter_api_key:
            yield emit({"type": "error", "detail": "OPENROUTER_API_KEY is not configured."})
            return

        db = SessionLocal()
        try:
            yield emit({"type": "status", "stage": "market", "message": "กำลังดึงข้อมูลตลาด"})
            try:
                market_data = fetch_market_data(symbol)
            except Exception as e:
                yield emit({"type": "error", "detail": f"Failed to fetch market data: {str(e)}"})
                return

            yield emit({"type": "status", "stage": "news", "message": "กำลังดึงข่าว"})
            news = fetch_all_news(symbol)

            regime = detect_regime(market_data, news)
            similar_cases = rag_service.get_similar_cases(symbol, market_data, None, db)
            agent_fb = get_agent_feedback(db, regime=regime)

            # Analysts, streamed as each finishes.
            yield emit({"type": "status", "stage": "agents", "message": "Agents กำลังวิเคราะห์"})
            agent_outputs: dict = {}
            for name, output in orchestrator.stream_agents(symbol, market_data, news):
                agent_outputs[name] = output
                yield emit({"type": "agent", "name": name, "output": output})

            # Synthesis.
            yield emit({"type": "status", "stage": "synthesis", "message": "กำลังสังเคราะห์ผล"})
            core = orchestrator._synthesize_core(
                symbol, market_data, agent_outputs, timeframe, similar_cases, agent_fb, regime
            )
            synth = core["synth"]
            yield emit({
                "type": "synthesis",
                "direction": core["direction"],
                "confidence": core["confidence"],
                "current_price": core["current_price"],
                "target_price": core["target_price"],
                "reasoning": synth.get("reasoning", ""),
                "key_risks": synth.get("key_risks", []),
                "catalysts": synth.get("catalysts", []),
                "recommendation": synth.get("recommendation", ""),
            })

            # Critic.
            yield emit({"type": "status", "stage": "critic", "message": "Risk Critic กำลังตรวจทาน"})
            critic_result = orchestrator.run_critic(symbol, core, agent_outputs, market_data)
            yield emit({"type": "critic", "output": critic_result})

            result = orchestrator.assemble(core, critic_result, agent_outputs)

            # Persist (snapshot + prediction + RAG index), same as the non-stream path.
            yield emit({"type": "status", "stage": "saving", "message": "กำลังบันทึกผล"})
            snapshot = MarketSnapshot(
                symbol=symbol,
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
                symbol=symbol,
                timeframe=timeframe,
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

            try:
                rag_service.index_prediction(prediction, market_data, db)
            except Exception as e:
                print(f"[analyze_stream] RAG index skipped: {e}")

            yield emit({"type": "final", "prediction": _prediction_to_dict(prediction)})
        except Exception as e:
            yield emit({"type": "error", "detail": str(e)})
        finally:
            db.close()

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@router.get("/market/{symbol}")
def get_market_data(symbol: str):
    try:
        return fetch_market_data(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/news/{symbol}")
def get_news(symbol: str):
    return {"symbol": symbol.upper(), "news": fetch_all_news(symbol.upper())}
