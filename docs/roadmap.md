# Agent-Invest — Development Roadmap

> วันที่เขียน: 2026-07-02  
> สถานะปัจจุบัน: Phase 0 (baseline) — FastAPI + SQLite + Anthropic SDK + 4 AI agents

---

## สถานะ Baseline (ก่อนเริ่ม Phase 1)

| Component | สถานะ |
|---|---|
| 4 agents: News / Fundamental / Technical / Sentiment | ✅ Done |
| Orchestrator พร้อม weighted direction scoring | ✅ Done |
| Prediction model + `accuracy_score` + `status` field | ✅ Done |
| `utils/accuracy.py` — direction accuracy + calibration bonus | ✅ Done |
| SQLite (SQLAlchemy ORM) | ✅ Done (Phase 1 migrate → PostgreSQL) |
| Anthropic SDK hardcoded ใน `base_agent.py` | ✅ Done (Phase 1 replace → OpenRouter) |
| Telegram bot + channel broadcast | ✅ Done |
| Next.js dashboard (analyze / predictions / accuracy / export) | ✅ Done |

---

## Phase 1 — OpenRouter + PostgreSQL + JSON Forecast

### เป้าหมาย
เปลี่ยน LLM provider จาก Anthropic SDK เป็น OpenRouter (เพื่อ swap model ได้ง่าย + ราคาถูกกว่า) และ migrate database จาก SQLite เป็น PostgreSQL (รองรับ Phase 3 pgvector)

### ไฟล์ที่ต้องแก้

#### `backend/config.py`
เพิ่ม fields:
```python
openrouter_api_key: str = ""
openrouter_model: str = "anthropic/claude-sonnet-4-6"   # เปลี่ยนได้ทีหลัง
openrouter_base_url: str = "https://openrouter.ai/api/v1"
# ลบ: anthropic_api_key, claude_model
```

#### `backend/agents/base_agent.py`
แทน `anthropic.Anthropic` client ด้วย `httpx.post` ไปยัง OpenRouter:
```python
# เดิม: client = anthropic.Anthropic(api_key=...)
# ใหม่: ใช้ httpx ส่ง POST /chat/completions รูปแบบ OpenAI-compatible
# response["choices"][0]["message"]["content"]
```
ไม่ต้อง import `anthropic` อีกต่อไป

#### `backend/database.py`
- ลบ `connect_args={"check_same_thread": False}` (SQLite-only)
- เพิ่ม pool settings สำหรับ PostgreSQL:
  ```python
  engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
  ```

#### `backend/.env.example`
```env
# เปลี่ยนจาก
ANTHROPIC_API_KEY=
DATABASE_URL=sqlite:///./agent_invest.db

# เป็น
OPENROUTER_API_KEY=
OPENROUTER_MODEL=anthropic/claude-sonnet-4-6
DATABASE_URL=postgresql://agent:secret@localhost:5432/agent_invest
```

#### `docker-compose.yml`
เพิ่ม postgres service:
```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_USER: agent
    POSTGRES_PASSWORD: secret
    POSTGRES_DB: agent_invest
  volumes:
    - pgdata:/var/lib/postgresql/data
  ports:
    - "5432:5432"

volumes:
  pgdata:
```
แก้ backend `DATABASE_URL` และ `ANTHROPIC_API_KEY` → `OPENROUTER_API_KEY`

#### `backend/requirements.txt`
```
# เพิ่ม
psycopg2-binary==2.9.9
# ลบ
anthropic==0.40.0
```

### JSON Forecast format ที่ต้องการ (ตรวจสอบ consistency)
Orchestrator.synthesize() ปัจจุบัน return:
```json
{
  "direction": "bullish|bearish|neutral",
  "confidence": 0.0-1.0,
  "current_price": 150.25,
  "target_price": 165.28,
  "timeframe": "1w",
  "reasoning": "...",
  "key_risks": ["..."],
  "catalysts": ["..."],
  "recommendation": "...",
  "agent_outputs": { "news": {...}, "fundamental": {...}, ... }
}
```
โครงสร้างนี้ถูกแล้ว ไม่ต้องเปลี่ยน แค่ตรวจสอบว่า agent แต่ละตัว enforce JSON schema เดิมอยู่

### งานสรุป Phase 1
| งาน | ไฟล์ | ความยาก |
|---|---|---|
| แทน Anthropic SDK ด้วย OpenRouter httpx call | `base_agent.py`, `config.py`, `requirements.txt` | ง่าย |
| เพิ่ม postgres service ใน docker-compose | `docker-compose.yml` | ง่าย |
| ปรับ database.py connection pool | `database.py` | ง่าย |
| อัพเดต `.env.example` + README | `.env.example`, `README.md` | ง่าย |
| test migrate + run ทุก endpoint ใหม่ | — | ปานกลาง |

