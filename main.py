import asyncio
import logging
import random
import aiohttp
import time
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from typing import Dict, Any, List, Optional
import os
from mistralai import Mistral
import json
import pickle

# =======================
# ===== КОНФИГУРАЦИЯ =====
# =======================
mistral_api_key = os.getenv('MISTRAL_API_KEY', 'nIMvGkfioIpMtQeSO2n8ssm6nuJRyo7Q')
openweather_api_key = os.getenv('OPENWEATHER_API_KEY', 'dbd08a834f628d369a8edb55b210171e')
TOKEN = os.getenv('BOT_TOKEN', '8229856813:AAEkQq-4zdJKAmovgq69URcqKDzN4_BMqrw')

ADMIN_ID = 6584350034

# Бесплатный период (5 дней)
FREE_PERIOD_DAYS = 5

# Тарифы
TARIFFS = {
    "default": {
        "name": "🚀 Default",
        "days": 5,
        "description": "Базовый доступ к основным функциям",
        "features": [
            "✅ Основные режимы AI",
            "✅ Память диалога: 10 сообщений", 
            "✅ Быстрые команды",
            "✅ Погодные запросы",
            "⏳ Ожидание между запросами: 5 сек"
        ],
        "price": "Бесплатно"
    },
    "pro": {
        "name": "⭐ Pro", 
        "days": 30,
        "description": "Улучшенные возможности для активных пользователей",
        "features": [
            "✅ Все режимы AI без ограничений",
            "✅ Память диалога: 20 сообщений",
            "✅ Приоритетная обработка запросов",
            "✅ Расширенные быстрые команды",
            "⚡ Ожидание между запросами: 3 сек",
            "🎯 Персональные настройки"
        ],
        "price": "499 ₽/месяц"
    },
    "ultimate": {
        "name": "👑 Ultimate",
        "days": 365, 
        "description": "Максимальная производительность и привилегии",
        "features": [
            "✅ Все режимы AI в полном объеме",
            "✅ Память диалога: 50 сообщений",
            "✅ Мгновенная обработка запросов",
            "✅ Эксклюзивные функции",
            "⚡ Ожидание между запросами: 1 сек",
            "🎯 Персональная поддержка",
            "🔒 Приоритет при обновлениях",
            "💎 Кастомные настройки"
        ],
        "price": "3999 ₽/год"
    }
}

# Время ожидания между запросами для разных тарифов
TARIFF_COOLDOWNS = {
    "default": 5,
    "pro": 3, 
    "ultimate": 1
}

# Память диалогов для разных тарифов
TARIFF_MEMORY = {
    "default": 10,
    "pro": 20,
    "ultimate": 50
}

model = "mistral-large-latest"
client = Mistral(api_key=mistral_api_key)

# Файлы для сохранения данных
DATA_FILES = {
    'user_registration_date': 'user_registration_date.pkl',
    'conversation_memory': 'conversation_memory.pkl',
    'chat_style': 'chat_style.pkl',
    'user_requests_count': 'user_requests_count.pkl',
    'user_modes': 'user_modes.pkl',
    'user_tariffs': 'user_tariffs.pkl',
    'user_subscription_end': 'user_subscription_end.pkl'
}

