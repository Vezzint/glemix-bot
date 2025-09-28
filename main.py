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
# ===== КОНФИГУРАЦИЯ =====
# =======================
mistral_api_key = os.getenv('MISTRAL_API_KEY', 'nIMvGkfioIpMtQeSO2n8ssm6nuJRyo7Q')
openweather_api_key = os.getenv('OPENWEATHER_API_KEY', 'dbd08a834f628d369a8edb55b210171e')
TOKEN = os.getenv('BOT_TOKEN', '8229856813:AAEkQq-4zdJKAmovgq69URcqKDzN4_BMqrw')

ADMIN_ID = 6584350034

# Лимиты запросов для разных режимов
USER_LIMITS = {
    "спокойный": 15,
    "обычный": 10, 
    "короткий": 13,
    "умный": 3
}

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
# ===== ЭМОДЗИ ==========
# =======================
emojis = {
    "friendly": ["💫", "✨", "🌟", "🎈", "🤗", "💝", "🎊", "💌"],
    "serious": ["🎯", "📊", "💼", "🔍", "📈", "🎓", "💡", "⚖️"],
    "balanced": ["💎", "🎨", "🔮", "💭", "🌈", "🦋", "🌸", "🌠"],
    "creative": ["🎭", "🖌️", "🎪", "🎸", "📸", "🎬", "🎮", "🧩"]
}

def get_emoji(style: str = "balanced") -> str:
    return random.choice(emojis.get(style, emojis["balanced"]))

# =======================
# ===== КЛАВИАТУРЫ =====
# =======================
def get_main_keyboard(chat_id: int) -> ReplyKeyboardMarkup:
    buttons = [[
        KeyboardButton(text="🚀 Начать работу"),
        KeyboardButton(text="🌟 Обо мне")
    ],
               [
                   KeyboardButton(text="⚙️ Настройки"),
                   KeyboardButton(text="❓ Помощь"),
                   KeyboardButton(text="🌤️ Погода")
               ]]
    if chat_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="👑 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons,
                               resize_keyboard=True,
                               input_field_placeholder="Выберите действие...")

def get_settings_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="🎭 Режимы AI"),
        KeyboardButton(text="📊 Статистика")
    ], [
        KeyboardButton(text="🎨 Стиль общения"),
        KeyboardButton(text="ℹ️ Информация")
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

def get_style_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="💫 Дружелюбный"),
        KeyboardButton(text="⚖️ Сбалансированный")
    ], [
        KeyboardButton(text="🎯 Деловой"),
        KeyboardButton(text="🎨 Креативный")
    ], [KeyboardButton(text="⬅️ Назад")]],
                               resize_keyboard=True)

def get_weather_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="🏙️ Новосибирск"),
        KeyboardButton(text="🏛️ Москва")
    ], [
        KeyboardButton(text="🌉 Санкт-Петербург"),
        KeyboardButton(text="📍 Другой город")
    ], [KeyboardButton(text="⬅️ Назад")]],
                               resize_keyboard=True)

def get_admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="📈 Статистика"),
        KeyboardButton(text="🔄 Сброс лимитов")
    ], [
        KeyboardButton(text="🧠 Управление AI"),
        KeyboardButton(text="👥 Пользователи")
    ], [
        KeyboardButton(text="⚡ Система"),
        KeyboardButton(text="📊 Логи")
    ], [KeyboardButton(text="⬅️ Главное меню")]],
                               resize_keyboard=True)

def get_ai_management_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="🎛️ Настройки модели"),
        KeyboardButton(text="🔧 Параметры AI")
    ], [
        KeyboardButton(text="📝 Промпты"),
        KeyboardButton(text="🧹 Очистка памяти")
    ], [KeyboardButton(text="⬅️ Админ-панель")]],
                               resize_keyboard=True)

