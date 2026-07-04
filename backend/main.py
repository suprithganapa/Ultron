"""
ULTRON web server (FastAPI).

Serves the futuristic dashboard and exposes:
  GET  /                -> the HUD frontend
  POST /api/login       -> exchange the password for a session token
  GET  /api/status      -> brain + tool status (auth)
  WS   /ws              -> real-time streaming chat (auth via ?token=)
  POST /api/chat        -> non-streaming chat (auth)
  GET  /api/tasks       -> personal-ops snapshot (auth)
  POST /api/clear       -> wipe a session's memory (auth)
"""
from __future__ import annotations

from fastapi import (Depends, FastAPI, Header, HTTPException, WebSocket,
                     WebSocketDisconnect)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent, auth, memory
from .config import settings
from .tools import REGISTRY, load_all

FRONTEND = settings.root / "frontend"

app = FastAPI(title="ULTRON", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*"
    else [o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    memory.init_db()
    load_all()
    print("=" * 60)
    print("  ULTRON online.")
    print(f"  Brain : {settings.brain_status()}")
    print(f"  Tools : {len(REGISTRY)} loaded")
    print(f"  Auth  : {'REQUIRED' if settings.require_auth() else 'open (local)'}")
    print(f"  Mode  : {'PUBLIC (hardened)' if settings.public_mode else 'local'}")
    print(f"  Store : {'Postgres' if settings.database_url else 'SQLite'}")
    print("=" * 60)


# --------------------------- auth plumbing ---------------------------

def require_user(authorization: str | None = Header(default=None)) -> None:
    """Dependency: allow if auth disabled, else demand a valid bearer token."""
    if not settings.require_auth():
        return
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    if not auth.verify_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")


class LoginIn(BaseModel):
    password: str


class ChatIn(BaseModel):
    message: str
    session: str = "default"
    image: str | None = None  # optional data URL for vision
    mode: str | None = None   # 'brief' | 'deep' | 'auto'


@app.post("/api/login")
def login(body: LoginIn) -> JSONResponse:
    # If no auth is configured, hand out a token freely (local convenience).
    if not settings.require_auth():
        return JSONResponse({"token": auth.issue_token(), "auth": False})
    if not auth.check_password(body.password):
        raise HTTPException(status_code=401, detail="Wrong password")
    return JSONResponse({"token": auth.issue_token(), "auth": True})


@app.get("/api/status")
def status(_: None = Depends(require_user)) -> dict:
    return {
        "name": "ULTRON",
        "version": "1.1.0",
        "brain": settings.brain_status(),
        "provider": settings.llm_provider,
        "public_mode": settings.public_mode,
        "tools": [
            {"name": t.name, "description": t.description} for t in REGISTRY.values()
        ],
    }


class BrainIn(BaseModel):
    provider: str


@app.post("/api/brain")
def set_brain(body: BrainIn, _: None = Depends(require_user)) -> dict:
    """Switch ULTRON's brain at runtime (no restart needed)."""
    p = body.provider.strip().lower()
    if p not in {"anthropic", "openai", "groq", "gemini", "mock"}:
        raise HTTPException(status_code=400, detail="unknown provider")
    settings.llm_provider = p
    return {"provider": p, "brain": settings.brain_status()}


@app.get("/api/auth-required")
def auth_required() -> dict:
    """Public endpoint so the UI knows whether to show a login screen."""
    return {"required": settings.require_auth()}


@app.get("/api/tasks")
def tasks(_: None = Depends(require_user)) -> dict:
    return {
        "tasks": memory.list_tasks(),
        "notes": memory.list_notes(),
        "reminders": memory.list_reminders(),
    }


@app.get("/api/history")
def history(session: str = "default", _: None = Depends(require_user)) -> dict:
    msgs = memory.get_history(session, limit=100)
    # Hide internal agent JSON turns; keep human-visible user/assistant text.
    visible = [m for m in msgs if m["role"] in ("user", "assistant")
               and not m["content"].startswith(("OBSERVATION:", "{"))]
    return {"messages": visible}


@app.post("/api/chat")
def chat(body: ChatIn, _: None = Depends(require_user)) -> JSONResponse:
    events = list(agent.run(body.session, body.message, body.image, body.mode))
    final = next((e["text"] for e in reversed(events) if e["type"] == "final"), "")
    return JSONResponse({"reply": final, "events": events})


@app.post("/api/clear")
def clear(body: ChatIn, _: None = Depends(require_user)) -> dict:
    memory.clear_history(body.session)
    return {"ok": True}


@app.websocket("/ws")
async def ws(sock: WebSocket) -> None:
    # Authenticate the socket via ?token= before accepting.
    if settings.require_auth():
        token = sock.query_params.get("token")
        if not auth.verify_token(token):
            await sock.close(code=1008)
            return
    await sock.accept()
    try:
        while True:
            data = await sock.receive_json()
            message = data.get("message", "")
            session = data.get("session", "default")
            image = data.get("image")
            mode = data.get("mode")
            if not message.strip() and not image:
                continue
            for event in agent.run(session, message, image, mode):
                await sock.send_json(event)
            await sock.send_json({"type": "done"})
    except WebSocketDisconnect:
        return
    except Exception as e:  # keep the socket alive on tool errors
        await sock.send_json({"type": "error", "text": str(e)})


# --- static frontend (mounted last so /api and /ws take precedence) ---
@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND), name="frontend")