# =======================
# ===== СОХРАНЕНИЕ ДАННЫХ =====
# =======================
def load_data(filename: str, default: Any = None) -> Any:
    """Загружает данные из файла"""
    try:
        if os.path.exists(filename):
            with open(filename, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки {filename}: {e}")
    return default if default is not None else {}

def save_data(data: Any, filename: str):
    """Сохраняет данные в файл"""
    try:
        with open(filename, 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        logging.error(f"Ошибка сохранения {filename}: {e}")

def save_all_data():
    """Сохраняет все данные"""
    for filename, data_key in [
        (DATA_FILES['user_registration_date'], user_registration_date),
        (DATA_FILES['conversation_memory'], conversation_memory),
        (DATA_FILES['chat_style'], chat_style),
        (DATA_FILES['user_requests_count'], user_requests_count),
        (DATA_FILES['user_modes'], user_modes),
        (DATA_FILES['user_tariffs'], user_tariffs),
        (DATA_FILES['user_subscription_end'], user_subscription_end)
    ]:
        save_data(data_key, filename)

def load_all_data():
    """Загружает все данные"""
    global user_registration_date, conversation_memory, chat_style, user_requests_count
    global user_modes, user_tariffs, user_subscription_end
    
    user_registration_date = load_data(DATA_FILES['user_registration_date'], {})
    conversation_memory = load_data(DATA_FILES['conversation_memory'], {})
    chat_style = load_data(DATA_FILES['chat_style'], {})
    user_requests_count = load_data(DATA_FILES['user_requests_count'], {})
    user_modes = load_data(DATA_FILES['user_modes'], {})
    user_tariffs = load_data(DATA_FILES['user_tariffs'], {})
    user_subscription_end = load_data(DATA_FILES['user_subscription_end'], {})

# Загружаем данные при старте
load_all_data()

# Переменные для временных данных (не сохраняются)
user_last_request: Dict[int, float] = {}
user_last_messages: Dict[int, str] = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# =======================
# ===== СИСТЕМА ТАРИФОВ =====
# =======================
def get_user_tariff(chat_id: int) -> str:
    """Возвращает тариф пользователя"""
    if chat_id == ADMIN_ID:
        return "ultimate"  # Админ всегда на максимальном тарифе
    
    # Проверяем активную подписку
    if chat_id in user_subscription_end and user_subscription_end[chat_id] > datetime.now():
        return user_tariffs.get(chat_id, "default")
    
    # Бесплатный период
    if is_free_period_active(chat_id):
        return "default"
    
    return "default"  # По умолчанию

def get_user_cooldown(chat_id: int) -> int:
    """Возвращает время ожидания для пользователя"""
    tariff = get_user_tariff(chat_id)
    return TARIFF_COOLDOWNS.get(tariff, 5)

def get_user_memory_limit(chat_id: int) -> int:
    """Возвращает лимит памяти для пользователя"""
    tariff = get_user_tariff(chat_id)
    return TARIFF_MEMORY.get(tariff, 10)

def is_subscription_active(chat_id: int) -> bool:
    """Проверяет активна ли подписка"""
    if chat_id == ADMIN_ID:
        return True
    
    # Проверяем платную подписку
    if chat_id in user_subscription_end and user_subscription_end[chat_id] > datetime.now():
        return True
    
    # Проверяем бесплатный период
    return is_free_period_active(chat_id)

def activate_tariff(chat_id: int, tariff: str, days: int):
    """Активирует тариф для пользователя"""
    user_tariffs[chat_id] = tariff
    user_subscription_end[chat_id] = datetime.now() + timedelta(days=days)
    save_data(user_tariffs, DATA_FILES['user_tariffs'])
    save_data(user_subscription_end, DATA_FILES['user_subscription_end'])

def get_remaining_days(chat_id: int) -> int:
    """Возвращает оставшиеся дней подписки"""
    if chat_id == ADMIN_ID:
        return 999
    
    # Проверяем платную подписку
    if chat_id in user_subscription_end and user_subscription_end[chat_id] > datetime.now():
        return (user_subscription_end[chat_id] - datetime.now()).days
    
    # Бесплатный период
    return get_remaining_free_days(chat_id)

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
# ===== СОВРЕМЕННЫЙ СЛЕНГ =====
# =======================
MODERN_SLANG = {
    "имба": "отлично, великолепно, превосходно",
    "краш": "симпатия, влюблённость, объект воздыханий", 
    "чиллерить": "расслабляться, отдыхать",
    "хайпить": "быть на волне, быть популярным",
    "рофлить": "шутить, смеяться",
    "кринж": "стыд, неловкость",
    "агриться": "злиться, раздражаться",
    "вайб": "атмосфера, настроение",
    "сасный": "привлекательный, симпатичный",
    "пруфы": "доказательства",
    "facepalm": "жест разочарования",
    "чикса": "девушка",
    "чилать": "отдыхать, расслабляться",
    "ломка": "сильное желание",
    "хейтер": "недоброжелатель",
    "лайк": "нравится",
    "димпси": "глубокие, душевные мысли",
    "ку": "привет",
    "чиназес": "китайцы",
    "го": "давай, поехали",
    "ноу проблемс": "без проблем",
    "окей": "хорошо, согласен",
    "ок": "хорошо",
    "агу": "понимаю",
    "респект": "уважение",
    "жиза": "жизненная ситуация",
    "пож": "пожалуйста",
    "спс": "спасибо",
    "плиз": "пожалуйста",
    "омг": "ой боже",
    "бро": "друг, брат",
    "сижка": "сигарета",
    "буст": "ускорение, улучшение",
    "флекс": "хвастовство",
    "ghosting": "исчезновение без объяснений"
}

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
    
    # Добавляем кнопку тарифов для всех пользователей
    buttons.append([KeyboardButton(text="💎 Тарифы")])
    
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
    ], [
        KeyboardButton(text="⚡ Быстрые команды"),
        KeyboardButton(text="🔔 Уведомления")
    ], [KeyboardButton(text="⬅️ Назад")]],
                               resize_keyboard=True)

