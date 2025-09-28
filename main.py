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
from mistralai import Mistral

# =======================
# ===== CONFIG ==========
# =======================
mistral_api_key = os.getenv('MISTRAL_API_KEY', 'nIMvGkfioIpMtQeSO2n8ssm6nuJRyo7Q')
openweather_api_key = os.getenv('OPENWEATHER_API_KEY', 'dbd08a834f628d369a8edb55b210171e')
TOKEN = os.getenv('BOT_TOKEN', '8229856813:AAEkQq-4zdJKAmovgq69URcqKDzN4_BMqrw')

ADMIN_ID = 6584350034

# Лимиты для разных режимов
USER_LIMITS = {"короткий": 13, "обычный": 10, "спокойный": 15, "умный": 3}

model = "mistral-large-latest"
client = Mistral(api_key=mistral_api_key)

chat_style: Dict[int, str] = {}
chat_memory: Dict[int, Dict[str, Any]] = {}
user_requests_count: Dict[int, Dict[str, int]] = {}
user_last_messages: Dict[int, str] = {}
user_modes: Dict[int, str] = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                   KeyboardButton(text="❓ Помощь"),
                   KeyboardButton(text="🌤 Погода")
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

def get_mode_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="🧘 Спокойный (15)"),
            KeyboardButton(text="💬 Обычный (10)")
        ],
                  [
                      KeyboardButton(text="⚡ Короткий (13)"),
                      KeyboardButton(text="🧠 Умный (3)")
                  ], [KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True)

def get_weather_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="Новосибирск"),
        KeyboardButton(text="Москва")
    ], [
        KeyboardButton(text="Санкт-Петербург"),
        KeyboardButton(text="⬅️ Назад")
    ]],
                               resize_keyboard=True)

