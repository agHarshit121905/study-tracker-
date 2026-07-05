# 📚 Interview Prep Tracker

A personal study tracker for IT/CS interview prep. You log what you studied each
day with a confidence rating; it looks back over your history and tells you what
to focus on **tomorrow, this week, and this month** — prioritising weak and
stale topics and flagging syllabus gaps.

No quizzes. No ML training. Just a self-report log + a spaced-repetition-style
priority formula + a clean UI.

## How it works

- **Log today** — pick a subject/topic, rate your confidence 1–5, add a note.
- **Priority engine** (`engine.py`) — each topic has an "ideal revision interval"
  based on your last confidence (weak = revisit fast, strong = wait longer). A
  topic becomes *due* once enough days pass. Never-logged topics are tracked as
  gaps.
- **My plan** — the app schedules due revisions first, fills remaining slots with
  new topics, and spreads everything across the next day / week / month.
- **Overview** — coverage by subject, confidence spread, stale-topic warnings.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. Your history is saved to a local SQLite file
(`data/study.db`) and **persists** between runs. That's it — for a personal
daily tracker, running locally is the simplest fully-persistent setup.

## Where your data is stored

The study log lives in SQLite. The app picks the backend automatically:

- **Local file** (default) — `data/study.db` via Python's built-in `sqlite3`.
  Persists on your machine; no extra setup.
- **Turso** (hosted SQLite) — used automatically if `TURSO_DATABASE_URL` and
  `TURSO_AUTH_TOKEN` are set. This is what you want for a **persistent
  deployment**, because platforms like Streamlit Community Cloud wipe the local
  disk on every redeploy.

The sidebar shows which backend is active. If you ever had an old
`data/log.json`, it's imported into the database automatically on first run.

## Deploy on Streamlit Community Cloud (free)

Push this folder to a GitHub repo, then at [share.streamlit.io](https://share.streamlit.io)
create a new app pointing at `app.py`. It installs `requirements.txt` for you.

> ⚠️ Streamlit Cloud's disk is ephemeral, so a *local* `study.db` resets on
> redeploy. For your history to survive, add Turso (below).

### Making cloud data persistent with Turso (~5 min, free)

1. Install the CLI and sign up:
   ```bash
   curl -sSfL https://get.tur.so/install.sh | bash
   turso auth signup
   ```
2. Create a database and grab its credentials:
   ```bash
   turso db create interview-tracker
   turso db show interview-tracker --url        # -> TURSO_DATABASE_URL
   turso db tokens create interview-tracker     # -> TURSO_AUTH_TOKEN
   ```
3. In your Streamlit app: **Settings → Secrets**, paste:
   ```toml
   TURSO_DATABASE_URL = "libsql://interview-tracker-<you>.turso.io"
   TURSO_AUTH_TOKEN = "your-token"
   ```
4. Redeploy. The sidebar should now read “☁️ Turso”. Done — data persists.

Locally you can do the same with a `.env`/exported vars, or just leave it on the
local file.

## Customise the syllabus

Edit `data/syllabus.json` — it's just `{ "Subject": ["Topic", ...] }`. Add,
remove, or rename anything; the engine adapts automatically. (There's also a
built-in copy in `engine.py` as a fallback if the file is missing.)

## Optional: AI-written plan

The **✨ Write it up with AI** toggle turns the structured plan into a friendly
summary via Gemini. Set a key first — as an env var locally, or in Streamlit
Secrets when deployed:

```toml
GEMINI_API_KEY = "your-key"
```

Never paste the key into code or chat. Without a key, the app just shows the
rule-based plan.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI |
| `engine.py` | Scoring, plans, and the SQLite/Turso data layer |
| `data/syllabus.json` | Your topic list |
| `data/study.db` | Your study history (auto-created; local mode) |
| `requirements.txt` | Dependencies (Streamlit required; libsql/gemini optional) |