**เวลาประมาณ:** 1-2 วัน

---

## Phase 2 — Scoring & Evaluation

### เป้าหมาย
ระบบ evaluate prediction ที่ละเอียดขึ้น: แยก score ต่อ agent, ต่อ timeframe, ต่อ symbol, calibration curve, และ endpoint ใหม่สำหรับ dashboard

### ปัจจุบันมีอะไรแล้ว
- `utils/accuracy.py`: `calc_accuracy_score()` — direction (60%) + price proximity (30%) + calibration bonus (10%)
- `compute_stats()` — aggregate by timeframe + symbol
- `Prediction.accuracy_score` — single float 0-1

### สิ่งที่ขาด
1. **Per-agent scoring** — ปัจจุบัน `agent_outputs` เก็บเป็น JSON แต่ไม่เคย evaluate ว่า agent ไหน predict direction ถูกบ้าง
2. **Calibration tracking** — confidence 0.8 ควรจะถูก 80% ของเวลา (Brier score)
3. **Streak & trend** — consecutive hits/misses ต่อ symbol
4. **EvaluationResult table** — แยก table เพื่อเก็บ breakdown ไม่ให้ Prediction table บวม

### โมเดลใหม่: `backend/models/evaluation.py`
```python
class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id             = Column(String(36), primary_key=True, default=_uuid)
    prediction_id  = Column(String(36), ForeignKey("predictions.id"), nullable=False, index=True)
    evaluated_at   = Column(DateTime, default=utcnow)

    # direction
    direction_correct  = Column(Boolean, nullable=False)
    agent_directions   = Column(JSON)   # {"news": True, "fundamental": False, ...}

    # price
    price_error_pct    = Column(Float)  # abs((actual - target) / entry) * 100
    price_score        = Column(Float)  # 0-0.3 component

    # calibration
    brier_score        = Column(Float)  # (confidence - outcome)^2, outcome=1 if correct
    confidence_bucket  = Column(String(10))  # "0.5-0.6", "0.6-0.7", ...

    # composite
    total_score        = Column(Float)  # = accuracy_score (denorm for fast query)
```

### ฟังก์ชันใหม่ใน `utils/accuracy.py`
```python
def calc_agent_direction_hits(agent_outputs: dict, actual_direction: str) -> dict[str, bool]:
    """ตรวจว่า agent แต่ละตัว predict direction ถูกไหม"""

def calc_brier_score(confidence: float, direction_correct: bool) -> float:
    """(confidence - int(correct))^2"""

def calc_price_error_pct(target: float | None, actual: float, entry: float) -> float | None:
    """None ถ้าไม่มี target_price"""

def build_evaluation(prediction, actual_price: float) -> dict:
    """ประกอบ EvaluationResult ทั้งหมด จาก Prediction object"""
```

### Endpoint ใหม่
```
GET  /accuracy                    # เดิม — aggregate stats (เพิ่ม brier_score)
GET  /accuracy/agents             # NEW — per-agent direction accuracy across all predictions
GET  /accuracy/calibration        # NEW — confidence bucket vs actual hit rate
GET  /accuracy/{prediction_id}    # NEW — EvaluationResult detail ต่อ prediction
```

### แก้ flow ใน `api/predictions.py`
ตอน `POST /predictions/{id}/auto-compare` → สร้าง `EvaluationResult` row ด้วย

### งานสรุป Phase 2
| งาน | ไฟล์ | ความยาก |
|---|---|---|
| สร้าง `EvaluationResult` model | `models/evaluation.py` | ง่าย |
| เพิ่มฟังก์ชัน evaluate ใน accuracy.py | `utils/accuracy.py` | ปานกลาง |
| แก้ auto-compare ให้ save EvaluationResult | `api/predictions.py` | ง่าย |
| Endpoint /accuracy/agents และ /calibration | `api/accuracy.py` | ปานกลาง |
| Frontend: เพิ่ม calibration chart + agent breakdown | `frontend/app/accuracy/page.tsx` | ปานกลาง |

**เวลาประมาณ:** 3-5 วัน

---

## Phase 3 — RAG (ดึงเคสเก่ามาเทียบ)

### เป้าหมาย
ตอน analyze symbol ใหม่ ให้ดึง prediction เก่าที่คล้ายกัน (symbol เดียวกัน + สถานการณ์ตลาดคล้าย) มาใส่ใน prompt เพื่อ grounding และ few-shot learning

