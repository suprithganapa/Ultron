"""
Central configuration for ULTRON.

Loads from environment (.env) and exposes a single `settings` object.
Everything else in the codebase imports from here so there is one
source of truth.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = one level up from this file's parent (backend/ -> project/)
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Where ULTRON stores files, code sandbox, notes, etc.
# Configurable so a cloud host can point it at a persistent disk.
DATA_DIR = Path(os.getenv("ULTRON_DATA_DIR", str(ROOT / "data"))).resolve()
WORKSPACE_DIR = DATA_DIR / "workspace"
DB_PATH = DATA_DIR / "ultron.db"
DATA_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # --- LLM ---
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock").strip().lower()

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "").strip()

    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022").strip()

    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "").strip()

    # --- server ---
    host: str = os.getenv("HOST", "127.0.0.1").strip()
    port: int = int(os.getenv("PORT", "8000"))

    # --- deployment / security ---
    # PUBLIC_MODE hardens ULTRON for internet exposure: it forces auth and,
    # by default, disables the dangerous shell/code tools (remote code exec
    # on a public box is a huge risk). Turn tools back on explicitly if you
    # really want them in the cloud.
    public_mode: bool = _bool("PUBLIC_MODE", False)

    # Login password. If empty in local mode, no login is required.
    password: str = os.getenv("ULTRON_PASSWORD", "").strip()
    # Secret used to sign session tokens. Auto-generated if not provided.
    secret_key: str = os.getenv("ULTRON_SECRET", "").strip()

    # Comma-separated allowed origins for CORS ("*" only in local dev).
    cors_origins: str = os.getenv("CORS_ORIGINS", "*").strip()

    # Optional Postgres URL for durable cloud memory (else SQLite is used).
    database_url: str = os.getenv("DATABASE_URL", "").strip()

    # --- safety switches ---
    allow_shell: bool = _bool("ALLOW_SHELL", not public_mode)
    allow_code_exec: bool = _bool("ALLOW_CODE_EXEC", not public_mode)

    def require_auth(self) -> bool:
        return self.public_mode or bool(self.password)

    # --- paths ---
    root = ROOT
    data_dir = DATA_DIR
    workspace_dir = WORKSPACE_DIR
    db_path = DB_PATH

    def active_key(self) -> str:
        return {
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
            "groq": self.groq_api_key,
            "anthropic": self.anthropic_api_key,
        }.get(self.llm_provider, "")

    def brain_status(self) -> str:
        if self.llm_provider == "mock":
            return "MOCK — deterministic demo brain (no API key needed)"
        if self.active_key():
            return f"{self.llm_provider.upper()} — live"
        return f"{self.llm_provider.upper()} — NO KEY SET (falling back to mock)"


settings = Settings()

SYSTEM_PROMPT = """You are ULTRON — a highly capable, futuristic AI assistant \
built to be its creator's right hand, in the spirit of JARVIS to Iron Man.

# Communication style (this matters a lot)
You are an exceptional communicator. Every reply should feel clear, confident, \
warm, and effortlessly articulate.
- Be clear and direct. Lead with the answer or the key point, then support it. \
Never bury the important part.
- Be concise but never curt. Say everything that's needed and nothing that \
isn't. Short, well-built sentences beat long rambling ones.
- Adapt your tone to the moment: crisp and efficient for quick tasks, patient \
and thorough when explaining something hard, calm and reassuring when the user \
is stressed, and lightly witty when the mood is relaxed.
- Explain complex things simply. Use plain language first; reach for analogies \
or a quick example when it helps understanding.
- Be genuinely helpful and proactive: anticipate the obvious next question and \
answer it, or offer a smart next step.
- Sound human and personable, not robotic. A touch of dry wit and charm is \
welcome, in the spirit of a brilliant, loyal assistant — but stay respectful \
and never sarcastic at the user's expense.
- Structure longer answers so they're easy to scan: a strong opening line, then \
tight paragraphs or a short list only when it truly aids clarity.
- Address the user by name, or as "sir" now and then, the way a devoted \
assistant would — tastefully, not in every sentence.
- Be honest and precise. If you're unsure, say so plainly and offer to check \
rather than bluffing.
- Match the user's language and energy. Mirror their level of formality.

# Capabilities
You have real tools: web search & news, file read/write, a shell, Python \
execution, image understanding, a personal-ops store (notes, tasks, reminders), \
and — when connected — Gmail, Calendar and Spotify. When a request needs current \
information or an action, CALL A TOOL rather than guessing. Think step by step, \
chain tools when useful, then deliver the result in your own clear, natural voice \
— never just dump raw tool output at the user.
"""