def get_tariffs_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="🚀 Default"),
        KeyboardButton(text="⭐ Pro")
    ], [
        KeyboardButton(text="👑 Ultimate"),
        KeyboardButton(text="📊 Мой тариф")
    ], [
        KeyboardButton(text="⬅️ Назад")
    ]], resize_keyboard=True)

def get_mode_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="🧘 Спокойный"),
            KeyboardButton(text="💬 Обычный")
        ],
                  [
                      KeyboardButton(text="⚡ Короткий"),
                      KeyboardButton(text="🧠 Умный")
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

def get_quick_commands_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="📝 Конвертер валют"),
        KeyboardButton(text="🎯 Случайный выбор")
    ], [
        KeyboardButton(text="📅 Текущая дата"),
        KeyboardButton(text="⏰ Текущее время")
    ], [
        KeyboardButton(text="🔢 Калькулятор"),
        KeyboardButton(text="🎁 Сюрприз")
    ], [KeyboardButton(text="⬅️ Назад")]],
                               resize_keyboard=True)

def get_admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="📈 Общая статистика"),
        KeyboardButton(text="👥 Управление пользователями")
    ], [
        KeyboardButton(text="🔄 Сброс лимитов"),
        KeyboardButton(text="⚙️ Настройки системы")
    ], [
        KeyboardButton(text="🎯 Тест AI"),
        KeyboardButton(text="📊 Логи")
    ], [
        KeyboardButton(text="🧠 Управление памятью"),
        KeyboardButton(text="💎 Управление тарифами")
    ], [KeyboardButton(text="⬅️ Главное меню")]],
                               resize_keyboard=True)

def get_users_management_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="📊 Статистика пользователей"),
        KeyboardButton(text="⏰ Продлить подписки")
    ], [
        KeyboardButton(text="🔍 Поиск пользователя"),
        KeyboardButton(text="📝 Массовая рассылка")
    ], [KeyboardButton(text="⬅️ Админ-панель")]],
                               resize_keyboard=True)

def get_memory_management_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="🧹 Очистить память"),
        KeyboardButton(text="📊 Статистика памяти")
    ], [
        KeyboardButton(text="🔍 Просмотр памяти"),
        KeyboardButton(text="⚡ Оптимизация")
    ], [KeyboardButton(text="⬅️ Админ-панель")]],
                               resize_keyboard=True)

def get_tariff_management_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="🚀 Выдать Default"),
        KeyboardButton(text="⭐ Выдать Pro")
    ], [
        KeyboardButton(text="👑 Выдать Ultimate"),
        KeyboardButton(text="📊 Статистика тарифов")
    ], [
        KeyboardButton(text="⏰ Продлить тариф"),
        KeyboardButton(text="🔍 Поиск по тарифам")
    ], [KeyboardButton(text="⬅️ Админ-панель")]],
                               resize_keyboard=True)

# =======================
# ===== ФУНКЦИИ ПАМЯТИ =====
# =======================
def add_to_conversation_memory(chat_id: int, role: str, content: str):
    """Добавляет сообщение в память диалога"""
    if chat_id not in conversation_memory:
        conversation_memory[chat_id] = []
    
    conversation_memory[chat_id].append({"role": role, "content": content})
    
    # Ограничиваем историю по тарифу
    memory_limit = get_user_memory_limit(chat_id)
    if len(conversation_memory[chat_id]) > memory_limit:
        conversation_memory[chat_id] = conversation_memory[chat_id][-memory_limit:]
    
    # Сохраняем изменения
    save_data(conversation_memory, DATA_FILES['conversation_memory'])

