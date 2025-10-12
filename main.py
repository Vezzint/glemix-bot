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
# ===== УЛУЧШЕННОЕ СОХРАНЕНИЕ ДАННЫХ =====
# =======================
def load_data(filename: str, default: Any = None) -> Any:
    """Загружает данные из файла с улучшенной обработкой ошибок"""
    try:
        if os.path.exists(filename):
            with open(filename, 'rb') as f:
                data = pickle.load(f)
                if data is not None:
                    return data
    except Exception as e:
        logging.error(f"Ошибка загрузки {filename}: {e}")
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
        temp_filename = f"{filename}.tmp"
        with open(temp_filename, 'wb') as f:
            pickle.dump(data, f)
        if os.path.exists(filename):
            os.replace(temp_filename, filename)
        else:
            os.rename(temp_filename, filename)
    except Exception as e:
        logging.error(f"Ошибка сохранения {filename}: {e}")
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
    
    user_requests_count[chat_id]["total"] = user_requests_count[chat_id].get("total", 0) + 1
    save_data(user_requests_count, DATA_FILES['user_requests_count'])
    
    increment_daily_requests(chat_id)

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
    
    if chat_id in user_subscription_end and user_subscription_end[chat_id] > datetime.now():
        return user_tariffs.get(chat_id, "default")
    
    if is_free_period_active(chat_id):
        return "default"
    
    return "default"

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
    
    if chat_id in user_subscription_end and user_subscription_end[chat_id] > datetime.now():
        return True
    
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
    
    if chat_id in user_subscription_end and user_subscription_end[chat_id] > datetime.now():
        return (user_subscription_end[chat_id] - datetime.now()).days
    
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
    if not is_subscription_active(chat_id) and chat_id != ADMIN_ID:
        remaining_free = get_remaining_free_days(chat_id)
        if remaining_free <= 0:
            return False, f"Бесплатный период закончился. Для продолжения работы активируйте один из тарифов."
        else:
            return True, ""
    
    remaining_requests = get_remaining_daily_requests(chat_id)
    if remaining_requests <= 0:
        current_tariff = get_user_tariff(chat_id)
        daily_limit = TARIFFS[current_tariff]["daily_limits"]
        return False, f"Дневной лимит запросов исчерпан ({daily_limit}/день). Попробуйте завтра или улучшите тариф."
    
    return True, ""

# =======================
# ===== УМНАЯ ОБРАБОТКА ФОТО =====
# =======================
async def process_image_with_instructions(image_bytes: bytes, user_instruction: str) -> str:
    """Обрабатывает изображение с учетом инструкций пользователя"""
    try:
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Определяем тип запроса
        user_instruction_lower = user_instruction.lower()
        
        if any(word in user_instruction_lower for word in ["переведи", "перевод", "translate"]):
            prompt = "Пожалуйста, извлеки текст с этого изображения и переведи его на русский язык. Верни только перевод без оригинального текста."
        elif any(word in user_instruction_lower for word in ["сумма", "суммируй", "сложи", "посчитай"]):
            prompt = "Пожалуйста, извлеки все числа с этого изображения и посчитай их сумму. Верни только результат вычисления."
        elif any(word in user_instruction_lower for word in ["анализ", "проанализируй", "расскажи"]):
            prompt = "Пожалуйста, проанализируй содержимое этого изображения и расскажи, что на нем изображено или о чем текст."
        elif any(word in user_instruction_lower for word in ["упрости", "сократи", "кратко"]):
            prompt = "Пожалуйста, извлеки текст с этого изображения и представь его в сокращенном виде, сохраняя основную суть."
        else:
            prompt = "Пожалуйста, извлеки весь текст с этого изображения. Верни только распознанный текст без дополнительных комментариев."
        
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
                        "text": prompt
                    }
                ]
            }
        ]
        
        response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=messages,
            max_tokens=2000  # Увеличиваем лимит для сложных запросов
        )
        
        result = response.choices[0].message.content.strip()
        
        if not result or "не вижу текста" in result.lower():
            return "❌ Не удалось обработать изображение. Попробуйте с более четким фото или уточните запрос."
        
        return result
        
    except Exception as e:
        logger.error(f"Image processing error: {e}")
        return "❌ Ошибка обработки изображения. Попробуйте еще раз."

