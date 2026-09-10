import asyncio
import logging
import re

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
    UsernameOccupiedError,
    UsernamePurchaseAvailableError,
)
from telethon.tl.functions.account import CheckUsernameRequest

log = logging.getLogger("monitor")

# Telegram account.checkUsername accepts 5-32 chars.
USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$")


class UsernameMonitor:
    def __init__(self, client: TelegramClient, db, notify, interval: float, delay: float):
        self.client = client
        self.db = db
        self.notify = notify
        self.interval = interval
        self.delay = delay

    @staticmethod
    def normalize(raw):
        return raw.strip().strip("`").lstrip("@").lower()

    @classmethod
    def valid(cls, username):
        return bool(USERNAME_RE.fullmatch(username))

    async def check(self, username):
        try:
            result = await self.client(
                CheckUsernameRequest(username=username)
            )

            # True means Telegram accepted the username as available
            # for normal username assignment.
            if bool(result):
                return "available"

            return "unknown"

        except UsernameNotOccupiedError:
            # Kept for compatibility with clients/layers that surface
            # the older error form.
            return "available"

        except UsernameOccupiedError:
            return "occupied"

        except UsernamePurchaseAvailableError:
            return "fragment"

        except UsernameInvalidError:
            return "invalid"

        except FloodWaitError as e:
            log.warning("FloodWait: sleeping %s seconds", e.seconds)
            await asyncio.sleep(e.seconds)
            return None

        except Exception as e:
            # Some Telegram layers expose RPC errors by name.
            name = getattr(e, "rpc_error", None)
            rpc_name = getattr(name, "error_message", None) or getattr(e, "message", "")
            rpc_name = str(rpc_name).upper()

            if "USERNAME_PURCHASE_AVAILABLE" in rpc_name:
                return "fragment"
            if "USERNAME_OCCUPIED" in rpc_name:
                return "occupied"
            if "USERNAME_INVALID" in rpc_name:
                return "invalid"

            log.exception("Failed to check @%s", username)
            return None

    async def check_one_and_notify(self, username):
        old = self.db.get(username)
        if not old:
            return None

        new = await self.check(username)
        if new is None:
            return None

        old_status = old["status"]
        self.db.update_status(username, new)

        # Do not alert on initial state.
        if old_status == "unknown":
            return new

        # Normal free username.
        if old_status != "available" and new == "available":
            await self.notify(username, "available")

        # Fragment collectible. Notification can be disabled globally.
        if (
            old_status != "fragment"
            and new == "fragment"
            and self.db.fragment_alerts_enabled()
        ):
            await self.notify(username, "fragment")

        return new

    async def run(self):
        log.info(
            "Monitor started: interval=%ss delay=%ss fragment_alerts=%s",
            self.interval,
            self.delay,
            self.db.fragment_alerts_enabled(),
        )

        while True:
            rows = self.db.all()

            for row in rows:
                try:
                    await self.check_one_and_notify(row["username"])
                except Exception:
                    log.exception("Unhandled error for @%s", row["username"])

                await asyncio.sleep(self.delay)

            await asyncio.sleep(self.interval)
