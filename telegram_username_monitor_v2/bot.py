import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

log = logging.getLogger("bot")


class ControlBot:
    def __init__(self, token, admin_chat_id, db, monitor):
        self.bot = Bot(token)
        self.dp = Dispatcher()
        self.admin_chat_id = int(admin_chat_id)
        self.db = db
        self.monitor = monitor

        self.dp.message.register(self.start, Command("start"))
        self.dp.message.register(self.help, Command("help"))
        self.dp.message.register(self.add, Command("add"))
        self.dp.message.register(self.remove, Command("remove"))
        self.dp.message.register(self.list_cmd, Command("list"))
        self.dp.message.register(self.status, Command("status"))
        self.dp.message.register(self.check, Command("check"))
        self.dp.message.register(self.settings, Command("settings"))

        self.dp.callback_query.register(self.settings_callback, F.data.startswith("settings:"))

    def authorized(self, message_or_callback):
        chat = getattr(message_or_callback, "chat", None)
        if chat is None:
            message = getattr(message_or_callback, "message", None)
            chat = getattr(message, "chat", None)
        return bool(chat and chat.id == self.admin_chat_id)

    async def deny(self, message):
        await message.answer("⛔ Нет доступа.")

    def settings_keyboard(self):
        enabled = self.db.fragment_alerts_enabled()
        state = "ВКЛ 🟢" if enabled else "ВЫКЛ 🔴"
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"💎 Fragment: {state}",
                    callback_data="settings:fragment:toggle"
                )],
                [InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="settings:refresh"
                )],
            ]
        )

    def settings_text(self):
        enabled = self.db.fragment_alerts_enabled()
        return (
            "⚙️ <b>Настройки мониторинга</b>\\n\\n"
            "🟢 Свободные username: <b>ВКЛ</b>\\n"
            f"💎 Fragment username: <b>{'ВКЛ' if enabled else 'ВЫКЛ'}</b>\\n\\n"
            "Если Fragment выключен, такие username продолжают "
            "проверяться, но уведомления по ним не отправляются."
        )

    async def start(self, message: Message):
        if not self.authorized(message):
            return await self.deny(message)

        await message.answer(
            "👋 <b>Username Monitor</b>\\n\\n"
            "/add username — добавить\\n"
            "/add name1 name2 name3 — несколько\\n"
            "/remove username — удалить\\n"
            "/list — список\\n"
            "/status — статистика\\n"
            "/check username — проверить сейчас\\n"
            "/settings — настройки\\n"
            "/help — помощь",
            parse_mode="HTML"
        )

    async def help(self, message: Message):
        await self.start(message)

    async def add(self, message: Message):
        if not self.authorized(message):
            return await self.deny(message)

        raw = message.text.partition(" ")[2].strip()
        if not raw:
            return await message.answer(
                "Использование:\\n/add myusername\\n"
                "или\\n/add name1 name2 name3"
            )

        parts = raw.replace(",", " ").split()
        usernames, invalid = [], []

        for item in parts:
            u = self.monitor.normalize(item)
            if self.monitor.valid(u):
                usernames.append(u)
            else:
                invalid.append(item)

        if not usernames:
            return await message.answer("❌ Нет корректных username.")

        added, existing = self.db.add_many(usernames)

        text = []
        if added:
            text.append("✅ Добавлены:\\n" + "\\n".join(f"@{u}" for u in added))
        if existing:
            text.append("ℹ️ Уже были:\\n" + "\\n".join(f"@{u}" for u in existing))
        if invalid:
            text.append("⚠️ Некорректные:\\n" + "\\n".join(invalid))

        await message.answer("\\n\\n".join(text))

    async def remove(self, message: Message):
        if not self.authorized(message):
            return await self.deny(message)

        raw = message.text.partition(" ")[2].strip()
        if not raw:
            return await message.answer("Использование: /remove username")

        u = self.monitor.normalize(raw.split()[0])
        if self.db.remove(u):
            await message.answer(f"🗑 Удалён @{u}")
        else:
            await message.answer(f"Не найден @{u}")

    async def list_cmd(self, message: Message):
        if not self.authorized(message):
            return await self.deny(message)

        rows = self.db.all()
        if not rows:
            return await message.answer("Watchlist пуст.")

        chunks, current = [], "📡 Watchlist:\\n"
        for r in rows:
            line = f"@{r['username']} — {r['status']}\\n"
            if len(current) + len(line) > 3500:
                chunks.append(current)
                current = ""
            current += line

        if current:
            chunks.append(current)

        for chunk in chunks:
            await message.answer(chunk)

    async def status(self, message: Message):
        if not self.authorized(message):
            return await self.deny(message)

        s = self.db.stats()
        fragment_state = "ВКЛ 🟢" if self.db.fragment_alerts_enabled() else "ВЫКЛ 🔴"

        await message.answer(
            "📊 <b>Status</b>\\n\\n"
            f"Всего: {s['total']}\\n"
            f"🔴 Занято: {s['occupied']}\\n"
            f"🟢 Свободно: {s['available']}\\n"
            f"💎 Fragment: {s['fragment']}\\n"
            f"⚪ Unknown: {s['unknown']}\\n"
            f"⚠️ Invalid: {s['invalid']}\\n\\n"
            f"Уведомления Fragment: {fragment_state}",
            parse_mode="HTML"
        )

    async def check(self, message: Message):
        if not self.authorized(message):
            return await self.deny(message)

        raw = message.text.partition(" ")[2].strip()
        if not raw:
            return await message.answer("Использование: /check username")

        u = self.monitor.normalize(raw.split()[0])
        if not self.monitor.valid(u):
            return await message.answer("❌ Некорректный username.")

        if not self.db.get(u):
            self.db.add_many([u])

        result = await self.monitor.check_one_and_notify(u)
        if result is None:
            await message.answer("⚠️ Не удалось получить результат.")
        else:
            await message.answer(f"@{u}: {result}")

    async def settings(self, message: Message):
        if not self.authorized(message):
            return await self.deny(message)

        await message.answer(
            self.settings_text(),
            reply_markup=self.settings_keyboard(),
            parse_mode="HTML"
        )

    async def settings_callback(self, callback: CallbackQuery):
        if not self.authorized(callback):
            await callback.answer("Нет доступа.", show_alert=True)
            return

        if callback.data == "settings:fragment:toggle":
            new_value = not self.db.fragment_alerts_enabled()
            self.db.set_fragment_alerts(new_value)
            await callback.answer(
                "Fragment уведомления " + ("включены" if new_value else "выключены")
            )

        await callback.message.edit_text(
            self.settings_text(),
            reply_markup=self.settings_keyboard(),
            parse_mode="HTML"
        )

    async def notify_available(self, username, kind):
        if kind == "available":
            await self.bot.send_message(
                self.admin_chat_id,
                "🚨 <b>USERNAME СТАЛ СВОБОДЕН!</b>\\n\\n"
                f"@{username}\\n\\n"
                "Можно попробовать занять его в Telegram.",
                parse_mode="HTML"
            )

        elif kind == "fragment":
            await self.bot.send_message(
                self.admin_chat_id,
                "💎 <b>FRAGMENT USERNAME</b>\\n\\n"
                f"@{username}\\n\\n"
                "Telegram сообщает, что username доступен для покупки на Fragment.",
                parse_mode="HTML"
            )

    async def run(self):
        await self.dp.start_polling(self.bot)
