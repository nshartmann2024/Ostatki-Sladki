"""
Web-адаптер «Остатки сладки»: Streamlit UI.
Запуск из корня: streamlit run adapters/web/app.py
"""
import html
import os
import re
import sqlite3
import sys
from pathlib import Path

import streamlit as st

_web_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(os.path.dirname(_web_dir))
if _root not in sys.path:
    sys.path.insert(0, _root)

from core.core_engine import handle_event, ResponsePlan, Message, Action
from db.analytics import log_event as _log_analytics

_ANALYTICS_DB = os.path.join(_root, "db", "app.db")

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # app.py -> web -> adapters -> project root
PHOTO_DIR = PROJECT_ROOT / "assets" / "photos"

NORMALIZE_WORDS = {
    "картошка": "картофель",
    "картошки": "картофель",
    "картофеля": "картофель",
    "луковица": "лук",
    "лука": "лук",
    "чеснока": "чеснок",
    "бананы": "банан",
    "яблоки": "яблоко",
    "батон": "хлеб",
    "булка": "хлеб",
}


def resolve_photo_path(recipe_id: str) -> str | None:
    """
    Возвращает путь к фото рецепта.
    Работает стабильно в локале и в облаке.
    """
    if not recipe_id:
        return None
    # 1) Явные исключения (несовпадения id и имени файла)
    EXPLICIT_MAP = {
        "erdaepfel_vogerlsalat_v1": "erdaepfel_vogel_salat.jpg",
        "brotsuppe_rahm_2025": "brotsuppe.jpg",
        "erdapfelgulasch_v1": "erdaepfelgulasch.jpg",
    }
    if recipe_id in EXPLICIT_MAP:
        candidate = PHOTO_DIR / EXPLICIT_MAP[recipe_id]
        if candidate.exists():
            return str(candidate)
    # 2) Прямое совпадение recipe_id.jpg
    direct = PHOTO_DIR / f"{recipe_id}.jpg"
    if direct.exists():
        return str(direct)
    # 3) Если есть суффикс _v1 — пробуем без него
    if recipe_id.endswith("_v1"):
        base_id = recipe_id[:-3]
        fallback = PHOTO_DIR / f"{base_id}.jpg"
        if fallback.exists():
            return str(fallback)
    return None


# Одно фото на главной: картофельный салат с маш-салатом
_HERO_PHOTO = "assets/photos/erdaepfel_vogel_salat.jpg"
POPULAR_INGREDIENTS = ["Творог", "Сыр", "Бананы", "Рис", "Яблоки", "Картофель", "Хлеб"]
# Сайдбар: 3 с фото (id, title_ru, photo_url из БД) + 3 быстрые кнопки
SIDEBAR_FEATURED_IDS = ["topfenaufstrich_bunt_v1", "erdapfelgulasch_v1", "brotauflauf_kaese_v1"]
SIDEBAR_QUICK_IDS = ["bananencreme_v1", "arme_ritter_v1", "erdaepfelkrapferl_v1"]
STORAGE_OPEN = {
    "Чеснок": "Храните свежий чеснок при комнатной температуре в сухом и хорошо проветриваемом месте — например, в сетке или корзине. Не держите его в холодильнике: там он быстрее прорастает. Очищенные зубчики лучше использовать сразу или заморозить.",
    "Лук": "Лук храните в прохладном, тёмном и сухом месте. Не держите его рядом с картофелем — так он быстрее портится. Нарезанный лук можно заморозить порционно и использовать для жарки и супов.",
    "Молоко": "Открытое молоко храните в холодильнике и используйте в течение 2–3 дней. Закрытая упаковка может храниться дольше, но после вскрытия держите её только в холоде. Молоко можно замораживать до 2–3 месяцев, но не в стеклянной таре.",
}
STORAGE_BUTTONS = {
    "Хлеб": "Храните хлеб целым в хлебнице или тканевом мешке. В холодильнике он быстрее черствеет. Можно замораживать ломтиками до 6 месяцев.",
    "Картофель": "Картофель держите в прохладном, тёмном и сухом месте вне холодильника. Не храните рядом с луком. Зелёные и сильно проросшие клубни лучше не использовать.",
    "Капуста": "Капусту храните целым кочаном в холодильнике или прохладном помещении. В подвале её можно подвесить за кочерыжку. Нашинкованную капусту можно заморозить порционно.",
    "Бананы": "Бананы лучше хранить при комнатной температуре, подвешенными. Переспелые плоды можно нарезать и заморозить. В морозилке бананы хранятся до 3–4 месяцев.",
}


