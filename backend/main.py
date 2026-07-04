"""
ULTRON web server (FastAPI) — multi-user platform.

Auth:      register / login / me
Chat:      per-user, per-conversation (WebSocket + REST)
History:   conversation CRUD (ChatGPT-style sidebar)
Admin:     users, stats, health, manage — for the admin account
"""
from __future__ import annotations

import time

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
_STARTED = time.time()

app = FastAPI(title="ULTRON", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*"
    else [o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    memory.init_db()
    load_all()
    print("=" * 60)
    print("  ULTRON v2 online (multi-user).")
    print(f"  Brain : {settings.brain_status()}")
    print(f"  Tools : {len(REGISTRY)} loaded")
    print(f"  Store : {'Postgres' if settings.database_url else 'SQLite'}")
    print(f"  Users : {memory.count_users()} registered")
    print("=" * 60)


# --------------------------- auth plumbing ---------------------------

def require_user(authorization: str | None = Header(default=None)) -> int:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    uid = auth.verify_token(token)
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = memory.get_user(uid)
    if not user or user.get("disabled"):
        raise HTTPException(status_code=403, detail="Account unavailable")
    return uid


def require_admin(uid: int = Depends(require_user)) -> int:
    user = memory.get_user(uid)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return uid


def _own_conversation(conv_id: int, uid: int) -> dict:
    conv = memory.get_conversation(conv_id)
    if not conv or conv["user_id"] != uid:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def _title_from(message: str) -> str:
    words = message.strip().split()
    title = " ".join(words[:7])
    return (title[:48] + "…") if len(title) > 48 else (title or "New chat")


def _public_user(u: dict) -> dict:
    return {"id": u["id"], "email": u["email"], "is_admin": bool(u["is_admin"])}


# ------------------------------ models ------------------------------

class Creds(BaseModel):
    email: str
    password: str


class ChatIn(BaseModel):
    message: str
    conversation_id: int | None = None
    image: str | None = None
    mode: str | None = None


class TitleIn(BaseModel):
    title: str


class BrainIn(BaseModel):
    provider: str


class DisableIn(BaseModel):
    disabled: bool


# ------------------------------- auth -------------------------------

@app.post("/api/register")
def register(body: Creds) -> JSONResponse:
    user, err = auth.register(body.email, body.password)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return JSONResponse({"token": auth.issue_token(user["id"]),
                         "user": _public_user(user)})


@app.post("/api/login")
def login(body: Creds) -> JSONResponse:
    user, err = auth.authenticate(body.email, body.password)
    if err:
        raise HTTPException(status_code=401, detail=err)
    return JSONResponse({"token": auth.issue_token(user["id"]),
                         "user": _public_user(user)})


@app.get("/api/me")
def me(uid: int = Depends(require_user)) -> dict:
    return _public_user(memory.get_user(uid))


@app.get("/api/status")
def status(uid: int = Depends(require_user)) -> dict:
    return {
        "name": "ULTRON", "version": "2.0.0",
        "brain": settings.brain_status(), "provider": settings.llm_provider,
        "tools": [{"name": t.name, "description": t.description}
                  for t in REGISTRY.values()],
    }


# --------------------------- conversations --------------------------

@app.get("/api/conversations")
def list_conversations(uid: int = Depends(require_user)) -> dict:
    return {"conversations": memory.list_conversations(uid)}


@app.post("/api/conversations")
def new_conversation(uid: int = Depends(require_user)) -> dict:
    cid = memory.create_conversation(uid)
    return {"id": cid, "title": "New chat"}


@app.get("/api/conversations/{conv_id}/messages")
def conv_messages(conv_id: int, uid: int = Depends(require_user)) -> dict:
    _own_conversation(conv_id, uid)
    msgs = memory.get_messages(conv_id, limit=200)
    visible = [m for m in msgs if m["role"] in ("user", "assistant")
               and not m["content"].startswith(("OBSERVATION:", "{"))]
    return {"messages": visible}


@app.patch("/api/conversations/{conv_id}")
def rename_conv(conv_id: int, body: TitleIn, uid: int = Depends(require_user)) -> dict:
    _own_conversation(conv_id, uid)
    memory.rename_conversation(conv_id, body.title)
    return {"ok": True}


@app.delete("/api/conversations/{conv_id}")
def delete_conv(conv_id: int, uid: int = Depends(require_user)) -> dict:
    _own_conversation(conv_id, uid)
    memory.delete_conversation(conv_id)
    return {"ok": True}


@app.get("/api/tasks")
def tasks(uid: int = Depends(require_user)) -> dict:
    return {"tasks": memory.list_tasks(uid), "notes": memory.list_notes(uid),
            "reminders": memory.list_reminders(uid)}


# ------------------------------- chat -------------------------------

@app.post("/api/chat")
def chat(body: ChatIn, uid: int = Depends(require_user)) -> JSONResponse:
    conv_id = body.conversation_id
    if not conv_id:
        conv_id = memory.create_conversation(uid, _title_from(body.message))
    else:
        _own_conversation(conv_id, uid)
    events = list(agent.run(uid, conv_id, body.message, body.image, body.mode))
    final = next((e["text"] for e in reversed(events) if e["type"] == "final"), "")
    return JSONResponse({"reply": final, "conversation_id": conv_id})


@app.websocket("/ws")
async def ws(sock: WebSocket) -> None:
    uid = auth.verify_token(sock.query_params.get("token"))
    if not uid:
        await sock.close(code=1008)
        return
    user = memory.get_user(uid)
    if not user or user.get("disabled"):
        await sock.close(code=1008)
        return
    await sock.accept()
    try:
        while True:
            data = await sock.receive_json()
            message = data.get("message", "")
            image = data.get("image")
            mode = data.get("mode")
            conv_id = data.get("conversation_id")
            if not message.strip() and not image:
                continue
            if not conv_id:
                conv_id = memory.create_conversation(uid, _title_from(message))
                await sock.send_json({"type": "conversation", "id": conv_id,
                                      "title": _title_from(message)})
            else:
                conv = memory.get_conversation(conv_id)
                if not conv or conv["user_id"] != uid:
                    await sock.send_json({"type": "error", "text": "Invalid conversation"})
                    continue
                if conv["title"] == "New chat" and message.strip():
                    t = _title_from(message)
                    memory.rename_conversation(conv_id, t)
                    await sock.send_json({"type": "title", "id": conv_id, "title": t})
            for event in agent.run(uid, conv_id, message, image, mode):
                await sock.send_json(event)
            await sock.send_json({"type": "done"})
    except WebSocketDisconnect:
        return
    except Exception as e:
        await sock.send_json({"type": "error", "text": str(e)})


# ------------------------------ admin -------------------------------

@app.get("/api/admin/users")
def admin_users(uid: int = Depends(require_admin)) -> dict:
    return {"users": memory.list_users()}


@app.get("/api/admin/stats")
def admin_stats(uid: int = Depends(require_admin)) -> dict:
    return {"totals": memory.global_stats(), "per_user": memory.user_stats()}


@app.get("/api/admin/health")
def admin_health(uid: int = Depends(require_admin)) -> dict:
    return {
        "brain": settings.brain_status(), "provider": settings.llm_provider,
        "store": "Postgres" if settings.database_url else "SQLite",
        "tools": len(REGISTRY), "public_mode": settings.public_mode,
        "uptime_seconds": int(time.time() - _STARTED),
    }


@app.post("/api/admin/users/{user_id}/disable")
def admin_disable(user_id: int, body: DisableIn,
                  uid: int = Depends(require_admin)) -> dict:
    memory.set_user_disabled(user_id, body.disabled)
    return {"ok": True}


@app.delete("/api/admin/users/{user_id}")
def admin_delete(user_id: int, uid: int = Depends(require_admin)) -> dict:
    if user_id == uid:
        raise HTTPException(status_code=400, detail="You can't delete yourself.")
    memory.delete_user(user_id)
    return {"ok": True}


@app.post("/api/brain")
def set_brain(body: BrainIn, uid: int = Depends(require_admin)) -> dict:
    p = body.provider.strip().lower()
    if p not in {"anthropic", "openai", "groq", "gemini", "mock"}:
        raise HTTPException(status_code=400, detail="unknown provider")
    settings.llm_provider = p
    return {"provider": p, "brain": settings.brain_status()}


# --------------------------- static frontend ------------------------

@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(FRONTEND / "admin.html")


if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND), name="frontend")
