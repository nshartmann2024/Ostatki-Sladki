"""
Аудит поиска по must_have_json для ключевых ингредиентов.
Запуск из корня проекта: python scripts/audit_must_have.py
"""
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "db", "app.db")

KEYS = ["яблоко", "шоколад", "сыр", "грибы"]


def _search_in_text(text, key):
    if not text:
        return False
    if isinstance(text, list):
        text = " ".join(str(x) for x in text)
    return key.lower() in (text or "").lower()


def main():
    if not os.path.isfile(DB_PATH):
        print(f"DB not found: {DB_PATH}")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT id, title_de, title_ru, short_desc, ingredients_json, steps_json, notes, must_have_json FROM recipes"
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    for key in KEYS:
        print(f"\n=== {key.upper()} ===")
        in_text = []
        in_must_have = []
        for r in rows:
            title_ru = r.get("title_ru") or ""
            title_de = r.get("title_de") or ""
            short_desc = r.get("short_desc") or ""
            ingredients = r.get("ingredients_json")
            if isinstance(ingredients, str):
                ingredients = json.loads(ingredients) if ingredients else []
            steps = r.get("steps_json")
            if isinstance(steps, str):
                steps = json.loads(steps) if steps else []
            notes = r.get("notes") or ""
            full_text = " ".join([title_ru, title_de, short_desc, notes] + (ingredients or []) + (steps or []))
            if _search_in_text(full_text, key):
                in_text.append((r["id"], r["title_ru"]))
            must_have = r.get("must_have_json")
            if isinstance(must_have, str):
                must_have = json.loads(must_have) if must_have else []
            if key in (must_have or []):
                in_must_have.append((r["id"], r["title_ru"]))
        print(f"  a) В тексте (title/desc/ingredients/steps/notes): {[t[0] for t in in_text]}")
        for rid, title in in_text:
            print(f"     - {rid}: {title}")
        print(f"  b) По must_have_json матчатся: {[t[0] for t in in_must_have]}")
        for rid, title in in_must_have:
            print(f"     - {rid}: {title}")
        need_tag = [t for t in in_text if t[0] not in [m[0] for m in in_must_have]]
        print(f"  c) Нужно добавить тег: {[t[0] for t in need_tag]}")
        for rid, title in need_tag:
            print(f"     - {rid}: {title}")
    print()


if __name__ == "__main__":
    main()