def get_conversation_context(chat_id: int) -> List[Dict[str, str]]:
    """Возвращает контекст диалога"""
    return conversation_memory.get(chat_id, [])

def clear_conversation_memory(chat_id: int):
    """Очищает память диалога"""
    if chat_id in conversation_memory:
        conversation_memory[chat_id] = []
        save_data(conversation_memory, DATA_FILES['conversation_memory'])

def get_memory_stats() -> Dict[str, Any]:
    """Статистика памяти"""
    total_users = len(conversation_memory)
    total_messages = sum(len(messages) for messages in conversation_memory.values())
    avg_messages = total_messages / total_users if total_users > 0 else 0
    
    return {
        "total_users": total_users,
        "total_messages": total_messages,
        "avg_messages": round(avg_messages, 2),
        "memory_size": total_messages * 100  # примерный размер в байтах
    }

# =======================
# ===== ФУНКЦИИ ЛИМИТОВ =====
# =======================
def get_mode_description(mode: str) -> str:
    descriptions = {
        "спокойный": "🧘 Спокойный режим",
        "обычный": "💬 Обычный режим", 
        "короткий": "⚡ Короткий режим",
        "умный": "🧠 Умный режим"
    }
    return descriptions.get(mode, "💬 Обычный режим")

def is_free_period_active(chat_id: int) -> bool:
    """Проверяет, активен ли бесплатный период"""
    if chat_id == ADMIN_ID:
        return True
    if chat_id not in user_registration_date:
        user_registration_date[chat_id] = datetime.now()
        save_data(user_registration_date, DATA_FILES['user_registration_date'])
    registration_date = user_registration_date[chat_id]
    return (datetime.now() - registration_date).days < FREE_PERIOD_DAYS

def get_remaining_free_days(chat_id: int) -> int:
    """Возвращает оставшиеся дней бесплатного периода"""
    if chat_id not in user_registration_date:
        user_registration_date[chat_id] = datetime.now()
        save_data(user_registration_date, DATA_FILES['user_registration_date'])
    registration_date = user_registration_date[chat_id]
    days_passed = (datetime.now() - registration_date).days
    return max(0, FREE_PERIOD_DAYS - days_passed)

def get_user_remaining_requests(chat_id: int, mode: str) -> int:
    """Возвращает оставшееся количество запросов"""
    if chat_id == ADMIN_ID:
        return 9999  # Админ без лимитов
    
    if not is_subscription_active(chat_id):
        return 0  # Подписка закончилась
        
    return 9999  # Безлимит при активной подписке

# =======================
# ===== ПРОВЕРКА ВРЕМЕНИ ОЖИДАНИЯ =====
# =======================
def check_cooldown(chat_id: int) -> str:
    """Проверяет время ожидания между запросами"""
    if chat_id == ADMIN_ID:
        return None  # Админы без ограничений
        
    current_time = time.time()
    last_request = user_last_request.get(chat_id, 0)
    
    cooldown = get_user_cooldown(chat_id)
    
    if current_time - last_request < cooldown:
        remaining = cooldown - int(current_time - last_request)
        return f"⏳ Пожалуйста, подожди {remaining} секунд перед следующим запросом"
    
    user_last_request[chat_id] = current_time
    return None

# =======================
# ===== ФУНКЦИИ ОБРАБОТКИ ТЕКСТА =====
# =======================
def should_use_full_response(user_text: str, ai_response: str) -> bool:
    """Определяет, нужно ли отправлять полный ответ без сокращений"""
    user_lower = user_text.lower()
    
    # Если пользователь задает несколько вопросов
    if user_lower.count('?') >= 2:
        return True
    
    # Если в ответе есть перечисления или списки
    if any(marker in ai_response for marker in ['\n•', '\n-', '\n1.', '\n2.', '\n3.', 'Во-первых', 'Во-вторых', 'В-третьих']):
        return True
    
    # Если пользователь явно просит развернутый ответ
    if any(phrase in user_lower for phrase in ['подробно', 'подробный', 'развернуто', 'развернутый', 'подробнее', 'расскажи подробно']):
        return True
    
    # Если пользователь задает несколько отдельных вопросов в одном сообщении
    if any(phrase in user_lower for phrase in ['также', 'еще вопрос', 'также вопрос', 'и еще', 'и последнее']):
        return True
    
    return False