async def transcribe_audio_with_mistral(audio_bytes: bytes) -> str:
    """Транскрибирует аудио с помощью Mistral"""
    try:
        return ("🎤 Голосовое сообщение получено! \n\n"
                "К сожалению, функция распознавания речи временно недоступна. "
                "Пожалуйста, опишите ваш вопрос текстом.")
        
    except Exception as e:
        logger.error(f"Mistral audio processing error: {e}")
        return "❌ Ошибка обработки голосового сообщения. Пожалуйста, напишите ваш вопрос текстом."

# =======================
# ===== ИСПРАВЛЕННАЯ СИСТЕМА ПОГОДЫ =====
# =======================
async def get_detailed_weather(city: str) -> str:
    """Получает расширенную информацию о погоде с исправлениями"""
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
            "сидней": "Sydney",
            "казань": "Kazan",
            "новосибирск": "Novosibirsk",
            "екатеринбург": "Yekaterinburg"
        }

        api_city = city_mapping.get(city_clean.lower(), city_clean)
        url = f"http://api.openweathermap.org/data/2.5/weather?q={api_city}&appid={openweather_api_key}&units=metric&lang=ru"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # Основные данные
                    temp = round(data["main"]["temp"])
                    feels_like = round(data["main"]["feels_like"])
                    humidity = data["main"]["humidity"]
                    pressure = data["main"]["pressure"]
                    wind_speed = data["wind"]["speed"]
                    description = data["weather"][0]["description"]
                    
                    # Исправляем время восхода и заката
                    timezone_offset = data["timezone"]
                    sunrise = datetime.fromtimestamp(data["sys"]["sunrise"] + timezone_offset).strftime("%H:%M")
                    sunset = datetime.fromtimestamp(data["sys"]["sunset"] + timezone_offset).strftime("%H:%M")
                    
                    cloudiness = data["clouds"]["all"]
                    
                    # Создаем подробный отчет
                    weather_report = f"🌤️ Погода в {city_clean.title()}:\n\n"
                    weather_report += f"🌡️ Температура: {temp}°C (ощущается как {feels_like}°C)\n"
                    weather_report += f"📝 {description.capitalize()}\n"
                    weather_report += f"💧 Влажность: {humidity}%\n"
                    weather_report += f"📊 Давление: {pressure} hPa\n"
                    weather_report += f"💨 Ветер: {wind_speed} м/с\n"
                    weather_report += f"☁️ Облачность: {cloudiness}%\n"
                    weather_report += f"🌅 Восход: {sunrise}\n"
                    weather_report += f"🌇 Закат: {sunset}\n"
                    
                    # Умные рекомендации
                    if temp < -10:
                        weather_report += "\n❄️ Очень холодно! Теплая одежда обязательна."
                    elif temp < 0:
                        weather_report += "\n🧥 Морозно. Наденьте зимнюю куртку и шапку."
                    elif temp < 10:
                        weather_report += "\n🧣 Прохладно. Куртка и шарф будут кстати."
                    elif temp < 20:
                        weather_report += "\n👔 Комфортно. Легкая куртка или свитер."
                    else:
                        weather_report += "\n😎 Тепло! Можно одеваться легко."
                    
                    return weather_report
                else:
                    return f"❌ Не удалось получить погоду для '{city_clean}'. Проверьте название города."
                    
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        return "❌ Ошибка получения данных о погоде. Попробуйте позже."

# =======================
# ===== УМНАЯ СИСТЕМА ОТВЕТОВ =====
# =======================
def create_smart_response(text: str, question_type: str = "normal") -> str:
    """Создает умный ответ с автоматическим определением длины"""
    
    if not text or len(text.strip()) == 0:
        return "Не удалось получить ответ. Пожалуйста, повторите запрос."
    
    # Определяем нужную длину ответа на основе типа вопроса
    if question_type == "weather":
        # Погода всегда имеет фиксированный формат
        return text
    
    elif question_type == "calculation":
        # Вычисления короткие
        return text
    
    elif question_type == "photo_text":
        # Текст с фото может быть разным
        if len(text) > 1000:
            # Длинный текст - оставляем как есть
            return f"📝 Результат обработки:\n\n{text}"
        else:
            return f"📝 {text}"
    
    elif question_type == "simple":
        # Простые вопросы - короткие ответы
        if len(text) > 300:
            # Если AI дал длинный ответ на простой вопрос, сокращаем
            sentences = text.split('. ')
            if len(sentences) > 1:
                return '. '.join(sentences[:2]) + '.'
        return text
    
    else:
        # Сложные вопросы - полные ответы
        return text

