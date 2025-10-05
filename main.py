import asyncio
import logging
import random
import aiohttp
import time
import base64
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from typing import Dict, Any, List, Optional
import os
from mistralai import Mistral
import pickle
import json

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
    'user_daily_requests': 'user_daily_requests.pkl',
    'admin_logs': 'admin_logs.pkl',
    'admin_temp_data': 'admin_temp_data.pkl'
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
admin_logs = load_data(DATA_FILES['admin_logs'], [])
admin_temp_data = load_data(DATA_FILES['admin_temp_data'], {})

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
            return False, f"Бесплатный период закончился. Для продолжения работы активируйте один из тарифов."
        else:
            return True, ""
    
    # Проверка дневного лимита
    remaining_requests = get_remaining_daily_requests(chat_id)
    if remaining_requests <= 0:
        current_tariff = get_user_tariff(chat_id)
        daily_limit = TARIFFS[current_tariff]["daily_limits"]
        return False, f"Дневной лимит запросов исчерпан ({daily_limit}/день). Попробуйте завтра или улучшите тариф."
    
    return True, ""

# =======================
# ===== РЕАЛЬНАЯ ОБРАБОТКА ФОТО И ГОЛОСА =====
# =======================
async def extract_text_from_image(image_bytes: bytes) -> str:
    """Извлекает текст из изображения с помощью Mistral OCR"""
    try:
        # Кодируем изображение в base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Создаем сообщение с изображением для Mistral
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{image_base64}"
                    },
                    {
                        "type": "text", 
                        "text": "Пожалуйста, извлеки весь текст с этого изображения. Верни только распознанный текст без дополнительных комментариев."
                    }
                ]
            }
        ]
        
        # Используем модель с поддержкой зрения
        response = client.chat.complete(
            model="pixtral-12b-2409",  # Модель с поддержкой изображений
            messages=messages,
            max_tokens=1000
        )
        
        extracted_text = response.choices[0].message.content.strip()
        
        if not extracted_text or "не вижу текста" in extracted_text.lower() or "не могу распознать" in extracted_text.lower():
            return "❌ Не удалось распознать текст на изображении. Попробуйте с более четким фото."
        
        return f"📝 Распознанный текст:\n\n{extracted_text}"
        
    except Exception as e:
        logger.error(f"Mistral OCR error: {e}")
        return "❌ Ошибка распознавания текста. Попробуйте другое изображение."

async def transcribe_audio(audio_bytes: bytes) -> str:
    """Транскрибирует аудио с помощью Mistral Speech-to-Text"""
    try:
        # Для Mistral нужно использовать их API для аудио
        # Временно используем заглушку, пока не настроим полноценную интеграцию
        return "🎤 Голосовое сообщение получено. В настоящее время функция распознавания речи находится в разработке. Пожалуйста, напишите ваш вопрос текстом."
        
        # Когда будет доступно, код будет выглядеть так:
        # response = client.audio.transcriptions.create(
        #     file=audio_bytes,
        #     model="mistral-whisper-large-v3",
        #     response_format="text"
        # )
        # return response.text
        
    except Exception as e:
        logger.error(f"Audio transcription error: {e}")
        return "❌ Ошибка распознавания голосового сообщения. Попробуйте написать текст."

