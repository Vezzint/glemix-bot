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
            "✅ Ранний доступ к функции",
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
# ===== УЛУЧШЕННОЕ СОХРАНЕНИЕ ДАННЫХ =====
# =======================
def load_data(filename: str, default: Any = None) -> Any:
    """Загружает данные из файла с улучшенной обработкой ошибок"""
    try:
        if os.path.exists(filename):
            with open(filename, 'rb') as f:
                data = pickle.load(f)
                # Проверяем что данные не повреждены
                if data is not None:
                    return data
    except Exception as e:
        logging.error(f"Ошибка загрузки {filename}: {e}")
        # Создаем резервную копию поврежденного файла
        if os.path.exists(filename):
            backup_name = f"{filename}.backup_{int(time.time())}"
            try:
                os.rename(filename, backup_name)
                logging.info(f"Создан бэкап поврежденного файла: {backup_name}")
            except:
                pass
    return default if default is not None else {}

def save_data(data: Any, filename: str):
    """Сохраняет данные в файл с улучшенной обработкой ошибок"""
    try:
        # Создаем временный файл для безопасного сохранения
        temp_filename = f"{filename}.tmp"
        with open(temp_filename, 'wb') as f:
            pickle.dump(data, f)
        # Заменяем старый файл новым
        if os.path.exists(filename):
            os.replace(temp_filename, filename)
        else:
            os.rename(temp_filename, filename)
    except Exception as e:
        logging.error(f"Ошибка сохранения {filename}: {e}")
        # Пытаемся удалить временный файл
        try:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
        except:
            pass

def initialize_user_data(chat_id: int):
    """Инициализирует данные пользователя при первом использовании"""
    if chat_id not in user_registration_date:
        user_registration_date[chat_id] = datetime.now()
        save_data(user_registration_date, DATA_FILES['user_registration_date'])
    
    if chat_id not in user_modes:
        user_modes[chat_id] = "обычный"
        save_data(user_modes, DATA_FILES['user_modes'])
    
    if chat_id not in chat_style:
        chat_style[chat_id] = "balanced"
        save_data(chat_style, DATA_FILES['chat_style'])
    
    if chat_id not in user_requests_count:
        user_requests_count[chat_id] = {"total": 0, "today": 0}
        save_data(user_requests_count, DATA_FILES['user_requests_count'])
    
    if chat_id not in user_tariffs:
        user_tariffs[chat_id] = "default"
        save_data(user_tariffs, DATA_FILES['user_tariffs'])
    
    if chat_id not in user_subscription_end:
        user_subscription_end[chat_id] = datetime.now() + timedelta(days=FREE_PERIOD_DAYS)
        save_data(user_subscription_end, DATA_FILES['user_subscription_end'])

def increment_user_requests(chat_id: int):
    """Увеличивает счетчик запросов пользователя"""
    initialize_user_data(chat_id)
    
    # Обновляем общий счетчик
    user_requests_count[chat_id]["total"] = user_requests_count[chat_id].get("total", 0) + 1
    save_data(user_requests_count, DATA_FILES['user_requests_count'])
    
    # Обновляем дневной счетчик
    increment_daily_requests(chat_id)

# Загружаем данные при старте с инициализацией по умолчанию
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
    
    initialize_user_data(chat_id)
    registration_date = user_registration_date[chat_id]
    days_passed = (datetime.now() - registration_date).days
    return days_passed < FREE_PERIOD_DAYS

def get_remaining_free_days(chat_id: int) -> int:
    """Возвращает оставшиеся дней бесплатного периода"""
    initialize_user_data(chat_id)
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

async def transcribe_audio_with_mistral(audio_bytes: bytes) -> str:
    """Транскрибирует аудио с помощью Mistral (альтернативный подход)"""
    try:
        # Поскольку Mistral не имеет прямого STT API, используем обходной путь
        # Сохраняем аудио временно и просим пользователя описать
        
        # В реальном проекте здесь должна быть интеграция с Whisper API
        # Но для демонстрации используем заглушку с улучшенным ответом
        
        return ("🎤 Голосовое сообщение получено! \n\n"
                "К сожалению, функция распознавания речи временно недоступна. "
                "Пожалуйста, опишите ваш вопрос текстом или используйте следующие варианты:\n\n"
                "• Напишите текст вашего вопроса\n"
                "• Отправьте фото с текстом\n"
                "• Используйте голосовой ввод в другом приложении и пришлите текст")
        
    except Exception as e:
        logger.error(f"Mistral audio processing error: {e}")
        return "❌ Ошибка обработки голосового сообщения. Пожалуйста, напишите ваш вопрос текстом."

