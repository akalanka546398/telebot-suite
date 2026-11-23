# Telegram Bot + Admin Dashboard (starter project)

A small, opt-in Telegram bot plus an admin dashboard, built around three
things: broadcasting to subscribers, a support inbox, and basic analytics.
Everyone in it chose to be there — the bot only messages people who sent it
`/start`, and support tickets only exist for people who messaged you first.

## What's included

- **bot.py** — the Telegram bot itself (aiogram 3). Handles `/start`,
  `/stop`, forwards user messages into a support inbox, sends scheduled
  broadcasts, and delivers admin replies typed in the dashboard.
- **dashboard.py** — a small FastAPI web app: subscriber analytics, a
  broadcast composer (send now or schedule), and a support ticket inbox.
- **database.py** — SQLite schema + helpers, shared by both processes.
- **templates/** — the dashboard's HTML pages.

## Setup

1. **Get a bot token.** Message [@BotFather](https://t.me/BotFather) on
   Telegram, run `/newbot`, and copy the token it gives you.

2. **Get your own numeric Telegram ID** (so the bot can notify you of new
   support messages). Message [@userinfobot](https://t.me/userinfobot) and
   it will reply with your ID.

3. **Install dependencies** (Python 3.11+ recommended):

   ```bash
   cd telebot_suite
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Set environment variables:**

   ```bash
   export BOT_TOKEN="123456:ABC-your-token-here"
   export ADMIN_CHAT_ID="123456789"
   ```

5. **Run both processes** (two terminals, or two systemd services / Docker
   containers in production):

   ```bash
   # Terminal 1 — the bot
   python bot.py

   # Terminal 2 — the dashboard
   uvicorn dashboard:app --host 0.0.0.0 --port 8000
   ```

6. Open `http://localhost:8000` for the dashboard. Message your bot on
   Telegram and send `/start` to subscribe as a test subscriber.

## Important before going further

- **Add authentication to the dashboard.** As shipped it has none — anyone
  who can reach the port can send broadcasts and read support messages. Put
  it behind a login (e.g. `fastapi-login`), a reverse proxy with basic auth,
  or a VPN/tailnet before exposing it beyond localhost.
- **Respect Telegram's Bot API terms.** This bot only messages users who
  explicitly subscribed via `/start`, and `BROADCAST_RATE_PER_SEC` is set
  conservatively — raise it with caution.
- **Back up `data.db` regularly** — it's the only copy of your subscriber
  list and support history.

## Extending it

- Add media (photos/documents) to broadcasts: `bot.send_photo(...)` etc. in
  `bot.py`, and a file upload field in `compose.html`.
- Add a simple chart to analytics using Chart.js in `index.html`, fed by a
  new `/api/stats` JSON endpoint.
- Swap SQLite for Postgres if you outgrow a single file — only
  `database.py` would need to change.
