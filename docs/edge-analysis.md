# Agent-Invest — System Strengths, Weaknesses & Edge Cases

> วันที่วิเคราะห์: 2026-07-02  
> Branch: feat/edge-of-phase  
> ครอบคลุม: Phase 1–5 ทั้งหมด

---

## จุดแข็ง (Strengths)

### 1. Multi-Agent Ensemble ที่ทำงานขนาน
4 agents รันพร้อมกันใน `ThreadPoolExecutor(max_workers=4)` — ไม่ blocking กัน ทำให้ latency รวมเท่ากับ agent ที่ช้าที่สุด ไม่ใช่ผลรวม
- ถ้า agent ตัวใดตัวหนึ่ง timeout/crash → fallback เป็น neutral/0.3 confidence โดยอัตโนมัติ (`orchestrator.py:41-46`)

### 2. Weighted Scoring แทน Majority Vote
`_weighted_direction()` ไม่ใช้ voting ธรรมดา แต่คำนวณ weighted sum ของ direction × confidence × weight ต่อ agent — ทำให้ agent ที่มี confidence ต่ำมีอิทธิพลน้อยกว่าโดยอัตโนมัติ

### 3. Model-Agnostic ตั้งแต่ Phase 1
`OPENROUTER_MODEL` เป็น env var เดียวที่ต้องเปลี่ยนเพื่อ swap โมเดล OpenRouter ไม่มี hard-code ใดๆ ใน agent logic

### 4. Graceful Degradation ของ RAG
`PGVECTOR_AVAILABLE` flag ใน `models/embedding.py` — ถ้า pgvector ไม่ได้ install หรือ embedding API ล้มเหลว ระบบยังวิเคราะห์ได้ตามปกติ (แค่ไม่มี similar cases)

### 5. Calibration Tracking แยกต่างหาก
Brier score ถูก track แยกจาก accuracy_score — ทำให้รู้ว่าโมเดล overconfident/underconfident แม้ direction ถูกต้อง ซึ่งสำคัญมากสำหรับ financial prediction

### 6. Phase Gating ด้วย Flags
Feature ที่อาจทำให้ระบบช้าหรือแพงล้วน default=false:
- `RAG_ENABLED=false` → ไม่เรียก embedding API
- `AUTO_ANALYZE_ENABLED=false` → ไม่สร้าง prediction อัตโนมัติ
- `USE_LOCAL_MODEL=false` → ใช้ OpenRouter ตามปกติ

### 7. การแยก EvaluationResult ออกจาก Prediction
ไม่ยัด evaluation fields เข้า Prediction table โดยตรง ทำให้ Prediction table สะอาด และสามารถ re-evaluate โดยไม่ต้องแก้ prediction ต้นฉบับ

---

## จุดอ่อน (Weaknesses)

### ระดับ Critical (มีโอกาสทำให้ระบบผิดพลาด)

#### W1: Target Price Formula ไม่สมเหตุสมผล
**ที่:** `orchestrator.py:81`
```python
target_price = round(current_price * (1 + confidence * 0.1), 4)
```
- confidence=0.7 ให้ target เสมอ +7% ไม่ว่าจะเป็น AAPL หรือ BTC
- ไม่ใช้ volatility ของ symbol (BTC มี daily swing 5% ปกติ, AAPL แค่ 1%)
- ผล: `price_error_pct` ที่คำนวณใน Phase 2 ไม่สะท้อนความเป็นจริง

**Fix ที่ควรทำ:** ใช้ ATR (Average True Range) หรือ historical volatility ต่อ symbol

#### W2: Direction Threshold Hardcoded
**ที่:** `orchestrator.py:66-70`
```python
if final_score > 0.15: direction = "bullish"
elif final_score < -0.15: direction = "bearish"
```
- threshold 0.15 เป็น magic number ไม่ calibrated กับ actual data
- ถ้า score = 0.14 → neutral, score = 0.16 → bullish (cliff edge)
- ผล: neutral class อาจ overrepresented เกินจริง

