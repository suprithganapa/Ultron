#!/usr/bin/env python3
"""
One-time Spotify connection for ULTRON.

Prerequisite: create a Spotify app at developer.spotify.com and set these
environment variables (in .env) before running — see INTEGRATIONS.md:

    SPOTIPY_CLIENT_ID=...
    SPOTIPY_CLIENT_SECRET=...
    SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback

Run once:

    python scripts/spotify_login.py

Approve access in the browser; a token cache is saved so ULTRON can control
playback (Premium account required for play/pause/skip).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import settings  # noqa: E402
from backend.tools.spotify_tools import SPOTIFY_SCOPES  # noqa: E402


def main() -> None:
    import os
    if not os.getenv("SPOTIPY_CLIENT_ID"):
        print("ERROR: SPOTIPY_CLIENT_ID / SECRET / REDIRECT_URI not set in .env.")
        print("See INTEGRATIONS.md.")
        sys.exit(1)

    import spotipy
    from spotipy.oauth2 import SpotifyOAuth

    auth = SpotifyOAuth(
        scope=SPOTIFY_SCOPES,
        cache_path=str(settings.data_dir / ".spotify_cache"),
    )
    sp = spotipy.Spotify(auth_manager=auth)
    me = sp.current_user()
    print(f"\nConnected as {me['display_name']}. ULTRON can now control Spotify.")


if __name__ == "__main__":
    main()
