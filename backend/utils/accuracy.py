from datetime import datetime, timezone


def calc_direction_from_prices(entry_price: float, exit_price: float) -> str:
    pct = (exit_price - entry_price) / entry_price * 100
    if pct > 1.0:
        return "bullish"
    elif pct < -1.0:
        return "bearish"
    return "neutral"


def calc_accuracy_score(
    predicted_direction: str,
    actual_direction: str,
    predicted_price: float | None,
    actual_price: float,
    entry_price: float,
    confidence: float,
) -> float:
    direction_correct = predicted_direction == actual_direction

    if direction_correct:
        base_score = 0.6
    elif predicted_direction == "neutral" or actual_direction == "neutral":
        base_score = 0.4
    else:
        base_score = 0.0

    price_score = 0.0
    if predicted_price and entry_price:
        predicted_move_pct = abs((predicted_price - entry_price) / entry_price * 100)
        actual_move_pct = abs((actual_price - entry_price) / entry_price * 100)
        if predicted_move_pct > 0:
            ratio = min(actual_move_pct, predicted_move_pct) / max(actual_move_pct, predicted_move_pct)
            price_score = 0.3 * ratio * (1 if direction_correct else 0)

    calibration_bonus = 0.0
    if direction_correct and confidence > 0.7:
        calibration_bonus = 0.1
    elif not direction_correct and confidence < 0.4:
        calibration_bonus = 0.05

    return round(min(base_score + price_score + calibration_bonus, 1.0), 4)


def calc_brier_score(confidence: float, direction_correct: bool) -> float:
    outcome = 1.0 if direction_correct else 0.0
    return round((confidence - outcome) ** 2, 6)


def calc_price_error_pct(
    target_price: float | None, actual_price: float, entry_price: float
) -> float | None:
    if target_price is None or entry_price == 0:
        return None
    return round(abs((actual_price - target_price) / entry_price) * 100, 4)


def calc_price_score_component(
    predicted_price: float | None,
    actual_price: float,
    entry_price: float,
    direction_correct: bool,
) -> float:
    if not predicted_price or not entry_price:
        return 0.0
    predicted_move = abs((predicted_price - entry_price) / entry_price * 100)
    actual_move = abs((actual_price - entry_price) / entry_price * 100)
    if predicted_move == 0:
        return 0.0
    ratio = min(actual_move, predicted_move) / max(actual_move, predicted_move)
    return round(0.3 * ratio * (1 if direction_correct else 0), 6)


def confidence_bucket(confidence: float) -> str:
    # clamp so confidence=1.0 falls in "0.9-1.0" not the non-existent "1.0-1.1"
    clamped = min(confidence, 0.9999)
    lower = round(int(clamped * 10) / 10, 1)
    upper = round(lower + 0.1, 1)
    return f"{lower:.1f}-{upper:.1f}"


def calc_agent_direction_hits(agent_outputs: dict, actual_direction: str) -> dict[str, bool]:
    return {
        name: data.get("direction") == actual_direction
        for name, data in (agent_outputs or {}).items()
    }


def build_evaluation(prediction, actual_price: float) -> dict:
    """Build all EvaluationResult fields from a Prediction object and the actual price."""
    actual_direction = calc_direction_from_prices(prediction.current_price, actual_price)
    direction_correct = prediction.direction == actual_direction
    total_score = calc_accuracy_score(
        prediction.direction,
        actual_direction,
        prediction.target_price,
        actual_price,
        prediction.current_price,
        prediction.confidence,
    )
    return {
        "prediction_id": prediction.id,
        "direction_correct": direction_correct,
        "agent_directions": calc_agent_direction_hits(prediction.agent_outputs or {}, actual_direction),
        "price_error_pct": calc_price_error_pct(prediction.target_price, actual_price, prediction.current_price),
        "price_score": calc_price_score_component(
            prediction.target_price, actual_price, prediction.current_price, direction_correct
        ),
        "brier_score": calc_brier_score(prediction.confidence, direction_correct),
        "confidence_bucket": confidence_bucket(prediction.confidence),
        "total_score": total_score,
    }


def compute_stats(predictions: list) -> dict:
    total = len(predictions)
    compared = [p for p in predictions if p.status == "compared"]
    n_compared = len(compared)

    if n_compared == 0:
        return {
            "total": total,
            "compared": 0,
            "direction_accuracy": 0.0,
            "avg_confidence": 0.0,
            "avg_accuracy_score": 0.0,
            "avg_brier_score": None,
            "by_timeframe": {},
            "by_symbol": {},
        }

    direction_hits = sum(1 for p in compared if p.direction == p.actual_direction)

    by_tf: dict[str, dict] = {}
    by_sym: dict[str, dict] = {}

    for p in compared:
        for key, bucket in [(p.timeframe, by_tf), (p.symbol, by_sym)]:
            if key not in bucket:
                bucket[key] = {"total": 0, "hits": 0, "scores": []}
            bucket[key]["total"] += 1
            if p.direction == p.actual_direction:
                bucket[key]["hits"] += 1
            if p.accuracy_score is not None:
                bucket[key]["scores"].append(p.accuracy_score)

    def finalise(bucket: dict) -> dict:
        out = {}
        for k, v in bucket.items():
            scores = v["scores"]
            out[k] = {
                "total": v["total"],
                "direction_accuracy": round(v["hits"] / v["total"], 4),
                "avg_accuracy_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
            }
        return out

    scores = [p.accuracy_score for p in compared if p.accuracy_score is not None]
    return {
        "total": total,
        "compared": n_compared,
        "direction_accuracy": round(direction_hits / n_compared, 4),
        "avg_confidence": round(sum(p.confidence for p in compared) / n_compared, 4),
        "avg_accuracy_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "by_timeframe": finalise(by_tf),
        "by_symbol": finalise(by_sym),
    }
