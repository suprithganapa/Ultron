#!/usr/bin/env python3
"""
One-time Google (Gmail + Calendar) connection for ULTRON.

Prerequisite: download your OAuth client file from Google Cloud Console and
save it as `credentials.json` in the project root (see INTEGRATIONS.md).

Run once:

    python scripts/google_login.py

A browser opens, you approve access, and a token is saved to
data/google_token.json. ULTRON's Gmail/Calendar tools then work.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import settings  # noqa: E402
from backend.tools.google_tools import GMAIL_SCOPES  # noqa: E402


def main() -> None:
    creds_file = ROOT / "credentials.json"
    if not creds_file.exists():
        print("ERROR: credentials.json not found in the project root.")
        print("Create OAuth credentials (Desktop app) in Google Cloud Console,")
        print("download the JSON, and save it as credentials.json. See INTEGRATIONS.md.")
        sys.exit(1)

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), GMAIL_SCOPES)
    creds = flow.run_local_server(port=0)

    token_path = settings.data_dir / "google_token.json"
    token_path.write_text(creds.to_json())
    print(f"\nConnected. Token saved to {token_path}")
    print("ULTRON can now read/send Gmail and manage your Calendar.")


if __name__ == "__main__":
    main()
