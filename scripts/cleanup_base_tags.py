"""
Один раз удалить "лук" и "чеснок" из must_have_json у всех рецептов,
кроме тех, где лук или чеснок — ключевые ингредиенты (по названию).
Запуск из корня: python scripts/cleanup_base_tags.py
"""
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "db", "app.db")

TAGS_TO_REMOVE = {"лук", "чеснок"}


def is_key_onion(title_ru, title_de):
    t_ru = (title_ru or "").lower()
    t_de = (title_de or "").lower()
    return "луков" in t_ru or "zwiebel" in t_de


def is_key_garlic(title_ru, title_de):
    t_ru = (title_ru or "").lower()
    t_de = (title_de or "").lower()
    return "чесноч" in t_ru or "knoblauch" in t_de


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

    updated = 0
    kept_onion = []
    kept_garlic = []
    for r in rows:
        must_have_raw = r.get("must_have_json")
        must_have = list(json.loads(must_have_raw)) if must_have_raw else []
        if not must_have:
            continue
        key_onion = is_key_onion(r.get("title_ru"), r.get("title_de"))
        key_garlic = is_key_garlic(r.get("title_ru"), r.get("title_de"))
        if key_onion:
            kept_onion.append((r["id"], r.get("title_ru") or ""))
        if key_garlic:
            kept_garlic.append((r["id"], r.get("title_ru") or ""))
        new_list = [c for c in must_have if c not in TAGS_TO_REMOVE]
        if key_onion and "лук" in must_have:
            new_list.append("лук")
        if key_garlic and "чеснок" in must_have:
            new_list.append("чеснок")
        if new_list != must_have:
            conn.execute(
                "UPDATE recipes SET must_have_json = ? WHERE id = ?",
                (json.dumps(new_list, ensure_ascii=False), r["id"]),
            )
            updated += 1
    conn.commit()
    conn.close()

    report_path = os.path.join(ROOT, "scripts", "cleanup_base_tags_report.txt")
    lines = [
        f"Updated recipes: {updated}",
        "Recipes where 'лук' kept (key ingredient): " + ", ".join(x[0] for x in kept_onion),
        "Recipes where 'чеснок' kept (key ingredient): " + ", ".join(x[0] for x in kept_garlic),
        "",
        "[лук] kept:",
    ]
    for rid, title in kept_onion:
        lines.append(f"  {rid}: {title[:55]}")
    lines.append("")
    lines.append("[чеснок] kept:")
    for rid, title in kept_garlic:
        lines.append(f"  {rid}: {title[:55]}")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Updated recipes: {updated}")
    print("Onion kept (recipe_ids):", [x[0] for x in kept_onion])
    print("Garlic kept (recipe_ids):", [x[0] for x in kept_garlic])
    print(f"Report: {report_path}")
    return updated


if __name__ == "__main__":
    main()
