"""
Очистить must_have_json от базовых ингредиентов (яйцо, масло, мука, соль, перец, сливки, сметана).
Лук/чеснок/молоко — удалять с исключениями (ключевые по названию / молочные десерты).
Запуск из корня: python scripts/cleanup_must_have_base_tags.py
"""
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "db", "app.db")

REMOVE_DEFAULT = [
    "яйцо",
    "масло",
    "мука",
    "соль",
    "перец",
    "сливки",
    "сметана",
]
REMOVE_SET = set(REMOVE_DEFAULT)

# id рецептов, где "молоко" — поисковый тег (банановый крем, кофейный пудинг)
MILK_DESSERT_IDS = {"bananencreme_v1", "kaffeepudding_v1"}
DESSURE_MARKERS = ("крем", "мусс", "пудинг", "dessert", "pudding")


def is_key_onion(title_ru, title_de):
    t_ru = (title_ru or "").lower()
    t_de = (title_de or "").lower()
    return "луков" in t_ru or "zwiebel" in t_de


def is_key_garlic(title_ru, title_de):
    t_ru = (title_ru or "").lower()
    t_de = (title_de or "").lower()
    return "чесноч" in t_ru or "knoblauch" in t_de


def is_milk_dessert(recipe_id, title_ru, title_de):
    if recipe_id in MILK_DESSERT_IDS:
        return True
    t_ru = (title_ru or "").lower()
    t_de = (title_de or "").lower()
    if "банан" not in t_ru and "кофе" not in t_ru:
        return False
    combined = t_ru + " " + t_de
    return any(m in combined for m in DESSURE_MARKERS)


def main():
    if not os.path.isfile(DB_PATH):
        print(f"DB not found: {DB_PATH}")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT id, title_ru, title_de, must_have_json FROM recipes"
    )
    rows = [dict(r) for r in cur.fetchall()]

    processed = 0
    changed = 0
    kept_onion = []
    kept_garlic = []
    kept_milk = []
    sample_changes = []

    for r in rows:
        processed += 1
        recipe_id = r["id"]
        title_ru = r.get("title_ru") or ""
        title_de = r.get("title_de") or ""
        must_have_raw = r.get("must_have_json")
        must_have = list(json.loads(must_have_raw)) if must_have_raw else []
        before = list(must_have)

        new_list = [c for c in must_have if c not in REMOVE_SET]

        if "лук" in new_list and not is_key_onion(title_ru, title_de):
            new_list = [c for c in new_list if c != "лук"]
        elif "лук" in new_list:
            kept_onion.append(recipe_id)

        if "чеснок" in new_list and not is_key_garlic(title_ru, title_de):
            new_list = [c for c in new_list if c != "чеснок"]
        elif "чеснок" in new_list:
            kept_garlic.append(recipe_id)

        if "молоко" in new_list and not is_milk_dessert(recipe_id, title_ru, title_de):
            new_list = [c for c in new_list if c != "молоко"]
        else:
            if "молоко" in new_list:
                kept_milk.append(recipe_id)
            elif is_milk_dessert(recipe_id, title_ru, title_de):
                new_list.append("молоко")
                kept_milk.append(recipe_id)

        if new_list != before:
            changed += 1
            if len(sample_changes) < 10:
                sample_changes.append((recipe_id, before, new_list))
            conn.execute(
                "UPDATE recipes SET must_have_json = ? WHERE id = ?",
                (json.dumps(new_list, ensure_ascii=False), recipe_id),
            )

    conn.commit()
    conn.close()

    report_path = os.path.join(ROOT, "scripts", "cleanup_must_have_base_report.txt")
    lines = [
        f"processed: {processed}",
        f"changed: {changed}",
        f"kept_onion: {kept_onion}",
        f"kept_garlic: {kept_garlic}",
        f"kept_milk: {kept_milk}",
        "",
        "sample 10 changes: id | before -> after",
    ]
    for rid, b, a in sample_changes:
        lines.append(f"  {rid} | {b} -> {a}")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("processed:", processed)
    print("changed:", changed)
    print("kept_onion:", kept_onion)
    print("kept_garlic:", kept_garlic)
    print("kept_milk:", kept_milk)
    print("sample change ids:", [x[0] for x in sample_changes])
    print("Report (full before/after):", report_path)
    return changed


if __name__ == "__main__":
    main()
