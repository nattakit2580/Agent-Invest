"""
Export dataset from PostgreSQL and format as instruction-tuning JSONL.

Usage:
    python scripts/export_training_data.py \
        --min-score 0.5 \
        --balance \
        --output-dir ./training_data

Outputs:
    training_data/train.jsonl   (90%)
    training_data/val.jsonl     (10%)
    training_data/stats.json    (summary)
"""
import sys
import os
import json
import random
import argparse
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import SessionLocal
from models.prediction import Prediction
from utils.dataset_formatter import format_dataset


def main():
    parser = argparse.ArgumentParser(description="Export fine-tuning dataset")
    parser.add_argument("--min-score", type=float, default=0.5, help="Minimum accuracy_score to include")
    parser.add_argument("--balance", action="store_true", help="Balance direction classes")
    parser.add_argument("--output-dir", type=str, default="./training_data")
    parser.add_argument("--val-split", type=float, default=0.1, help="Fraction for validation set")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        predictions = (
            db.query(Prediction)
            .filter(Prediction.status == "compared")
            .filter(Prediction.accuracy_score >= args.min_score)
            .filter(Prediction.accuracy_score.isnot(None))
            .all()
        )
        print(f"Found {len(predictions)} predictions with accuracy_score >= {args.min_score}")

        cases = []
        for p in predictions:
            cases.append({
                "id": p.id,
                "symbol": p.symbol,
                "timeframe": p.timeframe,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "market_snapshot": {"price": p.current_price},
                "agent_outputs": p.agent_outputs or {},
                "prediction": {
                    "direction": p.direction,
                    "confidence": p.confidence,
                    "target_price": p.target_price,
                    "reasoning": p.reasoning,
                },
                "outcome": {
                    "actual_price": p.actual_price,
                    "actual_direction": p.actual_direction,
                    "accuracy_score": p.accuracy_score,
                    "direction_correct": p.direction == p.actual_direction,
                },
            })
    finally:
        db.close()

    formatted = format_dataset(cases, min_score=args.min_score, direction_balance=args.balance)
    print(f"Formatted {len(formatted)} training examples")

    random.seed(args.seed)
    random.shuffle(formatted)

    n_val = max(1, int(len(formatted) * args.val_split))
    val_set = formatted[:n_val]
    train_set = formatted[n_val:]

    def write_jsonl(path: Path, records: list[dict]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    write_jsonl(output_dir / "train.jsonl", train_set)
    write_jsonl(output_dir / "val.jsonl", val_set)

    stats = {
        "total": len(formatted),
        "train": len(train_set),
        "val": len(val_set),
        "min_score": args.min_score,
        "balanced": args.balance,
    }
    with open(output_dir / "stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"Train: {len(train_set)} | Val: {len(val_set)}")
    print(f"Output: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