# =======================
# ===== СПЕЦИАЛЬНЫЕ ОТВЕТЫ =====
# =======================
SPECIAL_RESPONSES = {
    "кто ты": "Я твой личный AI-помощник на Mistral AI! 🤖✨",
    "привет": "Привет! Рад тебя видеть! 😊",
    "как дела": "Всё отлично, работаю 24/7 на Railway! 💪",
    "спасибо": "Всегда рад помочь! ❤️",
    "пока": "До скорой встречи! 👋",
    "шутка": "Почему программист всегда ходит в душ с телефоном? Потому что там нужно следовать инструкциям step by step! 😄"
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
# ===== ФОРМАТ ОТВЕТОВ =====
# =======================
def format_ai_response(text: str, style: str, mode: str) -> str:
    emoji = get_emoji(style)
    formatted = text.strip()

    if mode == "короткий":
        sentences = formatted.split('. ')
        if len(sentences) > 2:
            formatted = '. '.join(sentences[:2]) + '.'
    elif mode == "спокойный":
        calm_emojis = ["🌿", "🍃", "🌼", "🌸", "💮", "🪷"]
        if random.random() > 0.7:
            formatted = f"{random.choice(calm_emojis)} {formatted}"

    return f"{emoji} {formatted}"

async def send_long_message(message: types.Message, text: str, style: str = "balanced", mode: str = "обычный", chunk_size: int = 4000):
    formatted = format_ai_response(text, style, mode)
    for i in range(0, len(formatted), chunk_size):
        try:
            await message.answer(formatted[i:i + chunk_size])
        except TelegramBadRequest:
            await message.answer(text[i:i + chunk_size])

# =======================
# ===== ПОГОДА =====
# =======================
async def get_weather(city: str) -> str:
    city_clean = city.strip()
    if not city_clean:
        return "❓ Укажите город: например, 'Новосибирск'"

    city_mapping = {
        "новосибирск": "Novosibirsk",
        "москва": "Moscow", 
        "санкт-петербург": "Saint Petersburg",
        "спб": "Saint Petersburg",
        "питер": "Saint Petersburg"
    }

    api_city = city_mapping.get(city_clean.lower(), city_clean)

    url = f"http://api.openweathermap.org/data/2.5/weather?q={api_city}&appid={openweather_api_key}&units=metric&lang=ru"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return f"⚠️ Не удалось получить погоду для '{city_clean}'. Проверьте название города."
                data = await resp.json()
                temp = data["main"]["temp"]
                feels = data["main"]["feels_like"]
                desc = data["weather"][0]["description"]
                humidity = data["main"]["humidity"]
                wind_speed = data["wind"]["speed"]
                return (f"🌤 Погода в {city_clean.title()}:\n"
                        f"• Температура: {temp}°C\n"
                        f"• Ощущается как: {feels}°C\n"
                        f"• Описание: {desc}\n"
                        f"• Влажность: {humidity}%\n"
                        f"• Ветер: {wind_speed} м/с")
    except Exception as e:
        logger.error(f"Ошибка при получении погоды: {e}")
        return f"⚠️ Ошибка при получении данных о погоде для '{city_clean}'."

# =======================
# ===== КОМАНДЫ =========
# =======================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    chat_style[chat_id] = "balanced"
    user_modes[chat_id] = "обычный"

    if chat_id not in user_requests_count:
        user_requests_count[chat_id] = {}
    for mode in USER_LIMITS.keys():
        if mode not in user_requests_count[chat_id]:
            user_requests_count[chat_id][mode] = 0

    chat_memory.setdefault(chat_id, {"current_topic": None, "topics": {}})

    current_mode = user_modes[chat_id]
    remaining = get_user_remaining_requests(chat_id, current_mode)

    welcome_text = (
        "🌟 *Добро пожаловать!* 🌟\n\n"
        "Я - твой Telegram бот с Mistral AI, работающий 24/7 на Railway!\n\n"
        f"📊 *Режим:* {get_mode_description(current_mode)}\n"
        f"🔄 *Осталось запросов:* {remaining}\n\n"
        "Выбери действие 👇")

    await message.answer(welcome_text,
                         reply_markup=get_main_keyboard(chat_id))

@dp.message(Command("style"))
async def cmd_style(message: types.Message):
    current_style = chat_style.get(message.chat.id, "balanced")
    style_text = ("⚙️ *Настройки стиля:*\n\n"
                  f"Текущий: {get_style_name(current_style)}\n\n"
                  "Варианты:\n"
                  "• /style_balanced - сбалансированный\n"
                  "• /style_serious - деловой\n"
                  "• /style_friendly - неформальный")
    await message.answer(style_text, parse_mode="Markdown")

@dp.message(Command("style_friendly"))
async def cmd_style_friendly(message: types.Message):
    chat_style[message.chat.id] = "friendly"
    await message.answer("💫 Стиль изменён на неформальный",
                         reply_markup=get_main_keyboard(message.chat.id))

@dp.message(Command("style_balanced"))
async def cmd_style_balanced(message: types.Message):
    chat_style[message.chat.id] = "balanced"
    await message.answer("⚖️ Стиль изменён на сбалансированный",
                         reply_markup=get_main_keyboard(message.chat.id))

@dp.message(Command("style_serious"))
async def cmd_style_serious(message: types.Message):
    chat_style[message.chat.id] = "serious"
    await message.answer("🎯 Стиль изменён на деловой",
                         reply_markup=get_main_keyboard(message.chat.id))

@dp.message(Command("view_memory"))
async def view_memory(message: types.Message):
    if message.chat.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора.")
        return
    memory = chat_memory.get(message.chat.id, {"topics": {}})
    await message.answer(f"🧠 Память: {memory}")

@dp.message(Command("clear_memory"))
async def clear_memory(message: types.Message):
    if message.chat.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора.")
        return
    chat_memory[message.chat.id] = {"current_topic": None, "topics": {}}
    await message.answer("✅ Память очищена.")

@dp.message(Command("reset_user"))
async def reset_user(message: types.Message):
    if message.chat.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора.")
        return
    chat_memory.clear()
    user_requests_count.clear()
    user_last_messages.clear()
    user_modes.clear()
    await message.answer("✅ Все пользователи сброшены.")

# =======================
# ===== ОБРАБОТКА КНОПОК =====
# =======================
@dp.message(F.text.in_(["🚀 Старт", "ℹ️ Обо мне", "⚙️ Настройки", "❓ Помощь", "🌤 Погода", "👑 Админ"]))
async def handle_main_buttons(message: types.Message):
    text = message.text
    chat_id = message.chat.id

    if text == "🌤 Погода":
        await message.answer("Выберите город для погоды:",
                             reply_markup=get_weather_keyboard())
    elif text == "🚀 Старт":
        await cmd_start(message)
    elif text == "ℹ️ Обо мне":
        about_text = ("🤖 *Обо мне*\n\n"
                      "Я - современный AI-помощник на Mistral AI! 🚀\n\n"
                      "🌟 *Доступные режимы:*\n"
                      "• 🧘 Спокойный - 15 запросов\n"
                      "• 💬 Обычный - 10 запросов\n"
                      "• ⚡ Короткий - 13 запросов\n"
                      "• 🧠 Умный - 3 запроса\n\n"
                      "Работаю 24/7 на Railway! ✨")
        await message.answer(about_text,
                             reply_markup=get_main_keyboard(chat_id))
    elif text == "⚙️ Настройки":
        await message.answer("⚙️ Настройки:", 
                             reply_markup=get_settings_keyboard())
    elif text == "❓ Помощь":
        current_mode = user_modes.get(chat_id, "обычный")
        remaining = get_user_remaining_requests(chat_id, current_mode)
        help_text = ("❓ *Помощь*\n\n"
                     "Просто напиши мне что-нибудь и я отвечу!\n"
                     "Также могу помочь с:\n"
                     "• Ответами на вопросы\n" 
                     "• Генерацией текстов\n"
                     "• Анализом контента\n\n"
                     f"📊 Твой режим: {current_mode}\n"
                     f"🔄 Осталось запросов: {remaining}")
        await message.answer(help_text,
                             reply_markup=get_main_keyboard(chat_id))
    elif text == "👑 Админ" and chat_id == ADMIN_ID:
        await message.answer("👑 Админ панель\n\n"
                            "Доступные команды:\n"
                            "/stats - статистика\n"
                            "/reset - сброс данных",
                            reply_markup=get_main_keyboard(chat_id))

@dp.message(F.text.in_(["🎭 Режимы", "📊 Статистика"]))
async def handle_settings_buttons(message: types.Message):
    text = message.text
    chat_id = message.chat.id

    if text == "🎭 Режимы":
        current_mode = user_modes.get(chat_id, "обычный")
        remaining = get_user_remaining_requests(chat_id, current_mode)
        mode_text = (f"🎭 Твой режим: {get_mode_description(current_mode)}\n"
                    f"🔄 Осталось запросов: {remaining}\n\n"
                    "Выбери новый режим:")
        await message.answer(mode_text,
                             reply_markup=get_mode_keyboard())
    elif text == "📊 Статистика":
        current_mode = user_modes.get(chat_id, "обычный")
        used = user_requests_count.get(chat_id, {}).get(current_mode, 0)
        stats_text = (f"📊 Статистика:\n"
                     f"• Режим: {current_mode}\n"
                     f"• Использовано: {used}\n"
                     f"• Осталось: {get_user_remaining_requests(chat_id, current_mode)}")
        await message.answer(stats_text)

@dp.message(F.text.in_(["🧘 Спокойный (15)", "💬 Обычный (10)", "⚡ Короткий (13)", "🧠 Умный (3)"]))
async def handle_mode_buttons(message: types.Message):
    chat_id = message.chat.id
    text = str(message.text or "")

    mode_mapping = {
        "🧘 Спокойный (15)": "спокойный",
        "💬 Обычный (10)": "обычный", 
        "⚡ Короткий (13)": "короткий",
        "🧠 Умный (3)": "умный"
    }

    new_mode = mode_mapping.get(text, "обычный")
    user_modes[chat_id] = new_mode

    if chat_id not in user_requests_count:
        user_requests_count[chat_id] = {}
    if new_mode not in user_requests_count[chat_id]:
        user_requests_count[chat_id][new_mode] = 0

    remaining = get_user_remaining_requests(chat_id, new_mode)

    success_text = (f"✅ Режим изменен на {get_mode_description(new_mode)}\n"
                   f"🔄 Осталось запросов: {remaining}")
    await message.answer(success_text,
                         reply_markup=get_settings_keyboard())

@dp.message(F.text.in_(["Новосибирск", "Москва", "Санкт-Петербург"]))
async def send_weather_city(message: types.Message):
    try:
        city = str(message.text)
        weather = await get_weather(city)
        await message.answer(weather,
                             reply_markup=get_main_keyboard(message.chat.id))
    except Exception as e:
        logger.error(f"Ошибка в send_weather_city: {e}")
        await message.answer("⚠️ Ошибка при получении погоды",
                             reply_markup=get_main_keyboard(message.chat.id))

@dp.message(F.text == "⬅️ Назад")
async def handle_back(message: types.Message):
    await message.answer("Главное меню", 
                         reply_markup=get_main_keyboard(message.chat.id))

# =======================
# ===== АДМИН КОМАНДЫ ====
# =======================
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    total_users = len(user_requests_count)
    stats_text = f"📊 Статистика бота:\n• Пользователей: {total_users}"
    await message.answer(stats_text)

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    user_requests_count.clear()
    user_modes.clear()
    await message.answer("✅ Данные сброшены")

def get_style_name(style: str) -> str:
    names = {
        "friendly": "Неформальный 💫",
        "balanced": "Сбалансированный ⚖️",
        "serious": "Деловой 🎯"
    }
    return names.get(style, "Сбалансированный ⚖️")

# =======================
# ===== ОСНОВНОЙ ХЭНДЛЕР =====
# =======================
@dp.message()
async def main_handler(message: types.Message):
    chat_id = message.chat.id
    user_text = (message.text or "").strip()
    style = chat_style.get(chat_id, "balanced")
    mode = user_modes.get(chat_id, "обычный")

    if not user_text:
        await message.answer("❌ Пожалуйста, отправь текстовое сообщение.")
        return

    if user_text.startswith("/"):
        return

    # Лимит пользователей (админы без лимита)
    if chat_id != ADMIN_ID:
        if chat_id not in user_requests_count:
            user_requests_count[chat_id] = {}
        if mode not in user_requests_count[chat_id]:
            user_requests_count[chat_id][mode] = 0

        remaining = get_user_remaining_requests(chat_id, mode)

        if remaining <= 0:
            await message.answer(
                f"⚠️ Лимит исчерпан!\n\n"
                f"Режим: {mode}\n"
                f"Лимит: {USER_LIMITS[mode]} запросов\n\n"
                "⚡ Попробуй другой режим в настройках!")
            return

        user_requests_count[chat_id][mode] += 1

    # Специальные ответы
    user_text_lower = user_text.lower().strip()

    if user_text_lower in ["пока", "до свидания", "до связи"]:
        await message.answer("До скорой встречи! 👋")
        return

    special_found = False
    for key, value in SPECIAL_RESPONSES.items():
        if key in user_text_lower and key != "пока":
            await message.answer(value)
            special_found = True
            break

    if special_found:
        return

    # Погода через текст
    if any(word in user_text_lower for word in ["погода", "погоду", "температура"]):
        city = user_text_lower
        for w in ["погода", "погоду", "температура", "в", "какая", "какой"]:
            city = city.replace(w, "").strip()
        city = city.replace(",", "").strip()

        if not city:
            await message.answer("❓ Укажите город, например: 'погода Москва'")
            return

        weather = await get_weather(city)
        await message.answer(weather)
        return

    # Общение с AI
    try:
        system_prompts = {
            "спокойный": "Ты спокойный и расслабленный AI-помощник. Отвечай мягко и дружелюбно.",
            "обычный": "Ты умный и креативный AI-помощник, который отлично разбирается в текстах.",
            "короткий": "Ты мастер кратких ответов. Отвечай максимально лаконично, сохраняя суть.",
            "умный": "Ты эксперт AI-помощник с глубокими знаниями. Анализируй вопросы тщательно и давай развернутые ответы."
        }

        system_prompt = system_prompts.get(mode, "Ты умный и креативный AI-помощник.")
        user_content = user_text

        # Обработка reply-сообщений
        if message.reply_to_message and message.reply_to_message.text:
            replied_text = message.reply_to_message.text

            if any(w in user_text_lower for w in [
                    "доработать", "улучшить", "усовершенствовать", "покруче",
                    "посоветуй", "варианты", "версии"
            ]):
                system_prompt = "Ты эксперт по улучшению текстов. Проанализируй текст и предложи конкретные варианты доработки."
                user_content = f"Предложи варианты улучшения этого текста: {replied_text}"

            elif any(w in user_text_lower for w in ["сократи", "сделай короче", "укороти", "кратко", "короче"]):
                system_prompt = "Ты мастер сокращения текстов. Сохраняй основную суть и ключевые идеи."
                user_content = f"Сократи этот текст: {replied_text}"

            elif any(w in user_text_lower for w in [
                    "нормально", "правильно", "исправить", "мнение",
                    "что думаешь", "критика", "совет"
            ]):
                system_prompt = "Ты профессиональный редактор. Дай конструктивную обратную связь по тексту."
                user_content = f"Проанализируй этот текст: {replied_text}. Вопрос: {user_text}"

        response = client.chat.complete(model=model,
                                        messages=[{
                                            "role": "system",
                                            "content": system_prompt
                                        }, {
                                            "role": "user", 
                                            "content": user_content
                                        }])
        ai_text = response.choices[0].message.content

        if not ai_text:
            ai_text = "❌ Не удалось получить ответ"

        await send_long_message(message, str(ai_text), style, mode)

    except Exception as e:
        logger.error(f"Ошибка при запросе к AI: {e}")
        await message.answer("⚠️ Временная ошибка, попробуйте ещё раз.")

# =======================
# ===== RUN BOT =========
# =======================
async def main():
    logger.info("🚀 Запуск бота...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("🚀 Бот запущен и работает 24/7 на Railway!")
    asyncio.run(main())