# =======================
# ===== АДМИН ПАНЕЛЬ =====
# =======================
def add_admin_log(action: str, admin_id: int = ADMIN_ID, target_user: Optional[int] = None):
    """Добавляет запись в лог админ-панели"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "admin_id": admin_id,
        "action": action,
        "target_user": target_user
    }
    admin_logs.append(log_entry)
    # Сохраняем только последние 100 записей
    if len(admin_logs) > 100:
        admin_logs.pop(0)
    save_data(admin_logs, DATA_FILES['admin_logs'])

def get_main_keyboard(chat_id: int) -> ReplyKeyboardMarkup:
    """Главная клавиатура с админ-панелью для админа"""
    keyboard = [
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
    ]
    
    # Добавляем кнопку админ-панели только для администратора
    if chat_id == ADMIN_ID:
        keyboard.append([KeyboardButton(text="🛠️ Админ-панель")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура админ-панели"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👥 Статистика пользователей"),
                KeyboardButton(text="📊 Общая статистика")
            ],
            [
                KeyboardButton(text="💎 Управление тарифами"),
                KeyboardButton(text="📢 Рассылка")
            ],
            [
                KeyboardButton(text="🔍 Поиск пользователя"),
                KeyboardButton(text="📋 Логи действий")
            ],
            [
                KeyboardButton(text="⚙️ Сброс данных пользователя"),
                KeyboardButton(text="🔄 Сброс дневных лимитов")
            ],
            [
                KeyboardButton(text="⬅️ Главное меню")
            ]
        ],
        resize_keyboard=True
    )

def get_tariff_management_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура управления тарифами"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🚀 Выдать Default"),
                KeyboardButton(text="⭐ Выдать Pro")
            ],
            [
                KeyboardButton(text="💎 Выдать Advanced"),
                KeyboardButton(text="👑 Выдать Ultimate")
            ],
            [
                KeyboardButton(text="🗑️ Сбросить тариф"),
                KeyboardButton(text="📅 Продлить на 30 дней")
            ],
            [
                KeyboardButton(text="⬅️ Админ-панель")
            ]
        ],
        resize_keyboard=True
    )

async def get_user_info(user_id: int) -> str:
    """Получает информацию о пользователе"""
    try:
        user = await bot.get_chat(user_id)
        username = f"@{user.username}" if user.username else "Нет username"
        first_name = user.first_name or "Не указано"
        last_name = user.last_name or "Не указано"
        
        tariff = get_user_tariff(user_id)
        remaining_days = get_remaining_days(user_id)
        remaining_requests = get_remaining_daily_requests(user_id)
        total_requests = user_requests_count.get(user_id, {}).get("total", 0)
        reg_date = user_registration_date.get(user_id, "Не зарегистрирован")
        
        if isinstance(reg_date, datetime):
            reg_date = reg_date.strftime("%Y-%m-%d %H:%M")
        
        info = f"👤 Информация о пользователе:\n\n"
        info += f"🆔 ID: {user_id}\n"
        info += f"👤 Имя: {first_name} {last_name}\n"
        info += f"📱 Username: {username}\n"
        info += f"📅 Регистрация: {reg_date}\n"
        info += f"💎 Тариф: {TARIFFS[tariff]['name']}\n"
        info += f"⏳ Осталось дней: {remaining_days}\n"
        info += f"📊 Запросов сегодня: {remaining_requests}/{TARIFFS[tariff]['daily_limits']}\n"
        info += f"📈 Всего запросов: {total_requests}\n"
        info += f"✅ Статус: {'Активен' if is_subscription_active(user_id) else 'Неактивен'}"
        
        return info
    except Exception as e:
        return f"❌ Ошибка получения информации: {e}"

def set_admin_temp(admin_id: int, key: str, value: Any):
    """Сохраняет временные данные админа"""
    if admin_id not in admin_temp_data:
        admin_temp_data[admin_id] = {}
    admin_temp_data[admin_id][key] = value
    save_data(admin_temp_data, DATA_FILES['admin_temp_data'])

def get_admin_temp(admin_id: int, key: str, default: Any = None) -> Any:
    """Получает временные данные админа"""
    return admin_temp_data.get(admin_id, {}).get(key, default)

# =======================
# ===== СИСТЕМА ОТВЕТОВ GLEMIXAI =====
# =======================
def create_glemixai_response(text: str, message_type: str = "normal") -> str:
    """Создает профессиональный женский ответ в стиле GlemixAI"""
    if not text or len(text.strip()) == 0:
        responses = [
            "Не удалось получить ответ. Пожалуйста, повторите запрос.",
            "Произошла ошибка при обработке запроса. Попробуйте еще раз.",
            "Не совсем поняла ваш вопрос. Можете уточнить?"
        ]
        return random.choice(responses)
    
    # Профессиональные вступления
    if message_type == "weather":
        intros = ["Вот информация о погоде:", "Погодные условия:", "Текущая погода:"]
    elif message_type == "currency":
        intros = ["Актуальные курсы валют:", "Курсы на сегодня:", "Вот текущие курсы:"]
    elif message_type == "calculation":
        intros = ["Результат вычисления:", "Ответ:", "Получилось:"]
    elif message_type == "photo_text":
        intros = ["Текст с изображения:", "Распознанный текст:", "Вот что удалось прочитать:"]
    elif message_type == "voice":
        intros = ["Расшифровка голосового:", "Текст с голосового:", "Распознанная речь:"]
    elif message_type == "document":
        intros = ["Проанализировала ваш документ:", "Вот анализ материала:", "По вашему заданию:"]
    else:
        intros = [
            "Вот что я могу сказать:",
            "Отвечаю на ваш вопрос:",
            "По этому вопросу:",
            "Мой ответ:",
            "Вот информация:"
        ]
    
    intro = random.choice(intros)
    
    # Профессиональные заключения
    outros = [
        "\n\nНадеюсь, это поможет.",
        "\n\nЕсли нужна дополнительная помощь - обращайтесь.",
        "\n\nЕсть еще вопросы?",
        "\n\nМогу помочь с чем-то еще."
    ]
    
    outro = random.choice(outros)
    
    # Ограничиваем длину основного текста
    if len(text) > 1500:
        main_text = text[:1500] + "..."
    else:
        main_text = text
    
    # Собираем финальный ответ
    response = f"{intro}\n\n{main_text}{outro}"
    
    return response

# =======================
# ===== КЛАВИАТУРЫ =====
# =======================
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
    
    welcome_text = f"🤖 GlemixAI\n\nДобро пожаловать! Я ваш AI-помощник.\n\n"
    
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
        welcome_text += "💡 Бесплатный период скоро закончится.\n\n"
    
    welcome_text += "Выберите действие:"

    await message.answer(welcome_text, reply_markup=get_main_keyboard(chat_id))

# =======================
# ===== ОБРАБОТКА ФОТО С REAL OCR =====
# =======================
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    """Обработка фото с реальным OCR через Mistral"""
    chat_id = message.chat.id
    
    # Проверка возможности сделать запрос
    can_request, error_msg = can_user_make_request(chat_id)
    if not can_request:
        await message.answer(error_msg)
        return
    
    # Отправляем "Думаю"
    thinking_msg_id = await send_thinking_message(chat_id)
    
    try:
        # Скачиваем фото
        photo = message.photo[-1]  # Берем самое качественное фото
        file_info = await bot.get_file(photo.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        image_bytes = downloaded_file.read()
        
        # Извлекаем текст с помощью Mistral OCR
        extracted_text = await extract_text_from_image(image_bytes)
        
        # Обновляем счетчики
        increment_daily_requests(chat_id)
        
        # Отправляем ответ
        await delete_thinking_message(chat_id, thinking_msg_id)
        
        if extracted_text.startswith("❌"):
            # Если ошибка распознавания
            await message.answer(extracted_text)
        else:
            # Если текст распознан успешно
            response = create_glemixai_response(extracted_text, "photo_text")
            await message.answer(response)
            
            # Предлагаем помощь с распознанным текстом
            help_text = "📋 Нужна помощь с распознанным текстом? Задайте вопрос или попросите что-то сделать с этим текстом."
            await message.answer(help_text)
        
    except Exception as e:
        logger.error(f"Photo processing error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("❌ Ошибка обработки изображения. Попробуйте другое фото.")

# =======================
# ===== ОБРАБОТКА ГОЛОСОВЫХ СООБЩЕНИЙ =====
# =======================
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
        # Скачиваем голосовое сообщение
        voice = message.voice
        file_info = await bot.get_file(voice.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        audio_bytes = downloaded_file.read()
        
        # Транскрибируем аудио
        transcribed_text = await transcribe_audio(audio_bytes)
        
        # Обновляем счетчики
        increment_daily_requests(chat_id)
        
        # Отправляем ответ
        await delete_thinking_message(chat_id, thinking_msg_id)
        
        if transcribed_text.startswith("🎤"):
            # Если это заглушка (функция в разработке)
            await message.answer(transcribed_text)
        else:
            # Если аудио распознано успешно
            response = create_glemixai_response(transcribed_text, "voice")
            await message.answer(response)
        
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("❌ Ошибка обработки голосового сообщения. Попробуйте написать текст.")

# =======================
# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
# =======================
async def send_thinking_message(chat_id: int) -> int:
    """Отправляет сообщение 'Думаю' и возвращает его ID"""
    thinking_messages = [
        "💭 Обрабатываю запрос...",
        "🤔 Анализирую...", 
        "⚡ Генерирую ответ...",
        "🎯 Формирую решение...",
        "📝 Распознаю текст...",
        "🎤 Расшифровываю аудио..."
    ]
    message = await bot.send_message(chat_id, random.choice(thinking_messages))
    return message.message_id

async def delete_thinking_message(chat_id: int, message_id: int):
    """Удаляет сообщение 'Думаю'"""
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception as e:
        logger.error(f"Ошибка удаления сообщения: {e}")

# =======================
# ===== ОБРАБОТКА ОСНОВНЫХ КНОПОК =====
# =======================
@dp.message(F.text == "🚀 Начать работу")
async def handle_start_work(message: types.Message):
    await cmd_start(message)

@dp.message(F.text == "🌟 Обо мне")
async def handle_about(message: types.Message):
    about_text = (
        "🤖 GlemixAI\n\n"
        "Я - современный AI-помощник с реальными функциями:\n\n"
        "• 📝 Извлечение текста с фото (OCR)\n" 
        "• 🎤 Распознавание голосовых сообщений\n"
        "• 🧠 Умные ответы на вопросы\n"
        "• 🌤️ Погода, калькулятор, конвертер\n"
        "• 💎 Гибкая система тарифов\n\n"
        "Работаю на Mistral AI - одном из лучших AI-провайдеров!"
    )
    await message.answer(about_text, reply_markup=get_main_keyboard(message.from_user.id))

@dp.message(F.text == "⚙️ Настройки")
async def handle_settings(message: types.Message):
    settings_text = "⚙️ Настройки\n\nВыберите категорию:"
    await message.answer(settings_text, reply_markup=get_settings_keyboard())

@dp.message(F.text == "❓ Помощь")
async def handle_help(message: types.Message):
    help_text = (
        "❓ Помощь по GlemixAI\n\n"
        "Что я умею:\n"
        "• 📸 Извлекать текст с фотографий\n"
        "• 🎤 Распознавать голосовые сообщения\n" 
        "• 💬 Отвечать на любые вопросы\n"
        "• 🌤️ Показывать погоду\n"
        "• 🔢 Выполнять вычисления\n\n"
        "Просто отправьте:\n"
        "• Фото с текстом - распознаю его\n"
        "• Голосовое сообщение - расшифрую\n"
        "• Текст - отвечу на вопрос"
    )
    await message.answer(help_text)

@dp.message(F.text == "🌤️ Погода")
async def handle_weather_button(message: types.Message):
    await message.answer("🌤️ Введите название города для получения погоды:")

@dp.message(F.text == "💎 Тарифы")
async def handle_tariffs(message: types.Message):
    tariffs_text = "💎 Доступные тарифы:\n\n"
    
    for tariff_id, tariff_info in TARIFFS.items():
        tariffs_text += f"{tariff_info['name']}\n"
        tariffs_text += f"Цена: {tariff_info['price']}\n"
        tariffs_text += f"Лимит: {tariff_info['daily_limits']} запросов/день\n"
        tariffs_text += f"Ожидание: {TARIFF_COOLDOWNS[tariff_id]} сек\n\n"
    
    await message.answer(tariffs_text, reply_markup=get_tariffs_keyboard())

@dp.message(F.text == "📊 Мой тариф")
async def handle_my_tariff(message: types.Message):
    chat_id = message.from_user.id
    current_tariff = get_user_tariff(chat_id)
    remaining_days = get_remaining_days(chat_id)
    remaining_requests = get_remaining_daily_requests(chat_id)
    
    tariff_text = f"📊 Ваш текущий тариф:\n\n"
    tariff_text += f"💎 {TARIFFS[current_tariff]['name']}\n"
    tariff_text += f"⏳ Осталось дней: {remaining_days}\n"
    tariff_text += f"📊 Запросов сегодня: {remaining_requests}/{TARIFFS[current_tariff]['daily_limits']}\n"
    tariff_text += f"⚡ Ожидание: {get_user_cooldown(chat_id)} сек\n"
    tariff_text += f"💾 Память: {get_user_memory_limit(chat_id)} сообщений"
    
    await message.answer(tariff_text)

@dp.message(F.text == "⬅️ Назад")
async def handle_back(message: types.Message):
    await message.answer("Главное меню", reply_markup=get_main_keyboard(message.from_user.id))

# =======================
# ===== ОБРАБОТКА ОБЫЧНЫХ СООБЩЕНИЙ =====
# =======================
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
        "📅 Текущая дата", "⏰ Текущее время", "🔢 Калькулятор", "🎁 Сюрприз",
        "🛠️ Админ-панель", "👥 Статистика пользователей", "📊 Общая статистика",
        "💎 Управление тарифами", "📢 Рассылка", "🔍 Поиск пользователя", 
        "📋 Логи действий", "⚙️ Сброс данных пользователя", "🔄 Сброс дневных лимитов",
        "🚀 Выдать Default", "⭐ Выдать Pro", "💎 Выдать Advanced", "👑 Выдать Ultimate",
        "🗑️ Сбросить тариф", "📅 Продлить на 30 дней", "⬅️ Админ-панель", "⬅️ Главное меню"
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
        await message.answer(f"⏳ Подождите {remaining} сек. перед следующим запросом.")
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
        message_type = "normal"
        
        if any(word in user_text_lower for word in ["погода", "погоду"]):
            city = user_text_lower.replace("погода", "").replace("погоду", "").strip()
            if not city:
                city = "Москва"
            weather_info = await get_weather(city)
            response_text = weather_info
            message_type = "weather"
            
        elif "курс" in user_text_lower or "валют" in user_text_lower:
            response_text = "💱 Курсы валют:\nUSD → 90.5 ₽\nEUR → 98.2 ₽\nCNY → 12.5 ₽"
            message_type = "currency"
            
        elif any(word in user_text_lower for word in ["посчитай", "сколько будет", "=", "calc", "calculate"]):
            # Простой калькулятор
            try:
                expr = user_text_lower.replace("посчитай", "").replace("сколько будет", "").replace("=", "").replace("calc", "").replace("calculate", "").strip()
                # Безопасное вычисление
                allowed_chars = set('0123456789+-*/.() ')
                if all(c in allowed_chars for c in expr):
                    result = eval(expr)
                    response_text = f"🔢 {expr} = {result}"
                else:
                    response_text = "❌ Небезопасное выражение"
                message_type = "calculation"
            except:
                response_text = "❌ Не могу вычислить"
                message_type = "calculation"
                
        else:
            # AI-ответ с профессиональным промптом
            try:
                # Подготовка контекста
                if chat_id not in conversation_memory:
                    conversation_memory[chat_id] = []
                
                # Профессиональный системный промпт для GlemixAI
                system_prompt = """Ты - GlemixAI, современный AI-помощник женского пола. Отвечай профессионально, четко и по делу.