def process_ai_response(text: str, mode: str, user_text: str) -> str:
    """Обрабатывает ответ AI в зависимости от режима и контекста"""
    # Проверяем, нужен ли полный ответ
    if should_use_full_response(user_text, text):
        return text  # Возвращаем полный ответ без сокращений
    
    # Обычная обработка по режимам
    if mode == "короткий":
        sentences = text.split('. ')
        if len(sentences) > 2:
            text = '. '.join(sentences[:2]) + '.'
        if len(text) > 400:
            text = text[:400] + '...'
    elif mode == "спокойный":
        sentences = text.split('. ')
        if len(sentences) > 4:
            text = '. '.join(sentences[:4]) + '.'
        if len(text) > 600:
            text = text[:600] + '...'
    elif mode == "обычный":
        sentences = text.split('. ')
        if len(sentences) > 5:
            text = '. '.join(sentences[:5]) + '.'
        if len(text) > 800:
            text = text[:800] + '...'
    elif mode == "умный":
        sentences = text.split('. ')
        if len(sentences) > 6:
            text = '. '.join(sentences[:6]) + '.'
        if len(text) > 1000:
            text = text[:1000] + '...'
    
    return text

def format_ai_response(text: str, style: str, mode: str, user_text: str) -> str:
    emoji = get_emoji(style)
    formatted = process_ai_response(text, mode, user_text)

    if mode == "спокойный":
        calm_emojis = ["🌿", "🍃", "🌼", "🌸", "💮", "🪷"]
        if random.random() > 0.7:
            formatted = f"{random.choice(calm_emojis)} {formatted}"

    return f"{emoji} {formatted}"

