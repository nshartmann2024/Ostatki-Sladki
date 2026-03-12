"""
Инициализация БД и импорт рецептов для MVP «Остатки Сладки».
"""
import json
import os
import sqlite3

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "app.db")
SCHEMA_PATH = os.path.join(SCRIPT_DIR, "schema.sql")
RECIPES_PATH = os.path.join(SCRIPT_DIR, "..", "data", "recipes_seed_min.json")


def _list_to_json(r, primary_key, fallback_key):
    raw = r.get(primary_key)
    if raw is None:
        raw = r.get(fallback_key)
    if not isinstance(raw, list):
        raw = []
    return json.dumps(raw, ensure_ascii=False)


def main():
    with sqlite3.connect(DB_PATH) as conn:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())

        with open(RECIPES_PATH, encoding="utf-8") as f:
            data = json.load(f)

        recipes = data["recipes"]
        cursor = conn.cursor()
        for r in recipes:
            ingredients_json = _list_to_json(r, "ingredients_json", "ingredients")
            steps_json = _list_to_json(r, "steps_json", "steps")
            must_have_json = _list_to_json(r, "must_have_json", "must_have")
            all_ingredients_json = _list_to_json(r, "all_ingredients_json", "all_ingredients")
            cursor.execute(
                """
                INSERT OR REPLACE INTO recipes (
                    id, title_de, title_ru, is_classic, category, time_min, difficulty,
                    format_type, short_desc, ingredients_json, steps_json, notes, storage_tip,
                    must_have_json, all_ingredients_json, photo_url, photo_file_id_tg
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r.get("id"),
                    r.get("title_de"),
                    r.get("title_ru"),
                    1 if r.get("is_classic") else 0,
                    r.get("category"),
                    r.get("time_min"),
                    r.get("difficulty"),
                    r.get("format_type"),
                    r.get("short_desc"),
                    ingredients_json,
                    steps_json,
                    r.get("notes"),
                    r.get("storage_tip"),
                    must_have_json,
                    all_ingredients_json,
                    r.get("photo_url"),
                    r.get("photo_file_id_tg"),
                ),
            )

        n = len(recipes)
        first_three_ids = [r["id"] for r in recipes[:3]]

        cursor.execute("SELECT id, must_have_json FROM recipes")
        check_rows = cursor.fetchmany(3)

    print("Imported recipes:", n)
    for rid in first_three_ids:
        print(rid)
    for row in check_rows:
        print(row[0], row[1])


if __name__ == "__main__":
    main()