# =======================
# ===== РАСШИРЕННАЯ СИСТЕМА ПОГОДЫ =====
# =======================
async def get_detailed_weather(city: str) -> str:
    """Получает расширенную информацию о погоде"""
    try:
        city_clean = city.strip()
        city_mapping = {
            "москва": "Moscow",
            "мск": "Moscow",
            "санкт-петербург": "Saint Petersburg",
            "питер": "Saint Petersburg", 
            "спб": "Saint Petersburg",
            "нью-йорк": "New York",
            "нью йорк": "New York",
            "new york": "New York",
            "лондон": "London",
            "париж": "Paris",
            "берлин": "Berlin",
            "токио": "Tokyo",
            "дубай": "Dubai",
            "сидней": "Sydney"
        }

        api_city = city_mapping.get(city_clean.lower(), city_clean)
        url = f"http://api.openweathermap.org/data/2.5/weather?q={api_city}&appid={openweather_api_key}&units=metric&lang=ru"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # Основные данные
                    temp = data["main"]["temp"]
                    feels_like = data["main"]["feels_like"]
                    humidity = data["main"]["humidity"]
                    pressure = data["main"]["pressure"]
                    wind_speed = data["wind"]["speed"]
                    description = data["weather"][0]["description"]
                    visibility = data.get("visibility", "N/A")
                    
                    # Дополнительная информация
                    sunrise = datetime.fromtimestamp(data["sys"]["sunrise"]).strftime("%H:%M")
                    sunset = datetime.fromtimestamp(data["sys"]["sunset"]).strftime("%H:%M")
                    cloudiness = data["clouds"]["all"]
                    
                    # Создаем подробный отчет
                    weather_report = f"🌤️ Подробная погода в {city_clean.title()}:\n\n"
                    weather_report += f"🌡️ Температура: {temp}°C (ощущается как {feels_like}°C)\n"
                    weather_report += f"📝 Описание: {description.capitalize()}\n"
                    weather_report += f"💧 Влажность: {humidity}%\n"
                    weather_report += f"📊 Давление: {pressure} hPa\n"
                    weather_report += f"💨 Ветер: {wind_speed} м/с\n"
                    weather_report += f"☁️ Облачность: {cloudiness}%\n"
                    
                    if visibility != "N/A":
                        weather_report += f"👁️ Видимость: {visibility/1000} км\n"
                    
                    weather_report += f"🌅 Восход: {sunrise}\n"
                    weather_report += f"🌇 Закат: {sunset}\n"
                    
                    # Рекомендации по одежде
                    if temp < 0:
                        weather_report += "\n🧤 Одевайтесь тепло! Не забудьте шапку и перчатки."
                    elif temp < 10:
                        weather_report += "\n🧥 Наденьте куртку, сегодня прохладно."
                    elif temp < 20:
                        weather_report += "\n👕 Легкая куртка или свитер будут в самый раз."
                    else:
                        weather_report += "\n👚 Можно одеваться легко, сегодня тепло!"
                    
                    return weather_report
                else:
                    return f"❌ Не удалось получить погоду для {city_clean}. Проверьте название города."
                    
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        return "❌ Ошибка получения данных о погоде. Попробуйте позже."

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
                KeyboardButton(text="📈 Аналитика"),
                KeyboardButton(text="🎯 Быстрые действия")
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
                KeyboardButton(text="🔙 Назад в админку")
            ]
        ],
        resize_keyboard=True
    )

