import asyncio
import logging
import random
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramBadRequest
from typing import Dict, Any
import os

# =======================
# ===== CONFIG ==========
# =======================

TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 6584350034

# Лимиты для разных режимов
USER_LIMITS = {"короткий": 13, "обычный": 10, "спокойный": 15, "умный": 3}

chat_style: Dict[int, str] = {}
chat_memory: Dict[int, Dict[str, Any]] = {}
user_requests_count: Dict[int, Dict[str, int]] = {}
user_last_messages: Dict[int, str] = {}
user_modes: Dict[int, str] = {}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# =======================
# ===== EMOJIS ==========
# =======================
emojis = {
    "friendly": ["💡", "👍", "👌", "🎯", "⚡", "🔍", "💫", "🌟"],
    "serious": ["💭", "📚", "🎯", "⚡", "🔍", "📊", "💡", "🎓"],
    "balanced": ["💡", "👍", "🎯", "⚡", "💫", "🌟", "🔍"]
}

def get_emoji(style: str = "balanced") -> str:
    return random.choice(emojis.get(style, emojis["balanced"]))

# =======================
# ===== КЛАВИАТУРЫ =====
# =======================
def get_main_keyboard(chat_id: int) -> ReplyKeyboardMarkup:
    buttons = [[
        KeyboardButton(text="🚀 Старт"),
        KeyboardButton(text="ℹ️ Обо мне")
    ],
               [
                   KeyboardButton(text="⚙️ Настройки"),
                   KeyboardButton(text="❓ Помощь")
               ]]
    if chat_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="👑 Админ")])
    return ReplyKeyboardMarkup(keyboard=buttons,
                               resize_keyboard=True,
                               input_field_placeholder="Выберите действие...")

def get_settings_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="🎭 Режимы"),
        KeyboardButton(text="📊 Статистика")
    ], [KeyboardButton(text="⬅️ Назад")]],
                               resize_keyboard=True)

# =======================
# ===== СПЕЦИАЛЬНЫЕ ОТВЕТЫ =====
# =======================
SPECIAL_RESPONSES = {
    "кто ты": "Я твой Telegram бот! 🤖",
    "привет": "Привет! Рад тебя видеть! 😊",
    "как дела": "Всё отлично, работаю 24/7! 💪",
    "спасибо": "Всегда рад помочь! ❤️",
    "пока": "До скорой встречи! 👋"
}

def get_mode_description(mode: str) -> str:
    descriptions = {
        "спокойный": "🧘 Спокойный режим (15 запросов)",
        "обычный": "💬 Обычный режим (10 запросов)",
        "короткий": "⚡ Короткий режим (13 запросов)",
        "умный": "🧠 Умный режим (3 запроса)"
    }
    return descriptions.get(mode, "💬 Обычный режим")

def get_user_remaining_requests(chat_id: int, mode: str) -> int:
    if chat_id not in user_requests_count:
        user_requests_count[chat_id] = {}
    if mode not in user_requests_count[chat_id]:
        user_requests_count[chat_id][mode] = 0
    return USER_LIMITS[mode] - user_requests_count[chat_id][mode]

# =======================
# ===== КОМАНДЫ =========
# =======================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    user_modes[chat_id] = "обычный"
    
    if chat_id not in user_requests_count:
        user_requests_count[chat_id] = {}
    for mode in USER_LIMITS.keys():
        if mode not in user_requests_count[chat_id]:
            user_requests_count[chat_id][mode] = 0

    current_mode = user_modes[chat_id]
    remaining = get_user_remaining_requests(chat_id, current_mode)

    welcome_text = (
        "🌟 *Добро пожаловать!* 🌟\n\n"
        "Я - твой Telegram бот, работающий 24/7!\n\n"
        f"📊 *Режим:* {get_mode_description(current_mode)}\n"
        f"🔄 *Осталось запросов:* {remaining}\n\n"
        "Выбери действие 👇")

    await message.answer(welcome_text,
                         parse_mode="Markdown",
                         reply_markup=get_main_keyboard(chat_id))

@dp.message(F.text.in_(["🚀 Старт", "ℹ️ Обо мне", "⚙️ Настройки", "❓ Помощь"]))
async def handle_buttons(message: types.Message):
    text = message.text
    chat_id = message.chat.id

    if text == "🚀 Старт":
        await cmd_start(message)
    elif text == "ℹ️ Обо мне":
        await message.answer("🤖 Я - твой личный бот!\nРаботаю 24/7 на Railway! 🚀")
    elif text == "⚙️ Настройки":
        await message.answer("⚙️ Настройки:", reply_markup=get_settings_keyboard())
    elif text == "❓ Помощь":
        await message.answer("❓ Просто напиши мне что-нибудь!")

@dp.message(F.text.in_(["🎭 Режимы", "📊 Статистика"]))
async def handle_settings(message: types.Message):
    text = message.text
    chat_id = message.chat.id

    if text == "🎭 Режимы":
        current_mode = user_modes.get(chat_id, "обычный")
        remaining = get_user_remaining_requests(chat_id, current_mode)
        mode_text = (f"🎭 Твой режим: {get_mode_description(current_mode)}\n"
                    f"🔄 Осталось запросов: {remaining}")
        await message.answer(mode_text)
    elif text == "📊 Статистика":
        current_mode = user_modes.get(chat_id, "обычный")
        used = user_requests_count.get(chat_id, {}).get(current_mode, 0)
        stats_text = (f"📊 Статистика:\n"
                     f"• Режим: {current_mode}\n"
                     f"• Использовано: {used}\n"
                     f"• Осталось: {get_user_remaining_requests(chat_id, current_mode)}")
        await message.answer(stats_text)

@dp.message(F.text == "⬅️ Назад")
async def handle_back(message: types.Message):
    await message.answer("Главное меню", reply_markup=get_main_keyboard(message.chat.id))

# =======================
# ===== ОСНОВНОЙ ХЭНДЛЕР =====
# =======================
@dp.message()
async def main_handler(message: types.Message):
    chat_id = message.chat.id
    user_text = (message.text or "").strip()
    mode = user_modes.get(chat_id, "обычный")

    if not user_text:
        return

    if user_text.startswith("/"):
        return

    # Лимит запросов
    if chat_id != ADMIN_ID:
        if chat_id not in user_requests_count:
            user_requests_count[chat_id] = {}
        if mode not in user_requests_count[chat_id]:
            user_requests_count[chat_id][mode] = 0

        remaining = get_user_remaining_requests(chat_id, mode)
        if remaining <= 0:
            await message.answer("⚠️ Лимит запросов исчерпан!")
            return

        user_requests_count[chat_id][mode] += 1

    # Специальные ответы
    user_text_lower = user_text.lower().strip()
    for key, value in SPECIAL_RESPONSES.items():
        if key in user_text_lower:
            await message.answer(value)
            return

    # Обычный ответ
    responses = [
        f"Ты сказал: '{user_text}' 👍",
        f"Получил твое сообщение: '{user_text}' 💫",
        f"Запомнил: '{user_text}' 🎯"
    ]
    await message.answer(random.choice(responses))

# =======================
# ===== RUN BOT =========
# =======================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("🚀 Бот запущен и работает 24/7!")
    asyncio.run(main())
