# ULTRON — your own AI assistant

> **U**nified **L**ogic · **T**actical **R**esponse · **O**perations **N**etwork
>
> A JARVIS-style AI assistant that talks, listens, and actually *does things* —
> web research, file control, code execution, and your personal task ops — all
> behind a futuristic HUD dashboard.

ULTRON is a full-stack AI agent. A Python backend runs a real tool-calling
agent loop with a pluggable LLM brain; a browser dashboard gives you voice and
text control with an Iron-Man-style interface. It runs **out of the box with no
API keys** in a keyless demo mode, and upgrades to a full conversational brain
the moment you drop in a key.

---

## What it can do

| Area | Tools |
|------|-------|
| **Research** | `search_web`, `fetch_url`, `get_news` — live web search & headlines |
| **Vision** | attach an image and ULTRON *sees* it — screenshots, photos, diagrams, handwriting |
| **Computer / files** | `list_files`, `read_file`, `write_file` — inspect your machine, write to a safe workspace |
| **Coding** | `run_python`, `run_shell` — execute code and commands with timeouts and safety switches |
| **Personal ops** | notes, tasks, reminders — persisted, never forgotten |
| **Memory of you** | `remember`, `whoami`, `update_profile` — ULTRON learns who you are and personalises every reply |
| **Gmail + Calendar** | `gmail_unread`, `gmail_send`, `calendar_upcoming`, `calendar_add` (opt-in) |
| **Spotify** | `spotify_now_playing`, `spotify_play`, `spotify_pause`, `spotify_next` (opt-in) |
| **System** | `get_time`, `system_info` — clock and machine diagnostics |

Every capability is a small Python function. Adding a new one is a few lines
(see *Extending* below).

**Runs anywhere:** locally with a beautiful HUD, or deployed to the cloud with
a login wall, HTTPS, and durable memory. See **[DEPLOY.md](DEPLOY.md)** to host
it publicly and **[INTEGRATIONS.md](INTEGRATIONS.md)** to connect Gmail,
Calendar & Spotify.

### Security & memory highlights

- **Login-protected** in public mode (signed session tokens; set a password).
- **Durable memory** — SQLite locally, Postgres in the cloud, so past chats and
  everything ULTRON learns about you survive restarts.
- **Hardened for the internet** — public mode disables remote code execution,
  locks CORS, and keeps every secret in environment variables, never in git.

---

## Architecture

```
                         Browser  (frontend/)
        ┌───────────────────────────────────────────────┐
        │  HUD dashboard · text chat · voice in/out      │
        │  Web Speech API  (STT + TTS, no keys needed)   │
        └───────────────▲───────────────┬───────────────┘
                        │  WebSocket /ws │  (streamed thoughts,
                        │                ▼   tool calls, answers)
        ┌───────────────┴───────────────────────────────┐
        │              FastAPI server  (backend/main.py) │
        │                                                │
        │   agent.py   ── ReAct loop (portable JSON)     │
        │      │                                         │
        │      ├── llm.py     pluggable brain            │
        │      │        openai · gemini · groq ·         │
        │      │        anthropic · MOCK (keyless)       │
        │      │                                         │
        │      ├── tools/     web · files · code ·       │
        │      │              system · personal          │
        │      │                                         │
        │      └── memory.py  SQLite: history, notes,    │
        │                     tasks, reminders           │
        └────────────────────────────────────────────────┘
```

The agent uses a **portable ReAct protocol**: the LLM replies with strict JSON
(a tool call or a final answer), so the *same* loop drives every provider —
including the keyless mock brain that lets the whole system run and demo
immediately.

---

## Quick start

### 1. Install

```bash
cd Ultron
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure (optional)

```bash
copy .env.example .env      # Windows
# cp .env.example .env      # macOS/Linux
```

ULTRON runs **without any keys** in `mock` mode. To unlock the full
conversational brain, set `LLM_PROVIDER` and the matching key in `.env`:

```
LLM_PROVIDER=groq          # or openai | gemini | anthropic
GROQ_API_KEY=sk-...
```

Groq and Gemini both have generous free tiers — good places to start.

### 3. Run

```bash
python run.py
```

Open **http://127.0.0.1:8000** in your browser. Click the mic and talk, or
type. ULTRON replies in text and speaks back.

---

## Voice

Voice works entirely in the browser via the **Web Speech API** — speech
recognition for your mic and speech synthesis for ULTRON's replies. No paid
STT/TTS keys, no extra setup. Best support is in Chrome/Edge. Toggle the
speaker button to mute spoken replies.

---

## Extending ULTRON — add a tool

1. Open (or create) a file in `backend/tools/`.
2. Write a function and decorate it:

```python
from . import tool

@tool("weather", "Get the weather for a city.", {"city": "city name"})
def weather(city: str) -> str:
    ...
    return "It's 24°C and clear in " + city
```

3. Make sure the module is imported in `backend/tools/__init__.py`'s
   `load_all()`.

That's it — ULTRON discovers the tool, tells the LLM about it, and can call it.

---

## Safety

- File **writes** are sandboxed to `data/workspace/`.
- Shell and Python execution are gated by `ALLOW_SHELL` / `ALLOW_CODE_EXEC`
  in `.env` and run with 30-second timeouts.
- Only run with execution enabled on a machine you trust.

---

## Project layout

```
Ultron/
├── run.py                  # launcher: python run.py
├── requirements.txt
├── .env.example
├── backend/
│   ├── main.py             # FastAPI app: HTTP + WebSocket
│   ├── config.py           # settings + system prompt
│   ├── agent.py            # ReAct agent loop
│   ├── llm.py              # pluggable LLM providers + mock brain
│   ├── memory.py           # SQLite: history, notes, tasks, reminders
│   └── tools/
│       ├── web.py          # search_web, fetch_url, get_news
│       ├── files.py        # list_files, read_file, write_file
│       ├── code.py         # run_shell, run_python
│       ├── system.py       # get_time, system_info
│       └── personal.py     # notes, tasks, reminders
├── frontend/
│   ├── index.html          # HUD dashboard
│   ├── style.css           # Iron-Man aesthetic
│   └── app.js              # chat, voice, live panels
└── data/                   # SQLite db + write sandbox (auto-created)
```

## Tech stack

FastAPI · Uvicorn · httpx · SQLite · vanilla JS + Web Speech API · a portable
ReAct agent over OpenAI / Gemini / Groq / Anthropic (or keyless mock).

## License

MIT — build on it, ship it, make it yours.
