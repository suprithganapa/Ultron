# Deploying ULTRON publicly (always-on, secure)

This gets ULTRON running on the internet with **HTTPS**, a **login wall**, and
**durable memory** (a real database, so it never forgets across restarts).
We'll use **Render** because it's free, gives you HTTPS automatically, and can
provision a free Postgres database in the same step.

> **Important — cloud vs local.** In the cloud, ULTRON runs on a rented server,
> so it can't touch *your* PC's files. That's why `PUBLIC_MODE=true` disables
> the shell/code tools. The cloud version is your always-available brain for
> chat, web search, notes/tasks/reminders, images, memory, and (once set up)
> Gmail/Calendar/Spotify. Keep running it locally too when you want it to
> control your own computer.

---

## Step 1 — Put ULTRON on GitHub

```bash
cd Ultron
git init
git add .
git commit -m "ULTRON: personal AI assistant"
git branch -M main
git remote add origin https://github.com/<your-username>/ultron.git
git push -u origin main
```

`.env` is gitignored, so your secrets never leave your machine. Good.

---

## Step 2 — Deploy on Render

1. Create a free account at **https://render.com** and connect your GitHub.
2. Click **New → Blueprint**, choose your `ultron` repo. Render reads
   `render.yaml` and sets up **two things**: the web service *and* a free
   Postgres database (durable memory), wired together automatically.
3. When prompted, fill in the secret values (these are kept out of git):
   - `ULTRON_PASSWORD` — the password you'll log in with. Make it strong.
   - `GROQ_API_KEY` — your Groq key (the brain).
   - `GEMINI_API_KEY` — enables image/vision.
   - `TAVILY_API_KEY` — better web search (optional).
4. Click **Apply**. First build takes a few minutes.
5. You'll get a URL like `https://ultron.onrender.com`. Open it, enter your
   password, and ULTRON is live — from any device, anywhere.

`ULTRON_SECRET` (token signing) and `DATABASE_URL` (Postgres) are set
automatically by the blueprint. You don't touch them.

---

## Step 3 — Lock it down (recommended)

- Set `CORS_ORIGINS` to your exact URL (e.g. `https://ultron.onrender.com`)
  in the Render dashboard, instead of `*`.
- Use a long, unique `ULTRON_PASSWORD`.
- Keep `PUBLIC_MODE=true` in the cloud (it's already set by the blueprint).
- Rotate any API key that has ever been shared in plaintext.

---

## Notes on the free tier

- Render's free web service **sleeps after ~15 minutes idle** and wakes on the
  next request (first hit takes a few seconds). Your **memory is safe** — it
  lives in Postgres, not on the web server, so nothing is lost when it sleeps.
- To keep it always warm, upgrade the service to a paid instance, or ping it
  periodically with a free uptime monitor (e.g. UptimeRobot).

---

## Alternative hosts

The same Docker image runs anywhere. On **Railway** or **Fly.io**, create a
Postgres add-on, then set the same environment variables (`DATABASE_URL`,
`PUBLIC_MODE=true`, `ULTRON_PASSWORD`, `ULTRON_SECRET`, and your API keys).
The `Dockerfile` is all they need to build.