def _get_recipe_by_id(recipe_id):
    """Вернуть dict с id, title_ru, photo_url или None."""
    db_path = os.path.join(_root, "db", "app.db")
    if not os.path.isfile(db_path):
        return None
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute(
                "SELECT id, title_ru, photo_url FROM recipes WHERE id = ?",
                (recipe_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"id": row[0], "title_ru": row[1] or "", "photo_url": row[2] or ""}
    except Exception:
        return None


def _strip_html(text):
    if not text:
        return text
    return text.replace("<b>", "").replace("</b>", "").replace("&nbsp;", " ")


def _parse_recipe_meta(meta_line):
    """Из строки вида '⏱ 25 мин • легко • 🇦🇹' извлечь time_min, difficulty, is_classic."""
    if not meta_line:
        return None, "", False
    s = _strip_html(meta_line).strip()
    time_min = None
    m = re.search(r"⏱\s*(\d+)\s*мин", s)
    if m:
        time_min = m.group(1)
    parts = [p.strip() for p in s.split("•")]
    difficulty = ""
    for p in parts[1:] if len(parts) > 1 else []:
        if not p or "🇦" in p or "мин" in p:
            continue
        difficulty = p
        break
    is_classic = "🇦" in s or "AT" in s.upper()
    return time_min, difficulty, is_classic


def _capitalize(s):
    if not (s or s.strip()):
        return ""
    s = s.strip()
    return s[0].upper() + s[1:] if len(s) > 1 else s.upper()


def _render_recipe_card(messages):
    """Рендер карточки: заголовок, одна строка метрик, описание, ингредиенты, шаги. Без st.metric и st.columns."""
    full_text = "\n\n".join(m.text for m in messages)
    full_text = _strip_html(full_text)
    lines = full_text.split("\n")
    if len(lines) < 2:
        st.markdown(full_text)
        return
    title_line = lines[0].strip()
    time_min, difficulty, is_classic = _parse_recipe_meta(lines[1])
    difficulty_cap = _capitalize(difficulty)

    # Заголовок (не раздувать)
    st.markdown(f"## {title_line}")

    # Метрики одной строкой с классом os-meta
    time_part = f"{time_min} мин" if time_min else "—"
    diff_part = difficulty_cap or "—"
    klass_part = "🇦🇹 Австрия" if is_classic else "—"
    meta_line = f"⏱ {time_part} • 🔪 {diff_part} • {klass_part}"
    st.markdown(f'<div class="os-meta">{html.escape(meta_line)}</div>', unsafe_allow_html=True)

    idx = 2
    while idx < len(lines) and "Ингредиенты" not in lines[idx]:
        idx += 1
    if idx > 2:
        desc = "\n".join(lines[2:idx]).strip()
        if desc:
            st.markdown(desc)
    st.markdown("### Ингредиенты")
    idx += 1
    ing_start = idx
    while idx < len(lines) and "Шаги" not in lines[idx] and "---" not in lines[idx]:
        idx += 1
    for line in lines[ing_start:idx]:
        line = line.strip().lstrip("• ").strip()
        if line:
            st.markdown(f"- {line}")
    while idx < len(lines) and (not lines[idx].strip() or "Шаги" in lines[idx] or lines[idx].strip() == "---"):
        idx += 1
    st.markdown("### Шаги")
    if idx < len(lines):
        for line in lines[idx:]:
            line = line.strip().lstrip("• ").strip()
            if line:
                st.markdown(f"- {line}")


def _response_to_dict(rp):
    return {
        "messages": [{"type": m.type, "text": m.text} for m in rp.messages],
        "actions": [{"id": a.id, "label": a.label} for a in rp.actions],
        "state_patch": rp.state_patch,
        "ui_mode": rp.ui_mode,
        "ui_hints": rp.ui_hints,
    }


def _dict_to_response(d):
    if d is None:
        return None
    messages = [Message(type=m.get("type", "text"), text=m.get("text", "")) for m in d.get("messages", [])]
    actions = [Action(id=a["id"], label=a["label"]) for a in d.get("actions", [])]
    return type("_R", (), {
        "messages": messages,
        "actions": actions,
        "state_patch": d.get("state_patch", {}),
        "ui_mode": d.get("ui_mode", "search"),
        "ui_hints": d.get("ui_hints"),
    })()


st.set_page_config(page_title="Остатки Сладки", layout="centered")

# CSS: фон, карточка по маркеру, скрыть image toolbar. Поле поиска НЕ ТРОГАЕМ (никаких input/textarea).
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
  background: #F6F1EA !important;
}

