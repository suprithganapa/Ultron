"""
Spotify control tools.

Dormant until you connect Spotify (see INTEGRATIONS.md): set the three
SPOTIPY_* env vars and run `python scripts/spotify_login.py` once. Playback
control requires a Spotify Premium account and an active device.
"""
from __future__ import annotations

import os

from ..config import settings
from . import tool

SPOTIFY_SCOPES = ("user-read-playback-state user-modify-playback-state "
                  "user-read-currently-playing")

_NOT_CONNECTED = (
    "Spotify isn't connected. Follow INTEGRATIONS.md: set SPOTIPY_CLIENT_ID, "
    "SPOTIPY_CLIENT_SECRET and SPOTIPY_REDIRECT_URI, then run "
    "`python scripts/spotify_login.py` once."
)


def _client():
    """Return (spotipy client, error)."""
    if not os.getenv("SPOTIPY_CLIENT_ID"):
        return None, _NOT_CONNECTED
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        auth = SpotifyOAuth(
            scope=SPOTIFY_SCOPES,
            cache_path=str(settings.data_dir / ".spotify_cache"),
            open_browser=False,
        )
        return spotipy.Spotify(auth_manager=auth), None
    except ModuleNotFoundError:
        return None, "spotipy isn't installed. Run `pip install -r requirements.txt`."
    except Exception as e:
        return None, f"Spotify auth error: {e}"


@tool("spotify_now_playing", "Show what's currently playing on Spotify.", {})
def spotify_now_playing() -> str:
    sp, err = _client()
    if err:
        return err
    try:
        cur = sp.current_playback()
        if not cur or not cur.get("item"):
            return "Nothing is playing right now."
        it = cur["item"]
        artists = ", ".join(a["name"] for a in it["artists"])
        state = "playing" if cur.get("is_playing") else "paused"
        return f"Now {state}: {it['name']} — {artists}"
    except Exception as e:
        return f"Couldn't reach Spotify: {e}"


@tool(
    "spotify_play",
    "Play a song/artist by search, or resume playback if no query is given.",
    {"query": "what to play, e.g. 'Blinding Lights' (optional)"},
)
def spotify_play(query: str = "") -> str:
    sp, err = _client()
    if err:
        return err
    try:
        if query:
            res = sp.search(q=query, type="track", limit=1)
            items = res["tracks"]["items"]
            if not items:
                return f"Couldn't find '{query}' on Spotify."
            track = items[0]
            sp.start_playback(uris=[track["uri"]])
            artists = ", ".join(a["name"] for a in track["artists"])
            return f"Playing {track['name']} — {artists}"
        sp.start_playback()
        return "Resumed playback."
    except Exception as e:
        return f"Couldn't start playback: {e} (need Premium + an active device)."


@tool("spotify_pause", "Pause Spotify playback.", {})
def spotify_pause() -> str:
    sp, err = _client()
    if err:
        return err
    try:
        sp.pause_playback()
        return "Paused."
    except Exception as e:
        return f"Couldn't pause: {e}"


@tool("spotify_next", "Skip to the next track on Spotify.", {})
def spotify_next() -> str:
    sp, err = _client()
    if err:
        return err
    try:
        sp.next_track()
        return "Skipped to the next track."
    except Exception as e:
        return f"Couldn't skip: {e}"
