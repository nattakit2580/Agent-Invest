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
from tasks.scheduler import create_scheduler
from config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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


@app.get("/")
def root():
    return {"status": "ok", "app": "Agent Invest API"}


@app.get("/health")
def health():
    return {"status": "healthy"}
