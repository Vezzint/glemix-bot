import asyncio
import logging
import random
import aiohttp
import time
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramBadRequest
from typing import Dict, Any, List
import os
from mistralai import Mistral
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

# Тарифы (цены в рублях в месяц)
TARIFFS = {
    "default": {
        "name": "🚀 Default",
        "days": 30,
        "description": "Базовый доступ",
        "features": [
            "✅ 20 запросов в день",
            "✅ Память: 10 сообщений", 
            "✅ Основные режимы AI",
            "✅ Быстрые команды",
            "⏳ Ожидание: 5 сек"
        ],
        "price": "10 ₽/месяц",
        "daily_limits": 20,
        "is_free_first": True
    },
    "pro": {
        "name": "⭐ Pro", 
        "days": 30,
        "description": "Для активных пользователей",
        "features": [
            "✅ 50 запросов в день",
            "✅ Память: 20 сообщений",
            "✅ Все режимы AI",
            "✅ Приоритетная обработка",
            "⚡ Ожидание: 3 сек"
        ],
        "price": "50 ₽/месяц",
        "daily_limits": 50,
        "is_free_first": False
    },
    "advanced": {
        "name": "💎 Advanced",
        "days": 30,
        "description": "Расширенные возможности",
        "features": [
            "✅ 100 запросов в день", 
            "✅ Память: 35 сообщений",
            "✅ Ранний доступ к функциям",
            "✅ Расширенные команды",
            "⚡ Ожидание: 2 сек"
        ],
        "price": "150 ₽/месяц",
        "daily_limits": 100,
        "is_free_first": False
    },
    "ultimate": {
        "name": "👑 Ultimate",
        "days": 30, 
        "description": "Максимальная производительность",
        "features": [
            "✅ Безлимитные запросы",
            "✅ Память: 100 сообщений",
            "✅ Мгновенная обработка",
            "✅ Эксклюзивные функции",
            "⚡ Ожидание: 1 сек",
            "🎯 Персональная поддержка"
        ],
        "price": "300 ₽/месяц",
        "daily_limits": 99999,
        "is_free_first": False
    }
}

# Время ожидания между запросами
TARIFF_COOLDOWNS = {
    "default": 5,
    "pro": 3,
    "advanced": 2, 
    "ultimate": 1
}

