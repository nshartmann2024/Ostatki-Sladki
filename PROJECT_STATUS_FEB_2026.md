# PROJECT STATUS — FEB 2026 (UPDATED)

## PROJECT OVERVIEW

**Остатки сладки** — подбор рецептов по одному ингредиенту в стиле венской домашней кухни. Пользователь вводит ингредиент (или нажимает быструю кнопку) и получает список рецептов; можно открыть рецепт и вернуться к поиску.

- **Публичный сайт:** https://ostatki-sladki.streamlit.app  
- **Репозиторий GitHub:** nshartmann2024/Ostatki-Sladki  
- **База данных:** SQLite `db/app.db`  
- **Entry point Streamlit:** `adapters/web/app.py`  

На сайте: главный заголовок, описание концепции, поиск по ингредиенту, быстрые кнопки ингредиентов, SEO-страницы ингредиентов по URL, sidebar популярных рецептов, блок Telegram, блок хранения продуктов, блок «О проекте».

---

## CURRENT STATUS (кратко)

**Реализовано:** поиск по форме, SEO-страницы по `?ingredient=...`, кнопки «Что приготовить из…» с корректной сменой URL, отображение рецептов и фото, открытие рецепта, нормализация ингредиентов (canonical / NORMALIZE_WORDS), sitemap по `?sitemap=1`, аналитика.

**Проблема URL и поиск:** при вводе нового ингредиента в поиске контент меняется, но URL может оставаться старым из‑за особенностей `st.experimental_set_query_params` и `st.rerun()`. В коде: убран `set_query_params` из submit run, установка URL перенесена в следующий run (`force_results_mode`, `last_search_query`). Логика корректна, но Streamlit не гарантирует обновление URL. **Решение:** считаем допустимым; SEO опирается на прямые ссылки `?ingredient=картофель` и т.д.; поиск — внутренняя функция, не обязана менять URL.

**Приоритеты дальше:** 1) sitemap.xml (уже есть по `?sitemap=1`), 2) Google Search Console, 3) Яндекс Вебмастер, 4) дальнейшее SEO-расширение.

---

## CURRENT DEPLOYMENT STATUS

- Git установлен и настроен на Windows; локальный репозиторий инициализирован.
- Выполнен первый commit проекта.
- Создан GitHub-репозиторий **nshartmann2024/Ostatki-Sladki**, код загружен.
- Проект опубликован в **Streamlit Community Cloud**.  
  Публичный URL: **https://ostatki-sladki.streamlit.app**

---

## ARCHITECTURE

- **Core** остаётся platform-independent (логика в `core/core_engine.py`). Telegram и Web — тонкие adapters: вызывают `handle_event()`, отображают `ResponsePlan`. Контракт ResponsePlan не менялся (messages, actions, state_patch, ui_mode, ui_hints).
- **БД:** SQLite `db/app.db`. Канонические ингредиенты и алиасы — `data/ingredients_canonical.json`. Seed рецептов — `data/recipes_seed_min.json`, импорт через `db/init_db.py`.
- **Поиск:** по одному каноническому ингредиенту; `normalize_input()` с токенизацией фразы; canonical + aliases; поиск по `must_have_json`. Поддержка фраз («отварной картофель» → «картофель» и т.д.). В Web перед вызовом core применяется `NORMALIZE_WORDS`.
- **Web (Streamlit):** карточка рецепта через маркер `#os-recipe-card-marker` и CSS; фото через `resolve_photo_path()` и `PROJECT_ROOT` / `PHOTO_DIR`; результаты сразу под формой поиска в `results_anchor`.
- **Telegram:** та же логика через core; state в памяти; кнопка «Озвучить (скоро)» временно скрыта в UI.
- **Ограничения MVP:** поиск только по одному ингредиенту; нет морфологии, стоп-слов, комбинированного поиска (AND/OR); Telegram state не персистентный.

---

## ANALYTICS SYSTEM

В проект добавлена внутренняя продуктовая аналитика без внешних сервисов.

- **Helper:** `db/analytics.py`  
  - `log_event(event_type, channel, event_value=..., recipe_id=..., db_path=...)` — запись события в SQLite.  
  - `ensure_analytics_schema(conn)` — создание таблицы при первом использовании (без удаления данных).

- **Таблица:** `analytics_events`  
  Поля: `id`, `event_type`, `event_value`, `recipe_id`, `channel`, `created_at`.

- **Типы событий:**  
  `search_submit`, `ingredient_click`, `recipe_open`, `telegram_click`.

- **Источники записей:** Web (Streamlit) и Telegram bot.

- **Отчёт:** `scripts/analytics_report.py`  
  Запуск: `python scripts/analytics_report.py`  
  Показывает: активность по периодам (сегодня / 7 / 30 дней), топ поисков, топ быстрых ингредиентов, топ открытых рецептов, клики Telegram, последние события. Статистика подтверждена как рабочая.

---

## DEPLOYMENT PIPELINE

**Local development → Git → GitHub → Streamlit Cloud**

- Локальная разработка и тесты (Web: `streamlit run adapters/web/app.py`; Telegram: `python adapters/telegram/bot.py`).
- Коммиты в локальный Git, push в репозиторий **nshartmann2024/Ostatki-Sladki** на GitHub.
- Деплой через Streamlit Community Cloud с entry point `adapters/web/app.py`; публичный сайт обновляется из ветки репозитория.

---

## NEXT STEPS / TODO (приоритеты)

1. **Sitemap:** реализован по `?sitemap=1`; при необходимости — статический файл через `scripts/generate_sitemap.py`.
2. **Google Search Console** — подключить и проверить индексацию.
3. **Яндекс Вебмастер** — подключить и проверить индексацию.
4. **SEO-расширение** — развивать страницы ингредиентов, мета-теги при необходимости.
5. По необходимости: стоп-слова или алиасы; поиск по двум ингредиентам (AND); персистентный state для Telegram.

---

## База рецептов

- **Всего рецептов в БД:** 32.
- **Последние добавленные (7 рецептов по порядку в seed):**  
  Erdaepfelkrapferl — Розетки из остатков пюре; Topfenweckerl — Творожные булочки из остатков; Topfenauflauf süß — Запеканка из творога и подсохшего сладкого хлеба; Restltopf Auflauf — Запеканка из мясных и овощных остатков; Knoblauchsuppe — Чесночный суп; Käsesuppe — Сырный суп из остатков; Topfenaufstrich bunt — Разноцветные намазки из творога.

---

## Формат взаимодействия с ChatGPT / Cursor

1. Инструкции агенту оформляются в блоке «промт для курсор».
2. Кодовые вставки — по языку (python, json и т.д.).
3. Немецкий — только в title рецепта; интерфейс полностью русский.
4. difficulty только: «Просто», «Средне», «Сложно».
5. Алиасы — только русские слова.

**Дата обновления:** февраль 2026.