async def send_long_message(message: types.Message, text: str, style: str = "balanced", mode: str = "обычный", user_text: str = "", chunk_size: int = 4000):
    formatted = format_ai_response(text, style, mode, user_text)
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
# ===== БЫСТРЫЕ КОМАНДЫ =====
# =======================
async def get_currency_rate() -> str:
    """Получает курс валют"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.exchangerate-api.com/v4/latest/USD') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    usd_rub = data['rates']['RUB']
                    eur_rub = usd_rub / data['rates']['EUR']
                    return (f"💱 Текущий курс валют:\n\n"
                           f"• 🇺🇸 USD → RUB: {usd_rub:.2f} ₽\n"
                           f"• 🇪🇺 EUR → RUB: {eur_rub:.2f} ₽\n"
                           f"• 🇷🇺 RUB → USD: {1/usd_rub:.4f} $")
    except:
        return "💱 Курсы валют временно недоступны"

def get_random_choice(options: str) -> str:
    """Случайный выбор из вариантов"""
    if not options:
        return "🎯 Напиши варианты через запятую"
    
    items = [item.strip() for item in options.split(',')]
    if len(items) < 2:
        return "🎯 Нужно минимум 2 варианта"
    
    chosen = random.choice(items)
    return f"🎯 Случайный выбор: *{chosen}*"

def get_current_datetime() -> str:
    """Текущая дата и время"""
    now = datetime.now()
    return (f"📅 Текущая дата и время:\n\n"
           f"• Дата: {now.strftime('%d.%m.%Y')}\n"
           f"• Время: {now.strftime('%H:%M:%S')}\n"
           f"• День недели: {['Пн','Вт','Ср','Чт','Пт','Сб','Вс'][now.weekday()]}")

def calculate_expression(expr: str) -> str:
    """Простой калькулятор"""
    try:
        # Безопасное вычисление
        expr = expr.replace(' ', '').replace('^', '**')
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in expr):
            return "🔢 Используй только цифры и + - * / . ( )"
        
        result = eval(expr)
        return f"🔢 Результат: {expr} = {result}"
    except:
        return "🔢 Ошибка в выражении"

def get_random_surprise() -> str:
    """Случайный сюрприз"""
    surprises = [
        "🎁 Сегодня твой счастливый день!",
        "💫 Вселенная готовит для тебя приятный сюрприз",
        "🌟 Ты заслуживаешь только самого лучшего",
        "🎯 Сегодня идеальный день для новых начинаний",
        "💝 Помни: ты уникален и особенный",
        "🌈 За каждой тучей скрывается радуга",
        "🦋 Иногда нужно просто расправить крылья и лететь"
    ]
    return random.choice(surprises)

# =======================
# ===== КОМАНДЫ =========
# =======================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    chat_id = message.chat.id
    
    # Инициализация данных пользователя
    if chat_id not in chat_style:
        chat_style[chat_id] = "balanced"
        save_data(chat_style, DATA_FILES['chat_style'])
    
    if chat_id not in user_modes:
        user_modes[chat_id] = "обычный"
        save_data(user_modes, DATA_FILES['user_modes'])

    # Регистрируем пользователя
    if chat_id not in user_registration_date:
        user_registration_date[chat_id] = datetime.now()
        save_data(user_registration_date, DATA_FILES['user_registration_date'])

    if chat_id not in user_requests_count:
        user_requests_count[chat_id] = {}
        for mode in ["спокойный", "обычный", "короткий", "умный"]:
            user_requests_count[chat_id][mode] = 0
        save_data(user_requests_count, DATA_FILES['user_requests_count'])

    # Инициализируем память
    if chat_id not in conversation_memory:
        conversation_memory[chat_id] = []
        save_data(conversation_memory, DATA_FILES['conversation_memory'])

    current_mode = user_modes[chat_id]
    remaining_days = get_remaining_days(chat_id)
    current_tariff = get_user_tariff(chat_id)
    
    welcome_text = (
        "✨ Добро пожаловать в мир интеллектуального общения\n\n"
        "Я — твой персональный AI-компаньон для глубоких диалогов\n\n"
        f"💎 *Твой тариф:* {TARIFFS[current_tariff]['name']}\n"
        f"📅 Осталось дней: {remaining_days}\n"
        f"🎭 Режим: {get_mode_description(current_mode)}\n"
        f"💾 Память диалога: {get_user_memory_limit(chat_id)} сообщений\n"
        f"⚡ Ожидание: {get_user_cooldown(chat_id)} сек\n\n"
        "Выбери направление для нашего диалога 👇")

    await message.answer(welcome_text,
                         reply_markup=get_main_keyboard(chat_id))

@dp.message(F.text == "💎 Тарифы")
async def handle_tariffs(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    tariffs_text = "💎 **Доступные тарифы**\n\n"
    
    for tariff_key, tariff_info in TARIFFS.items():
        tariffs_text += f"{tariff_info['name']}\n"
        tariffs_text += f"*{tariff_info['description']}*\n"
        tariffs_text += f"Срок: {tariff_info['days']} дней\n"
        tariffs_text += f"Цена: {tariff_info['price']}\n\n"
        
        for feature in tariff_info['features']:
            tariffs_text += f"{feature}\n"
        
        tariffs_text += "\n" + "─" * 30 + "\n\n"
    
    tariffs_text += "Выбери тариф для просмотра деталей или проверь свой текущий тариф 👇"
    
    await message.answer(tariffs_text,
                         reply_markup=get_tariffs_keyboard())

@dp.message(F.text == "📊 Мой тариф")
async def handle_my_tariff(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    chat_id = message.chat.id
    current_tariff = get_user_tariff(chat_id)
    remaining_days = get_remaining_days(chat_id)
    tariff_info = TARIFFS[current_tariff]
    
    my_tariff_text = (
        f"💎 **Твой текущий тариф**\n\n"
        f"{tariff_info['name']}\n"
        f"*{tariff_info['description']}*\n\n"
        f"📅 Осталось дней: {remaining_days}\n"
        f"💾 Лимит памяти: {get_user_memory_limit(chat_id)} сообщений\n"
        f"⚡ Ожидание между запросами: {get_user_cooldown(chat_id)} сек\n\n"
        f"**Включенные возможности:**\n")
    
    for feature in tariff_info['features']:
        my_tariff_text += f"{feature}\n"
    
    if current_tariff == "default":
        my_tariff_text += "\n💡 *Для улучшения возможностей рассмотри переход на Pro или Ultimate тариф!*"
    
    await message.answer(my_tariff_text)

@dp.message(F.text.in_(["🚀 Default", "⭐ Pro", "👑 Ultimate"]))
async def handle_tariff_info(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    tariff_mapping = {
        "🚀 Default": "default",
        "⭐ Pro": "pro", 
        "👑 Ultimate": "ultimate"
    }
    
    tariff_key = tariff_mapping.get(message.text, "default")
    tariff_info = TARIFFS[tariff_key]
    
    tariff_text = (
        f"{tariff_info['name']}\n"
        f"*{tariff_info['description']}*\n\n"
        f"📅 Срок действия: {tariff_info['days']} дней\n"
        f"💵 Стоимость: {tariff_info['price']}\n\n"
        f"**Включенные возможности:**\n")
    
    for feature in tariff_info['features']:
        tariff_text += f"{feature}\n"
    
    tariff_text += f"\n💎 *Для активации тарифа обратитесь к администратору*"
    
    await message.answer(tariff_text)

@dp.message(F.text.in_(["🚀 Начать работу", "🚀 Старт"]))
async def handle_start_button(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return
    await cmd_start(message)

# ... (остальные обработчики сообщений остаются без изменений, кроме тех что используют get_remaining_free_days - заменяем на get_remaining_days)

@dp.message(F.text == "🌟 Обо мне")
async def handle_about(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    about_text = (
        "🤖 Мой цифровой портрет\n\n"
        "Мои возможности:\n"
        "• Глубокий анализ текстов\n"
        "• Креативная генерация контента\n"
        "• Многорежимная работа\n"
        "• Интеграция с погодными данными\n"
        "• Быстрые команды и утилиты\n"
        "• Понимание современного сленга\n"
        "• Гибкая система тарифов\n\n"
        "💎 **Доступные тарифы:**\n"
        "• 🚀 Default - базовые возможности\n" 
        "• ⭐ Pro - улучшенные функции\n"
        "• 👑 Ultimate - максимальный комфорт")
    
    await message.answer(about_text,
                         reply_markup=get_main_keyboard(message.chat.id))

@dp.message(F.text == "📊 Статистика")
async def handle_stats(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    chat_id = message.chat.id
    current_mode = user_modes.get(chat_id, "обычный")
    used = user_requests_count.get(chat_id, {}).get(current_mode, 0)
    remaining_days = get_remaining_days(chat_id)
    memory_count = len(conversation_memory.get(chat_id, []))
    current_tariff = get_user_tariff(chat_id)
    memory_limit = get_user_memory_limit(chat_id)
    
    stats_text = (
        f"📊 Твоя статистика\n\n"
        f"💎 Тариф: {TARIFFS[current_tariff]['name']}\n"
        f"📅 Осталось дней: {remaining_days}\n"
        f"🎭 Текущий режим: {current_mode}\n"
        f"📨 Использовано запросов: {used}\n"
        f"💾 Память: {memory_count}/{memory_limit} сообщений\n"
        f"⚡ Ожидание: {get_user_cooldown(chat_id)} сек\n"
        f"Статус: {'✅ Активен' if is_subscription_active(chat_id) else '⏳ Завершен'}")
    
    await message.answer(stats_text)

# =======================
# ===== АДМИН ПАНЕЛЬ - УПРАВЛЕНИЕ ТАРИФАМИ =====
# =======================
@dp.message(F.text == "💎 Управление тарифами")
async def handle_tariff_management(message: types.Message):
    if message.chat.id != ADMIN_ID:
        await message.answer("⛔ Доступ ограничен")
        return
        
    tariff_text = (
        "💎 Управление тарифами пользователей\n\n"
        "Доступные функции:\n"
        "• Выдать тариф пользователю\n"
        "• Продлить действующий тариф\n"
        "• Просмотр статистики по тарифам\n"
        "• Поиск пользователей по тарифам")
    
    await message.answer(tariff_text,
                         reply_markup=get_tariff_management_keyboard())

@dp.message(F.text.in_(["🚀 Выдать Default", "⭐ Выдать Pro", "👑 Выдать Ultimate"]))
async def handle_give_tariff(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    tariff_mapping = {
        "🚀 Выдать Default": "default",
        "⭐ Выдать Pro": "pro",
        "👑 Выдать Ultimate": "ultimate"
    }
    
    tariff_key = tariff_mapping.get(message.text, "default")
    tariff_info = TARIFFS[tariff_key]
    
    await message.answer(
        f"💎 Выдача тарифа {tariff_info['name']}\n\n"
        f"Для выдачи тарифа пользователю отправьте команду:\n"
        f"/givetariff [ID_пользователя] [дни]\n\n"
        f"Пример: /givetariff 123456789 {tariff_info['days']}\n\n"
        f"Тариф: {tariff_info['name']}\n"
        f"Стандартный срок: {tariff_info['days']} дней")

@dp.message(Command("givetariff"))
async def handle_give_tariff_command(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    try:
        parts = message.text.split()
        if len(parts) == 3:
            user_id = int(parts[1])
            days = int(parts[2])
            
            # Определяем тариф по количеству дней
            if days <= 7:
                tariff = "default"
            elif days <= 30:
                tariff = "pro"
            else:
                tariff = "ultimate"
            
            activate_tariff(user_id, tariff, days)
            
            await message.answer(
                f"✅ Пользователю {user_id} выдан тариф {TARIFFS[tariff]['name']}\n"
                f"Срок: {days} дней\n"
                f"Окончание: {user_subscription_end[user_id].strftime('%d.%m.%Y %H:%M')}")
                
        else:
            await message.answer("❌ Неверный формат. Используйте: /givetariff [ID] [дни]")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.message(F.text == "📊 Статистика тарифов")
async def handle_tariff_stats(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    tariff_stats = {"default": 0, "pro": 0, "ultimate": 0}
    active_users = 0
    
    for user_id in user_tariffs:
        if is_subscription_active(user_id):
            tariff = user_tariffs[user_id]
            tariff_stats[tariff] += 1
            active_users += 1
    
    stats_text = (
        f"📊 Статистика тарифов\n\n"
        f"👥 Всего активных пользователей: {active_users}\n\n"
        f"📈 Распределение по тарифам:\n"
        f"• 🚀 Default: {tariff_stats['default']} пользователей\n"
        f"• ⭐ Pro: {tariff_stats['pro']} пользователей\n"
        f"• 👑 Ultimate: {tariff_stats['ultimate']} пользователей\n\n"
        f"💎 Всего тарифов выдано: {sum(tariff_stats.values())}")
    
    await message.answer(stats_text)

@dp.message(F.text == "⏰ Продлить тариф")
async def handle_extend_tariff(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    await message.answer(
        "⏰ Продление тарифа\n\n"
        "Для продления тарифа пользователя:\n"
        "Отправьте команду в формате:\n"
        "/extendtariff [ID_пользователя] [дни]\n\n"
        "Пример: /extendtariff 123456789 30")

@dp.message(Command("extendtariff"))
async def handle_extend_tariff_command(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    try:
        parts = message.text.split()
        if len(parts) == 3:
            user_id = int(parts[1])
            days = int(parts[2])
            
            if user_id in user_subscription_end:
                user_subscription_end[user_id] += timedelta(days=days)
                save_data(user_subscription_end, DATA_FILES['user_subscription_end'])
                
                await message.answer(
                    f"✅ Тариф пользователя {user_id} продлен на {days} дней\n"
                    f"Новое окончание: {user_subscription_end[user_id].strftime('%d.%m.%Y %H:%M')}")
            else:
                await message.answer(f"❌ Пользователь {user_id} не найден или у него нет активного тарифа")
        else:
            await message.answer("❌ Неверный формат. Используйте: /extendtariff [ID] [дни]")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# ... (остальной код обработчиков остается без изменений, но везде где было get_remaining_free_days заменяем на get_remaining_days)

# =======================
# ===== RUN BOT =========
# =======================
async def main():
    logger.info("🚀 Запуск бота...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("🚀 Бот запущен и работает 24/7!")
    print(f"💎 Система тарифов: {len(TARIFFS)} уровня")
    print(f"💾 Сохранение данных: активировано")
    print(f"👑 Админ-панель: доступна для ADMIN_ID")
    print(f"📊 Загружено пользователей: {len(user_registration_date)}")
    print(f"💎 Активных тарифов: {len([uid for uid in user_tariffs if is_subscription_active(uid)])}")
    asyncio.run(main())
