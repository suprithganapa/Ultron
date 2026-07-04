"""
User profile — this is what makes ULTRON *yours*.

A small JSON file holds who you are, your preferences, and free-form facts
ULTRON learns about you over time. It is injected into the system prompt on
every turn, so ULTRON always answers with you in mind.
"""
from __future__ import annotations

import json
from typing import Any

from .config import settings

PROFILE_PATH = settings.data_dir / "profile.json"

DEFAULT_PROFILE: dict[str, Any] = {
    "name": "Suprith",
    "email": "suprithgb2005@gmail.com",
    "role": "",
    "location": "",
    "about": "",
    "preferences": [],   # e.g. "prefers concise answers"
    "facts": [],         # free-form things ULTRON has learned
}


def load_profile() -> dict[str, Any]:
    if PROFILE_PATH.exists():
        try:
            data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
            # backfill any missing keys
            return {**DEFAULT_PROFILE, **data}
        except Exception:
            pass
    save_profile(DEFAULT_PROFILE)
    return dict(DEFAULT_PROFILE)


def save_profile(profile: dict[str, Any]) -> None:
    PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")


def set_field(field: str, value: str) -> str:
    p = load_profile()
    if field not in p or field in ("facts", "preferences"):
        return f"Unknown profile field '{field}'. Use one of: " \
               f"name, email, role, location, about."
    p[field] = value
    save_profile(p)
    return f"Updated your {field} to '{value}'."


def add_fact(fact: str) -> str:
    p = load_profile()
    if fact not in p["facts"]:
        p["facts"].append(fact)
        save_profile(p)
    return f"Got it — I'll remember that: {fact}"


def add_preference(pref: str) -> str:
    p = load_profile()
    if pref not in p["preferences"]:
        p["preferences"].append(pref)
        save_profile(p)
    return f"Noted your preference: {pref}"


def profile_prompt() -> str:
    """Render the profile as a block for the system prompt."""
    p = load_profile()
    lines = ["--- WHO YOU SERVE (your user) ---"]
    if p.get("name"):
        lines.append(f"Name: {p['name']}")
    if p.get("role"):
        lines.append(f"Role: {p['role']}")
    if p.get("location"):
        lines.append(f"Location: {p['location']}")
    if p.get("email"):
        lines.append(f"Email: {p['email']}")
    if p.get("about"):
        lines.append(f"About: {p['about']}")
    if p.get("preferences"):
        lines.append("Preferences: " + "; ".join(p["preferences"]))
    if p.get("facts"):
        lines.append("Things you know about them:")
        lines += [f"  - {f}" for f in p["facts"]]
    lines.append(
        "Always address them by name when natural, honour their preferences, "
        "and use these facts to personalise every answer."
    )
    return "\n".join(lines)
