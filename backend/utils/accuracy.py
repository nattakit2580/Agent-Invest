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
            "by_timeframe": {},
            "by_symbol": {},
        }

    direction_hits = sum(
        1 for p in compared if p.predicted_direction == p.actual_direction
    )

    by_tf: dict[str, dict] = {}
    by_sym: dict[str, dict] = {}

    for p in compared:
        for key, bucket in [(p.timeframe, by_tf), (p.symbol, by_sym)]:
            if key not in bucket:
                bucket[key] = {"total": 0, "hits": 0, "avg_score": 0.0, "scores": []}
            bucket[key]["total"] += 1
            if p.predicted_direction == p.actual_direction:
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

    return {
        "total": total,
        "compared": n_compared,
        "direction_accuracy": round(direction_hits / n_compared, 4),
        "avg_confidence": round(sum(p.confidence for p in compared) / n_compared, 4),
        "avg_accuracy_score": round(
            sum(p.accuracy_score for p in compared if p.accuracy_score) / n_compared, 4
        ),
        "by_timeframe": finalise(by_tf),
        "by_symbol": finalise(by_sym),
    }
