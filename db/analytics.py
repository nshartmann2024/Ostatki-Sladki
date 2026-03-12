"""
Минимальное логирование событий в SQLite для аналитики.
Не зависит от core; вызывается из adapters (web, telegram).
Отчёт: python scripts/analytics_report.py
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

_DB_DIR = Path(__file__).resolve().parent
_DEFAULT_DB_PATH = _DB_DIR / "app.db"

_ANALYTICS_SQL = """
CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    event_value TEXT,
    channel TEXT NOT NULL,
    recipe_id TEXT,
    created_at TEXT NOT NULL
);
"""


def ensure_analytics_schema(conn: sqlite3.Connection) -> None:
    """Создать таблицу analytics_events, если её нет. Без удаления данных."""
    conn.execute(_ANALYTICS_SQL)


def log_event(
    event_type: str,
    channel: str,
    event_value: str | None = None,
    recipe_id: str | None = None,
    db_path: str | os.PathLike | None = None,
) -> None:
    """
    Записать одно событие в analytics_events.
    При ошибке (нет БД, нет прав) — молча игнорировать, чтобы не ломать приложение.
    """
    path = db_path or _DEFAULT_DB_PATH
    if not os.path.isfile(path):
        return
    try:
        with sqlite3.connect(path) as conn:
            ensure_analytics_schema(conn)
            created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                """
                INSERT INTO analytics_events (event_type, event_value, channel, recipe_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_type or "", (event_value or "")[:500], channel or "", (recipe_id or "")[:200], created_at),
            )
    except Exception:
        pass