### สิ่งที่ต้องการก่อน Phase 3 เริ่ม
- Phase 1 เสร็จ (PostgreSQL พร้อมแล้ว)
- มี prediction ที่ `status = compared` อย่างน้อย 50-100 เคส (ไม่งั้น RAG ไม่มีประโยชน์)

### Architecture

```
POST /analyze
  │
  ├── fetch_market_data()  ─────────────────────────────┐
  ├── fetch_news()                                       │
  │                                                      ▼
  └── RAGRetriever.get_similar_cases(symbol, market_data)
        │
        ├── สร้าง query embedding จาก symbol + market context
        ├── pgvector similarity search ใน prediction_embeddings
        └── return top-5 similar past cases (พร้อม actual outcome)
              │
              ▼
        Orchestrator.synthesize() — inject similar_cases เข้า prompt
```

### PostgreSQL Extension ที่ต้องใช้
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### โมเดลใหม่: `backend/models/embedding.py`
```python
from pgvector.sqlalchemy import Vector

class PredictionEmbedding(Base):
    __tablename__ = "prediction_embeddings"

    id             = Column(String(36), primary_key=True, default=_uuid)
    prediction_id  = Column(String(36), ForeignKey("predictions.id"), unique=True, index=True)
    embedding      = Column(Vector(1536))   # OpenRouter embedding model dimension
    text_snapshot  = Column(Text)           # ข้อความที่ใช้ embed
    created_at     = Column(DateTime, default=utcnow)
```
Index:
```python
from sqlalchemy import Index
Index("ix_embedding_vector", PredictionEmbedding.embedding, postgresql_using="ivfflat")
```

### ไฟล์ใหม่: `backend/services/rag.py`
```python
class RAGRetriever:
    def embed_text(self, text: str) -> list[float]:
        """เรียก OpenRouter embedding API"""

    def index_prediction(self, prediction: Prediction, db: Session) -> None:
        """embed reasoning + agent summaries แล้ว save ลง prediction_embeddings"""

    def get_similar_cases(
        self, symbol: str, market_data: dict, db: Session, k: int = 5
    ) -> list[dict]:
        """
        1. สร้าง query text จาก symbol + price + RSI + direction indicators
        2. embed query
        3. pgvector cosine similarity search
        4. filter เฉพาะ status='compared' (มี actual outcome)
        5. return formatted list พร้อม {direction, confidence, actual_direction, accuracy_score}
        """
```

### แก้ `agents/orchestrator.py`
```python
def synthesize(self, ..., similar_cases: list[dict] = None) -> dict:
    # ถ้ามี similar_cases ให้ inject เข้า prompt:
    # "SIMILAR PAST CASES:\n- AAPL 2024-03: bullish→actual bullish (score 0.87)\n- ..."
```

### แก้ `api/analyze.py`
```python
# หลัง save prediction:
rag.index_prediction(prediction, db)   # background หรือ sync
```

### dependencies ใหม่ใน `requirements.txt`
```
pgvector==0.3.2
```

### งานสรุป Phase 3
| งาน | ไฟล์ | ความยาก |
|---|---|---|
| enable pgvector extension + migration | `docker-compose.yml`, alembic | ปานกลาง |
| สร้าง PredictionEmbedding model + ivfflat index | `models/embedding.py` | ปานกลาง |
| สร้าง RAGRetriever service | `services/rag.py` | ยาก |
| inject similar_cases เข้า orchestrator prompt | `agents/orchestrator.py` | ปานกลาง |
| index prediction หลัง compare (background task) | `api/predictions.py` | ง่าย |
| endpoint `GET /rag/similar/{prediction_id}` (debug/UI) | `api/rag.py` | ง่าย |

**เวลาประมาณ:** 1-2 สัปดาห์

---

## Phase 4 — Dataset Collection (500-5,000 เคส)

### เป้าหมาย
สะสม prediction ที่มี actual outcome ครบ พร้อม features ให้เพียงพอสำหรับ fine-tune โมเดลใน Phase 5

### เงื่อนไขของ 1 เคสที่ใช้ได้
```
prediction.status = "compared"          ✅ มี actual_price
prediction.accuracy_score is not None   ✅ มี label
prediction.agent_outputs is not None    ✅ มี input features
market_snapshot ที่ created_at ใกล้เคียง  ✅ มี technical indicators
```

### Auto-compare Scheduler
ปัจจุบัน auto-compare ต้องเรียก API เอง ต้องเพิ่ม scheduler job:

