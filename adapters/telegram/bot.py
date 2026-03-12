"""
Тонкий Telegram-адаптер (aiogram 3.x): перевод событий в core.handle_event и отображение ResponsePlan.
"""
import asyncio
import logging
import os
import sys

# Уменьшить шум в терминале
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)

# корень проекта для импорта core
_bot_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(os.path.dirname(_bot_dir))
if _root not in sys.path:
    sys.path.insert(0, _root)

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.core_engine import handle_event
from db.analytics import log_event as _log_analytics

# Placeholders to protect <b>/</b> from HTML escaping (single chars unlikely in text)
_HTML_B_OPEN, _HTML_B_CLOSE = "\x01", "\x02"


def _escape_html_keep_b(text: str) -> str:
    """Экранировать &, <, > в тексте, оставляя теги <b> и </b> как есть."""
    if not text:
        return text
    # Сначала убираем теги в «безопасные» плейсхолдеры (сначала </b>, чтобы не задеть внутри <b>)
    t = text.replace("</b>", _HTML_B_CLOSE).replace("<b>", _HTML_B_OPEN)
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = t.replace(_HTML_B_OPEN, "<b>").replace(_HTML_B_CLOSE, "</b>")
    return t

TOKEN = os.environ.get("OS_TG_TOKEN")
if not TOKEN:
    raise SystemExit("Set OS_TG_TOKEN environment variable")

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Хранилище state в памяти (user_key -> dict)
state_store: dict[str, dict] = {}


def _normalize_button_label(label: str, action_id: str) -> str:
    """Обрезать до 36 символов (кроме фиксированных кнопок), капитализация."""
    if not label:
        return label
    label = label.strip()
    if action_id == "more" and label == "Ещё варианты…":
        return label
    if action_id == "back" and label == "← Назад к вариантам":
        return label
    if len(label) > 36:
        label = label[:36].rstrip() + "…"
    label = label[:1].upper() + label[1:] if label else label
    return label


def _reply_markup_from_actions(actions):
    if not actions:
        return None
    kb = InlineKeyboardBuilder()
    for action in actions:
        # временно скрываем кнопку озвучки
        if action.id == "ozvuchit":
            continue
        label = _normalize_button_label(action.label, action.id)
        kb.button(text=label, callback_data=action.id)
    kb.adjust(1)
    return kb.as_markup()


# Технические/отладочные фразы из core — не показывать пользователю, заменять на нейтральные
_TG_SKIP_OR_REPLACE = [
    ("Пока MVP: просто напиши второй ингредиент текстом.", "Введите 1 ингредиент (можно фразой). Например: «отварной картофель», «творог», «белый хлеб», «шоколад»."),
]


def _collect_non_empty_texts(plan):
    """Собрать непустые тексты из plan.messages (без "" и "—"). Технические фразы заменяются на нейтральные."""
    texts = []
    for msg in plan.messages:
        text = (msg.text or "").strip()
        if not text or text == "—":
            continue
        for tech, replacement in _TG_SKIP_OR_REPLACE:
            if tech in text or text == tech:
                text = replacement
                break
        if text:
            texts.append(text)
    return texts


def _get_photo_input(plan):
    """Если в plan есть фото для отправки — вернуть (file_id или FSInputFile), иначе None."""
    hints = plan.ui_hints or {}
    file_id = hints.get("photo_file_id_tg")
    if file_id:
        return file_id
    photo_url = hints.get("photo_url")
    if photo_url:
        path = os.path.join(_root, photo_url)
        if os.path.isfile(path):
            return FSInputFile(path)
    return None


def _related_recipes_markup(related_list):
    """Inline-клавиатура для блока «Похожие рецепты» (кнопки на открытие рецепта по id)."""
    if not related_list:
        return None
    kb = InlineKeyboardBuilder()
    for item in related_list:
        rid = item.get("id")
        title = (item.get("title") or str(rid))[:64]
        kb.button(text=title, callback_data=f"recipe:{rid}")
    kb.adjust(1)
    return kb.as_markup()


async def _send_plan(chat_id: int, plan):
    """Отправить все plan.messages (пустые и прочерки пропускаем) и при наличии actions — inline-клавиатуру. Если есть фото в ui_hints — сначала отправить фото."""
    photo_input = _get_photo_input(plan)
    if photo_input is not None:
        await bot.send_photo(chat_id, photo=photo_input)
    texts = _collect_non_empty_texts(plan)
    reply_markup = _reply_markup_from_actions(plan.actions)
    for i, text in enumerate(texts):
        safe_text = _escape_html_keep_b(text)
        if i == len(texts) - 1 and reply_markup:
            await bot.send_message(chat_id, safe_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id, safe_text, parse_mode=ParseMode.HTML)
    if reply_markup and not texts:
        await bot.send_message(chat_id, " ", reply_markup=reply_markup)
    related_list = (plan.ui_hints or {}).get("related_recipes")
    if related_list:
        related_markup = _related_recipes_markup(related_list)
        if related_markup:
            await bot.send_message(
                chat_id,
                "Похожие рецепты:",
                reply_markup=related_markup,
            )


async def _edit_message_with_plan(callback: CallbackQuery, plan):
    """Редактировать сообщение с callback: один текст из plan.messages + клавиатура. Игнорировать 'message is not modified'."""
    texts = _collect_non_empty_texts(plan)
    text = "\n\n".join(texts) if texts else " "
    safe_text = _escape_html_keep_b(text)
    reply_markup = _reply_markup_from_actions(plan.actions)
    try:
        await callback.message.edit_text(
            safe_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            raise


@router.message(CommandStart())
async def cmd_start(message: Message):
    user_key = f"tg:{message.from_user.id}"
    state_store[user_key] = {}
    await message.answer("Введите 1 ингредиент (можно фразой). Например: «отварной картофель», «творог», «белый хлеб», «шоколад».")


@router.message(F.text)
async def on_text(message: Message):
    user_key = f"tg:{message.from_user.id}"
    state = state_store.get(user_key, {})
    plan = handle_event({
        "user_key": user_key,
        "channel": "telegram",
        "text_input": message.text or "",
        "action_id": None,
        "state": state,
    })
    state_store[user_key] = {**state, **plan.state_patch}
    await _send_plan(message.chat.id, plan)


@router.callback_query()
async def on_callback(callback: CallbackQuery):
    await callback.answer()
    user_key = f"tg:{callback.from_user.id}"
    state = state_store.get(user_key, {})
    plan = handle_event({
        "user_key": user_key,
        "channel": "telegram",
        "text_input": "",
        "action_id": callback.data,
        "state": state,
    })
    state_store[user_key] = {**state, **plan.state_patch}
    data = callback.data or ""
    if data in ("more", "back", "back:first", "another", "add_ingredient"):
        await _edit_message_with_plan(callback, plan)
    else:
        # Выбор рецепта: убрать inline-кнопки у сообщения со списком, чтобы не копились
        if data.startswith("recipe:"):
            _log_analytics("recipe_open", "telegram", recipe_id=data[7:], db_path=os.path.join(_root, "db", "app.db"))
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        await _send_plan(callback.message.chat.id, plan)


async def main():
    delay = 1
    max_delay = 30
    try:
        while True:
            try:
                await dp.start_polling(bot)
                break
            except (TelegramNetworkError, aiohttp.ClientError, TimeoutError) as e:
                logger.warning("Network error, reconnecting in %ds: %s", delay, e)
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
    except asyncio.CancelledError:
        pass
    finally:
        await bot.session.close()
        print("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")