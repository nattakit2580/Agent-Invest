"""
Auto-eval: เทียบโมเดล fine-tuned (local) กับ base model (OpenRouter) บน validation set
ก่อนตัดสินใจสลับ USE_LOCAL_MODEL=true

Usage:
    python scripts/eval_model.py                          # ใช้ val.jsonl + config ปัจจุบัน
    python scripts/eval_model.py --val-file ./training_data/val.jsonl --limit 50
    python scripts/eval_model.py --skip-base              # eval เฉพาะ local model

Metrics ต่อโมเดล:
    - direction_accuracy   ทาย direction ตรง ground truth (actual outcome) กี่ %
    - json_validity        ตอบเป็น JSON ที่ parse ได้กี่ %
    - avg_latency_sec      เวลาเฉลี่ยต่อ request

Verdict: แนะนำสลับเมื่อ local accuracy >= base accuracy - tolerance
         และ json_validity >= 0.90
"""
import sys
import os
import json
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from config import get_settings

settings = get_settings()

VALID_DIRECTIONS = {"bullish", "bearish", "neutral"}


def parse_json_block(text: str) -> dict:
    """หา JSON object สุดท้ายในข้อความ (ทน ReAct preamble ได้) — logic เดียวกับ BaseAgent."""
    end = text.rfind("}")
    if end == -1:
        raise ValueError("No JSON found")
    depth = 0
    for i in range(end, -1, -1):
        if text[i] == "}":
            depth += 1
        elif text[i] == "{":
            depth -= 1
            if depth == 0:
                return json.loads(text[i : end + 1])
    raise ValueError("No complete JSON object found")


