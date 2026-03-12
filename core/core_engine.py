import json
import os
import random
import sqlite3
from dataclasses import dataclass

from core import config
from core import related

# Реплики персонажа: спокойный, практичный тон. Без имени, без юмора.
PHRASES_BEFORE_LIST = [
    ("bl_1", "Сейчас подберу варианты."),
    ("bl_2", "Есть что показать."),
    ("bl_3", "Смотри варианты ниже."),
    ("bl_4", "Вот что нашёл."),
    ("bl_5", "Можно из этого."),
]
PHRASES_AFTER_RECIPE = [
    ("ar_1", "Если нужен другой рецепт — напиши ингредиент."),
    ("ar_2", "Можно искать по другому ингредиенту."),
    ("ar_3", "Если что-то ещё нужно — пиши."),
    ("ar_4", "Держи. При необходимости спроси ещё."),
    ("ar_5", "Вот рецепт. При желании могу подсказать другой."),
]
MAX_USED_PHRASES = 5


@dataclass
class Message:
    type: str = "text"
    text: str = ""


@dataclass
class Action:
    id: str
    label: str


@dataclass
class ResponsePlan:
    messages: list
    actions: list
    state_patch: dict
    ui_hints: dict | None
    ui_mode: str = "search"


def _pick_phrase(phrases: list, used_key: str, state: dict) -> tuple[str | None, str | None]:
    """Возвращает (id, text) одной фразы, по возможности не из последних used_key. Обновлённый used_key не возвращаем — вызывающий добавит в state_patch."""
    state = state or {}
    used = list(state.get(used_key, []))[-MAX_USED_PHRASES:]
    available = [(pid, text) for pid, text in phrases if pid not in used]
    if not available:
        available = phrases
    pid, text = random.choice(available)
    new_used = (used + [pid])[-MAX_USED_PHRASES:]
    return pid, text, new_used


DIFFICULTY_RU = {"easy": "легко", "medium": "средне", "hard": "сложно"}


def _format_recipe_messages(recipe: dict) -> list:
    ingredients_list = json.loads(recipe.get("ingredients_json") or "[]")
    ingredients_lines = "\n".join("• " + (x if isinstance(x, str) else str(x)) for x in ingredients_list)
    difficulty_raw = (recipe.get("difficulty") or "").strip()
    difficulty_display = DIFFICULTY_RU.get(difficulty_raw.lower(), difficulty_raw) if difficulty_raw else ""
    meta = f"⏱ {recipe.get('time_min', 0)} мин"
    if difficulty_display:
        meta += f" • {difficulty_display}"
    is_classic_int = int(recipe.get("is_classic", 0))
    if is_classic_int == 1:
        flag = "\U0001F1E6\U0001F1F9"
        meta += f" • {flag}"
    part1 = (
        f"<b>{recipe.get('title_de', '')}</b> — {recipe.get('title_ru', '')}\n"
        f"{meta}\n\n"
        f"{recipe.get('short_desc', '')}\n\n\n"
        f"<b>Ингредиенты:</b>\n{ingredients_lines}\n"
    )
    if recipe.get("notes"):
        part1 += f"\n<b>Примечание:</b> {recipe['notes']}"

    steps_list = json.loads(recipe.get("steps_json") or "[]")
    steps_lines = "\n".join("• " + (s if isinstance(s, str) else str(s)) for s in steps_list)
    storage_tip = recipe.get("storage_tip") or ""
    format_type = recipe.get("format_type") or "two_step"
    steps_header = "\n\n<b>Шаги:</b>\n"

    if format_type == "card":
        msg_text = part1 + steps_header + steps_lines
        if storage_tip:
            msg_text += f"\n\n<b>Совет по хранению:</b> {storage_tip}"
        return [Message(text=msg_text)]

    messages = [Message(text=part1)]
    msg2 = steps_header + steps_lines
    if storage_tip:
        msg2 += f"\n\n<b>Совет по хранению:</b> {storage_tip}"
    messages.append(Message(text=msg2))
    return messages


