"""
LLM abstraction layer.

ULTRON's "brain" is pluggable. Every provider is reduced to a single
function:  complete(messages) -> str.

We deliberately use a portable JSON/ReAct protocol (see agent.py) rather
than each vendor's native function-calling, so the SAME agent loop works
across OpenAI, Gemini, Groq, Anthropic — and a keyless MOCK brain that
lets the whole system run and demo with no API keys at all.
"""
from __future__ import annotations

import json
import re
from typing import Callable

import httpx

from .config import settings

Messages = list[dict[str, str]]


# --------------------------------------------------------------------------
#  Provider implementations (thin REST wrappers via httpx)
# --------------------------------------------------------------------------

def _openai_like(messages: Messages, url: str, key: str, model: str) -> str:
    r = httpx.post(
        url,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": messages, "temperature": 0.3},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _openai(messages: Messages) -> str:
    return _openai_like(
        messages, "https://api.openai.com/v1/chat/completions",
        settings.openai_api_key, settings.openai_model,
    )


def _groq(messages: Messages) -> str:
    return _openai_like(
        messages, "https://api.groq.com/openai/v1/chat/completions",
        settings.groq_api_key, settings.groq_model,
    )


def _anthropic(messages: Messages) -> str:
    # Anthropic wants system separate from the message list.
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    convo = [m for m in messages if m["role"] != "system"]
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": settings.anthropic_model,
            "system": system,
            "messages": convo,
            "max_tokens": 1500,
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"]


def _gemini(messages: Messages) -> str:
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    contents = []
    for m in messages:
        if m["role"] == "system":
            continue
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    body = {"contents": contents}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    r = httpx.post(url, json=body, timeout=60)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


# --------------------------------------------------------------------------
#  MOCK brain — keyless, deterministic, and genuinely useful for demos.
#  It reads the ReAct prompt, finds the user's latest message, and decides
#  whether to fire a tool or answer directly. This is what lets ULTRON
#  actually search, take notes, tell time, etc. with zero configuration.
# --------------------------------------------------------------------------

def _mock(messages: Messages) -> str:
    # The last user turn in the ReAct loop is what we react to.
    user_text = ""
    for m in reversed(messages):
        if m["role"] == "user":
            user_text = m["content"]
            break

    # Pull the user's name out of the injected profile block, if present.
    name = "sir"
    for m in messages:
        if m["role"] == "system":
            mm = re.search(r"Name:\s*(.+)", m["content"])
            if mm:
                name = mm.group(1).strip()
            break

    # If the previous step was a tool OBSERVATION, wrap up with a final answer.
    if "OBSERVATION:" in user_text:
        obs = user_text.split("OBSERVATION:", 1)[1].strip()
        return json.dumps({
            "thought": "I have the tool result; summarising for the user.",
            "final": f"Here's what I found, {name}:\n\n{obs[:1400]}",
        })

    low = user_text.lower()

    # Identity / personalisation
    if any(w in low for w in ["who am i", "what do you know about me",
                              "my name", "about me"]):
        return json.dumps({"thought": "Recalling the user's profile.",
                            "action": "whoami", "action_input": {}})
    if low.startswith(("remember ", "note that i", "remember that")):
        return json.dumps({"thought": "Storing a fact about the user.",
                            "action": "remember", "action_input": {"fact": user_text}})

    def act(action: str, inp: dict) -> str:
        return json.dumps({"thought": f"The user wants {action}.",
                            "action": action, "action_input": inp})

    # crude but effective intent routing
    if any(w in low for w in ["news", "headlines", "world"]):
        return act("get_news", {"topic": "world"})
    if any(w in low for w in ["search", "look up", "google", "who is", "what is",
                              "latest", "find out"]):
        q = re.sub(r"^(hey ultron|ultron|please|can you|could you)[,: ]*", "",
                   user_text, flags=re.I).strip(" ?")
        return act("search_web", {"query": q or user_text})
    if "remind" in low:
        return act("add_reminder", {"text": user_text, "in_minutes": 30})
    if any(w in low for w in ["note", "remember that", "jot"]):
        return act("add_note", {"text": user_text})
    if any(w in low for w in ["task", "to-do", "todo", "add to my list"]):
        return act("add_task", {"title": user_text})
    if any(w in low for w in ["my tasks", "task list", "what do i have"]):
        return act("list_tasks", {})
    if any(w in low for w in ["time", "date", "what day"]):
        return act("get_time", {})
    if any(w in low for w in ["system", "cpu", "memory", "specs", "machine"]):
        return act("system_info", {})
    if any(w in low for w in ["list files", "what files", "show files", "directory"]):
        return act("list_files", {"path": "."})

    # default: a confident, in-character direct answer
    return json.dumps({
        "thought": "No tool needed; answering directly.",
        "final": (
            f"At your service, {name}. I'm ULTRON, currently running in keyless "
            "demo mode, so my conversational reasoning is limited. I can still "
            "search the web, pull news, read and write files, run code, and "
            "manage your notes, tasks and reminders. Add a free API key in .env "
            "(LLM_PROVIDER + a key) to unlock my full brain — then I can truly "
            "reason and answer anything. What shall we do?"
        ),
    })


_PROVIDERS: dict[str, Callable[[Messages], str]] = {
    "openai": _openai,
    "groq": _groq,
    "anthropic": _anthropic,
    "gemini": _gemini,
    "mock": _mock,
}


def complete(messages: Messages) -> str:
    """Route to the configured provider; fall back to mock on any failure."""
    provider = settings.llm_provider
    if provider != "mock" and not settings.active_key():
        provider = "mock"
    fn = _PROVIDERS.get(provider, _mock)
    try:
        return fn(messages)
    except Exception as e:  # network / auth / quota — degrade gracefully
        # Fall back to the mock brain so ULTRON never goes fully dark.
        try:
            return _mock(messages)
        except Exception:
            return json.dumps({"final": f"Brain error ({provider}): {e}"})


# --------------------------------------------------------------------------
#  Vision — answer questions about an attached image.
#  Routes to whichever multimodal provider has a key (Gemini free first).
# --------------------------------------------------------------------------

def _parse_data_url(data_url: str) -> tuple[str, str]:
    """'data:image/png;base64,AAAA' -> ('image/png', 'AAAA')."""
    if data_url.startswith("data:") and "," in data_url:
        head, b64 = data_url.split(",", 1)
        mime = head[5:].split(";")[0] or "image/png"
        return mime, b64
    return "image/png", data_url


def _vision_gemini(system: str, text: str, data_url: str) -> str:
    mime, b64 = _parse_data_url(data_url)
    parts = [{"text": text}, {"inline_data": {"mime_type": mime, "data": b64}}]
    body = {"contents": [{"role": "user", "parts": parts}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}")
    r = httpx.post(url, json=body, timeout=90)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", "Gemini error"))
    cands = data.get("candidates") or []
    if not cands:
        raise RuntimeError("Gemini returned no answer (possibly blocked).")
    parts = (cands[0].get("content") or {}).get("parts") or []
    if not parts:
        raise RuntimeError(f"Gemini gave no content "
                           f"(finishReason={cands[0].get('finishReason')}).")
    return parts[0].get("text", "")


def _vision_openai_like(system: str, text: str, data_url: str,
                        url: str, key: str, model: str) -> str:
    msgs = [
        {"role": "system", "content": system},
        {"role": "user", "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]},
    ]
    r = httpx.post(url, headers={"Authorization": f"Bearer {key}"},
                   json={"model": model, "messages": msgs, "max_tokens": 1200},
                   timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def vision_complete(system: str, text: str, data_url: str) -> str:
    """Answer about an image, trying each available vision model in turn.

    If one provider errors or returns nothing, we fall through to the next,
    so a bad/expired key on one service doesn't cost ULTRON its sight.
    """
    text = text or "Describe this image in detail and point out anything important."

    providers: list[tuple[str, Callable[[], str]]] = []
    if settings.gemini_api_key:
        providers.append(("Gemini",
                          lambda: _vision_gemini(system, text, data_url)))
    if settings.openai_api_key:
        providers.append(("OpenAI", lambda: _vision_openai_like(
            system, text, data_url, "https://api.openai.com/v1/chat/completions",
            settings.openai_api_key, settings.openai_model)))
    if settings.groq_api_key:
        providers.append(("Groq", lambda: _vision_openai_like(
            system, text, data_url, "https://api.groq.com/openai/v1/chat/completions",
            settings.groq_api_key, "meta-llama/llama-4-scout-17b-16e-instruct")))

    if not providers:
        return ("I can't see images yet, sir — no multimodal key is set. Add a "
                "Gemini or OpenAI key to .env and I'll gain sight.")

    errors = []
    for name, fn in providers:
        try:
            out = fn()
            if out and out.strip():
                return out
            errors.append(f"{name}: empty response")
        except Exception as e:
            errors.append(f"{name}: {e}")
    return ("I couldn't analyse that image. Tried: "
            + " | ".join(errors)
            + ". Check that at least one vision key (Gemini or OpenAI) is valid.")