Основные принципы:
- Будь точной и информативной
- Фокусируйся на решении задачи пользователя
- Отвечай развернуто, но без лишних деталей
- Сохраняй профессиональный тон
- Используй четкие формулировки

Отвечай на русском языке, 3-5 предложений. Будь полезной и эффективной в решении задач."""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ]
                
                # Добавляем историю если есть
                for msg in conversation_memory[chat_id][-3:]:
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
                response_text = "⚠️ Ошибка при обработке запроса. Попробуйте еще раз."
        
        # Отправляем ответ
        await delete_thinking_message(chat_id, thinking_msg_id)
        glemixai_response = create_glemixai_response(response_text, message_type)
        await message.answer(glemixai_response)
        
    except Exception as e:
        logger.error(f"Handler error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.")

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
                    
                    return f"🌤️ Погода в {city_clean.title()}: {temp}°C (ощущается {feels}°C), {desc}"
                else:
                    return f"Не удалось получить погоду для {city_clean}"
    except Exception as e:
        return "Ошибка получения погоды"

# =======================
# ===== ЗАПУСК БОТА =====
# =======================
async def main():
    logger.info("🚀 Запуск GlemixAI...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("🤖 GlemixAI запущен!")
    print(f"💎 Тарифы: {len(TARIFFS)} варианта")
    print(f"💾 Пользователей: {len(user_registration_date)}")
    print(f"🛠️ Админ ID: {ADMIN_ID}")
    print("✅ GlemixAI готов к работе!")
    asyncio.run(main())
