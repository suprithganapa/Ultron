"""
Per-user profile — what makes ULTRON personal to each account.

Stored in the database (profiles table), one per user. Injected into the
system prompt every turn so ULTRON always answers with that user in mind.
"""
from __future__ import annotations

from typing import Any

from . import memory

DEFAULT_PROFILE: dict[str, Any] = {
    "name": "",
    "email": "",
    "role": "",
    "location": "",
    "about": "",
    "preferences": [],
    "facts": [],
}


def load_profile(user_id: int) -> dict[str, Any]:
    p = memory.get_profile(user_id)
    if p is None:
        p = dict(DEFAULT_PROFILE)
        user = memory.get_user(user_id)
        if user:
            p["email"] = user["email"]
            p["name"] = user["email"].split("@")[0].title()
        memory.save_profile(user_id, p)
    return {**DEFAULT_PROFILE, **p}


def set_field(user_id: int, field: str, value: str) -> str:
    p = load_profile(user_id)
    if field not in p or field in ("facts", "preferences"):
        return "Unknown profile field. Use: name, email, role, location, about."
    p[field] = value
    memory.save_profile(user_id, p)
    return f"Updated your {field} to '{value}'."


def add_fact(user_id: int, fact: str) -> str:
    p = load_profile(user_id)
    if fact not in p["facts"]:
        p["facts"].append(fact)
        memory.save_profile(user_id, p)
    return f"Got it — I'll remember that: {fact}"


def add_preference(user_id: int, pref: str) -> str:
    p = load_profile(user_id)
    if pref not in p["preferences"]:
        p["preferences"].append(pref)
        memory.save_profile(user_id, p)
    return f"Noted your preference: {pref}"


def profile_prompt(user_id: int) -> str:
    p = load_profile(user_id)
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
    lines.append("Always address them by name when natural, honour their "
                 "preferences, and personalise every answer.")
    return "\n".join(lines)