# Память диалогов
TARIFF_MEMORY = {
    "default": 10,
    "pro": 20,
    "advanced": 35,
    "ultimate": 100
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
    'user_subscription_end': 'user_subscription_end.pkl',
    'user_daily_requests': 'user_daily_requests.pkl'
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

# Загружаем данные при старте
user_registration_date = load_data(DATA_FILES['user_registration_date'], {})
conversation_memory = load_data(DATA_FILES['conversation_memory'], {})
chat_style = load_data(DATA_FILES['chat_style'], {})
user_requests_count = load_data(DATA_FILES['user_requests_count'], {})
user_modes = load_data(DATA_FILES['user_modes'], {})
user_tariffs = load_data(DATA_FILES['user_tariffs'], {})
user_subscription_end = load_data(DATA_FILES['user_subscription_end'], {})
user_daily_requests = load_data(DATA_FILES['user_daily_requests'], {})

# Переменные для временных данных
user_last_request: Dict[int, float] = {}
user_thinking_messages: Dict[int, int] = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# =======================
# ===== СИСТЕМА ТАРИФОВ И ЛИМИТОВ =====
# =======================
def get_user_tariff(chat_id: int) -> str:
    """Возвращает тариф пользователя"""
    if chat_id == ADMIN_ID:
        return "ultimate"
    
    # Если есть активная платная подписка
    if chat_id in user_subscription_end and user_subscription_end[chat_id] > datetime.now():
        return user_tariffs.get(chat_id, "default")
    
    # Бесплатный период для Default тарифа
    if is_free_period_active(chat_id):
        return "default"
    
    # Если бесплатный период закончился, но нет подписки
    return "default"  # Но доступ будет ограничен

def get_user_cooldown(chat_id: int) -> int:
    """Возвращает время ожидания для пользователя"""
    tariff = get_user_tariff(chat_id)
    return TARIFF_COOLDOWNS.get(tariff, 5)

def get_user_memory_limit(chat_id: int) -> int:
    """Возвращает лимит памяти для пользователя"""
    tariff = get_user_tariff(chat_id)
    return TARIFF_MEMORY.get(tariff, 10)

def get_user_daily_limit(chat_id: int) -> int:
    """Возвращает дневной лимит запросов"""
    tariff = get_user_tariff(chat_id)
    return TARIFFS[tariff]["daily_limits"]

def get_remaining_daily_requests(chat_id: int) -> int:
    """Возвращает оставшиеся запросы на сегодня"""
    today = datetime.now().date()
    daily_data = user_daily_requests.get(chat_id, {})
    if daily_data.get("date") != today:
        return get_user_daily_limit(chat_id)
    return max(0, get_user_daily_limit(chat_id) - daily_data.get("count", 0))

def increment_daily_requests(chat_id: int):
    """Увеличивает счетчик дневных запросов"""
    today = datetime.now().date()
    if chat_id not in user_daily_requests or user_daily_requests[chat_id].get("date") != today:
        user_daily_requests[chat_id] = {"date": today, "count": 1}
    else:
        user_daily_requests[chat_id]["count"] += 1
    save_data(user_daily_requests, DATA_FILES['user_daily_requests'])

def is_subscription_active(chat_id: int) -> bool:
    """Проверяет активна ли подписка (бесплатная или платная)"""
    if chat_id == ADMIN_ID:
        return True
    
    # Платная подписка
    if chat_id in user_subscription_end and user_subscription_end[chat_id] > datetime.now():
        return True
    
    # Бесплатный период
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
    
    # Платная подписка
    if chat_id in user_subscription_end and user_subscription_end[chat_id] > datetime.now():
        return (user_subscription_end[chat_id] - datetime.now()).days
    
    # Бесплатный период
    return get_remaining_free_days(chat_id)

def is_free_period_active(chat_id: int) -> bool:
    """Проверяет, активен ли бесплатный период"""
    if chat_id == ADMIN_ID:
        return True
    if chat_id not in user_registration_date:
        user_registration_date[chat_id] = datetime.now()
        save_data(user_registration_date, DATA_FILES['user_registration_date'])
    registration_date = user_registration_date[chat_id]
    days_passed = (datetime.now() - registration_date).days
    return days_passed < FREE_PERIOD_DAYS

def get_remaining_free_days(chat_id: int) -> int:
    """Возвращает оставшиеся дней бесплатного периода"""
    if chat_id not in user_registration_date:
        user_registration_date[chat_id] = datetime.now()
        save_data(user_registration_date, DATA_FILES['user_registration_date'])
    registration_date = user_registration_date[chat_id]
    days_passed = (datetime.now() - registration_date).days
    return max(0, FREE_PERIOD_DAYS - days_passed)

def can_user_make_request(chat_id: int) -> tuple[bool, str]:
    """Проверяет может ли пользователь сделать запрос"""
    # Проверка подписки
    if not is_subscription_active(chat_id) and chat_id != ADMIN_ID:
        remaining_free = get_remaining_free_days(chat_id)
        if remaining_free <= 0:
            return False, f"⏳ Бесплатный период закончился. Для продолжения активируйте тариф."
        else:
            return True, ""
    
    # Проверка дневного лимита
    remaining_requests = get_remaining_daily_requests(chat_id)
    if remaining_requests <= 0:
        current_tariff = get_user_tariff(chat_id)
        daily_limit = TARIFFS[current_tariff]["daily_limits"]
        return False, f"📊 Лимит запросов исчерпан ({daily_limit}/день). Попробуйте завтра или улучшите тариф."
    
    return True, ""

# =======================
# ===== УМНАЯ СИСТЕМА ОТВЕТОВ =====
# =======================
def create_concise_response(text: str) -> str:
    """Создает максимально краткий и точный ответ"""
    if not text or len(text.strip()) == 0:
        return "Не удалось получить ответ."
    
    # Убираем лишние вступления и общие фразы
    lines = text.split('\n')
    clean_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Пропускаем общие фразы
        skip_phrases = [
            'конечно', 'разумеется', 'безусловно', 'определенно',
            'я с удовольствием', 'позвольте мне', 'хорошо, давайте',
            'отличный вопрос', 'интересный вопрос', 'что ж,',
            'добрый день', 'приветствую', 'здравствуйте'
        ]
        
        if any(phrase in line.lower() for phrase in skip_phrases):
            continue
            
        clean_lines.append(line)
    
    if not clean_lines:
        return text[:200] + "..." if len(text) > 200 else text
    
    # Берем самую суть - первые 1-2 предложения
    first_line = clean_lines[0]
    sentences = first_line.split('. ')
    
    if len(sentences) > 1:
        # Объединяем первые 2 предложения если они короткие
        if len(sentences[0]) < 50 and len(sentences) > 1:
            result = '. '.join(sentences[:2]) + '.'
        else:
            result = sentences[0] + '.'
    else:
        result = first_line
    
    # Добавляем вторую строку если она важная и не делает ответ слишком длинным
    if len(clean_lines) > 1 and len(result) < 150:
        second_line = clean_lines[1]
        if len(second_line) > 10 and len(second_line) < 100:
            result += ' ' + second_line
    
    # Ограничиваем длину
    if len(result) > 250:
        result = result[:250] + '...'
    
    return result.strip()

# =======================
# ===== КЛАВИАТУРЫ =====
# =======================
def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🚀 Начать работу"),
                KeyboardButton(text="🌟 Обо мне")
            ],
            [
                KeyboardButton(text="⚙️ Настройки"),
                KeyboardButton(text="❓ Помощь"),
                KeyboardButton(text="🌤️ Погода")
            ],
            [
                KeyboardButton(text="💎 Тарифы")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

def get_settings_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎭 Режимы AI"),
                KeyboardButton(text="📊 Статистика")
            ],
            [
                KeyboardButton(text="🎨 Стиль общения"),
                KeyboardButton(text="ℹ️ Информация")
            ],
            [
                KeyboardButton(text="⚡ Быстрые команды")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )

def get_tariffs_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🚀 Default"),
                KeyboardButton(text="⭐ Pro")
            ],
            [
                KeyboardButton(text="💎 Advanced"),
                KeyboardButton(text="👑 Ultimate")
            ],
            [
                KeyboardButton(text="📊 Мой тариф")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )

def get_mode_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🧘 Спокойный"),
                KeyboardButton(text="💬 Обычный")
            ],
            [
                KeyboardButton(text="⚡ Короткий"),
                KeyboardButton(text="🧠 Умный")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )

def get_style_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💫 Дружелюбный"),
                KeyboardButton(text="⚖️ Сбалансированный")
            ],
            [
                KeyboardButton(text="🎯 Деловой"),
                KeyboardButton(text="🎨 Креативный")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )

def get_quick_commands_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📝 Конвертер валют"),
                KeyboardButton(text="🎯 Случайный выбор")
            ],
            [
                KeyboardButton(text="📅 Текущая дата"),
                KeyboardButton(text="⏰ Текущее время")
            ],
            [
                KeyboardButton(text="🔢 Калькулятор"),
                KeyboardButton(text="🎁 Сюрприз")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )

# =======================
# ===== ОСНОВНЫЕ КОМАНДЫ =====
# =======================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    
    # Инициализация пользователя
    if chat_id not in user_registration_date:
        user_registration_date[chat_id] = datetime.now()
        save_data(user_registration_date, DATA_FILES['user_registration_date'])
    
    if chat_id not in user_modes:
        user_modes[chat_id] = "обычный"
        save_data(user_modes, DATA_FILES['user_modes'])
    
    if chat_id not in chat_style:
        chat_style[chat_id] = "balanced"
        save_data(chat_style, DATA_FILES['chat_style'])

    current_mode = user_modes[chat_id]
    remaining_days = get_remaining_days(chat_id)
    current_tariff = get_user_tariff(chat_id)
    remaining_requests = get_remaining_daily_requests(chat_id)
    is_free = is_free_period_active(chat_id)
    
    welcome_text = f"✨ Добро пожаловать!\n\n"
    
    if is_free:
        welcome_text += f"🎁 Бесплатный период: {remaining_days} дней\n"
    else:
        welcome_text += f"💎 Тариф: {TARIFFS[current_tariff]['name']}\n"
        welcome_text += f"📅 Осталось дней: {remaining_days}\n"
    
    welcome_text += f"📊 Запросов сегодня: {remaining_requests}/{TARIFFS[current_tariff]['daily_limits']}\n"
    welcome_text += f"🎭 Режим: {current_mode}\n"
    welcome_text += f"💾 Память: {get_user_memory_limit(chat_id)} сообщений\n"
    welcome_text += f"⚡ Ожидание: {get_user_cooldown(chat_id)} сек\n\n"
    
    if is_free and remaining_days <= 2:
        welcome_text += "💡 Бесплатный период скоро закончится!\n\n"
    
    welcome_text += "Выбери действие 👇"

    await message.answer(welcome_text, reply_markup=get_main_keyboard())

