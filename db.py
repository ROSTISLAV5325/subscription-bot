import sqlite3
from datetime import datetime, timedelta

DB_PATH = "club.db"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def init_db():
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                full_name  TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id    INTEGER PRIMARY KEY,
                expires_at TEXT NOT NULL,
                active     INTEGER NOT NULL DEFAULT 1,
                reminded_3 INTEGER NOT NULL DEFAULT 0,
                reminded_1 INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                tariff_key      TEXT NOT NULL,
                method          TEXT NOT NULL,      -- 'stars', 'card' або 'manual'
                amount_uah      INTEGER DEFAULT 0,
                stars           INTEGER DEFAULT 0,
                status          TEXT NOT NULL,      -- 'pending', 'approved', 'rejected', 'refunded'
                charge_id       TEXT,               -- ID платежу Telegram Stars (для повернення)
                receipt_file_id TEXT,               -- фото/файл квитанції
                created_at      TEXT NOT NULL
            );
            """
        )


# ---------- Користувачі ----------

def add_user(user_id: int, username: str | None, full_name: str):
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, full_name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username,
                                               full_name = excluded.full_name
            """,
            (user_id, username, full_name, _now()),
        )


def get_user(user_id: int):
    with _conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def all_user_ids() -> list[int]:
    with _conn() as conn:
        return [row["user_id"] for row in conn.execute("SELECT user_id FROM users")]


# ---------- Підписки ----------

def get_subscription(user_id: int):
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
        ).fetchone()


def is_active(user_id: int) -> bool:
    sub = get_subscription(user_id)
    return bool(sub and sub["active"] and datetime.fromisoformat(sub["expires_at"]) > datetime.now())


def activate_subscription(user_id: int, days: int) -> datetime:
    """Додає дні до підписки. Якщо підписка ще діє — продовжує від дати закінчення."""
    now = datetime.now()
    sub = get_subscription(user_id)
    if sub and sub["active"] and datetime.fromisoformat(sub["expires_at"]) > now:
        base = datetime.fromisoformat(sub["expires_at"])
    else:
        base = now
    expires = base + timedelta(days=days)
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO subscriptions (user_id, expires_at, active, reminded_3, reminded_1)
            VALUES (?, ?, 1, 0, 0)
            ON CONFLICT(user_id) DO UPDATE SET expires_at = excluded.expires_at,
                                               active = 1, reminded_3 = 0, reminded_1 = 0
            """,
            (user_id, expires.isoformat(sep=" ", timespec="seconds")),
        )
    return expires


def set_expires(user_id: int, expires: datetime):
    """Для тестів: встановити точну дату закінчення підписки."""
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO subscriptions (user_id, expires_at, active, reminded_3, reminded_1)
            VALUES (?, ?, 1, 0, 0)
            ON CONFLICT(user_id) DO UPDATE SET expires_at = excluded.expires_at,
                                               active = 1, reminded_3 = 0, reminded_1 = 0
            """,
            (user_id, expires.isoformat(sep=" ", timespec="seconds")),
        )


def deactivate_subscription(user_id: int):
    with _conn() as conn:
        conn.execute("UPDATE subscriptions SET active = 0 WHERE user_id = ?", (user_id,))


def mark_reminded(user_id: int, days: int):
    column = "reminded_1" if days == 1 else "reminded_3"
    with _conn() as conn:
        conn.execute(f"UPDATE subscriptions SET {column} = 1 WHERE user_id = ?", (user_id,))


def active_subscriptions():
    with _conn() as conn:
        return conn.execute("SELECT * FROM subscriptions WHERE active = 1").fetchall()


# ---------- Платежі ----------

def create_payment(user_id: int, tariff_key: str, method: str, status: str,
                   amount_uah: int = 0, stars: int = 0,
                   charge_id: str | None = None, receipt_file_id: str | None = None) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO payments (user_id, tariff_key, method, amount_uah, stars,
                                  status, charge_id, receipt_file_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, tariff_key, method, amount_uah, stars, status,
             charge_id, receipt_file_id, _now()),
        )
        return cur.lastrowid


def get_payment(payment_id: int):
    with _conn() as conn:
        return conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()


def set_payment_status(payment_id: int, status: str):
    with _conn() as conn:
        conn.execute("UPDATE payments SET status = ? WHERE id = ?", (status, payment_id))


def pending_payments():
    with _conn() as conn:
        return conn.execute(
            "SELECT * FROM payments WHERE status = 'pending' ORDER BY id"
        ).fetchall()


# ---------- Статистика ----------

def get_stats() -> dict:
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_start = month_start.isoformat(sep=" ", timespec="seconds")
    now = _now()
    with _conn() as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE active = 1 AND expires_at > ?", (now,)
        ).fetchone()[0]
        month = conn.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(amount_uah), 0), COALESCE(SUM(stars), 0)
            FROM payments
            WHERE status = 'approved' AND method != 'manual' AND created_at >= ?
            """,
            (month_start,),
        ).fetchone()
        pending = conn.execute(
            "SELECT COUNT(*) FROM payments WHERE status = 'pending'"
        ).fetchone()[0]
    return {
        "users": users,
        "active": active,
        "month_payments": month[0],
        "month_uah": month[1],
        "month_stars": month[2],
        "pending": pending,
    }