**Fix ที่ควรทำ:** หลัง Phase 4 (มี data) → หา optimal threshold จาก ROC curve บน dataset

#### W3: `auto_compare` โหลด ALL pending predictions
**ที่:** `scheduler.py:25`
```python
pending = db.query(Prediction).filter(Prediction.status == "pending").all()
```
- ถ้ามี 50,000 pending → โหลด 50,000 objects เข้า memory ทุก 6 ชั่วโมง
- อาจทำให้ OOM หรือ database timeout

**Fix ที่ควรทำ:**
```python
# paginate ด้วย yield_per หรือ จำกัด batch
q.filter(...).yield_per(200)
```

#### W4: `index_prediction` เป็น Synchronous บน Request Thread
**ที่:** `api/analyze.py:60`
```python
rag_service.index_prediction(prediction, market_data, db)  # เรียก HTTP ไป OpenRouter
```
- ทุก POST /analyze รอ embedding API (~500ms-2s) ก่อน return
- ถ้า OpenRouter embeddings slow → analyze endpoint ช้าตามไปด้วย

**Fix ที่ควรทำ:** ย้ายไปทำใน background thread หรือ task queue:
```python
from fastapi import BackgroundTasks
background_tasks.add_task(rag_service.index_prediction, prediction, market_data, db)
```

---

### ระดับ Medium (ทำให้ผลลัพธ์ผิดเพี้ยนหรือ data loss)

#### W5: JSONL Export ขาด Technical Indicators ~~(แก้แล้วใน branch นี้)~~
เดิม `market_snapshot` ใน export มีแค่ `{"price": ...}` — ขาด rsi_14, macd, sma_20, sma_50 ซึ่งเป็น features สำคัญสำหรับ fine-tuning  
**Status:** แก้แล้วใน branch นี้ (join MarketSnapshot ที่ใกล้เคียงที่สุดตาม timestamp)

#### W6: `confidence_bucket(1.0)` → "1.0-1.1" ไม่อยู่ใน BUCKETS ~~(แก้แล้ว)~~
calibration endpoint จะ silently drop ข้อมูลถ้า confidence = 1.0  
**Status:** แก้แล้ว (clamp ที่ 0.9999)

#### W7: `build_assistant_response` ใน Phase 5 มี `key_risks: []` เสมอ ~~(แก้แล้ว)~~
โมเดลจะ fine-tune ให้ output key_risks ว่างเปล่าทุกครั้ง  
**Status:** แก้แล้ว (ดึง key_risks จาก agent_outputs)

#### W8: Duplicate Predictions จาก auto_analyze ~~(แก้แล้ว)~~
ทุก interval จะสร้าง prediction ใหม่แม้ symbol เดิมยังไม่ถึงเวลา compare  
**Status:** แก้แล้ว (skip ถ้ามี pending prediction สำหรับ symbol+timeframe นั้นอยู่แล้ว)

#### W9: RAG Embedding Asymmetry
Query embedding สร้างจาก market_data เท่านั้น (agents ยังไม่รัน) แต่ stored embeddings รวม agent summaries ด้วย → vector space ไม่ตรงกัน ลด retrieval quality

**Fix ที่ควรทำ:** มีสองแนวทาง:
1. ทำ "lightweight pre-analysis" ด้วย RSI/MACD signals ก่อน embed query
2. ใช้ two-pass: embed จาก market data อย่างเดียว ทั้ง query และ stored

#### W10: ไม่มี Database Migration (Alembic)
ใช้ `Base.metadata.create_all()` — ถ้าเพิ่ม column ในโมเดล production DB จะไม่ update อัตโนมัติ ต้องทำ SQL migration เอง

**Fix ที่ควรทำ:** เพิ่ม `alembic init alembic` และ `alembic revision --autogenerate`

---

### ระดับ Low (Design debt)

#### W11: `auto_analyze` ใช้ timeframe เดียว
`AUTO_ANALYZE_TIMEFRAME=1w` เท่านั้น — dataset จะ skewed ไปที่ 1w ซึ่งไม่ดีสำหรับ diversity ของ training data

