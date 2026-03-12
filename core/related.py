"""
Подбор похожих рецептов по must_have и общим ингредиентам.
"""
import json


def _parse_list(recipe: dict, key: str) -> list:
    """Вернуть список из JSON-поля рецепта; если нет или не список — пустой список."""
    raw = recipe.get(key)
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            out = json.loads(raw)
            return out if isinstance(out, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def get_related_recipes(
    current_recipe_id: str,
    all_recipes: list[dict],
    limit: int = 3,
) -> list[dict]:
    """
    Возвращает список из limit рецептов, похожих на текущий.
    Логика:
    - Исключить текущий рецепт
    - Скорить кандидатов: score = must_have_overlap*100 + all_ingredients_overlap
    - must_have_overlap = количество пересечений must_have_json
    - all_ingredients_overlap = количество пересечений all_ingredients_json
    - сортировка по score desc, затем по all_ingredients_overlap desc, затем по title asc
    - вернуть top limit с полями: id, title, photo_url, difficulty
    """
    current = None
    candidates = []
    for r in all_recipes:
        rid = r.get("id")
        if rid == current_recipe_id:
            current = r
            continue
        if not rid:
            continue
        candidates.append(r)

    if not current:
        return []

    must_have_current = set(_parse_list(current, "must_have_json"))
    all_ing_current = set(_parse_list(current, "all_ingredients_json"))

    def title_str(rec: dict) -> str:
        de = (rec.get("title_de") or "").strip()
        ru = (rec.get("title_ru") or "").strip()
        return f"{de} — {ru}" if de and ru else (ru or de or rec.get("id", ""))

    scored = []
    for rec in candidates:
        must_have_rec = set(_parse_list(rec, "must_have_json"))
        all_ing_rec = set(_parse_list(rec, "all_ingredients_json"))
        must_have_overlap = len(must_have_current & must_have_rec)
        all_ing_overlap = len(all_ing_current & all_ing_rec)
        score = must_have_overlap * 100 + all_ing_overlap
        scored.append(
            (
                score,
                all_ing_overlap,
                title_str(rec),
                rec,
            )
        )

    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    top = [x[3] for x in scored[:limit]]

    return [
        {
            "id": r.get("id"),
            "title": title_str(r),
            "photo_url": r.get("photo_url"),
            "difficulty": r.get("difficulty") or "",
        }
        for r in top
    ]


if __name__ == "__main__":
    # Self-check без запуска по умолчанию: вызвать вручную или из теста
    _r1 = {
        "id": "reisfleisch_v1",
        "title_de": "Reisfleisch",
        "title_ru": "рис с мясом",
        "must_have_json": '["рис", "мясо"]',
        "all_ingredients_json": '["рис", "мясо", "лук", "морковь", "масло"]',
        "photo_url": None,
        "difficulty": "Средне",
    }
    _r2 = {
        "id": "reisauflauf_v1",
        "title_de": "Reisauflauf",
        "title_ru": "рисовая запеканка",
        "must_have_json": '["рис"]',
        "all_ingredients_json": '["рис", "молоко", "яйцо", "масло"]',
        "photo_url": None,
        "difficulty": "Просто",
    }
    _all = [_r1, _r2]
    _out = get_related_recipes("reisfleisch_v1", _all, limit=3)
    assert len(_out) == 1
    assert _out[0]["id"] == "reisauflauf_v1"
    assert "рис" in _out[0]["title"].lower() or "Reis" in _out[0]["title"]
    print("Self-check OK")