def handle_event(event: dict) -> ResponsePlan:
    user_key = event.get("user_key")
    channel = event.get("channel")
    text_input = event.get("text_input") or ""
    action_id = event.get("action_id")
    state = event.get("state")

    if action_id == "another":
        return ResponsePlan(
            messages=[Message(text="Ок, напиши другой ингредиент.")],
            actions=[],
            state_patch={"last_results": [], "last_recipe_id": None, "last_canonical": None, "last_offset": None, "last_total": None},
            ui_hints=None,
            ui_mode="search",
        )
    if action_id == "reset":
        return ResponsePlan(
            messages=[Message(text="Ок, напиши ингредиент.")],
            actions=[],
            state_patch={"last_results": [], "last_recipe_id": None, "last_canonical": None, "last_offset": None, "last_total": None},
            ui_hints=None,
            ui_mode="search",
        )
    if action_id == "add_ingredient":
        return ResponsePlan(
            messages=[Message(text="Пока MVP: просто напиши второй ингредиент текстом.")],
            actions=[],
            state_patch={},
            ui_hints=None,
            ui_mode="search",
        )
    if action_id == "back:first":
        state = state or {}
        canonical = state.get("last_canonical")
        if not canonical:
            return ResponsePlan(
                messages=[Message(text="Напишите ингредиент (1–2 слова).")],
                actions=[],
                state_patch={"last_recipe_id": None, "last_offset": 0},
                ui_hints=None,
                ui_mode="search",
            )
        offset = 0
        limit = 6
        page_results, total_count = search_recipes(canonical, offset=offset, limit=limit)
        actions = [Action(id=f"recipe:{r['id']}", label=r["title_ru"]) for r in page_results]
        if total_count > offset + limit:
            actions.append(Action(id="more", label="Ещё варианты…"))
        return ResponsePlan(
            messages=[Message(text=f'Нашёл варианты по «{canonical}». Выберите рецепт:')],
            actions=actions,
            state_patch={"last_recipe_id": None, "last_offset": 0, "last_canonical": canonical, "last_total": total_count},
            ui_hints=None,
            ui_mode="results",
        )
    if action_id == "back":
        state = state or {}
        canonical = state.get("last_canonical")
        if not canonical:
            return ResponsePlan(
                messages=[Message(text="Напишите ингредиент (1–2 слова).")],
                actions=[],
                state_patch={"last_recipe_id": None},
                ui_hints=None,
                ui_mode="search",
            )
        offset = state.get("last_offset", 0)
        limit = 6
        page_results, total_count = search_recipes(canonical, offset=offset, limit=limit)
        actions = [Action(id=f"recipe:{r['id']}", label=r["title_ru"]) for r in page_results]
        if total_count > offset + limit:
            actions.append(Action(id="more", label="Ещё варианты…"))
        return ResponsePlan(
            messages=[Message(text=f'Нашёл варианты по «{canonical}». Выберите рецепт:')],
            actions=actions,
            state_patch={"last_recipe_id": None},
            ui_hints=None,
            ui_mode="results",
        )
    if action_id == "more":
        state = state or {}
        canonical = state.get("last_canonical")
        if not canonical:
            return ResponsePlan(
                messages=[Message(text="Сначала введите ингредиент.")],
                actions=[],
                state_patch={},
                ui_hints=None,
                ui_mode="search",
            )
        prev_offset = state.get("last_offset", 0)
        offset = prev_offset + 6
        limit = 6
        page_results, total_count = search_recipes(canonical, offset=offset, limit=limit)
        actions = [Action(id=f"recipe:{r['id']}", label=r["title_ru"]) for r in page_results]
        if total_count > offset + limit:
            actions.append(Action(id="more", label="Ещё варианты…"))
        actions.append(Action(id="back:first", label="← К первому списку"))
        return ResponsePlan(
            messages=[Message(text=f'Нашёл варианты по «{canonical}». Выберите рецепт:')],
            actions=actions,
            state_patch={"last_canonical": canonical, "last_offset": offset, "last_total": total_count},
            ui_hints=None,
            ui_mode="results",
        )
    if action_id and action_id.startswith("recipe:"):
        recipe_id = action_id[7:]
        recipe = get_recipe_by_id(recipe_id)
        if recipe is None:
            return ResponsePlan(
                messages=[Message(text="Рецепт не найден.")],
                actions=[],
                state_patch={},
                ui_hints=None,
                ui_mode="results",
            )
        messages = _format_recipe_messages(recipe)
        _, after_text, new_used_after = _pick_phrase(PHRASES_AFTER_RECIPE, "used_phrases_after_recipe", state)
        messages.append(Message(type="text", text=after_text))
        actions = [
            Action(id="back:first", label="← К первым вариантам"),
            Action(id="back", label="← Назад к вариантам"),
            Action(id="ozvuchit", label="Озвучить (скоро)"),
            Action(id="another", label="Другое блюдо"),
            Action(id="add_ingredient", label="Добавить ингредиент"),
        ]
        ui_hints = {
            "photo_url": recipe.get("photo_url"),
            "photo_file_id_tg": recipe.get("photo_file_id_tg"),
        }
        if config.FEATURE_RELATED_RECIPES:
            all_recipes = get_all_recipes()
            related_list = related.get_related_recipes(recipe_id, all_recipes, limit=3)
            ui_hints["related_recipes"] = related_list
        return ResponsePlan(
            messages=messages,
            actions=actions,
            state_patch={"last_recipe_id": recipe_id, "used_phrases_after_recipe": new_used_after},
            ui_hints=ui_hints,
            ui_mode="recipe",
        )

    canonical = normalize_input(text_input)
    offset = 0
    limit = 6
    page_results, total_count = search_recipes(canonical, offset=offset, limit=limit)

    if canonical is None:
        return ResponsePlan(
            messages=[Message(text="Не понял ингредиент. Введите 1 ингредиент (можно фразой). Например: «отварной картофель», «творог», «белый хлеб», «шоколад».")],
            actions=[],
            state_patch={},
            ui_hints=None,
            ui_mode="search",
        )
    if not page_results and total_count == 0:
        return ResponsePlan(
            messages=[Message(text=f'По ингредиенту «{canonical}» пока ничего не нашёл.')],
            actions=[],
            state_patch={},
            ui_hints=None,
            ui_mode="search",
        )
    actions = [Action(id=f"recipe:{r['id']}", label=r["title_ru"]) for r in page_results]
    if total_count > offset + limit:
        actions.append(Action(id="more", label="Ещё варианты…"))
    _, before_text, new_used_before = _pick_phrase(PHRASES_BEFORE_LIST, "used_phrases_before_list", state)
    messages = [
        Message(type="text", text=f'Я понял: ищу рецепты с «{canonical}».'),
        Message(type="text", text=before_text),
        Message(type="text", text=f'Нашёл варианты по «{canonical}». Выберите рецепт:'),
    ]
    return ResponsePlan(
        messages=messages,
        actions=actions,
        state_patch={
            "last_canonical": canonical,
            "last_offset": offset,
            "last_total": total_count,
            "used_phrases_before_list": new_used_before,
        },
        ui_hints=None,
        ui_mode="results",
    )