#### W12: ไม่มี Rate Limiting บน `/analyze`
ทุก call สร้าง 4 threads + 5 LLM API calls — ไม่มี throttle ป้องกัน abuse

#### W13: `orchestrator.py` import `asyncio` และ `json` โดยไม่ใช้ ~~(แก้แล้ว)~~
Dead imports — ลบออกแล้วใน branch นี้

#### W14: `_embed` ไม่มี Retry Logic
ถ้า embedding API fail ครั้งเดียว → `embedding=None` stored → prediction นั้นจะ miss จาก RAG ตลอดไป (ไม่มี re-embed mechanism นอกจาก POST /rag/index/{id} เรียกเอง)

#### W15: Accuracy Score ผสม Correctness กับ Calibration
`calibration_bonus = 0.1` ถ้า direction correct AND confidence > 0.7 ทำให้ accuracy_score ตีความยาก (ไม่รู้ว่าสูงเพราะ direction ถูก หรือเพราะ confident มาก)

---

## Edge Cases ที่ต้องระวัง

| Scenario | ผลกระทบ | จุดที่เกิด |
|---|---|---|
| `confidence = 1.0` | calibration bucket "1.0-1.1" ไม่มีใน list → data lost | `utils/accuracy.py` (**แก้แล้ว**) |
| Symbol ที่ yfinance ไม่รู้จัก | `fetch_market_data` raise exception → 400 error แต่ snapshot ไม่ถูก save | `api/analyze.py:18` |
| Agent ทุกตัว timeout พร้อมกัน | direction = "neutral", confidence = ค่าเฉลี่ย fallback 0.3 | `orchestrator.py:41-46` |
| pgvector ไม่ได้ enable บน Postgres | embedding จะ store เป็น None ทุก prediction | `models/embedding.py` fallback |
| `actual_price = entry_price` (no movement) | `calc_direction_from_prices` return "neutral", `price_error_pct` = 0% | `utils/accuracy.py:5-10` |
| Dataset ที่ bullish/bearish/neutral ไม่ balance | fine-tuned model จะ biased ไปทาง majority class | `utils/dataset_formatter.py` (direction_balance flag ช่วยได้) |
| `created_at` ของ Prediction ไม่มี timezone | `replace(tzinfo=timezone.utc)` ใน scheduler อาจผิดพลาดถ้า server timezone ไม่ใช่ UTC | `tasks/scheduler.py:29` |

---

## สรุปสถานะ Bug Fixes ในี Branch นี้

| Bug | ไฟล์ | สถานะ |
|---|---|---|
| `confidence_bucket(1.0)` → bucket ผิด | `utils/accuracy.py` | ✅ Fixed |
| Dead imports `asyncio`, `json` | `agents/orchestrator.py` | ✅ Fixed |
| `key_risks: []` เสมอใน fine-tune dataset | `utils/dataset_formatter.py` | ✅ Fixed |
| JSONL market_snapshot ขาด technical indicators | `api/dataset.py` | ✅ Fixed |
| RAG embedding asymmetry — documented | `api/analyze.py` | ✅ Documented (comment) |
| auto_analyze สร้าง duplicate predictions | `tasks/scheduler.py` | ✅ Fixed |

---

## คำแนะนำลำดับความสำคัญ

```
ทำก่อน (blocking correctness):
  1. W1  — Target price ใช้ ATR/volatility แทน confidence * 10%
  2. W10 — เพิ่ม Alembic migration system ก่อน production deploy
  3. W3  — paginate auto_compare query ด้วย yield_per

ทำหลัง Phase 4 (ต้องมี data ก่อน):
  4. W2  — calibrate direction threshold จาก ROC curve
  5. W9  — แก้ RAG embedding asymmetry (two-pass หรือ pre-analysis)

Nice to have:
  6. W4  — ย้าย index_prediction ไป BackgroundTasks
  7. W12 — เพิ่ม rate limiting (slowapi หรือ nginx)
  8. W11 — auto_analyze หลาย timeframe
```
