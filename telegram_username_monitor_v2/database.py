import sqlite3
from pathlib import Path
from datetime import datetime, timezone

class Database:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS usernames (
                    username TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'unknown',
                    last_checked TEXT,
                    last_change TEXT
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            db.execute("""
                INSERT OR IGNORE INTO settings(key, value)
                VALUES ('fragment_alerts', '0')
            """)
            db.commit()

    def add_many(self, usernames):
        now = datetime.now(timezone.utc).isoformat()
        added, existing = [], []
        with self._connect() as db:
            for username in usernames:
                cur = db.execute(
                    "SELECT 1 FROM usernames WHERE username = ?", (username,)
                )
                if cur.fetchone():
                    existing.append(username)
                else:
                    db.execute(
                        """INSERT INTO usernames
                        (username, status, last_checked, last_change)
                        VALUES (?, 'unknown', ?, ?)""",
                        (username, now, now)
                    )
                    added.append(username)
            db.commit()
        return added, existing

    def remove(self, username):
        with self._connect() as db:
            cur = db.execute("DELETE FROM usernames WHERE username = ?", (username,))
            db.commit()
            return cur.rowcount > 0

    def all(self):
        with self._connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT * FROM usernames ORDER BY username"
            ).fetchall()]

    def get(self, username):
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM usernames WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def update_status(self, username, status):
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute(
                """UPDATE usernames
                SET status = ?, last_checked = ?, last_change = ?
                WHERE username = ?""",
                (status, now, now, username)
            )
            db.commit()

    def get_setting(self, key, default=None):
        with self._connect() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_setting(self, key, value):
        with self._connect() as db:
            db.execute(
                """INSERT INTO settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (key, str(value))
            )
            db.commit()

    def fragment_alerts_enabled(self):
        return self.get_setting("fragment_alerts", "0") == "1"

    def set_fragment_alerts(self, enabled: bool):
        self.set_setting("fragment_alerts", "1" if enabled else "0")

    def stats(self):
        rows = self.all()
        return {
            "total": len(rows),
            "occupied": sum(r["status"] == "occupied" for r in rows),
            "available": sum(r["status"] == "available" for r in rows),
            "fragment": sum(r["status"] == "fragment" for r in rows),
            "invalid": sum(r["status"] == "invalid" for r in rows),
            "unknown": sum(r["status"] == "unknown" for r in rows),
        }