# Обработчики кнопок
@dp.message(F.text == "🚀 Начать работу")
async def handle_start_work(message: types.Message):
    await cmd_start(message)

@dp.message(F.text == "🌟 Обо мне")
async def handle_about(message: types.Message):
    about_text = (
        "🤖 Обо мне\n\n"
        "Я - AI-помощник с функциями:\n"
        "• Умные ответы на вопросы\n"
        "• Работа с текстами и изображениями\n"
        "• Голосовые сообщения\n"
        "• Погода, калькулятор, конвертер\n"
        "• Система тарифов\n\n"
        "Отвечаю кратко и по делу!")
    await message.answer(about_text, reply_markup=get_main_keyboard())

@dp.message(F.text == "⚙️ Настройки")
async def handle_settings(message: types.Message):
    settings_text = "⚙️ Настройки\n\nВыбери категорию:"
    await message.answer(settings_text, reply_markup=get_settings_keyboard())

@dp.message(F.text == "💎 Тарифы")
async def handle_tariffs(message: types.Message):
    tariffs_text = "💎 Доступные тарифы:\n\n"
    
    for tariff_key, tariff_info in TARIFFS.items():
        free_info = " (5 дней бесплатно)" if tariff_info.get("is_free_first", False) else ""
        tariffs_text += f"{tariff_info['name']}{free_info}\n"
        tariffs_text += f"{tariff_info['description']}\n"
        tariffs_text += f"💵 {tariff_info['price']}\n"
        tariffs_text += f"📊 {tariff_info['daily_limits']} запросов/день\n\n"
    
    tariffs_text += "Выбери тариф для деталей 👇"
    await message.answer(tariffs_text, reply_markup=get_tariffs_keyboard())

@dp.message(F.text == "📊 Мой тариф")
async def handle_my_tariff(message: types.Message):
    chat_id = message.chat.id
    current_tariff = get_user_tariff(chat_id)
    tariff_info = TARIFFS[current_tariff]
    remaining_days = get_remaining_days(chat_id)
    remaining_requests = get_remaining_daily_requests(chat_id)
    is_free = is_free_period_active(chat_id)
    
    my_tariff_text = f"💎 Твой тариф: {tariff_info['name']}\n\n"
    
    if is_free:
        my_tariff_text += f"🎁 Бесплатный период: {remaining_days} дней\n"
    else:
        my_tariff_text += f"📅 Осталось дней: {remaining_days}\n"
    
    my_tariff_text += f"📊 Запросов сегодня: {remaining_requests}/{tariff_info['daily_limits']}\n"
    my_tariff_text += f"💾 Память: {get_user_memory_limit(chat_id)} сообщ.\n"
    my_tariff_text += f"⚡ Ожидание: {get_user_cooldown(chat_id)} сек\n\n"
    my_tariff_text += f"Возможности:\n"
    
    for feature in tariff_info['features']:
        my_tariff_text += f"{feature}\n"
    
    if is_free and remaining_days <= 2:
        my_tariff_text += f"\n💡 После окончания бесплатного периода: {tariff_info['price']}"
    
    await message.answer(my_tariff_text)