def call_model(
    messages: list[dict],
    *,
    url: str,
    model: str,
    api_key: str | None = None,
    max_tokens: int = 600,
    timeout: int = 90,
) -> tuple[str, float]:
    """เรียกโมเดล (OpenAI-compatible) คืน (content, latency_sec)."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": model, "max_tokens": max_tokens, "messages": messages}
    start = time.time()
    resp = httpx.post(f"{url.rstrip('/')}/chat/completions", json=payload, headers=headers, timeout=timeout)
    latency = time.time() - start
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"], latency


def load_val_cases(path: Path, limit: int | None) -> list[dict]:
    """โหลด val.jsonl — แต่ละบรรทัดคือ {"messages": [system, user, assistant]}
    assistant content เป็น ground-truth JSON ที่มี direction = actual outcome."""
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            msgs = record.get("messages", [])
            if len(msgs) != 3:
                continue
            try:
                truth = json.loads(msgs[2]["content"])
            except (json.JSONDecodeError, KeyError):
                continue
            direction = str(truth.get("direction", "")).lower()
            if direction not in VALID_DIRECTIONS:
                continue
            cases.append({
                "input_messages": msgs[:2],   # system + user เท่านั้น
                "truth_direction": direction,
            })
            if limit and len(cases) >= limit:
                break
    return cases


def eval_model_on_cases(
    label: str,
    cases: list[dict],
    *,
    url: str,
    model: str,
    api_key: str | None,
    workers: int,
) -> dict:
    n = len(cases)
    results: list[dict] = [None] * n  # type: ignore

    def _run_one(idx: int, case: dict) -> tuple[int, dict]:
        out = {"json_ok": False, "direction_ok": False, "latency": None, "error": None}
        try:
            content, latency = call_model(case["input_messages"], url=url, model=model, api_key=api_key)
            out["latency"] = latency
            parsed = parse_json_block(content)
            out["json_ok"] = True
            predicted = str(parsed.get("direction", "")).lower()
            out["direction_ok"] = predicted == case["truth_direction"]
        except Exception as e:
            out["error"] = str(e)[:200]
        return idx, out

    print(f"\n── Evaluating [{label}] {model} @ {url} — {n} cases, {workers} workers ──")
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run_one, i, c) for i, c in enumerate(cases)]
        for future in as_completed(futures):
            idx, out = future.result()
            results[idx] = out
            done += 1
            if done % 10 == 0 or done == n:
                print(f"  {done}/{n} done")

    json_ok = sum(1 for r in results if r["json_ok"])
    dir_ok = sum(1 for r in results if r["direction_ok"])
    latencies = [r["latency"] for r in results if r["latency"] is not None]
    errors = [r["error"] for r in results if r["error"]]

    return {
        "label": label,
        "model": model,
        "url": url,
        "total": n,
        "json_validity": round(json_ok / n, 4) if n else 0.0,
        "direction_accuracy": round(dir_ok / n, 4) if n else 0.0,
        "direction_accuracy_of_valid": round(dir_ok / json_ok, 4) if json_ok else 0.0,
        "avg_latency_sec": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "error_count": len(errors),
        "sample_errors": errors[:3],
    }


def main():
    parser = argparse.ArgumentParser(description="Compare fine-tuned local model vs base model on val set")
    parser.add_argument("--val-file", type=str, default="./training_data/val.jsonl")
    parser.add_argument("--limit", type=int, default=100, help="จำนวนเคสสูงสุดที่ใช้ eval")
    parser.add_argument("--base-model", type=str, default=settings.openrouter_model)
    parser.add_argument("--local-url", type=str, default=settings.local_model_url)
    parser.add_argument("--local-model", type=str, default=settings.local_model_name)
    parser.add_argument("--tolerance", type=float, default=0.02,
                        help="ยอมให้ local แพ้ base ได้ไม่เกินเท่านี้ (default 0.02 = 2%%)")
    parser.add_argument("--min-json-validity", type=float, default=0.90)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--skip-base", action="store_true", help="eval เฉพาะ local (ประหยัดค่า API)")
    parser.add_argument("--output", type=str, default="./training_data/eval_results.json")
    args = parser.parse_args()

    val_path = Path(args.val_file)
    if not val_path.exists():
        print(f"ไม่พบ {val_path} — รัน scripts/export_training_data.py ก่อน")
        sys.exit(1)

    cases = load_val_cases(val_path, args.limit)
    if not cases:
        print("ไม่มีเคสที่ใช้ได้ใน val file")
        sys.exit(1)
    print(f"Loaded {len(cases)} validation cases from {val_path}")

    # ── Local (fine-tuned) ────────────────────────────────────────────────
    local_result = eval_model_on_cases(
        "local", cases,
        url=args.local_url, model=args.local_model, api_key=None,
        workers=args.workers,
    )

    # ── Base (OpenRouter) ─────────────────────────────────────────────────
    base_result = None
    if not args.skip_base:
        if not settings.openrouter_api_key:
            print("\n⚠️ OPENROUTER_API_KEY ไม่ได้ตั้งค่า — ข้าม base eval")
        else:
            base_result = eval_model_on_cases(
                "base", cases,
                url=settings.openrouter_base_url, model=args.base_model,
                api_key=settings.openrouter_api_key,
                workers=args.workers,
            )

    # ── Report ────────────────────────────────────────────────────────────
    print("\n" + "=" * 64)
    print(f"{'Metric':<28}{'Local':>16}{'Base':>16}")
    print("-" * 64)

    def _fmt(v, pct=False):
        if v is None:
            return "-"
        return f"{v * 100:.1f}%" if pct else str(v)

    rows = [
        ("Direction accuracy", "direction_accuracy", True),
        ("  (of valid JSON only)", "direction_accuracy_of_valid", True),
        ("JSON validity", "json_validity", True),
        ("Avg latency (sec)", "avg_latency_sec", False),
        ("Errors", "error_count", False),
    ]
    for title, key, pct in rows:
        lv = _fmt(local_result.get(key), pct)
        bv = _fmt(base_result.get(key), pct) if base_result else "-"
        print(f"{title:<28}{lv:>16}{bv:>16}")
    print("=" * 64)

    # ── Verdict ───────────────────────────────────────────────────────────
    verdict = {"switch_recommended": False, "reasons": []}
    if local_result["json_validity"] < args.min_json_validity:
        verdict["reasons"].append(
            f"local JSON validity {local_result['json_validity']:.0%} < ขั้นต่ำ {args.min_json_validity:.0%}"
        )
    if base_result:
        gap = base_result["direction_accuracy"] - local_result["direction_accuracy"]
        if gap > args.tolerance:
            verdict["reasons"].append(
                f"local แพ้ base {gap:.1%} (เกิน tolerance {args.tolerance:.0%})"
            )
        if not verdict["reasons"]:
            verdict["switch_recommended"] = True
            verdict["reasons"].append(
                f"local accuracy {local_result['direction_accuracy']:.1%} "
                f"vs base {base_result['direction_accuracy']:.1%} — อยู่ในเกณฑ์"
            )
    else:
        verdict["reasons"].append("ไม่มีผล base เทียบ — ตัดสินใจจาก local metrics เอง")
        if local_result["json_validity"] >= args.min_json_validity and local_result["direction_accuracy"] >= 0.5:
            verdict["switch_recommended"] = True

    print()
    if verdict["switch_recommended"]:
        print("✅ VERDICT: สลับได้ — ตั้ง USE_LOCAL_MODEL=true ใน .env")
    else:
        print("❌ VERDICT: ยังไม่ควรสลับ — ใช้ base model ต่อ")
    for reason in verdict["reasons"]:
        print(f"   • {reason}")

    # ── Save ──────────────────────────────────────────────────────────────
    output = {
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "val_file": str(val_path),
        "cases": len(cases),
        "local": local_result,
        "base": base_result,
        "verdict": verdict,
        "params": {
            "tolerance": args.tolerance,
            "min_json_validity": args.min_json_validity,
        },
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nผลบันทึกที่: {out_path.resolve()}")

    sys.exit(0 if verdict["switch_recommended"] else 2)


if __name__ == "__main__":
    main()
