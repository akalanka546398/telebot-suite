"""
The bot process. Run this with:

    python bot.py

Responsibilities:
  - /start  -> subscribes the user (opt-in), sends a welcome message
  - /stop   -> unsubscribes the user
  - any other text from a regular user -> logged as a support ticket message
    and forwarded to you (ADMIN_CHAT_ID) so you can see it in Telegram too
  - a background loop every POLL_INTERVAL_SECONDS:
      * sends any broadcasts that are due (created from the dashboard)
      * delivers any admin replies typed in the dashboard's support inbox
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

import config
import database as db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def on_start(message: Message):
    db.add_subscriber(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(
        "You're subscribed! You'll get updates here.\n"
        "Send /stop at any time to unsubscribe.\n"
        "You can also just type a message here if you need help — a real person will reply."
    )


@dp.message(Command("stop"))
async def on_stop(message: Message):
    db.remove_subscriber(message.from_user.id)
    await message.answer("You've been unsubscribed. Send /start to subscribe again anytime.")


@dp.message(F.text)
async def on_user_message(message: Message):
    """Any other text message is treated as a support request."""
    if message.from_user.id == config.ADMIN_CHAT_ID:
        return  # ignore the admin's own messages to the bot
    ticket_id = db.get_or_create_open_ticket(message.from_user.id)
    db.add_ticket_message(ticket_id, "user", message.text)
    await message.answer("Thanks — we've got your message and will reply here soon.")

    if config.ADMIN_CHAT_ID:
        who = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        try:
            await bot.send_message(
                config.ADMIN_CHAT_ID,
                f"New support message (ticket #{ticket_id}) from {who}:\n\n{message.text}\n\n"
                f"Reply from the dashboard's Support tab.",
            )
        except Exception as e:
            log.warning("Could not notify admin: %s", e)


async def send_broadcast(broadcast):
    subscriber_ids = db.active_subscriber_ids()
    sent, failed = 0, 0
    delay = 1.0 / max(config.BROADCAST_RATE_PER_SEC, 1)
    for user_id in subscriber_ids:
        try:
            await bot.send_message(user_id, broadcast["text"])
            sent += 1
        except TelegramForbiddenError:
            # user blocked the bot -> quietly unsubscribe them
            db.remove_subscriber(user_id)
            failed += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except Exception as e:
            log.warning("Failed to send to %s: %s", user_id, e)
            failed += 1
        await asyncio.sleep(delay)
    db.finish_broadcast(broadcast["id"], sent, failed)
    log.info("Broadcast #%s done: %s sent, %s failed", broadcast["id"], sent, failed)


async def background_loop():
    while True:
        try:
            for broadcast in db.due_broadcasts():
                db.mark_broadcast_sending(broadcast["id"])
                await send_broadcast(broadcast)

            for reply in db.pending_admin_replies():
                try:
                    await bot.send_message(reply["user_id"], reply["text"])
                except Exception as e:
                    log.warning("Could not deliver admin reply %s: %s", reply["message_id"], e)
                db.mark_delivered(reply["message_id"])
        except Exception as e:
            log.exception("Background loop error: %s", e)
        await asyncio.sleep(config.POLL_INTERVAL_SECONDS)


async def main():
    if not config.BOT_TOKEN:
        raise SystemExit("Set the BOT_TOKEN environment variable first (get one from @BotFather).")
    db.init_db()
    asyncio.create_task(background_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