@dp.message(F.text == "📊 Статистика")
async def handle_stats(message: types.Message):
    chat_id = message.chat.id
    current_tariff = get_user_tariff(chat_id)
    remaining_days = get_remaining_days(chat_id)
    remaining_requests = get_remaining_daily_requests(chat_id)
    total_requests = user_requests_count.get(chat_id, {}).get("total", 0)
    memory_usage = len(conversation_memory.get(chat_id, []))
    is_free = is_free_period_active(chat_id)
    
    stats_text = f"📊 Твоя статистика\n\n"
    
    if is_free:
        stats_text += f"🎁 Бесплатный период: {remaining_days} дней\n"
    else:
        stats_text += f"💎 Тариф: {TARIFFS[current_tariff]['name']}\n"
        stats_text += f"📅 Осталось дней: {remaining_days}\n"
    
    stats_text += f"📨 Запросов сегодня: {remaining_requests}/{TARIFFS[current_tariff]['daily_limits']}\n"
    stats_text += f"📈 Всего запросов: {total_requests}\n"
    stats_text += f"💾 Память: {memory_usage}/{get_user_memory_limit(chat_id)}\n"
    stats_text += f"⚡ Ожидание: {get_user_cooldown(chat_id)} сек\n"
    stats_text += f"✅ Статус: {'Активен' if is_subscription_active(chat_id) else 'Неактивен'}"
    
    await message.answer(stats_text)

@dp.message(F.text.in_(["🚀 Default", "⭐ Pro", "💎 Advanced", "👑 Ultimate"]))
async def handle_tariff_selection(message: types.Message):
    tariff_mapping = {
        "🚀 Default": "default",
        "⭐ Pro": "pro", 
        "💎 Advanced": "advanced",
        "👑 Ultimate": "ultimate"
    }
    
    tariff_key = tariff_mapping.get(message.text, "default")
    tariff_info = TARIFFS[tariff_key]
    
    tariff_text = f"{tariff_info['name']}\n\n"
    tariff_text += f"{tariff_info['description']}\n\n"
    
    if tariff_info.get("is_free_first", False):
        tariff_text += f"🎁 5 дней бесплатно, затем {tariff_info['price']}\n"
    else:
        tariff_text += f"💵 {tariff_info['price']}\n"
    
    tariff_text += f"📊 {tariff_info['daily_limits']} запросов в день\n"
    tariff_text += f"💾 Память: {TARIFF_MEMORY[tariff_key]} сообщений\n"
    tariff_text += f"⚡ Ожидание: {TARIFF_COOLDOWNS[tariff_key]} сек\n\n"
    tariff_text += "Возможности:\n"
    
    for feature in tariff_info['features']:
        tariff_text += f"{feature}\n"
    
    tariff_text += f"\n💎 Для активации обратитесь к администратору"
    
    await message.answer(tariff_text)

@dp.message(F.text == "🎭 Режимы AI")
async def handle_modes(message: types.Message):
    mode_text = "🎭 Выбери режим работы:"
    await message.answer(mode_text, reply_markup=get_mode_keyboard())

@dp.message(F.text.in_(["🧘 Спокойный", "💬 Обычный", "⚡ Короткий", "🧠 Умный"]))
async def handle_mode_selection(message: types.Message):
    chat_id = message.chat.id
    mode_mapping = {
        "🧘 Спокойный": "спокойный",
        "💬 Обычный": "обычный", 
        "⚡ Короткий": "короткий",
        "🧠 Умный": "умный"
    }
    
    new_mode = mode_mapping.get(message.text, "обычный")
    user_modes[chat_id] = new_mode
    save_data(user_modes, DATA_FILES['user_modes'])
    
    await message.answer(f"✅ Режим изменен на: {message.text}", reply_markup=get_settings_keyboard())

@dp.message(F.text == "⬅️ Назад")
async def handle_back(message: types.Message):
    await message.answer("Главное меню", reply_markup=get_main_keyboard())

# =======================
# ===== ОБРАБОТКА СООБЩЕНИЙ =====
# =======================
async def send_thinking_message(chat_id: int) -> int:
    """Отправляет сообщение 'Думаю' и возвращает его ID"""
    message = await bot.send_message(chat_id, "💭 Думаю...")
    return message.message_id

