import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

from database import Database
from monitor import UsernameMonitor
from bot import ControlBot

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

CHECK_INTERVAL = float(os.getenv("CHECK_INTERVAL", "5"))
CHECK_DELAY = float(os.getenv("CHECK_DELAY", "0.35"))
SESSION_NAME = os.getenv("SESSION_NAME", "telegram_username_monitor")
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()

async def main():
    db = Database(str(DATA_DIR / "usernames.sqlite3"))

    if SESSION_STRING:
        user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    else:
        user_client = TelegramClient(str(DATA_DIR / SESSION_NAME), API_ID, API_HASH)

    await user_client.start()

    me = await user_client.get_me()
    logging.getLogger("main").info(
        "MTProto session authorized as @%s",
        me.username or me.first_name,
    )

    bot_holder = None

    async def notify(username, kind):
        if bot_holder:
            await bot_holder.notify_available(username, kind)

    monitor = UsernameMonitor(
        client=user_client,
        db=db,
        notify=notify,
        interval=CHECK_INTERVAL,
        delay=CHECK_DELAY,
    )

    bot_holder = ControlBot(
        token=BOT_TOKEN,
        admin_chat_id=ADMIN_CHAT_ID,
        db=db,
        monitor=monitor,
    )

    monitor_task = asyncio.create_task(monitor.run())

    try:
        await bot_holder.run()
    finally:
        monitor_task.cancel()
        await user_client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