**ไฟล์แก้: `backend/tasks/scheduler.py`**
```python
# เพิ่ม job รัน every hour:
def auto_compare_expired_predictions(db):
    """
    ดึง predictions ที่ status=pending และ created_at + timeframe_days <= now
    เรียก yfinance ดึง current price → auto-compare
    """
    timeframe_days = {"1d": 1, "1w": 7, "1m": 30, "3m": 90}
```

### Export endpoint ใหม่: `GET /export/dataset`

**Query params:**
```
format=jsonl|csv|parquet
min_score=0.0       # filter เฉพาะ เคสที่มี accuracy_score >= X
symbol=AAPL         # filter ต่อ symbol (optional)
timeframe=1w        # filter ต่อ timeframe (optional)
limit=5000
```

**JSONL format (1 line = 1 training example):**
```json
{
  "id": "abc123",
  "symbol": "AAPL",
  "timeframe": "1w",
  "created_at": "2025-03-01T08:00:00Z",
  "market_snapshot": {
    "price": 175.50,
    "rsi_14": 62.3,
    "macd": 1.2,
    "sma_20": 170.0,
    "sma_50": 165.0,
    "pe_ratio": 28.5,
    "volume": 55000000
  },
  "agent_outputs": {
    "news":        {"direction": "bullish", "confidence": 0.7, "summary": "..."},
    "fundamental": {"direction": "bullish", "confidence": 0.8, "summary": "..."},
    "technical":   {"direction": "neutral", "confidence": 0.5, "summary": "..."},
    "sentiment":   {"direction": "bullish", "confidence": 0.65, "summary": "..."}
  },
  "prediction": {
    "direction": "bullish",
    "confidence": 0.72,
    "target_price": 182.0,
    "reasoning": "..."
  },
  "outcome": {
    "actual_price": 180.5,
    "actual_direction": "bullish",
    "accuracy_score": 0.85,
    "direction_correct": true,
    "price_error_pct": 0.83
  }
}
```

### Dataset Quality Dashboard (frontend)
เพิ่มหน้า `/dataset` แสดง:
- จำนวน cases ทั้งหมด / compared / export-ready
- distribution ของ direction (bullish/bearish/neutral balance)
- distribution ของ timeframe
- accuracy_score histogram
- progress bar ไปยัง target (500 → 1,000 → 5,000)

### งานสรุป Phase 4
| งาน | ไฟล์ | ความยาก |
|---|---|---|
| auto-compare scheduler job | `tasks/scheduler.py` | ปานกลาง |
| `GET /export/dataset` endpoint (JSONL + CSV) | `api/export.py` | ปานกลาง |
| Dataset quality dashboard (frontend) | `frontend/app/dataset/page.tsx` | ปานกลาง |
| เพิ่ม watchlist symbols + ตั้ง cron analyze อัตโนมัติ | `config.py`, `tasks/scheduler.py` | ง่าย |

**เวลาประมาณ:** 1 สัปดาห์ (code) + 1-6 เดือน (รอ data สะสม)

---

## Phase 5 — Fine-tune Open-Source Model

### เป้าหมาย
ใช้ dataset จาก Phase 4 (500-5,000 เคส) fine-tune โมเดล open-source เพื่อลด dependency และค่าใช้จ่าย API

### Prerequisite
- Phase 4: dataset ≥ 500 เคส (เป้าหมาย 1,000+ สำหรับผลดี)
- Phase 2: มี quality filter — ใช้ `accuracy_score >= 0.6` คัดเคส
- คอมหรือ cloud GPU (A100/H100 หรือ runpod/vast.ai)

### โมเดล open-source ที่น่าสนใจ
| โมเดล | ขนาด | เหมาะกับ |
|---|---|---|
| Qwen2.5-7B-Instruct | 7B | ราคาถูก, fine-tune บน consumer GPU |
| Mistral-7B-Instruct-v0.3 | 7B | JSON output ดี |
| Llama-3.1-8B-Instruct | 8B | community support ดี |
| DeepSeek-R1-Distill-Qwen-7B | 7B | reasoning task ดี |

### Format training data: Instruction-tuning JSONL

**ไฟล์ใหม่: `backend/utils/dataset_formatter.py`**
```python
def to_instruction_format(case: dict) -> dict:
    """
    แปลง export case เป็น {"messages": [...]} format
    สำหรับ supervised fine-tuning (SFT)
    """
    return {
        "messages": [
            {
                "role": "system",
                "content": "You are an investment analysis AI. Analyze the given market data and agent reports, then return a JSON prediction."
            },
            {
                "role": "user",
                "content": build_user_prompt(case)   # market_snapshot + agent_outputs
            },
            {
                "role": "assistant",
                "content": json.dumps({               # ground truth
                    "direction": case["outcome"]["actual_direction"],
                    "confidence": case["prediction"]["confidence"],
                    "reasoning": case["prediction"]["reasoning"],
                    "key_risks": [],
                    "recommendation": ""
                })
            }
        ]
    }
```

