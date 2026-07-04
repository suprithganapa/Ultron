"""
Gmail + Google Calendar tools.

These stay dormant until you connect a Google account (see INTEGRATIONS.md):
run `python scripts/google_login.py` once to create data/google_token.json.
Until then, each tool returns a friendly "not connected" message rather than
crashing — so ULTRON always boots.
"""
from __future__ import annotations

import base64
from email.mime.text import MIMEText

from ..config import settings
from . import tool

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]

_NOT_CONNECTED = (
    "Google isn't connected yet. Follow INTEGRATIONS.md: create OAuth "
    "credentials, then run `python scripts/google_login.py` once. "
)


def _service(api: str, version: str):
    """Return (service, error). error is a message string if unavailable."""
    token_path = settings.data_dir / "google_token.json"
    if not token_path.exists():
        return None, _NOT_CONNECTED
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
        return build(api, version, credentials=creds, cache_discovery=False), None
    except ModuleNotFoundError:
        return None, ("Google libraries aren't installed. Run "
                      "`pip install -r requirements.txt`.")
    except Exception as e:
        return None, f"Google auth error: {e}"


# ------------------------------- Gmail ------------------------------

@tool(
    "gmail_unread",
    "Check the user's most recent unread emails (senders + subjects).",
    {"max_results": "how many to show (default 5)"},
)
def gmail_unread(max_results: int = 5) -> str:
    svc, err = _service("gmail", "v1")
    if err:
        return err
    try:
        res = svc.users().messages().list(
            userId="me", q="is:unread", maxResults=int(max_results)).execute()
        msgs = res.get("messages", [])
        if not msgs:
            return "No unread emails. Inbox zero, sir."
        out = []
        for m in msgs:
            full = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject"]).execute()
            hdrs = {h["name"]: h["value"] for h in full["payload"]["headers"]}
            out.append(f"- {hdrs.get('From','?')}\n  {hdrs.get('Subject','(no subject)')}")
        return "Unread email:\n" + "\n".join(out)
    except Exception as e:
        return f"Couldn't read Gmail: {e}"


@tool(
    "gmail_send",
    "Send an email on the user's behalf.",
    {"to": "recipient address", "subject": "subject line", "body": "message body"},
)
def gmail_send(to: str, subject: str, body: str) -> str:
    svc, err = _service("gmail", "v1")
    if err:
        return err
    try:
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email sent to {to}."
    except Exception as e:
        return f"Couldn't send email: {e}"


# ------------------------------ Calendar ----------------------------

@tool(
    "calendar_upcoming",
    "List the user's upcoming calendar events.",
    {"max_results": "how many events (default 5)"},
)
def calendar_upcoming(max_results: int = 5) -> str:
    from datetime import datetime, timezone
    svc, err = _service("calendar", "v3")
    if err:
        return err
    try:
        now = datetime.now(timezone.utc).isoformat()
        res = svc.events().list(
            calendarId="primary", timeMin=now, maxResults=int(max_results),
            singleEvents=True, orderBy="startTime").execute()
        events = res.get("items", [])
        if not events:
            return "Nothing on your calendar coming up."
        out = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date"))
            out.append(f"- {start}: {e.get('summary','(no title)')}")
        return "Upcoming events:\n" + "\n".join(out)
    except Exception as e:
        return f"Couldn't read calendar: {e}"


@tool(
    "calendar_add",
    "Add an event to the user's calendar.",
    {"title": "event title",
     "start": "ISO start time, e.g. 2026-07-05T15:00:00",
     "end": "ISO end time (optional; defaults to 1h after start)"},
)
def calendar_add(title: str, start: str, end: str = "") -> str:
    from datetime import datetime, timedelta
    svc, err = _service("calendar", "v3")
    if err:
        return err
    try:
        if not end:
            end = (datetime.fromisoformat(start) + timedelta(hours=1)).isoformat()
        body = {
            "summary": title,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }
        ev = svc.events().insert(calendarId="primary", body=body).execute()
        return f"Added '{title}' to your calendar. Link: {ev.get('htmlLink','')}"
    except Exception as e:
        return f"Couldn't add event: {e}"