def should_use_long_answer(user_question: str, ai_response: str) -> bool:
    """Определяет, нужен ли длинный ответ"""
    user_lower = user_question.lower()
    
    # Вопросы, требующие развернутых ответов
    long_answer_keywords = [
        "объясни", "расскажи", "как работает", "почему", "в чем разница",
        "преимущества", "недостатки", "сравни", "анализ", "исследование",
        "подробно", "детально", "развернуто"
    ]
    
    # Вопросы, для которых достаточно короткого ответа
    short_answer_keywords = [
        "сколько времени", "который час", "какая дата", "привет", "пока",
        "как дела", "что нового", "курс", "погода", "посчитай"
    ]
    
    for keyword in long_answer_keywords:
        if keyword in user_lower:
            return True
    
    for keyword in short_answer_keywords:
        if keyword in user_lower:
            return False
    
    # Если ответ AI очень короткий, оставляем как есть
    if len(ai_response.split()) < 10:
        return False
    
    # По умолчанию - средняя длина
    return len(ai_response) > 500

# =======================
# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
# =======================
async def send_thinking_message(chat_id: int) -> int:
    """Отправляет фиксированное сообщение 'Думаю...'"""
    message = await bot.send_message(chat_id, "Думаю...")
    return message.message_id

async def delete_thinking_message(chat_id: int, message_id: int):
    """Удаляет сообщение 'Думаю...'"""
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception as e:
        logger.error(f"Ошибка удаления сообщения: {e}")

# =======================
# ===== АДМИН ПАНЕЛЬ И КЛАВИАТУРЫ =====
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
    if len(admin_logs) > 100:
        admin_logs.pop(0)
    save_data(admin_logs, DATA_FILES['admin_logs'])

def get_main_keyboard(chat_id: int) -> ReplyKeyboardMarkup:
    """Главная клавиатура"""
    keyboard = [
        [KeyboardButton(text="🚀 Начать работу"), KeyboardButton(text="🌟 Обо мне")],
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="❓ Помощь"), KeyboardButton(text="🌤️ Погода")],
        [KeyboardButton(text="💎 Тарифы")]
    ]
    
    if chat_id == ADMIN_ID:
        keyboard.append([KeyboardButton(text="🛠️ Админ-панель")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура админ-панели"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Статистика пользователей"), KeyboardButton(text="📊 Общая статистика")],
            [KeyboardButton(text="💎 Управление тарифами"), KeyboardButton(text="📢 Рассылка")],
            [KeyboardButton(text="🔍 Поиск пользователя"), KeyboardButton(text="📋 Логи действий")],
            [KeyboardButton(text="⚙️ Сброс данных пользователя"), KeyboardButton(text="🔄 Сброс дневных лимитов")],
            [KeyboardButton(text="📈 Аналитика"), KeyboardButton(text="🎯 Быстрые действия")],
            [KeyboardButton(text="⬅️ Главное меню")]
        ],
        resize_keyboard=True
    )