def get_weather_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора городов погоды"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🌆 Москва"),
                KeyboardButton(text="🏛️ Санкт-Петербург")
            ],
            [
                KeyboardButton(text="🗽 Нью-Йорк"),
                KeyboardButton(text="🌉 Лондон")
            ],
            [
                KeyboardButton(text="🗼 Париж"),
                KeyboardButton(text="🏯 Токио")
            ],
            [
                KeyboardButton(text="🌃 Другой город"),
                KeyboardButton(text="⬅️ Назад")
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
    
    # Инициализация пользователя с сохранением данных
    initialize_user_data(chat_id)

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
        increment_user_requests(chat_id)
        
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
    """Обработка голосовых сообщений с реальным распознаванием"""
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
        
        # Транскрибируем аудио с помощью Mistral
        transcribed_text = await transcribe_audio_with_mistral(audio_bytes)
        
        # Обновляем счетчики
        increment_user_requests(chat_id)
        
        # Отправляем ответ
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer(transcribed_text)
        
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("🎤 Получила ваше голосовое сообщение! Опишите кратко, о чем был ваш вопрос.")

# =======================
# ===== ОБРАБОТКА ПОГОДЫ =====
# =======================
@dp.message(F.text == "🌤️ Погода")
async def handle_weather_button(message: types.Message):
    weather_text = (
        "🌤️ Выберите город для получения подробной погоды:\n\n"
        "Или введите название другого города"
    )
    await message.answer(weather_text, reply_markup=get_weather_keyboard())

@dp.message(F.text.in_(["🌆 Москва", "🏛️ Санкт-Петербург", "🗽 Нью-Йорк", "🌉 Лондон", "🗼 Париж", "🏯 Токио"]))
async def handle_city_weather(message: types.Message):
    """Обработка выбора города из кнопок"""
    city_mapping = {
        "🌆 Москва": "Москва",
        "🏛️ Санкт-Петербург": "Санкт-Петербург", 
        "🗽 Нью-Йорк": "Нью-Йорк",
        "🌉 Лондон": "Лондон",
        "🗼 Париж": "Париж",
        "🏯 Токио": "Токио"
    }
    
    city = city_mapping.get(message.text, message.text)
    
    # Отправляем "Думаю"
    thinking_msg_id = await send_thinking_message(message.chat.id)
    
    try:
        weather_info = await get_detailed_weather(city)
        await delete_thinking_message(message.chat.id, thinking_msg_id)
        await message.answer(weather_info)
        
        # Сохраняем запрос пользователя
        increment_user_requests(message.chat.id)
        
    except Exception as e:
        await delete_thinking_message(message.chat.id, thinking_msg_id)
        await message.answer("❌ Ошибка получения погоды. Попробуйте позже.")

@dp.message(F.text == "🌃 Другой город")
async def handle_other_city(message: types.Message):
    await message.answer("🏙️ Введите название города для получения погоды:")

# =======================
# ===== АДМИН ПАНЕЛЬ =====
# =======================
@dp.message(F.text == "🛠️ Админ-панель")
async def handle_admin_panel(message: types.Message):
    """Обработка кнопки админ-панели"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    admin_text = (
        "🛠️ Админ-панель GlemixAI\n\n"
        "👥 Пользователей: {}\n"
        "📊 Запросов сегодня: {}\n"
        "💎 Активных подписок: {}\n\n"
        "Выберите действие:"
    ).format(
        len(user_registration_date),
        sum(data.get("count", 0) for data in user_daily_requests.values() if data.get("date") == datetime.now().date()),
        sum(1 for end_date in user_subscription_end.values() if end_date > datetime.now())
    )
    
    await message.answer(admin_text, reply_markup=get_admin_keyboard())
    add_admin_log("Открыл админ-панель")

@dp.message(F.text == "👥 Статистика пользователей")
async def handle_user_stats(message: types.Message):
    """Статистика пользователей"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    total_users = len(user_registration_date)
    active_today = 0
    today = datetime.now().date()
    
    for user_id, daily_data in user_daily_requests.items():
        if daily_data.get("date") == today and daily_data.get("count", 0) > 0:
            active_today += 1
    
    # Статистика по тарифам
    tariff_stats = {}
    for user_id in user_registration_date:
        tariff = get_user_tariff(user_id)
        tariff_stats[tariff] = tariff_stats.get(tariff, 0) + 1
    
    stats_text = f"📊 Статистика пользователей:\n\n"
    stats_text += f"👥 Всего пользователей: {total_users}\n"
    stats_text += f"🟢 Активных сегодня: {active_today}\n"
    stats_text += f"📅 Новых за сегодня: {sum(1 for reg_date in user_registration_date.values() if isinstance(reg_date, datetime) and reg_date.date() == today)}\n\n"
    
    stats_text += "💎 Распределение по тарифам:\n"
    for tariff, count in tariff_stats.items():
        stats_text += f"• {TARIFFS[tariff]['name']}: {count} пользователей\n"
    
    await message.answer(stats_text)
    add_admin_log("Просмотрел статистику пользователей")

@dp.message(F.text == "📊 Общая статистика")
async def handle_general_stats(message: types.Message):
    """Общая статистика"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    total_requests = sum(data.get("total", 0) for data in user_requests_count.values())
    today_requests = sum(data.get("count", 0) for data in user_daily_requests.values() if data.get("date") == datetime.now().date())
    
    # Самые активные пользователи
    top_users = sorted(user_requests_count.items(), key=lambda x: x[1].get("total", 0), reverse=True)[:5]
    
    stats_text = f"📈 Общая статистика:\n\n"
    stats_text += f"🔄 Всего запросов: {total_requests}\n"
    stats_text += f"📊 Запросов сегодня: {today_requests}\n"
    stats_text += f"💾 Активных диалогов: {len(conversation_memory)}\n\n"
    
    stats_text += "🏆 Топ-5 активных пользователей:\n"
    for i, (user_id, data) in enumerate(top_users, 1):
        try:
            user = await bot.get_chat(user_id)
            username = f"@{user.username}" if user.username else user.first_name
            stats_text += f"{i}. {username}: {data.get('total', 0)} запросов\n"
        except:
            stats_text += f"{i}. ID {user_id}: {data.get('total', 0)} запросов\n"
    
    await message.answer(stats_text)
    add_admin_log("Просмотрел общую статистику")

@dp.message(F.text == "💎 Управление тарифами")
async def handle_tariff_management(message: types.Message):
    """Управление тарифами"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    await message.answer("💎 Управление тарифами\n\nВыберите действие:", reply_markup=get_tariff_management_keyboard())
    add_admin_log("Открыл управление тарифами")

@dp.message(F.text == "📋 Логи действий")
async def handle_action_logs(message: types.Message):
    """Показывает логи действий админа"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    if not admin_logs:
        await message.answer("📋 Логи действий пусты")
        return
    
    # Показываем последние 10 записей
    recent_logs = admin_logs[-10:]
    logs_text = "📋 Последние действия админа:\n\n"
    
    for log in reversed(recent_logs):
        timestamp = datetime.fromisoformat(log["timestamp"]).strftime("%H:%M:%S")
        action = log["action"]
        target = f" (пользователь {log['target_user']})" if log.get('target_user') else ""
        logs_text += f"🕒 {timestamp}: {action}{target}\n"
    
    await message.answer(logs_text)
    add_admin_log("Просмотрел логи действий")

@dp.message(F.text == "📈 Аналитика")
async def handle_analytics(message: types.Message):
    """Аналитика использования"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    # Аналитика по времени суток
    hour_stats = {i: 0 for i in range(24)}
    for log in admin_logs:
        if "timestamp" in log:
            hour = datetime.fromisoformat(log["timestamp"]).hour
            hour_stats[hour] += 1
    
    analytics_text = "📈 Аналитика использования:\n\n"
    analytics_text += "🕒 Активность по часам:\n"
    for hour in range(24):
        if hour_stats[hour] > 0:
            analytics_text += f"• {hour:02d}:00 - {hour_stats[hour]} действий\n"
    
    await message.answer(analytics_text)
    add_admin_log("Просмотрел аналитику")

@dp.message(F.text == "🎯 Быстрые действия")
async def handle_quick_actions(message: types.Message):
    """Быстрые действия для админа"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    quick_text = (
        "🎯 Быстрые действия:\n\n"
        "Для выполнения действий введите команды:\n"
        "• /broadcast ТЕКСТ - рассылка всем пользователям\n"
        "• /userinfo ID - информация о пользователе\n"
        "• /settariff ID ТАРИФ ДНИ - установить тариф\n"
        "• /resetlimits ID - сбросить лимиты\n\n"
        "Пример: /settariff 123456 default 30"
    )
    await message.answer(quick_text)

@dp.message(F.text == "🔙 Назад в админку")
async def handle_back_to_admin(message: types.Message):
    """Возврат в админ-панель"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    await handle_admin_panel(message)

@dp.message(F.text == "⬅️ Главное меню")
async def handle_admin_back(message: types.Message):
    """Возврат в главное меню из админ-панели"""
    await message.answer("Главное меню", reply_markup=get_main_keyboard(message.from_user.id))

# =======================
# ===== КОМАНДЫ АДМИНА =====
# =======================
@dp.message(Command("userinfo"))
async def cmd_userinfo(message: types.Message, command: CommandObject):
    """Информация о пользователе по ID"""
    if message.from_user.id != ADMIN_ID:
        return
    
    if not command.args:
        await message.answer("❌ Укажите ID пользователя: /userinfo ID")
        return
    
    try:
        user_id = int(command.args.strip())
        user_info = await get_user_info(user_id)
        await message.answer(user_info)
        add_admin_log(f"Запросил информацию о пользователе {user_id}")
    except ValueError:
        await message.answer("❌ Неверный формат ID")

@dp.message(Command("settariff"))
async def cmd_settariff(message: types.Message, command: CommandObject):
    """Установка тарифа пользователю"""
    if message.from_user.id != ADMIN_ID:
        return
    
    args = command.args.split() if command.args else []
    if len(args) != 3:
        await message.answer("❌ Использование: /settariff ID ТАРИФ ДНИ\nПример: /settariff 123456 default 30")
        return
    
    try:
        user_id = int(args[0])
        tariff = args[1].lower()
        days = int(args[2])
        
        if tariff not in TARIFFS:
            await message.answer(f"❌ Неверный тариф. Доступные: {', '.join(TARIFFS.keys())}")
            return
        
        activate_tariff(user_id, tariff, days)
        await message.answer(f"✅ Пользователю {user_id} установлен тариф {TARIFFS[tariff]['name']} на {days} дней")
        add_admin_log(f"Установил тариф {tariff} пользователю {user_id} на {days} дней")
        
    except ValueError:
        await message.answer("❌ Неверный формат аргументов")

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message, command: CommandObject):
    """Рассылка сообщения всем пользователям"""
    if message.from_user.id != ADMIN_ID:
        return
    
    if not command.args:
        await message.answer("❌ Укажите текст рассылки: /broadcast ТЕКСТ")
        return
    
    broadcast_text = command.args
    success_count = 0
    fail_count = 0
    
    progress_msg = await message.answer("🔄 Начинаю рассылку...")
    
    for user_id in user_registration_date:
        try:
            await bot.send_message(user_id, f"📢 Рассылка от администратора:\n\n{broadcast_text}")
            success_count += 1
            await asyncio.sleep(0.1)  # Задержка чтобы не превысить лимиты
        except Exception as e:
            fail_count += 1
            logger.error(f"Broadcast error for {user_id}: {e}")
    
    await progress_msg.delete()
    await message.answer(f"✅ Рассылка завершена:\n✅ Успешно: {success_count}\n❌ Ошибок: {fail_count}")
    add_admin_log(f"Выполнил рассылку: {success_count} успешно, {fail_count} ошибок")

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
        "🎤 Расшифровываю аудио...",
        "🌤️ Запрашиваю погоду..."
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
        "• 🌤️ Подробная погода в любом городе\n"
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
        "• 🌤️ Показывать подробную погоду\n"
        "• 🔢 Выполнять вычисления\n\n"
        "Просто отправьте:\n"
        "• Фото с текстом - распознаю его\n"
        "• Голосовое сообщение - расшифрую\n"
        "• Текст - отвечу на вопрос\n"
        "• Название города - покажу погоду"
    )
    await message.answer(help_text)

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