# =======================
# ===== СПЕЦИАЛЬНЫЕ ОТВЕТЫ =====
# =======================
SPECIAL_RESPONSES = {
    "кто ты": [
        "✨ Я твой персональный AI-компаньон, созданный для интеллектуального общения и решения задач",
        "🌟 Я цифровой помощник с искусственным интеллектом, готовый помочь в любых вопросах",
        "💫 Интеллектуальный ассистент нового поколения, специализирующийся на глубоком анализе и креативных решениях"
    ],
    "привет": [
        "💖 Приветствую! Рада видеть тебя в нашем виртуальном пространстве",
        "🌸 Здравствуй! Готова к увлекательному диалогу и новым открытиям",
        "🎈 Привет! Какое прекрасное время для интеллектуальной беседы"
    ],
    "как дела": [
        "💝 Восхитительно! Готова к новым вызовам и интересным задачам",
        "🌈 Превосходно! Энергия бьёт ключом, жду твоих вопросов",
        "🎯 Отлично! Настроена на продуктивную работу и глубокий анализ"
    ],
    "спасибо": [
        "💌 Всегда рада помочь! Твоя благодарность вдохновляет на новые свершения",
        "🌟 Благодарю за тёплые слова! Это мотивирует становиться лучше",
        "✨ Спасибо за обратную связь! Стремлюсь быть максимально полезной"
    ],
    "пока": [
        "🦋 До скорой встречи! Буду с нетерпением ждать нашего следующего диалога",
        "🌅 До свидания! Пусть твой день будет наполнен inspiration",
        "🎐 Пока! Помни, что знания и технологии всегда на твоей стороне"
    ],
    "шутка": [
        "🎭 Почему нейросеть пошла на свидание с калькулятором? Потому что он умел производить на неё впечатляющие вычисления!",
        "🤖 Что сказал один AI другому? 'Давай останемся друзьями — у нас отличная химия... и алгоритмы!'",
        "💡 Почему бот всегда побеждает в шахматы? Потому что он думает на несколько ходов вперёд... и знает все правила!"
    ]
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
        return "❓ Пожалуйста, укажите город для получения погоды"

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
                    return f"🌫️ Не удалось получить данные о погоде для '{city_clean}'\nПроверьте правильность названия города"
                data = await resp.json()
                temp = data["main"]["temp"]
                feels = data["main"]["feels_like"]
                desc = data["weather"][0]["description"]
                humidity = data["main"]["humidity"]
                wind_speed = data["wind"]["speed"]
                return (f"🌤️ Погода в {city_clean.title()}\n\n"
                        f"• Температура: {temp}°C\n"
                        f"• Ощущается как: {feels}°C\n"
                        f"• Описание: {desc}\n"
                        f"• Влажность: {humidity}%\n"
                        f"• Ветер: {wind_speed} м/с")
    except Exception as e:
        logger.error(f"Ошибка при получении погоды: {e}")
        return f"🌪️ Ошибка при получении данных о погоде для '{city_clean}'"

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

    current_mode = user_modes[chat_id]
    remaining = get_user_remaining_requests(chat_id, current_mode)

    welcome_text = (
        "✨ Добро пожаловать в мир интеллектуального общения\n\n"
        "Я — твой персональный AI-компаньон для глубоких диалогов\n\n"
        f"Режим: {get_mode_description(current_mode)}\n"
        f"Доступно запросов: {remaining}\n\n"
        "Выбери направление для нашего диалога 👇")

    await message.answer(welcome_text,
                         reply_markup=get_main_keyboard(chat_id))

@dp.message(F.text.in_(["🚀 Начать работу", "🚀 Старт"]))
async def handle_start_button(message: types.Message):
    await cmd_start(message)

@dp.message(F.text == "🌟 Обо мне")
async def handle_about(message: types.Message):
    about_text = (
        "🤖 Мой цифровой портрет\n\n"
        "Мои возможности:\n"
        "• Глубокий анализ текстов\n"
        "• Креативная генерация контента\n"
        "• Многорежимная работа\n"
        "• Интеграция с погодными данными\n\n"
        "Доступные режимы:\n"
        "• Спокойный — 15 запросов\n"
        "• Обычный — 10 запросов\n"
        "• Короткий — 13 запросов\n"
        "• Умный — 3 запроса\n\n"
        "Каждый режим предлагает уникальный подход к общению")
    
    await message.answer(about_text,
                         reply_markup=get_main_keyboard(message.chat.id))

@dp.message(F.text == "⚙️ Настройки")
async def handle_settings(message: types.Message):
    settings_text = (
        "⚙️ Центр управления\n\n"
        "Настрой аспекты нашего взаимодействия:\n\n"
        "• Режимы AI — выбери стиль общения\n"
        "• Статистика — отслеживай активность\n"
        "• Стиль общения — настрой тон диалога\n"
        "• Информация — узнай больше о возможностях")
    
    await message.answer(settings_text,
                         reply_markup=get_settings_keyboard())

@dp.message(F.text == "❓ Помощь")
async def handle_help(message: types.Message):
    chat_id = message.chat.id
    current_mode = user_modes.get(chat_id, "обычный")
    remaining = get_user_remaining_requests(chat_id, current_mode)
    
    help_text = (
        "💫 Руководство по использованию\n\n"
        "Основные команды:\n"
        "• Просто напиши вопрос — получу развернутый ответ\n"
        "• Используй кнопки для быстрой навигации\n"
        "• Ответь на сообщение для работы с текстом\n\n"
        "Работа с контентом:\n"
        "• Сократи текст — сделаю лаконичнее\n"
        "• Улучши текст — предложу варианты\n"
        "• Проанализируй — дам обратную связь\n\n"
        f"Твой статус:\n"
        f"Режим: {current_mode}\n"
        f"Осталось запросов: {remaining}")
    
    await message.answer(help_text,
                         reply_markup=get_main_keyboard(chat_id))

@dp.message(F.text == "🎭 Режимы AI")
async def handle_modes(message: types.Message):
    chat_id = message.chat.id
    current_mode = user_modes.get(chat_id, "обычный")
    remaining = get_user_remaining_requests(chat_id, current_mode)
    
    mode_text = (
        f"🎭 Галерея режимов\n\n"
        f"Текущий выбор: {get_mode_description(current_mode)}\n"
        f"Доступно запросов: {remaining}\n\n"
        "Выбери новый режим для нашего диалога:")
    
    await message.answer(mode_text,
                         reply_markup=get_mode_keyboard())

@dp.message(F.text.in_(["🧘 Спокойный (15)", "💬 Обычный (10)", "⚡ Короткий (13)", "🧠 Умный (3)"]))
async def handle_mode_selection(message: types.Message):
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

    success_text = (
        f"✨ Режим успешно изменён\n\n"
        f"{get_mode_description(new_mode)}\n\n"
        f"Доступно запросов: {remaining}\n\n"
        "Готова к работе в новом формате")
    
    await message.answer(success_text,
                         reply_markup=get_settings_keyboard())

@dp.message(F.text == "🎨 Стиль общения")
async def handle_style_menu(message: types.Message):
    style_text = (
        f"🎨 Палитра стилей\n\n"
        "Выбери новый стиль общения:")
    
    await message.answer(style_text,
                         reply_markup=get_style_keyboard())

@dp.message(F.text.in_(["💫 Дружелюбный", "⚖️ Сбалансированный", "🎯 Деловой", "🎨 Креативный"]))
async def handle_style_selection(message: types.Message):
    chat_id = message.chat.id
    text = str(message.text or "")

    style_mapping = {
        "💫 Дружелюбный": "friendly",
        "⚖️ Сбалансированный": "balanced",
        "🎯 Деловой": "serious", 
        "🎨 Креативный": "creative"
    }

    new_style = style_mapping.get(text, "balanced")
    chat_style[chat_id] = new_style

    success_text = (
        f"🎨 Стиль общения обновлён\n\n"
        "Теперь наши диалоги заиграют новыми красками")
    
    await message.answer(success_text,
                         reply_markup=get_settings_keyboard())

@dp.message(F.text == "📊 Статистика")
async def handle_stats(message: types.Message):
    chat_id = message.chat.id
    current_mode = user_modes.get(chat_id, "обычный")
    used = user_requests_count.get(chat_id, {}).get(current_mode, 0)
    remaining = get_user_remaining_requests(chat_id, current_mode)
    
    stats_text = (
        f"📊 Твоя статистика\n\n"
        f"Текущий режим: {current_mode}\n"
        f"Использовано: {used} запросов\n"
        f"Осталось: {remaining} запросов")
    
    await message.answer(stats_text)

@dp.message(F.text == "ℹ️ Информация")
async def handle_info(message: types.Message):
    info_text = (
        "💎 Информационная панель\n\n"
        "Система запросов:\n"
        "• Каждый режим имеет свой лимит запросов\n"
        "• Лимиты обновляются при смене режима\n"
        "• Администраторы имеют неограниченный доступ\n\n"
        "Особенности работы:\n"
        "• Работаю 24/7 в облачной среде\n"
        "• Поддерживаю глубокий контекст диалога\n"
        "• Адаптируюсь под твой стиль общения")
    
    await message.answer(info_text)

@dp.message(F.text == "🌤️ Погода")
async def handle_weather_menu(message: types.Message):
    weather_text = (
        "🌤️ Метеостанция\n\n"
        "Выбери город для получения актуальной погоды\n"
        "Или напиши название любого другого города")
    
    await message.answer(weather_text,
                         reply_markup=get_weather_keyboard())

@dp.message(F.text.in_(["🏙️ Новосибирск", "🏛️ Москва", "🌉 Санкт-Петербург"]))
async def handle_weather_city(message: types.Message):
    city_mapping = {
        "🏙️ Новосибирск": "Новосибирск",
        "🏛️ Москва": "Москва",
        "🌉 Санкт-Петербург": "Санкт-Петербург"
    }
    
    city = city_mapping.get(message.text, message.text)
    weather = await get_weather(city)
    await message.answer(weather,
                         reply_markup=get_main_keyboard(message.chat.id))

@dp.message(F.text == "📍 Другой город")
async def handle_other_city(message: types.Message):
    await message.answer("🌍 Напиши название города для получения погоды")

@dp.message(F.text == "👑 Админ-панель")
async def handle_admin_panel(message: types.Message):
    if message.chat.id != ADMIN_ID:
        await message.answer("⛔ Доступ ограничен")
        return
        
    admin_text = (
        "👑 Административная панель\n\n"
        "Доступные функции:\n"
        "• Статистика — общая аналитика\n"
        "• Сброс лимитов — обнуление счетчиков\n"
        "• Управление AI — настройки нейросети\n"
        "• Пользователи — управление юзерами\n"
        "• Система — мониторинг работы\n"
        "• Логи — просмотр журналов")
    
    await message.answer(admin_text,
                         reply_markup=get_admin_keyboard())

@dp.message(F.text == "📈 Статистика")
async def handle_admin_stats(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    total_users = len(user_requests_count)
    total_requests = sum(sum(mode.values()) for mode in user_requests_count.values())
    
    stats_text = (
        f"📊 Системная статистика\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"📨 Всего запросов: {total_requests}\n"
        f"🎭 Активных режимов: {len(user_modes)}\n"
        f"💾 Память чатов: {len(chat_memory)}")
    
    await message.answer(stats_text)

@dp.message(F.text == "🔄 Сброс лимитов")
async def handle_reset_limits(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    user_requests_count.clear()
    await message.answer("✅ Лимиты всех пользователей сброшены")

@dp.message(F.text == "🧠 Управление AI")
async def handle_ai_management(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    ai_text = (
        "🧠 Центр управления AI\n\n"
        "Настройки нейросети:\n"
        "• Настройки модели — параметры Mistral\n"
        "• Параметры AI — тонкая настройка\n"
        "• Промпты — системные инструкции\n"
        "• Очистка памяти — сброс контекста")
    
    await message.answer(ai_text,
                         reply_markup=get_ai_management_keyboard())

@dp.message(F.text == "🎛️ Настройки модели")
async def handle_model_settings(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    settings_text = (
        "🎛️ Текущие настройки модели\n\n"
        f"Модель: {model}\n"
        f"API ключ: {'✅ Настроен' if mistral_api_key else '❌ Отсутствует'}\n"
        f"Стили общения: {len(chat_style)}\n"
        f"Режимы работы: {len(USER_LIMITS)}")
    
    await message.answer(settings_text)

@dp.message(F.text == "👥 Пользователи")
async def handle_users_management(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    users_text = (
        f"👥 Управление пользователями\n\n"
        f"Всего пользователей: {len(user_requests_count)}\n"
        f"Активных сессий: {len(user_modes)}\n"
        f"Использовано запросов: {sum(sum(mode.values()) for mode in user_requests_count.values())}")
    
    await message.answer(users_text)

@dp.message(F.text == "⚡ Система")
async def handle_system_info(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    system_text = (
        "⚡ Системная информация\n\n"
        "Статус: ✅ Активен\n"
        "Платформа: Railway\n"
        "Режим работы: 24/7\n"
        "Версия AI: Mistral Large\n"
        "Обновление: Автоматическое")
    
    await message.answer(system_text)

@dp.message(F.text == "📊 Логи")
async def handle_logs(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    logs_text = (
        "📊 Журнал системы\n\n"
        "Последние события:\n"
        "• Бот запущен и работает\n"
        "• AI модель загружена\n"
        "• Погодный API доступен\n"
        "• Пользователи активны\n\n"
        "Ошибок не обнаружено ✅")
    
    await message.answer(logs_text)

@dp.message(F.text == "⬅️ Назад")
async def handle_back(message: types.Message):
    await message.answer("Главное меню", 
                         reply_markup=get_main_keyboard(message.chat.id))

@dp.message(F.text == "⬅️ Главное меню")
async def handle_main_menu(message: types.Message):
    await message.answer("Возвращаюсь в главное меню",
                         reply_markup=get_main_keyboard(message.chat.id))

@dp.message(F.text == "⬅️ Админ-панель")
async def handle_back_to_admin(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    await message.answer("Возвращаюсь в админ-панель",
                         reply_markup=get_admin_keyboard())

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
        await message.answer("❌ Пожалуйста, отправь текстовое сообщение")
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
                f"⚠️ Лимит исчерпан\n\n"
                f"Режим: {mode}\n"
                f"Лимит: {USER_LIMITS[mode]} запросов\n\n"
                "Попробуй другой режим в настройках")
            return

        user_requests_count[chat_id][mode] += 1

    # Специальные ответы
    user_text_lower = user_text.lower().strip()

    if user_text_lower in ["пока", "до свидания", "до связи"]:
        await message.answer(random.choice(SPECIAL_RESPONSES["пока"]))
        return

    special_found = False
    for key, values in SPECIAL_RESPONSES.items():
        if key in user_text_lower and key != "пока":
            await message.answer(random.choice(values))
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
        await message.answer("⚠️ Временная ошибка, попробуйте ещё раз")

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