async def delete_thinking_message(chat_id: int, message_id: int):
    """Удаляет сообщение 'Думаю'"""
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception as e:
        logger.error(f"Ошибка удаления сообщения: {e}")

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    """Обработка голосовых сообщений"""
    chat_id = message.chat.id
    
    # Проверка возможности сделать запрос
    can_request, error_msg = can_user_make_request(chat_id)
    if not can_request:
        await message.answer(error_msg)
        return
    
    # Отправляем "Думаю"
    thinking_msg_id = await send_thinking_message(chat_id)
    
    try:
        response_text = "🎤 Получил голосовое сообщение! Для точного ответа напиши свой вопрос текстом."
        
        # Удаляем "Думаю" и отправляем ответ
        await delete_thinking_message(chat_id, thinking_msg_id)
        concise_response = create_concise_response(response_text)
        await message.answer(concise_response)
        
        # Обновляем счетчики
        increment_daily_requests(chat_id)
        
    except Exception as e:
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("❌ Ошибка обработки голосового сообщения")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    """Обработка фото с текстом"""
    chat_id = message.chat.id
    
    # Проверка возможности сделать запрос
    can_request, error_msg = can_user_make_request(chat_id)
    if not can_request:
        await message.answer(error_msg)
        return
    
    thinking_msg_id = await send_thinking_message(chat_id)
    
    try:
        if message.caption:
            # Если есть подпись, работаем с ней
            response_text = f"📸 Вижу фото! Текст: '{message.caption}'. Что нужно сделать?"
        else:
            response_text = "📸 Получил фото! Если на фото есть текст, опиши что нужно сделать."
        
        await delete_thinking_message(chat_id, thinking_msg_id)
        concise_response = create_concise_response(response_text)
        await message.answer(concise_response)
        increment_daily_requests(chat_id)
        
    except Exception as e:
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("❌ Ошибка обработки фото")

