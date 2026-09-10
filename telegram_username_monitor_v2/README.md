# Telegram Username Monitor

Мониторинг username без покупок.

Проверка выполняется напрямую через Telegram MTProto `account.checkUsername`,
а не через строку поиска Telegram и не через scraping Fragment. Telegram
официально описывает этот метод как проверку доступности username; среди
ошибок есть `USERNAME_OCCUPIED`, `USERNAME_INVALID` и
`USERNAME_PURCHASE_AVAILABLE` (последнее означает покупку через Fragment).

## Уведомления

По умолчанию:

- 🟢 обычный свободный username — уведомление ВКЛ;
- 💎 Fragment username — уведомление ВЫКЛ.

Управление:

```text
/settings
```

и inline-кнопкой `💎 Fragment: ВКЛ/ВЫКЛ`.

Если Fragment выключен, такие username всё равно классифицируются как
`fragment`, но уведомление не отправляется.

## Команды

```text
/add username
/add name1 name2 name3
/remove username
/list
/status
/check username
/settings
/help
```

## Railway

Подходит для Railway как long-running Service.

Добавьте Persistent Volume с Mount Path:

```text
/data
```

Variables:

```text
API_ID=...
API_HASH=...
BOT_TOKEN=...
ADMIN_CHAT_ID=...
SESSION_STRING=...
CHECK_INTERVAL=5
CHECK_DELAY=0.35
DATA_DIR=/data
SESSION_NAME=telegram_username_monitor
```

Start Command:

```text
python main.py
```

`/data/usernames.sqlite3` хранит watchlist и настройки, поэтому они
переживают restart/redeploy при подключенном Volume.

Для Railway лучше один раз получить Telethon `SESSION_STRING` локально,
затем сохранить его как Railway Variable. Не публикуйте SESSION_STRING,
API_HASH или BOT_TOKEN.

Не запускайте несколько replicas с одной MTProto-сессией.

## Local

```bash
pip install -r requirements.txt
python main.py
```

При первом запуске без `SESSION_STRING` Telethon попросит авторизацию.