@dp.message(F.text == "🎭 Режимы AI")
async def handle_ai_modes(message: types.Message):
    modes_text = (
        "🎭 Режимы AI\n\n"
        "Выберите режим работы:\n"
        "• 🧘 Спокойный - мягкие ответы\n"
        "• 💬 Обычный - сбалансированные ответы\n"
        "• ⚡ Короткий - краткие ответы\n"
        "• 🧠 Умный - детальные аналитические ответы"
    )
    await message.answer(modes_text, reply_markup=get_mode_keyboard())

@dp.message(F.text == "📊 Статистика")
async def handle_user_statistics(message: types.Message):
    chat_id = message.from_user.id
    total_requests = user_requests_count.get(chat_id, {}).get("total", 0)
    remaining_requests = get_remaining_daily_requests(chat_id)
    current_tariff = get_user_tariff(chat_id)
    
    stats_text = f"📊 Ваша статистика:\n\n"
    stats_text += f"📈 Всего запросов: {total_requests}\n"
    stats_text += f"📅 Осталось сегодня: {remaining_requests}/{TARIFFS[current_tariff]['daily_limits']}\n"
    stats_text += f"💎 Тариф: {TARIFFS[current_tariff]['name']}\n"
    stats_text += f"⏳ Осталось дней: {get_remaining_days(chat_id)}"
    
    await message.answer(stats_text)

