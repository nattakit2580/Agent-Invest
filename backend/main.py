from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import init_db
from api.analyze import router as analyze_router
from api.predictions import router as predictions_router
from api.accuracy import router as accuracy_router
from api.export import router as export_router
from api.telegram import router as telegram_router
from api.economic import router as economic_router
from api.calendar import router as calendar_router
from api.rag import router as rag_router
from api.dataset import router as dataset_router
from api.admin import router as admin_router
from api.deep_research import router as deep_research_router
from tasks.scheduler import create_scheduler
from config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Prime the per-agent model-override cache from the DB so the first analysis
    # doesn't pay a DB round-trip inside the agents.
    from services.agent_config import load_overrides
    load_overrides()

    # Register the "/" command menu with Telegram (shows in private chats and
    # groups). Idempotent, safe to run every startup; must never block boot.
    if settings.telegram_bot_token:
        try:
            from services.telegram_client import TelegramClient
            from services.telegram_bot import BOT_COMMANDS
            TelegramClient().set_my_commands(BOT_COMMANDS)
        except Exception as e:
            print(f"[Startup] Telegram setMyCommands failed (non-fatal): {e}")

    scheduler = create_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Agent Invest API",
    description="Multi-agent AI investment analysis system",
    version="1.0.0",
    lifespan=lifespan,
)

_cors_origins = [settings.frontend_url, "http://localhost:3000"]
_cors_origins += [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(_cors_origins)),
    allow_origin_regex=settings.cors_allow_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router)
app.include_router(predictions_router)
app.include_router(accuracy_router)
app.include_router(export_router)
app.include_router(telegram_router)
app.include_router(economic_router)
app.include_router(calendar_router)
app.include_router(rag_router)
app.include_router(dataset_router)
app.include_router(admin_router)
app.include_router(deep_research_router)


@app.get("/")
def root():
    return {"status": "ok", "app": "Agent Invest API"}


@app.get("/health")
def health():
    return {"status": "healthy"}
