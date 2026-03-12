"""
Добавляет недостающие теги в must_have_json на основе текста рецептов (макс. 8 тегов на рецепт).
Приоритет: ингредиенты из названия → базовые продукты → овощи.
Запуск из корня: python scripts/apply_must_have_updates.py
"""
import json
import os
import re
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "db", "app.db")
CANONICAL_PATH = os.path.join(ROOT, "data", "ingredients_canonical.json")
MAX_TAGS = 8

# Базовые продукты — не добавлять в must_have как поисковые теги
BASIC_EXCLUDE = {
    "масло", "молоко", "яйцо", "лук", "чеснок", "мука", "сахар", "соль",
    "перец", "вода", "сливки", "сметана", "йогурт",
}

# Порядок приоритета при добавлении тегов (только «поисковые» ингредиенты)
BASE_PRODUCTS = {"хлеб", "сыр", "картофель", "мясо", "грибы", "творог", "рис", "ветчина", "колбаса", "фасоль", "капуста", "шоколад", "яблоко"}
VEGGIES = {"морковь", "кабачок", "томаты", "брокколи", "огурец"}


def load_canonical_and_aliases():
    with open(CANONICAL_PATH, encoding="utf-8") as f:
        data = json.load(f)
    canonical_list = set(data.get("canonical", []))
    aliases = data.get("aliases", {})
    canonical_to_terms = {}
    for c in canonical_list:
        terms = [c]
        for alias, target in aliases.items():
            if target == c:
                terms.append(alias)
        canonical_to_terms[c] = terms
    return canonical_list, canonical_to_terms


def recipe_text_lower(r):
    parts = [
        r.get("title_ru") or "",
        r.get("title_de") or "",
        r.get("short_desc") or "",
        r.get("notes") or "",
    ]
    for key in ("ingredients_json", "steps_json"):
        raw = r.get(key)
        if isinstance(raw, str):
            raw = json.loads(raw) if raw else []
        if isinstance(raw, list):
            parts.extend(str(x) for x in raw)
    return " ".join(parts).lower()


def title_text_lower(r):
    return ((r.get("title_ru") or "") + " " + (r.get("title_de") or "")).lower()


def choose_tags_to_add(missing, title_text, canonical_to_terms, max_add):
    """Выбрать до max_add тегов из missing: из названия → база → овощи → остальное."""
    if max_add <= 0:
        return []
    order = []
    in_title = []
    for c in missing:
        for term in canonical_to_terms.get(c, [c]):
            if term.lower() in title_text:
                in_title.append(c)
                break
    in_base = [c for c in missing if c in BASE_PRODUCTS and c not in in_title]
    in_veggies = [c for c in missing if c in VEGGIES and c not in in_title and c not in in_base]
    rest = [c for c in missing if c not in in_title and c not in in_base and c not in in_veggies]
    for c in in_title:
        if c not in order:
            order.append(c)
    for c in in_base:
        if c not in order:
            order.append(c)
    for c in in_veggies:
        if c not in order:
            order.append(c)
    for c in rest:
        if c not in order:
            order.append(c)
    return order[:max_add]


def main():
    if not os.path.isfile(DB_PATH):
        print(f"DB not found: {DB_PATH}")
        return
    canonical_list, canonical_to_terms = load_canonical_and_aliases()
    keys_to_check = list(canonical_list)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT id, title_ru, title_de, short_desc, ingredients_json, steps_json, notes, must_have_json FROM recipes"
    )
    rows = [dict(r) for r in cur.fetchall()]

    updates = []
    total_added = 0
    for r in rows:
        text = recipe_text_lower(r)
        title_text = title_text_lower(r)
        must_have_raw = r.get("must_have_json")
        must_have = list(json.loads(must_have_raw)) if must_have_raw else []
        mentioned = set()
        for c in keys_to_check:
            for term in canonical_to_terms.get(c, [c]):
                if term.lower() in text:
                    mentioned.add(c)
                    break
        missing = (mentioned - set(must_have)) - BASIC_EXCLUDE
        if not missing or len(must_have) >= MAX_TAGS:
            continue
        max_add = MAX_TAGS - len(must_have)
        to_add = choose_tags_to_add(list(missing), title_text, canonical_to_terms, max_add)
        if not to_add:
            continue
        new_must_have = must_have + to_add
        new_must_have = new_must_have[:MAX_TAGS]
        updates.append((r["id"], json.dumps(new_must_have, ensure_ascii=False), len(to_add)))
        total_added += len(to_add)

    for recipe_id, new_json, n in updates:
        conn.execute("UPDATE recipes SET must_have_json = ? WHERE id = ?", (new_json, recipe_id))
    conn.commit()
    conn.close()

    print(f"Updated recipes: {len(updates)}")
    print(f"Tags added total: {total_added}")
    for recipe_id, new_json, n in updates:
        print(f"  {recipe_id}: +{n}")
    return len(updates), total_added


if __name__ == "__main__":
    main()
