# Connecting ULTRON to Gmail, Calendar & Spotify

These make ULTRON feel like JARVIS — it can read/send your email, manage your
calendar, and control your music. Each needs a one-time setup because you're
granting access to *your* private accounts.

> Do these **after** you've deployed (Step 2 in DEPLOY.md), because some redirect
> URLs need your live address. You can also set them up locally first to test.

---

## Gmail + Google Calendar

1. Go to **https://console.cloud.google.com** and create a project (free).
2. In **APIs & Services → Library**, enable **Gmail API** and **Google
   Calendar API**.
3. In **APIs & Services → OAuth consent screen**, choose **External**, add your
   own email as a **Test user**.
4. In **APIs & Services → Credentials → Create Credentials → OAuth client ID**,
   choose **Desktop app**. Download the JSON and save it as **`credentials.json`**
   in the ULTRON project root.
5. Connect it (one time):

   ```bash
   python scripts/google_login.py
   ```

   A browser opens; approve access. A token is saved to `data/google_token.json`.

Now try: *"any unread emails?"*, *"what's on my calendar?"*, *"email
alex@example.com that I'll be 10 minutes late"*, *"add lunch with Sam tomorrow
at 1pm"*.

**For the cloud deployment**, copy the contents of your local
`data/google_token.json` into a Render environment variable, or re-run the
connect step against the deployed instance. (Simplest: keep Gmail/Calendar on
your local ULTRON, where the token already lives.)

---

## Spotify

1. Go to **https://developer.spotify.com/dashboard** and create an app (free).
2. In the app settings, add a **Redirect URI**:
   `http://127.0.0.1:8888/callback`
3. Copy the **Client ID** and **Client Secret** into your `.env`:

   ```
   SPOTIPY_CLIENT_ID=your_client_id
   SPOTIPY_CLIENT_SECRET=your_client_secret
   SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
   ```

4. Connect it (one time):

   ```bash
   python scripts/spotify_login.py
   ```

Now try: *"what's playing?"*, *"play Blinding Lights"*, *"pause"*, *"next
track"*. Playback control needs a **Spotify Premium** account and an active
device (the app open somewhere).

---

## How ULTRON handles these safely

- If an integration isn't connected, its tools simply reply "not connected"
  instead of erroring — ULTRON always boots.
- Tokens live in your `data/` folder (gitignored) or environment variables,
  never in the code or repo.
- You can connect only the ones you want.
