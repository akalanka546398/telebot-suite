"""
Central configuration. Values are read from environment variables so the
bot token never has to be hard-coded into the source.

Set these before running either process:

    export BOT_TOKEN="123456:ABC-your-bot-token-from-BotFather"
    export ADMIN_CHAT_ID="123456789"      # your personal Telegram user id
    export DB_PATH="./data.db"            # optional, defaults shown below
"""
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0") or 0)
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "data.db"))

# How many broadcast messages to send per second (keep well under Telegram's
# ~30 msgs/sec global limit so you don't trip rate limiting / spam flags).
BROADCAST_RATE_PER_SEC = 20

# How often (seconds) the bot process checks for due broadcasts and pending
# admin replies from the dashboard.
POLL_INTERVAL_SECONDS = 15