@dp.message()
async def handle_all_messages(message: types.Message):
    """Обработка всех текстовых сообщений"""
    chat_id = message.chat.id
    user_text = message.text or ""
    
    # Игнорируем команды и кнопки, которые уже обработаны
    button_texts = [
        "🚀 Начать работу", "🌟 Обо мне", "⚙️ Настройки", "❓ Помощь", 
        "🌤️ Погода", "💎 Тарифы", "📊 Мой тариф", "📊 Статистика",
        "🎭 Режимы AI", "🎨 Стиль общения", "ℹ️ Информация",
        "⚡ Быстрые команды", "⬅️ Назад", "🚀 Default", "⭐ Pro",
        "💎 Advanced", "👑 Ultimate", "🧘 Спокойный", "💬 Обычный",
        "⚡ Короткий", "🧠 Умный", "💫 Дружелюбный", "⚖️ Сбалансированный",
        "🎯 Деловой", "🎨 Креативный", "📝 Конвертер валют", "🎯 Случайный выбор",
        "📅 Текущая дата", "⏰ Текущее время", "🔢 Калькулятор", "🎁 Сюрприз"
    ]
    
    if user_text.startswith('/') or user_text in button_texts:
        return
    
    # Проверка возможности сделать запрос
    can_request, error_msg = can_user_make_request(chat_id)
    if not can_request:
        await message.answer(error_msg)
        return
    
    # Проверка времени ожидания
    current_time = time.time()
    last_request = user_last_request.get(chat_id, 0)
    cooldown = get_user_cooldown(chat_id)
    
    if current_time - last_request < cooldown:
        remaining = cooldown - int(current_time - last_request)
        await message.answer(f"⏳ Подожди {remaining} сек.")
        return
    
    user_last_request[chat_id] = current_time
    
    # Отправляем "Думаю"
    thinking_msg_id = await send_thinking_message(chat_id)
    
    try:
        # Обновляем счетчики
        increment_daily_requests(chat_id)
        user_requests_count[chat_id] = user_requests_count.get(chat_id, {})
        user_requests_count[chat_id]["total"] = user_requests_count[chat_id].get("total", 0) + 1
        save_data(user_requests_count, DATA_FILES['user_requests_count'])
        
        # Обработка быстрых команд
        user_text_lower = user_text.lower()
        
        if any(word in user_text_lower for word in ["погода", "погоду"]):
            city = user_text_lower.replace("погода", "").replace("погоду", "").strip()
            if not city:
                city = "Москва"
            weather_info = await get_weather(city)
            response_text = weather_info
            
        elif "курс" in user_text_lower or "валют" in user_text_lower:
            response_text = "💱 Курсы валют:\nUSD → 90.5 ₽\nEUR → 98.2 ₽\nCNY → 12.5 ₽"
            
        elif any(word in user_text_lower for word in ["посчитай", "сколько будет", "="]):
            # Простой калькулятор
            try:
                expr = user_text_lower.replace("посчитай", "").replace("сколько будет", "").replace("=", "").strip()
                # Безопасное вычисление
                allowed_chars = set('0123456789+-*/.() ')
                if all(c in allowed_chars for c in expr):
                    result = eval(expr)
                    response_text = f"🔢 {expr} = {result}"
                else:
                    response_text = "❌ Небезопасное выражение"
            except:
                response_text = "❌ Не могу вычислить"
                
        else:
            # AI-ответ
            try:
                # Подготовка контекста
                if chat_id not in conversation_memory:
                    conversation_memory[chat_id] = []
                
                messages = [
                    {"role": "system", "content": "Отвечай максимально кратко и по делу. Без лишних слов и вступлений. Только суть. Ответ должен быть не более 2-3 предложений."},
                    {"role": "user", "content": user_text}
                ]
                
                # Добавляем историю если есть
                for msg in conversation_memory[chat_id][-3:]:  # Только последние 3 сообщения для экономии
                    messages.insert(1, msg)
                
                response = client.chat.complete(model=model, messages=messages)
                ai_text = response.choices[0].message.content
                
                # Сохраняем в память
                conversation_memory[chat_id].append({"role": "user", "content": user_text})
                conversation_memory[chat_id].append({"role": "assistant", "content": ai_text})
                
                # Ограничиваем память
                memory_limit = get_user_memory_limit(chat_id)
                if len(conversation_memory[chat_id]) > memory_limit:
                    conversation_memory[chat_id] = conversation_memory[chat_id][-memory_limit:]
                
                save_data(conversation_memory, DATA_FILES['conversation_memory'])
                response_text = ai_text
                
            except Exception as e:
                logger.error(f"AI error: {e}")
                response_text = "⚠️ Ошибка, попробуй еще раз"
        
        # Отправляем краткий ответ
        await delete_thinking_message(chat_id, thinking_msg_id)
        concise_response = create_concise_response(response_text)
        await message.answer(concise_response)
        
    except Exception as e:
        logger.error(f"Handler error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("❌ Ошибка")

async def get_weather(city: str) -> str:
    """Получение погоды"""
    try:
        city_clean = city.strip()
        city_mapping = {
            "новосибирск": "Novosibirsk",
            "москва": "Moscow", 
            "санкт-петербург": "Saint Petersburg",
            "спб": "Saint Petersburg",
            "питер": "Saint Petersburg"
        }

        api_city = city_mapping.get(city_clean.lower(), city_clean)
        url = f"http://api.openweathermap.org/data/2.5/weather?q={api_city}&appid={openweather_api_key}&units=metric&lang=ru"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    temp = data["main"]["temp"]
                    feels = data["main"]["feels_like"]
                    desc = data["weather"][0]["description"]
                    return f"🌤️ {city_clean.title()}: {temp}°C (ощущается {feels}°C), {desc}"
                else:
                    return f"🌫️ Не удалось получить погоду для {city_clean}"
    except Exception as e:
        return "🌪️ Ошибка получения погоды"

# =======================
# ===== ЗАПУСК БОТА =====
# =======================
async def main():
    logger.info("🚀 Запуск бота...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("🤖 Бот запущен!")
    print(f"💎 Тарифы: {len(TARIFFS)} варианта")
    print(f"💾 Пользователей: {len(user_registration_date)}")
    print("✅ Готов к работе!")
    asyncio.run(main())