def load_canonical():
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "ingredients_canonical.json")
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)
    return data["canonical"], data["aliases"]


def normalize_input(text):
    """
    Распознать один канонический ингредиент из фразы пользователя.
    Сначала проверяется вся строка, затем по первому подходящему токену.
    Примеры:
      normalize_input("отварной картофель") -> "картофель"
      normalize_input("картофель отварной") -> "картофель"
      normalize_input("белый хлеб") -> "хлеб"
      normalize_input("творог") -> "творог"
      normalize_input("шоколад") -> "шоколад" (если есть в canonical/aliases)
    """
    if not text:
        return None
    text_lower = text.lower().strip()
    canonical_list, aliases_dict = load_canonical()
    # Обратная совместимость: вся строка целиком
    if text_lower in aliases_dict:
        return aliases_dict[text_lower]
    if text_lower in canonical_list:
        return text_lower
    # Токенизация: пунктуация -> пробел, split
    for ch in ",.;:!?()[]{}\"'":
        text_lower = text_lower.replace(ch, " ")
    tokens = [t for t in text_lower.split() if t]
    for token in tokens:
        if token in aliases_dict:
            return aliases_dict[token]
        if token in canonical_list:
            return token
    return None


def list_recipes():
    db_path = os.path.join(os.path.dirname(__file__), "..", "db", "app.db")
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT id, title_ru FROM recipes")
        return cur.fetchall()


def search_recipes(canonical, offset=0, limit=6):
    if canonical is None:
        return [], 0
    db_path = os.path.join(os.path.dirname(__file__), "..", "db", "app.db")
    result = []
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT id, title_de, title_ru, must_have_json FROM recipes ORDER BY id")
        for row in cur:
            id_, title_de, title_ru, must_have_json = row
            must_have_list = json.loads(must_have_json or "[]")
            if canonical in must_have_list:
                result.append({"id": id_, "title_de": title_de, "title_ru": title_ru})
    total_count = len(result)
    page_results = result[offset:offset + limit]
    return page_results, total_count


def get_recipe_by_id(recipe_id):
    db_path = os.path.join(os.path.dirname(__file__), "..", "db", "app.db")
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT * FROM recipes WHERE id=?", (recipe_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return dict(zip([d[0] for d in cur.description], row))


def get_all_recipes():
    """Все рецепты для подбора похожих (id, title_de, title_ru, must_have_json, all_ingredients_json, photo_url, difficulty)."""
    db_path = os.path.join(os.path.dirname(__file__), "..", "db", "app.db")
    result = []
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "SELECT id, title_de, title_ru, must_have_json, all_ingredients_json, photo_url, difficulty FROM recipes ORDER BY id"
        )
        for row in cur:
            result.append(
                {
                    "id": row[0],
                    "title_de": row[1],
                    "title_ru": row[2],
                    "must_have_json": row[3],
                    "all_ingredients_json": row[4],
                    "photo_url": row[5],
                    "difficulty": row[6],
                }
            )
    return result


if __name__ == "__main__":
    # Проверка meta для классического рецепта (должен быть виден флаг в терминале)
    r = get_recipe_by_id("scheiterhaufen_v1")
    if r:
        difficulty_raw = (r.get("difficulty") or "").strip()
        difficulty_display = DIFFICULTY_RU.get(difficulty_raw.lower(), difficulty_raw) if difficulty_raw else ""
        meta = f"⏱ {r.get('time_min', 0)} мин"
        if difficulty_display:
            meta += f" • {difficulty_display}"
        is_classic_int = int(r.get("is_classic", 0))
        if is_classic_int == 1:
            flag = "\U0001F1E6\U0001F1F9"
            meta += f" • {flag}"
        print("meta scheiterhaufen_v1:", meta)
    plan = handle_event({"text_input": "хлеб"})
    print("хлеб ->", plan.messages[0].text if plan.messages else "", plan.actions[:2], plan.state_patch)
    plan2 = handle_event({"action_id": "more", "state": plan.state_patch})
    print("more ->", plan2.messages[0].text if plan2.messages else "", plan2.actions[:2], plan2.state_patch)