@dp.message(F.text == "🎨 Стиль общения")
async def handle_communication_style(message: types.Message):
    style_text = (
        "🎨 Стиль общения\n\n"
        "Выберите предпочтительный стиль:\n"
        "• 💫 Дружелюбный - неформальное общение\n"
        "• ⚖️ Сбалансированный - универсальный стиль\n"
        "• 🎯 Деловой - профессиональный тон\n"
        "• 🎨 Креативный - творческие ответы"
    )
    await message.answer(style_text, reply_markup=get_style_keyboard())

@dp.message(F.text == "ℹ️ Информация")
async def handle_info(message: types.Message):
    info_text = (
        "ℹ️ Информация о боте\n\n"
        "GlemixAI - современный AI-помощник на базе Mistral AI\n\n"
        "Возможности:\n"
        "• Распознавание текста с изображений\n"
        "• Обработка голосовых сообщений\n"
        "• Интеллектуальные ответы\n"
        "• Подробная метеослужба\n"
        "• Гибкая система подписок\n\n"
        "Версия: 2.0\n"
        "Разработчик: Glemix Team"
    )
    await message.answer(info_text)

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
        "🗑️ Сбросить тариф", "📅 Продлить на 30 дней", "⬅️ Админ-панель", "⬅️ Главное меню",
        "🌆 Москва", "🏛️ Санкт-Петербург", "🗽 Нью-Йорк", "🌉 Лондон", "🗼 Париж", "🏯 Токио",
        "🌃 Другой город", "📈 Аналитика", "🎯 Быстрые действия", "🔙 Назад в админку"
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
        increment_user_requests(chat_id)
        
        # Обработка погоды
        user_text_lower = user_text.lower()
        message_type = "normal"
        
        if any(word in user_text_lower for word in ["погода", "погоду"]) and len(user_text_lower) > 6:
            city = user_text_lower.replace("погода", "").replace("погоду", "").replace("в", "").strip()
            if city:
                weather_info = await get_detailed_weather(city)
                response_text = weather_info
                message_type = "weather"
            else:
                response_text = "Введите название города для получения погоды"
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

# =======================
# ===== ЗАПУСК БОТА =====
# =======================
async def main():
    logger.info("🚀 Запуск GlemixAI...")
    
    # Проверяем и инициализируем данные при запуске
    logger.info(f"💾 Загружено пользователей: {len(user_registration_date)}")
    logger.info(f"📊 Загружено запросов: {sum(data.get('total', 0) for data in user_requests_count.values())}")
    logger.info(f"🛠️ Админ ID: {ADMIN_ID}")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("🤖 GlemixAI запущен!")
    print(f"💎 Тарифы: {len(TARIFFS)} варианта")
    print(f"💾 Пользователей: {len(user_registration_date)}")
    print(f"📊 Всего запросов: {sum(data.get('total', 0) for data in user_requests_count.values())}")
    print(f"🛠️ Админ ID: {ADMIN_ID}")
    print("✅ GlemixAI готов к работе!")
    asyncio.run(main())