### Training Pipeline
```
backend/
└── scripts/
    ├── export_training_data.py     # export + format เป็น train.jsonl / val.jsonl (90/10 split)
    ├── upload_to_hf.py             # optional: upload dataset ไป Hugging Face Hub
    └── finetune_config.yaml        # unsloth / axolotl config
```

**finetune_config.yaml (unsloth):**
```yaml
base_model: unsloth/Qwen2.5-7B-Instruct
dataset_path: ./train.jsonl
output_dir: ./agent-invest-7b
num_train_epochs: 3
per_device_train_batch_size: 4
gradient_accumulation_steps: 4
learning_rate: 2e-4
lora_r: 16
lora_alpha: 32
max_seq_length: 2048
```

### Integration หลัง fine-tune
แก้ `config.py` เพิ่ม:
```python
use_local_model: bool = False
local_model_url: str = "http://localhost:11434/v1"  # ollama หรือ vllm
local_model_name: str = "agent-invest-7b"
```
แก้ `base_agent.py`:
```python
# ถ้า use_local_model=True → ส่ง request ไป local_model_url แทน OpenRouter
# format เหมือนกัน (OpenAI-compatible) ไม่ต้องเปลี่ยน agent logic
```

### งานสรุป Phase 5
| งาน | ไฟล์ | ความยาก |
|---|---|---|
| Dataset formatter (instruction format) | `utils/dataset_formatter.py` | ปานกลาง |
| Train/val split script | `scripts/export_training_data.py` | ง่าย |
| Fine-tune config (unsloth/axolotl) | `scripts/finetune_config.yaml` | ปานกลาง |
| เพิ่ม local model option ใน config + base_agent | `config.py`, `agents/base_agent.py` | ง่าย |
| Test local model vs OpenRouter accuracy | — | ยาก (iterative) |

**เวลาประมาณ:** 2-4 สัปดาห์ (รวม experiment)

---

## Timeline ภาพรวม

```
Month 1
  Week 1-2:   Phase 1 — OpenRouter + PostgreSQL
  Week 3-5:   Phase 2 — Scoring & Evaluation

Month 2
  Week 6-8:   Phase 3 — RAG

Month 2-8     Phase 4 — สะสม dataset (code 1 สัปดาห์, รอ data หลายเดือน)
  ├── 1 month:   ~50-150 cases (ถ้า run manually)
  ├── 3 months:  ~200-500 cases
  └── 6 months:  ~500-2,000 cases (ถ้าตั้ง cron auto-analyze)

Month 6-9     Phase 5 — Fine-tune (เริ่มได้เมื่อมี ≥500 cases)
```

---

## Dependencies สรุปตาม Phase

| Package | เพิ่มใน Phase | ทำไม |
|---|---|---|
| `psycopg2-binary` | 1 | PostgreSQL driver |
| `httpx` | 1 | มีแล้ว (ใช้แทน anthropic SDK) |
| `pgvector` | 3 | vector similarity search |
| `unsloth` หรือ `axolotl` | 5 | fine-tuning (ติดตั้งใน training env แยก) |

ลบ:
| Package | ลบใน Phase | ทำไม |
|---|---|---|
| `anthropic` | 1 | แทนด้วย OpenRouter httpx |

---

## ข้อควรระวัง

1. **Phase 3 ต้องการ Phase 4 data ก่อนจะมีประโยชน์จริง** — RAG ที่มีแค่ 10 เคสให้ผลน้อยมาก ควรรัน Phase 3 ควบคู่กับ Phase 4 แล้ว RAG จะดีขึ้นเองเมื่อ dataset โต

2. **Dataset quality > quantity** — 500 เคสที่ `accuracy_score ≥ 0.6` ดีกว่า 2,000 เคสที่มี noise สูง ควรตั้ง threshold ก่อน export

3. **Phase 1 migration: อย่าลืม migrate schema** — ถ้า production มี SQLite data อยู่แล้ว ต้องทำ data migration script แปลง SQLite → PostgreSQL ก่อน drop SQLite

4. **OpenRouter rate limits** — ตรวจสอบ rate limit ของ model ที่เลือก โดยเฉพาะถ้าตั้ง cron auto-analyze หลายสิบ symbols
