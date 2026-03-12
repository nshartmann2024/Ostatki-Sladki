"""
Убрать "хлеб" из must_have_json у рецептов, где хлеб не является ингредиентом
(ложные попадания по поиску "хлеб").
Запуск из корня: python scripts/fix_false_bread_hits.py
"""
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "db", "app.db")

# Слова-маркеры хлеба в тексте (подстрока, lower)
BREAD_MARKERS = (
    "хлеб", "булк", "батон", "сухар", "гренк", "кнедл",
    "semmel", "brot",
)


def recipe_text_lower(r):
    parts = [
        (r.get("title_ru") or ""),
        (r.get("title_de") or ""),
        (r.get("notes") or ""),
    ]
    for key in ("ingredients_json", "steps_json"):
        raw = r.get(key)
        if isinstance(raw, str):
            raw = json.loads(raw) if raw else []
        if isinstance(raw, list):
            parts.extend(str(x) for x in raw)
    return " ".join(parts).lower()


def has_bread_in_text(text_lower):
    return any(m in text_lower for m in BREAD_MARKERS)


def main():
    if not os.path.isfile(DB_PATH):
        print("DB not found:", DB_PATH)
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT id, title_ru, title_de, must_have_json, all_ingredients_json, ingredients_json, steps_json, notes FROM recipes"
    )
    rows = [dict(r) for r in cur.fetchall()]

    candidates = []
    for r in rows:
        must_have_raw = r.get("must_have_json")
        must_have = json.loads(must_have_raw) if must_have_raw else []
        if "хлеб" not in must_have:
            continue
        all_ing = r.get("all_ingredients_json")
        if all_ing:
            all_list = json.loads(all_ing) if isinstance(all_ing, str) else all_ing
            if all_list and "хлеб" in all_list:
                continue
        text = recipe_text_lower(r)
        if has_bread_in_text(text):
            continue
        candidates.append(r)

    found_false_bread = len(candidates)
    updated = 0
    changes = []

    for r in candidates:
        must_have_raw = r.get("must_have_json")
        must_have = list(json.loads(must_have_raw)) if must_have_raw else []
        before = list(must_have)
        new_list = [c for c in must_have if c != "хлеб"]
        after = new_list
        conn.execute(
            "UPDATE recipes SET must_have_json = ? WHERE id = ?",
            (json.dumps(new_list, ensure_ascii=False), r["id"]),
        )
        updated += 1
        changes.append((r["id"], r.get("title_ru") or "", before, after))

    conn.commit()
    conn.close()

    report_path = os.path.join(ROOT, "scripts", "fix_false_bread_report.txt")
    lines = [
        f"found_false_bread: {found_false_bread}",
        f"updated: {updated}",
        "",
    ]
    for rid, title_ru, before, after in changes:
        lines.append(f"  {rid} | {title_ru[:55]} | {before} -> {after}")
    for rid, title_ru, before, after in changes:
        if "разноцветные намазки" in (title_ru or "").lower():
            lines.append("")
            lines.append("Confirmed fixed: 'Разноцветные намазки из творога' (id: " + rid + ")")
            break
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("found_false_bread:", found_false_bread)
    print("updated:", updated)
    print("changed ids:", [c[0] for c in changes])
    for rid, title_ru, before, after in changes:
        if "разноцветные намазки" in (title_ru or "").lower():
            print("Confirmed fixed: topfenaufstrich (id:", rid + ")")
            break
    print("Report:", report_path)
    return updated


if __name__ == "__main__":
    main()