def get_weather_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора городов погоды"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌆 Москва"), KeyboardButton(text="🏛️ Санкт-Петербург")],
            [KeyboardButton(text="🗽 Нью-Йорк"), KeyboardButton(text="🌉 Лондон")],
            [KeyboardButton(text="🗼 Париж"), KeyboardButton(text="🏯 Токио")],
            [KeyboardButton(text="🌃 Другой город"), KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

# Остальные клавиатуры остаются без изменений
def get_settings_keyboard(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🎭 Режимы AI"), KeyboardButton(text="📊 Статистика")], [KeyboardButton(text="🎨 Стиль общения"), KeyboardButton(text="ℹ️ Информация")], [KeyboardButton(text="⚡ Быстрые команды")], [KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)
def get_tariffs_keyboard(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚀 Default"), KeyboardButton(text="⭐ Pro")], [KeyboardButton(text="💎 Advanced"), KeyboardButton(text="👑 Ultimate")], [KeyboardButton(text="📊 Мой тариф")], [KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)
def get_mode_keyboard(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🧘 Спокойный"), KeyboardButton(text="💬 Обычный")], [KeyboardButton(text="⚡ Короткий"), KeyboardButton(text="🧠 Умный")], [KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)
def get_style_keyboard(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="💫 Дружелюбный"), KeyboardButton(text="⚖️ Сбалансированный")], [KeyboardButton(text="🎯 Деловой"), KeyboardButton(text="🎨 Креативный")], [KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)

# =======================
# ===== ОСНОВНЫЕ КОМАНДЫ =====
# =======================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
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
# ===== УМНАЯ ОБРАБОТКА ФОТО =====
# =======================
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    """Обработка фото с расширенными возможностями"""
    chat_id = message.chat.id
    
    can_request, error_msg = can_user_make_request(chat_id)
    if not can_request:
        await message.answer(error_msg)
        return
    
    thinking_msg_id = await send_thinking_message(chat_id)
    
    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        image_bytes = downloaded_file.read()
        
        user_instruction = message.caption or "извлеки текст"
        
        # Обрабатываем изображение с учетом инструкций
        result = await process_image_with_instructions(image_bytes, user_instruction)
        
        increment_user_requests(chat_id)
        
        await delete_thinking_message(chat_id, thinking_msg_id)
        
        if result.startswith("❌"):
            await message.answer(result)
        else:
            response = create_smart_response(result, "photo_text")
            await message.answer(response)
            
            # Предлагаем дополнительные действия если это просто текст
            if "переведи" not in user_instruction.lower() and "анализ" not in user_instruction.lower():
                help_text = "📋 Что сделать с этим текстом? Могу:\n• Перевести\n• Суммировать числа\n• Сократить\n• Проанализировать"
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
    chat_id = message.chat.id
    
    can_request, error_msg = can_user_make_request(chat_id)
    if not can_request:
        await message.answer(error_msg)
        return
    
    thinking_msg_id = await send_thinking_message(chat_id)
    
    try:
        voice = message.voice
        file_info = await bot.get_file(voice.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        audio_bytes = downloaded_file.read()
        
        transcribed_text = await transcribe_audio_with_mistral(audio_bytes)
        
        increment_user_requests(chat_id)
        
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer(transcribed_text)
        
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("🎤 Получила ваше голосовое сообщение! Опишите кратко, о чем был ваш вопрос.")

# =======================
# ===== УМНАЯ ОБРАБОТКА ПОГОДЫ =====
# =======================
@dp.message(F.text == "🌤️ Погода")
async def handle_weather_button(message: types.Message):
    weather_text = "🌤️ Выберите город или введите название другого города:"
    await message.answer(weather_text, reply_markup=get_weather_keyboard())

@dp.message(F.text.in_(["🌆 Москва", "🏛️ Санкт-Петербург", "🗽 Нью-Йорк", "🌉 Лондон", "🗼 Париж", "🏯 Токио"]))
async def handle_city_weather(message: types.Message):
    city_mapping = {
        "🌆 Москва": "Москва",
        "🏛️ Санкт-Петербург": "Санкт-Петербург", 
        "🗽 Нью-Йорк": "Нью-Йорк",
        "🌉 Лондон": "Лондон",
        "🗼 Париж": "Париж",
        "🏯 Токио": "Токио"
    }
    
    city = city_mapping.get(message.text, message.text)
    
    thinking_msg_id = await send_thinking_message(message.chat.id)
    
    try:
        weather_info = await get_detailed_weather(city)
        await delete_thinking_message(message.chat.id, thinking_msg_id)
        await message.answer(weather_info)
        increment_user_requests(message.chat.id)
        
    except Exception as e:
        await delete_thinking_message(message.chat.id, thinking_msg_id)
        await message.answer("❌ Ошибка получения погоды. Попробуйте позже.")

@dp.message(F.text == "🌃 Другой город")
async def handle_other_city(message: types.Message):
    await message.answer("🏙️ Введите название города (например: 'Погода в Москве' или просто 'Москва'):")

# =======================
# ===== ОСНОВНАЯ ОБРАБОТКА СООБЩЕНИЙ =====
# =======================
@dp.message()
async def handle_all_messages(message: types.Message):
    chat_id = message.chat.id
    user_text = message.text or ""
    
    # Игнорируем обработанные команды и кнопки
    button_texts = ["🚀 Начать работу", "🌟 Обо мне", "⚙️ Настройки", "❓ Помощь", "🌤️ Погода", "💎 Тарифы", "📊 Мой тариф", "⬅️ Назад", "🛠️ Админ-панель", "🌆 Москва", "🏛️ Санкт-Петербург", "🗽 Нью-Йорк", "🌉 Лондон", "🗼 Париж", "🏯 Токио", "🌃 Другой город"]
    
    if user_text.startswith('/') or user_text in button_texts:
        return
    
    can_request, error_msg = can_user_make_request(chat_id)
    if not can_request:
        await message.answer(error_msg)
        return
    
    current_time = time.time()
    last_request = user_last_request.get(chat_id, 0)
    cooldown = get_user_cooldown(chat_id)
    
    if current_time - last_request < cooldown:
        remaining = cooldown - int(current_time - last_request)
        await message.answer(f"⏳ Подождите {remaining} сек. перед следующим запросом.")
        return
    
    user_last_request[chat_id] = current_time
    
    thinking_msg_id = await send_thinking_message(chat_id)
    
    try:
        increment_user_requests(chat_id)
        
        user_text_lower = user_text.lower()
        message_type = "normal"
        response_text = ""
        
        # Умное определение запроса погоды
        if any(word in user_text_lower for word in ["погода", "погоду", "температура"]):
            # Извлекаем город из запроса
            city = user_text_lower
            for word in ["погода", "погоду", "температура", "в", "какая", "сейчас"]:
                city = city.replace(word, "")
            city = city.strip(" вна")
            
            if city:
                weather_info = await get_detailed_weather(city)
                response_text = weather_info
                message_type = "weather"
            else:
                response_text = "Укажите город для получения погоды (например: 'Погода в Москве')"
                message_type = "weather"
                
        elif "курс" in user_text_lower or "валют" in user_text_lower:
            response_text = "💱 Курсы валют:\nUSD → 90.5 ₽\nEUR → 98.2 ₽\nCNY → 12.5 ₽"
            message_type = "currency"
            
        elif any(word in user_text_lower for word in ["посчитай", "сколько будет", "=", "calc", "calculate"]):
            try:
                expr = user_text_lower.replace("посчитай", "").replace("сколько будет", "").replace("=", "").replace("calc", "").replace("calculate", "").strip()
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
            # AI-ответ с умным определением длины
            try:
                if chat_id not in conversation_memory:
                    conversation_memory[chat_id] = []
                
                # Определяем сложность вопроса для промпта
                is_complex_question = should_use_long_answer(user_text, "")
                
                system_prompt = """Ты - GlemixAI, современный AI-помощник. Отвечай профессионально и по делу."""
                
                if is_complex_question:
                    system_prompt += " Дай развернутый ответ с объяснениями."
                else:
                    system_prompt += " Дай краткий и четкий ответ."
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ]
                
                for msg in conversation_memory[chat_id][-3:]:
                    messages.insert(1, msg)
                
                response = client.chat.complete(model=model, messages=messages)
                ai_text = response.choices[0].message.content
                
                # Сохраняем в память
                conversation_memory[chat_id].append({"role": "user", "content": user_text})
                conversation_memory[chat_id].append({"role": "assistant", "content": ai_text})
                
                memory_limit = get_user_memory_limit(chat_id)
                if len(conversation_memory[chat_id]) > memory_limit:
                    conversation_memory[chat_id] = conversation_memory[chat_id][-memory_limit:]
                
                save_data(conversation_memory, DATA_FILES['conversation_memory'])
                response_text = ai_text
                
                # Определяем тип ответа для умного форматирования
                if is_complex_question or len(ai_text.split()) > 100:
                    message_type = "complex"
                else:
                    message_type = "simple"
                
            except Exception as e:
                logger.error(f"AI error: {e}")
                response_text = "⚠️ Ошибка при обработке запроса. Попробуйте еще раз."
        
        # Отправляем умный ответ
        await delete_thinking_message(chat_id, thinking_msg_id)
        smart_response = create_smart_response(response_text, message_type)
        await message.answer(smart_response)
        
    except Exception as e:
        logger.error(f"Handler error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.")

# Остальные обработчики кнопок и админ-панели остаются без изменений
# ... (все остальные функции из предыдущего кода)

# =======================
# ===== ЗАПУСК БОТА =====
# =======================
async def main():
    logger.info("🚀 Запуск GlemixAI...")
    print("🤖 GlemixAI запущен!")
    print(f"💎 Тарифы: {len(TARIFFS)} варианта")
    print(f"💾 Пользователей: {len(user_registration_date)}")
    print(f"📊 Всего запросов: {sum(data.get('total', 0) for data in user_requests_count.values())}")
    print(f"🛠️ Админ ID: {ADMIN_ID}")
    print("✅ GlemixAI готов к работе!")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
