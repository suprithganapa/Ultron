"""Personal-ops tools: notes, tasks, reminders — scoped to the current user."""
from __future__ import annotations

import time
from datetime import datetime

from .. import memory
from ..context import get_user
from . import tool


# ------------------------------- notes ------------------------------

@tool("add_note", "Save a note for later.", {"text": "the note text"})
def add_note(text: str) -> str:
    nid = memory.add_note(get_user(), text)
    return f"Noted (#{nid}), sir."


@tool("list_notes", "List all saved notes.", {})
def list_notes() -> str:
    notes = memory.list_notes(get_user())
    if not notes:
        return "You have no notes."
    return "Your notes:\n" + "\n".join(f"  #{n['id']}: {n['text']}" for n in notes)


# ------------------------------- tasks ------------------------------

@tool("add_task", "Add a task to the to-do list.", {"title": "the task"})
def add_task(title: str) -> str:
    tid = memory.add_task(get_user(), title)
    return f"Task #{tid} added: {title}"


@tool("list_tasks", "Show the to-do list.", {})
def list_tasks() -> str:
    tasks = memory.list_tasks(get_user())
    if not tasks:
        return "Your task list is clear, sir."
    out = []
    for t in tasks:
        box = "[x]" if t["done"] else "[ ]"
        out.append(f"  {box} #{t['id']} {t['title']}")
    return "Your tasks:\n" + "\n".join(out)


@tool("complete_task", "Mark a task as done.", {"task_id": "the task id number"})
def complete_task(task_id: int) -> str:
    ok = memory.complete_task(get_user(), int(task_id))
    return f"Task #{task_id} completed." if ok else f"No task #{task_id}."


# ----------------------------- reminders ----------------------------

@tool(
    "add_reminder",
    "Set a reminder that fires after N minutes.",
    {"text": "what to be reminded of", "in_minutes": "minutes from now (number)"},
)
def add_reminder(text: str, in_minutes: float = 30) -> str:
    due = time.time() + float(in_minutes) * 60
    rid = memory.add_reminder(get_user(), text, due)
    when = datetime.fromtimestamp(due).strftime("%I:%M %p")
    return f"Reminder #{rid} set for {when}: {text}"


@tool("list_reminders", "List all reminders.", {})
def list_reminders() -> str:
    rems = memory.list_reminders(get_user())
    if not rems:
        return "No reminders set."
    out = []
    for r in rems:
        when = datetime.fromtimestamp(r["due"]).strftime("%d %b %I:%M %p")
        state = "fired" if r["fired"] else "pending"
        out.append(f"  #{r['id']} [{state}] {when} — {r['text']}")
    return "Reminders:\n" + "\n".join(out)