hr, [data-testid="stDivider"] { display: none !important; }

#os-recipe-card-marker { display: none !important; }

div[data-testid="stVerticalBlock"]:has(#os-recipe-card-marker) {
  background: #FFFFFF !important;
  border-radius: 18px !important;
  padding: 18px 18px 12px 18px !important;
  box-shadow: 0 10px 28px rgba(0,0,0,0.10) !important;
  border: 1px solid rgba(0,0,0,0.06) !important;
  margin-top: 10px !important;
}

div[data-testid="stVerticalBlock"]:has(#os-recipe-card-marker) img {
  border-radius: 14px !important;
  display: block !important;
}

[data-testid="stImageToolbar"] {
  display: none !important;
  visibility: hidden !important;
  opacity: 0 !important;
  pointer-events: none !important;
}
[data-testid="stImage"] button,
[data-testid="stImage"] [role="button"],
[data-testid="stImage"] [title*="fullscreen" i],
[data-testid="stImage"] [aria-label*="fullscreen" i],
[data-testid="stImage"] [title*="Full screen" i],
[data-testid="stImage"] [aria-label*="Full screen" i] {
  display: none !important;
  pointer-events: none !important;
}

div[data-testid="stVerticalBlock"]:has(#os-recipe-card-marker) h1,
div[data-testid="stVerticalBlock"]:has(#os-recipe-card-marker) h2 {
  font-size: clamp(22px, 4.6vw, 34px) !important;
  line-height: 1.12 !important;
  margin: 10px 0 8px 0 !important;
}

div[data-testid="stVerticalBlock"]:has(#os-recipe-card-marker) p {
  line-height: 1.35;
}

div[data-testid="stVerticalBlock"]:has(#os-recipe-card-marker) ul {
  margin-top: 6px !important;
  margin-bottom: 6px !important;
  padding-left: 22px !important;
}
div[data-testid="stVerticalBlock"]:has(#os-recipe-card-marker) li {
  margin: 2px 0 !important;
  line-height: 1.3 !important;
}

.os-meta { font-size: 14px !important; opacity: 0.85 !important; margin: 6px 0 10px 0 !important; }
div[data-testid="stVerticalBlock"]:has(#os-recipe-card-marker) h3,
div[data-testid="stVerticalBlock"]:has(#os-recipe-card-marker) h4 {
  font-size: 22px !important;
  margin: 18px 0 10px 0 !important;
}

[data-testid="stTextInput"] input {
  background-color: #FFFFFF !important;
  border: 1px solid rgba(0,0,0,0.15) !important;
  border-radius: 10px !important;
}

[data-testid="stTextInput"] input::placeholder {
  color: rgba(0,0,0,0.45) !important;
}

section[data-testid="stSidebar"] {
  background-color: #E2CCB3 !important;
  border-right: 1px solid #C9AE8F !important;
}

/* Кнопки «Что приготовить из…» — без переноса по середине слова */
div[data-ui="ingredients-row"] ~ div[data-testid="stHorizontalBlock"] button p {
  white-space: nowrap !important;
  word-break: keep-all !important;
  hyphens: none !important;
}
</style>
""", unsafe_allow_html=True)

if "state" not in st.session_state:
    st.session_state["state"] = {}
if "last_response" not in st.session_state:
    st.session_state["last_response"] = None
if "pending_query" not in st.session_state:
    st.session_state["pending_query"] = None
if "storage_tip_selected" not in st.session_state:
    st.session_state["storage_tip_selected"] = None
if "pending_recipe_id" not in st.session_state:
    st.session_state["pending_recipe_id"] = None
if "scroll_to_results" not in st.session_state:
    st.session_state["scroll_to_results"] = False

response = _dict_to_response(st.session_state.get("last_response"))
ui_mode = response.ui_mode if response else "search"

# Псевдо-submit по клику «популярный ингредиент» или рецепт в сайдбаре
pending = st.session_state.get("pending_query")
if pending is not None and pending != "":
    st.session_state["pending_query"] = None
    st.session_state["scroll_to_results"] = True
    query = (pending or "").lower().strip()
    if query in NORMALIZE_WORDS:
        query = NORMALIZE_WORDS[query]
    resp = handle_event({
        "user_key": "web:local",
        "channel": "web",
        "text_input": query,
        "action_id": None,
        "state": st.session_state.get("state"),
    })
    _log_analytics("ingredient_click", "web", event_value=pending or "", db_path=_ANALYTICS_DB)
    st.session_state["state"] = {**st.session_state["state"], **resp.state_patch}
    st.session_state["last_response"] = _response_to_dict(resp)
    st.rerun()
rid = st.session_state.get("pending_recipe_id")
if rid is not None:
    st.session_state["pending_recipe_id"] = None
    resp = handle_event({
        "user_key": "web:local",
        "channel": "web",
        "text_input": "",
        "action_id": f"recipe:{rid}",
        "state": st.session_state.get("state"),
    })
    r_info = _get_recipe_by_id(rid)
    _log_analytics("recipe_open", "web", recipe_id=rid, event_value=(r_info.get("title_ru") or "")[:200] if r_info else None, db_path=_ANALYTICS_DB)
    st.session_state["state"] = {**st.session_state["state"], **resp.state_patch}
    st.session_state["last_response"] = _response_to_dict(resp)
    st.rerun()

# Сайдбар: «Популярное сейчас» (3 с фото + «Открыть») + «Быстрые кнопки» (3 без фото)
st.sidebar.subheader("Популярное сейчас")
for rid in SIDEBAR_FEATURED_IDS:
    r = _get_recipe_by_id(rid)
    if not r:
        continue
    photo_path = resolve_photo_path(r["id"])
    if photo_path:
        st.sidebar.image(photo_path, width="stretch")
    st.sidebar.caption(r["title_ru"] or r["id"])
    if st.sidebar.button("Открыть", key="sb_" + r["id"]):
        st.session_state["pending_recipe_id"] = r["id"]
        st.rerun()
st.sidebar.subheader("Еще популярные рецепты")
for rid in SIDEBAR_QUICK_IDS:
    r = _get_recipe_by_id(rid)
    if r and st.sidebar.button(r["title_ru"] or r["id"], key="sbq_" + r["id"]):
        st.session_state["pending_recipe_id"] = r["id"]
        st.rerun()

# Заголовок: на главной — полный hero, в режиме рецепта — только название
if ui_mode == "recipe":
    st.title("Остатки сладки")

# Hero и лендинг только на главной
if ui_mode in ("search", "results"):
    st.title("Остатки сладки")
    st.markdown("Что приготовить быстро и просто из того, что есть дома — в стиле венской домашней кухни.")
    st.write('Наберите «творог» — получите подборку вариантов.')
    st.write('Наберите «рис» — идеи ужина из простых продуктов.')

    # Одно фото: картофельный салат с маш-салатом
    hero_path = os.path.join(_root, _HERO_PHOTO)
    if not os.path.isfile(hero_path):
        hero_path = os.path.join(_root, "assets/photos/erdaepfel-vogel salat.jpg")
    if os.path.isfile(hero_path):
        st.image(hero_path, width="stretch")

action_clicked_id = None
# Поиск — сразу под hero (без стилей, дефолтный Streamlit)
if ui_mode in ("search", "results"):
    with st.form(key="search_form", clear_on_submit=False):
        text_input = st.text_input("Введите 1 ингредиент (можно фразой). Например: «отварной картофель», «творог», «белый хлеб», «шоколад».")
        find_clicked = st.form_submit_button("Найти")

    if find_clicked:
        st.session_state["scroll_to_results"] = True
        raw_query = (text_input or "").strip()
        query = raw_query.lower().strip()
        if query in NORMALIZE_WORDS:
            query = NORMALIZE_WORDS[query]
        resp = handle_event({
            "user_key": "web:local",
            "channel": "web",
            "text_input": query,
            "action_id": None,
            "state": st.session_state.get("state"),
        })
        _log_analytics("search_submit", "web", event_value=raw_query or "", db_path=_ANALYTICS_DB)
        st.session_state["state"] = {**st.session_state["state"], **resp.state_patch}
        st.session_state["last_response"] = _response_to_dict(resp)
        st.rerun()

    # Якорь результатов — сразу под поиском
    st.markdown('<div id="results"></div>', unsafe_allow_html=True)
    results_anchor = st.empty()
    with results_anchor.container():
        if response and response.messages:
            _skip = lambda m: (m.text or "").strip().startswith("Я понял:") or (m.text or "").strip() == "Можно из этого."
            _filtered = [m for m in response.messages if not _skip(m)]
            if ui_mode == "recipe":
                recipe_id = (st.session_state.get("state") or {}).get("last_recipe_id")
                photo_path = resolve_photo_path(recipe_id) if recipe_id else None
                recipe_msgs = _filtered[:-1] if len(_filtered) > 1 else _filtered
                phrase_msg = _filtered[-1] if len(_filtered) > 1 else None
                if not recipe_msgs:
                    recipe_msgs = _filtered
                    phrase_msg = None
                st.markdown('<span id="os-recipe-card-marker"></span>', unsafe_allow_html=True)
                if photo_path:
                    st.image(photo_path, width="stretch")
                _render_recipe_card(recipe_msgs)
                if phrase_msg:
                    st.markdown(_strip_html(phrase_msg.text))
            else:
                for msg in _filtered:
                    st.markdown(_strip_html(msg.text))
        if response and response.actions:
            for action in response.actions:
                if ui_mode == "recipe" and action.id.startswith("recipe:"):
                    continue
                if action.id == "ozvuchit" or ("озвуч" in (action.label or "").lower()):
                    continue
                if st.button(action.label, key=action.id):
                    action_clicked_id = action.id
                    break
        if st.session_state.get("scroll_to_results") and response and response.messages:
            st.session_state["scroll_to_results"] = False
            st.markdown(
                '<script>document.getElementById("results").scrollIntoView({behavior:"smooth"});</script>',
                unsafe_allow_html=True,
            )

    # «Что приготовить из…» + кнопки ингредиентов (7 в один ряд, колонка Картофель шире)
    st.subheader("Что приготовить из…")
    st.markdown('<div data-ui="ingredients-row"></div>', unsafe_allow_html=True)
    cols = st.columns([1.0, 1.0, 1.0, 1.0, 1.0, 1.35, 1.0])
    for i, ing in enumerate(POPULAR_INGREDIENTS):
        with cols[i]:
            if st.button(ing, key="pop_" + ing):
                st.session_state["pending_query"] = ing.lower()
                st.rerun()

    # Telegram CTA
    st.subheader("Больше рецептов и историй — в Telegram")
    st.write("В канале — простая венская кухня на каждый день, традиционные блюда Австрии и истории о жизни в Вене.")
    st.write("Есть и венская классика: яблочный штрудель, штрудель с маком, ростбратен на гриле и кайзершмаррн.")
    with st.expander("Ещё примеры блюд в канале"):
        st.markdown(
            """
            🔗 [Ароматный яблочный штрудель](https://t.me/viennarezept/33)

            🔗 [Штрудель с маком](https://t.me/viennarezept/65)

            🔗 [Сочный ростбратен на гриле](https://t.me/viennarezept/122)

            🔗 [Клецки из картофельного теста с маком](https://t.me/viennarezept/20)

            """
        )
        if st.session_state.get("telegram_expander_link_shown"):
            st.link_button(
                "Открыть рецепты в Telegram",
                "https://t.me/+2oxmJaqm9BZhYWU0",
                width="content"
            )
        elif st.button("Открыть рецепты в Telegram", key="tg_exp_btn"):
            _log_analytics("telegram_click", "web", event_value="expander_link", db_path=_ANALYTICS_DB)
            st.session_state["telegram_expander_link_shown"] = True
            st.rerun()
    if st.session_state.get("telegram_main_link_shown"):
        st.markdown(
            '<span style="display:inline-flex;align-items:center;gap:8px;">'
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="#0088cc">'
            '<path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>'
            '</svg>'
            '<a href="https://t.me/+2oxmJaqm9BZhYWU0" target="_blank" rel="noopener" style="color:#0088cc;">Перейти в Telegram</a>'
            '</span>',
            unsafe_allow_html=True,
        )
    elif st.button("Перейти в Telegram", key="tg_main_btn"):
        _log_analytics("telegram_click", "web", event_value="main_link", db_path=_ANALYTICS_DB)
        st.session_state["telegram_main_link_shown"] = True
        st.rerun()

    # Хранение: 3 карточки в ряд + 4 по кнопке
    st.subheader("Как хранить продукты в домашних условиях")
    sc0, sc1, sc2 = st.columns(3)
    with sc0:
        st.markdown("**Молоко**")
        st.write(STORAGE_OPEN["Молоко"])
    with sc1:
        st.markdown("**Лук**")
        st.write(STORAGE_OPEN["Лук"])
    with sc2:
        st.markdown("**Чеснок**")
        st.write(STORAGE_OPEN["Чеснок"])
    stor_cols = st.columns(4)
    with stor_cols[0]:
        if st.button("Хлеб", key="stor_Хлеб"):
            st.session_state["storage_tip_selected"] = "Хлеб"
    with stor_cols[1]:
        if st.button("Картофель", key="stor_Картофель"):
            st.session_state["storage_tip_selected"] = "Картофель"
    with stor_cols[2]:
        if st.button("Капуста", key="stor_Капуста"):
            st.session_state["storage_tip_selected"] = "Капуста"
    with stor_cols[3]:
        if st.button("Бананы", key="stor_Бананы"):
            st.session_state["storage_tip_selected"] = "Бананы"
    sel = st.session_state.get("storage_tip_selected")
    if sel and sel in STORAGE_BUTTONS:
        st.markdown(f"**{sel}**")
        st.write(STORAGE_BUTTONS[sel])

# Режим рецепта: контент и кнопки (на главной они уже в results_anchor)
if ui_mode == "recipe" and response and response.messages:
    _skip_recipe = lambda m: (m.text or "").strip().startswith("Я понял:") or (m.text or "").strip() == "Можно из этого."
    _filtered_recipe = [m for m in response.messages if not _skip_recipe(m)]
    recipe_id = (st.session_state.get("state") or {}).get("last_recipe_id")
    photo_path = resolve_photo_path(recipe_id) if recipe_id else None
    recipe_msgs = _filtered_recipe[:-1] if len(_filtered_recipe) > 1 else _filtered_recipe
    phrase_msg = _filtered_recipe[-1] if len(_filtered_recipe) > 1 else None
    if not recipe_msgs:
        recipe_msgs = _filtered_recipe
        phrase_msg = None
    st.markdown('<span id="os-recipe-card-marker"></span>', unsafe_allow_html=True)
    if photo_path:
        st.image(photo_path, width="stretch")
    _render_recipe_card(recipe_msgs)
    if phrase_msg:
        st.markdown(_strip_html(phrase_msg.text))
if ui_mode == "recipe" and response and response.actions:
    for action in response.actions:
        if action.id.startswith("recipe:"):
            continue
        if action.id == "ozvuchit" or ("озвуч" in (action.label or "").lower()):
            continue
        if st.button(action.label, key=action.id):
            action_clicked_id = action.id
            break

# Обработка кликов по кнопкам (результаты и кнопки рендерятся в results_anchor выше)
if action_clicked_id is not None:
    resp = handle_event({
        "user_key": "web:local",
        "channel": "web",
        "text_input": "",
        "action_id": action_clicked_id,
        "state": st.session_state.get("state"),
    })
    if action_clicked_id and action_clicked_id.startswith("recipe:"):
        _rid = action_clicked_id[7:]
        _r_info = _get_recipe_by_id(_rid)
        _log_analytics("recipe_open", "web", recipe_id=_rid, event_value=(_r_info.get("title_ru") or "")[:200] if _r_info else None, db_path=_ANALYTICS_DB)
    st.session_state["state"] = {**st.session_state["state"], **resp.state_patch}
    st.session_state["last_response"] = _response_to_dict(resp)
    st.rerun()

if ui_mode == "recipe" or (response and response.actions):
    if st.button("Начать заново", key="start_over"):
        resp = handle_event({
            "user_key": "web:local",
            "channel": "web",
            "text_input": "",
            "action_id": "reset",
            "state": st.session_state.get("state"),
        })
        st.session_state["state"] = {**st.session_state["state"], **resp.state_patch}
        st.session_state["last_response"] = _response_to_dict(resp)
        st.rerun()

# SEO-блок внизу только на главной
if ui_mode in ("search", "results"):
    with st.expander("О проекте"):
        st.write(
            "«Остатки сладки» — подбор рецептов по ингредиентам в стиле венской кухни. "
            "Рецепты на каждый день и рецепты из простых продуктов: что приготовить быстро и просто, ужин из простых продуктов без похода в магазин. "
            "Венская кухня: супы, запеканки, салаты и десерты, которые легко повторить дома. "
            "Введите один ингредиент — получите подборку вариантов."
        )
