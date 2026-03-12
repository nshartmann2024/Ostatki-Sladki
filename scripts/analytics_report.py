"""
Простой отчёт по аналитике из db/app.db.
Запуск из корня проекта: python scripts/analytics_report.py
"""
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "db" / "app.db"


def _counts_since(cur, since_ts: str) -> dict:
    """Вернуть словарь event_type -> count и ключ 'total' для событий с created_at >= since_ts."""
    cur.execute(
        "SELECT event_type, COUNT(*) as cnt FROM analytics_events WHERE created_at >= ? GROUP BY event_type",
        (since_ts,),
    )
    by_type = {r["event_type"]: r["cnt"] for r in cur.fetchall()}
    by_type["total"] = sum(by_type.values())
    return by_type


def _print_period(cur, since_ts: str) -> None:
    c = _counts_since(cur, since_ts)
    total = c.get("total", 0)
    print(f"  всего событий: {total}")
    print(f"  поисков: {c.get('search_submit', 0)}")
    print(f"  клики ингредиентов: {c.get('ingredient_click', 0)}")
    print(f"  открытий рецептов: {c.get('recipe_open', 0)}")
    print(f"  клики telegram: {c.get('telegram_click', 0)}")


def main():
    if not DB_PATH.is_file():
        print("ERROR: db/app.db not found")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Проверяем наличие таблицы
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analytics_events'")
    if not cur.fetchone():
        print("Table analytics_events not found. Run the app once to create it.")
        conn.close()
        return

    print("=" * 50)
    print("ANALYTICS REPORT (analytics_events)")
    print("=" * 50)

    # АКТИВНОСТЬ ПО ПЕРИОДАМ (created_at в UTC)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day7_start = today_start - timedelta(days=7)
    day30_start = today_start - timedelta(days=30)
    fmt = "%Y-%m-%d %H:%M:%S"

    print("\n--- АКТИВНОСТЬ ПО ПЕРИОДАМ ---")
    print("Сегодня")
    _print_period(cur, today_start.strftime(fmt))
    print("Последние 7 дней")
    _print_period(cur, day7_start.strftime(fmt))
    print("Последние 30 дней")
    _print_period(cur, day30_start.strftime(fmt))

    # Топ 10 поисковых запросов
    cur.execute(
        """SELECT event_value, COUNT(*) as cnt FROM analytics_events
           WHERE event_type = 'search_submit' AND event_value != ''
           GROUP BY event_value ORDER BY cnt DESC LIMIT 10"""
    )
    rows = cur.fetchall()
    print("\n--- Top 10 search queries (search_submit) ---")
    for r in rows:
        print(f"  {r['cnt']:4d}  {r['event_value'][:60]}")

    # Топ 10 быстрых кнопок ингредиентов
    cur.execute(
        """SELECT event_value, COUNT(*) as cnt FROM analytics_events
           WHERE event_type = 'ingredient_click' AND event_value != ''
           GROUP BY event_value ORDER BY cnt DESC LIMIT 10"""
    )
    rows = cur.fetchall()
    print("\n--- Top 10 ingredient buttons (ingredient_click) ---")
    for r in rows:
        print(f"  {r['cnt']:4d}  {r['event_value'][:60]}")

    # Топ 10 открытых рецептов
    cur.execute(
        """SELECT recipe_id, event_value, COUNT(*) as cnt FROM analytics_events
           WHERE event_type = 'recipe_open' AND (recipe_id != '' OR recipe_id IS NOT NULL)
           GROUP BY recipe_id ORDER BY cnt DESC LIMIT 10"""
    )
    rows = cur.fetchall()
    print("\n--- Top 10 opened recipes (recipe_open) ---")
    for r in rows:
        title = (r["event_value"] or "")[:40] if r["event_value"] else ""
        print(f"  {r['cnt']:4d}  {r['recipe_id']}  {title}")

    # Общее число кликов в Telegram
    cur.execute("SELECT COUNT(*) as cnt FROM analytics_events WHERE event_type = 'telegram_click'")
    n = cur.fetchone()["cnt"]
    print("\n--- Telegram link clicks (telegram_click) ---")
    print(f"  Total: {n}")

    # Последние 20 событий
    cur.execute(
        """SELECT id, event_type, event_value, channel, recipe_id, created_at
           FROM analytics_events ORDER BY id DESC LIMIT 20"""
    )
    rows = cur.fetchall()
    print("\n--- Last 20 events ---")
    for r in rows:
        ev = (r["event_value"] or "")[:30]
        rid = r["recipe_id"] or ""
        print(f"  {r['id']:5d}  {r['created_at']}  {r['event_type']:18s}  ch={r['channel']:7s}  val={ev}  recipe_id={rid}")

    conn.close()
    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
