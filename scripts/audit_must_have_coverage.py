"""
Аудит покрытия must_have_json: какие canonical ингредиенты есть в тексте рецепта, но отсутствуют в must_have_json.
Запуск из корня: python scripts/audit_must_have_coverage.py
"""
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "db", "app.db")
CANONICAL_PATH = os.path.join(ROOT, "data", "ingredients_canonical.json")

# Ключевые canonical для проверки покрытия
CANONICAL_KEYS = [
    "хлеб", "картофель", "морковь", "лук", "кабачок", "томаты", "брокколи",
    "сыр", "мясо", "грибы", "творог", "рис", "капуста", "яйцо", "молоко",
    "ветчина", "колбаса", "фасоль", "яблоко", "шоколад", "чеснок", "масло",
]

# Базовые продукты — не индексируем как поисковые теги (только «поисковые» ингредиенты)
BASIC_EXCLUDE = {
    "масло", "молоко", "яйцо", "лук", "чеснок", "мука", "сахар", "соль",
    "перец", "вода", "сливки", "сметана", "йогурт",
}


def load_canonical_and_aliases():
    with open(CANONICAL_PATH, encoding="utf-8") as f:
        data = json.load(f)
    canonical_list = set(data.get("canonical", []))
    aliases = data.get("aliases", {})
    # Для каждого canonical собираем все варианты для поиска в тексте
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


def main():
    if not os.path.isfile(DB_PATH):
        print(f"DB not found: {DB_PATH}")
        return
    canonical_list, canonical_to_terms = load_canonical_and_aliases()
    keys_to_check = [k for k in CANONICAL_KEYS if k in canonical_list]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT id, title_ru, title_de, short_desc, ingredients_json, steps_json, notes, must_have_json FROM recipes"
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    report = []
    for r in rows:
        text = recipe_text_lower(r)
        must_have_raw = r.get("must_have_json")
        must_have = set(json.loads(must_have_raw)) if must_have_raw else set()
        mentioned = set()
        for c in keys_to_check:
            for term in canonical_to_terms.get(c, [c]):
                if term.lower() in text:
                    mentioned.add(c)
                    break
        missing = (mentioned - must_have) - BASIC_EXCLUDE
        if missing:
            report.append({
                "recipe_id": r["id"],
                "title_ru": r["title_ru"] or "",
                "missing_tags": sorted(missing),
                "current_must_have": sorted(must_have),
            })
        else:
            report.append({
                "recipe_id": r["id"],
                "title_ru": r["title_ru"] or "",
                "missing_tags": [],
                "current_must_have": sorted(must_have),
            })

    with_missing = sum(1 for r in report if r["missing_tags"])
    lines = [
        "recipe_id | title_ru | missing_tags",
        "-" * 80,
    ]
    for row in report:
        mid = ", ".join(row["missing_tags"]) if row["missing_tags"] else "—"
        lines.append(f"{row['recipe_id']} | {row['title_ru'][:45]} | {mid}")
    lines.extend(["", f"Рецептов с missing_tags: {with_missing}", f"Всего рецептов: {len(report)}"])
    out = "\n".join(lines)
    report_path = os.path.join(ROOT, "scripts", "audit_must_have_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"Recipes with missing_tags: {with_missing}", f"Total: {len(report)}", f"Report: {report_path}", sep="\n")
    return report


if __name__ == "__main__":
    main()
