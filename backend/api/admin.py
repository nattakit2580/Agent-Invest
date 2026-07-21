"""Admin API — password-guarded per-agent model configuration.

The password is verified server-side (Settings.admin_password, with no default).
The frontend sends it in the ``X-Admin-Password`` header on every admin request;
there is no session/token to keep this simple.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config import get_settings
from services.agent_config import (
    AGENT_NAMES,
    MODEL_CATALOG,
    get_effective_config,
    global_default_model,
    set_overrides,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _check_password(password: str | None) -> None:
    expected = get_settings().admin_password
    # Fail closed: with no password configured, deny everything (never treat an
    # empty server-side password as "auth disabled / accept all").
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin auth is not configured on the server (set ADMIN_PASSWORD).",
        )
    # Constant-time compare to avoid leaking the password via response timing.
    if not password or not secrets.compare_digest(password, expected):
        raise HTTPException(status_code=401, detail="รหัสผ่านไม่ถูกต้อง")


def require_admin(x_admin_password: str | None = Header(default=None)) -> None:
    _check_password(x_admin_password)


class LoginRequest(BaseModel):
    password: str


class AgentConfigUpdate(BaseModel):
    agent: str
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class ConfigUpdateRequest(BaseModel):
    agents: list[AgentConfigUpdate]


def _config_payload() -> dict:
    return {
        "agents": get_effective_config(),
        "models": MODEL_CATALOG,
        "global_default": global_default_model(),
    }


@router.post("/login")
def login(req: LoginRequest):
    _check_password(req.password)
    return {"ok": True}


@router.get("/config")
def get_config(x_admin_password: str | None = Header(default=None)):
    _check_password(x_admin_password)
    return _config_payload()


@router.put("/config")
def update_config(req: ConfigUpdateRequest, x_admin_password: str | None = Header(default=None)):
    _check_password(x_admin_password)

    updates: dict[str, dict] = {}
    for item in req.agents:
        if item.agent not in AGENT_NAMES:
            raise HTTPException(status_code=400, detail=f"ไม่รู้จัก agent: {item.agent}")
        cfg: dict = {}
        # Only include fields the client actually sent so blanks can clear them.
        fields = item.model_dump(exclude_unset=True)
        if "model" in fields:
            cfg["model"] = item.model
        if "temperature" in fields:
            cfg["temperature"] = item.temperature
        if "max_tokens" in fields:
            cfg["max_tokens"] = item.max_tokens
        updates[item.agent] = cfg

    set_overrides(updates)
    return _config_payload()
