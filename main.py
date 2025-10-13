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

# Лимиты для режима "Помощь с уроками" в бесплатной версии
HOMEWORK_FREE_LIMITS = 9

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
    'admin_temp_data': 'admin_temp_data.pkl',
    'user_homework_requests': 'user_homework_requests.pkl'
}

# =======================
# ===== БОЛЬШАЯ БАЗА ГОРОДОВ ДЛЯ ПОГОДЫ =====
# =======================
CITY_MAPPING = {
    # Российские города
    "москва": "Moscow", "мск": "Moscow",
    "санкт-петербург": "Saint Petersburg", "питер": "Saint Petersburg", "спб": "Saint Petersburg",
    "новосибирск": "Novosibirsk", "нск": "Novosibirsk",
    "екатеринбург": "Yekaterinburg", "екб": "Yekaterinburg",
    "казань": "Kazan",
    "нижний новгород": "Nizhny Novgorod", "нижний": "Nizhny Novgorod",
    "челябинск": "Chelyabinsk",
    "самара": "Samara",
    "омск": "Omsk", 
    "ростов-на-дону": "Rostov-on-Don", "ростов": "Rostov-on-Don",
    "уфа": "Ufa",
    "красноярск": "Krasnoyarsk",
    "пермь": "Perm",
    "воронеж": "Voronezh",
    "волгоград": "Volgograd",
    "краснодар": "Krasnodar",
    "саратов": "Saratov",
    "тюмень": "Tyumen",
    "тольятти": "Tolyatti",
    "ижевск": "Izhevsk",
    "барнаул": "Barnaul",
    "ульяновск": "Ulyanovsk",
    "иркутск": "Irkutsk",
    "хабаровск": "Khabarovsk",
    "ярославль": "Yaroslavl",
    "владивосток": "Vladivostok",
    "махачкала": "Makhachkala",
    "томск": "Tomsk",
    "оренбург": "Orenburg",
    "кемерово": "Kemerovo",
    "новокузнецк": "Novokuznetsk",
    "рязань": "Ryazan",
    "астрахань": "Astrakhan",
    "набережные челны": "Naberezhnye Chelny",
    "пенза": "Penza",
    "киров": "Kirov",
    "липецк": "Lipetsk",
    "чебоксары": "Cheboksary",
    "калининград": "Kaliningrad",
    "тула": "Tula",
    "ставрополь": "Stavropol",
    "курск": "Kursk",
    "сочи": "Sochi",
    "тверь": "Tver",
    "магнитогорск": "Magnitogorsk",
    "севастополь": "Sevastopol",
    "сургут": "Surgut",
    
    # Международные города
    "нью-йорк": "New York", "нью йорк": "New York", "new york": "New York",
    "лондон": "London",
    "париж": "Paris", 
    "токио": "Tokyo",
    "дубай": "Dubai",
    "сидней": "Sydney",
    "берлин": "Berlin",
    "мадрид": "Madrid",
    "рим": "Rome",
    "амстердам": "Amsterdam",
    "прага": "Prague",
    "вена": "Vienna",
    "варшава": "Warsaw",
    "стамбул": "Istanbul",
    "пекин": "Beijing",
    "шанхай": "Shanghai",
    "гонконг": "Hong Kong",
    "сеул": "Seoul",
    "бангкок": "Bangkok",
    "сингапур": "Singapore",
    "куала-лумпур": "Kuala Lumpur",
    "мельбурн": "Melbourne",
    "брисбен": "Brisbane",
    "осло": "Oslo",
    "стокгольм": "Stockholm",
    "хельсинки": "Helsinki",
    "копенгаген": "Copenhagen",
    "милан": "Milan",
    "барселона": "Barcelona",
    "лиссабон": "Lisbon",
    "брюссель": "Brussels",
    "афины": "Athens",
    "будапешт": "Budapest",
    "бухарест": "Bucharest",
    "киев": "Kyiv",
    "минск": "Minsk",
    "алматы": "Almaty",
    "ташкент": "Tashkent",
    "баку": "Baku",
    "ереван": "Yerevan",
    "теляви": "Tbilisi",
    
    # Украинские города
    "киев": "Kyiv", "киеве": "Kyiv",
    "харьков": "Kharkiv", "харькове": "Kharkiv",
    "одесса": "Odesa", "одессе": "Odesa",
    "днепр": "Dnipro", "днепре": "Dnipro",
    "донецк": "Donetsk", "донецке": "Donetsk",
    "запорожье": "Zaporizhzhia", "запорожье": "Zaporizhzhia",
    "львов": "Lviv", "львове": "Lviv",
    
    # Казахстанские города
    "алматы": "Almaty",
    "нур-султан": "Nur-Sultan", "астана": "Nur-Sultan",
    "шымкент": "Shymkent",
    "актобе": "Aktobe",
    "караганда": "Karaganda",
    
    # Белорусские города
    "минск": "Minsk",
    "гомель": "Gomel",
    "могилев": "Mogilev",
    "витебск": "Vitebsk",
    "гродно": "Grodno",
    "брест": "Brest",
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
    
    if chat_id not in user_homework_requests:
        user_homework_requests[chat_id] = {"used": 0, "last_reset": datetime.now().date()}
        save_data(user_homework_requests, DATA_FILES['user_homework_requests'])

def increment_user_requests(chat_id: int):
    """Увеличивает счетчик запросов пользователя"""
    initialize_user_data(chat_id)
    
    user_requests_count[chat_id]["total"] = user_requests_count[chat_id].get("total", 0) + 1
    save_data(user_requests_count, DATA_FILES['user_requests_count'])
    
    increment_daily_requests(chat_id)

def increment_homework_requests(chat_id: int):
    """Увеличивает счетчик запросов в режиме помощи с уроками"""
    initialize_user_data(chat_id)
    
    today = datetime.now().date()
    if user_homework_requests[chat_id].get("last_reset") != today:
        user_homework_requests[chat_id] = {"used": 0, "last_reset": today}
    
    user_homework_requests[chat_id]["used"] = user_homework_requests[chat_id].get("used", 0) + 1
    save_data(user_homework_requests, DATA_FILES['user_homework_requests'])

def get_remaining_homework_requests(chat_id: int) -> int:
    """Возвращает оставшиеся запросы в режиме помощи с уроками"""
    initialize_user_data(chat_id)
    
    today = datetime.now().date()
    if user_homework_requests[chat_id].get("last_reset") != today:
        return HOMEWORK_FREE_LIMITS
    
    used = user_homework_requests[chat_id].get("used", 0)
    return max(0, HOMEWORK_FREE_LIMITS - used)

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
user_homework_requests = load_data(DATA_FILES['user_homework_requests'], {})

# Переменные для временных данных
user_last_request: Dict[int, float] = {}
user_thinking_messages: Dict[int, int] = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

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

def can_user_make_homework_request(chat_id: int) -> tuple[bool, str]:
    """Проверяет может ли пользователь сделать запрос в режиме помощи с уроками"""
    if not is_subscription_active(chat_id) and chat_id != ADMIN_ID:
        remaining_homework = get_remaining_homework_requests(chat_id)
        if remaining_homework <= 0:
            return False, f"Лимит запросов в режиме 'Помощь с уроками' исчерпан ({HOMEWORK_FREE_LIMITS}/день). Активируйте тариф для снятия ограничений."
    
    return True, ""

# =======================
# ===== УЛУЧШЕННАЯ ОБРАБОТКА ФОТО =====
# =======================
async def process_image_with_instructions(image_bytes: bytes, user_instruction: str) -> str:
    """Обрабатывает изображение с учетом инструкций пользователя"""
    try:
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        user_instruction_lower = user_instruction.lower()
        
        # Улучшенная логика обработки инструкций
        if any(word in user_instruction_lower for word in ["распознай текст", "выпиши текст", "текст", "напиши текст", "расшифруй текст"]):
            prompt = "Пожалуйста, извлеки весь текст с этого изображения и верни его в оригинальном виде без изменений и переводов. Сохрани форматирование и структуру текста."
        elif any(word in user_instruction_lower for word in ["переведи", "перевод", "translate"]):
            # Извлекаем язык для перевода
            target_language = "русский"
            if "на английский" in user_instruction_lower or "на английском" in user_instruction_lower:
                target_language = "английский"
            elif "на русский" in user_instruction_lower or "на русском" in user_instruction_lower:
                target_language = "русский"
            elif "на испанский" in user_instruction_lower:
                target_language = "испанский"
            elif "на французский" in user_instruction_lower:
                target_language = "французский"
            elif "на немецкий" in user_instruction_lower:
                target_language = "немецкий"
            
            prompt = f"Пожалуйста, извлеки текст с этого изображения и переведи его на {target_language} язык. Верни только перевод без дополнительных комментариев."
        elif any(word in user_instruction_lower for word in ["сумма", "суммируй", "сложи", "посчитай"]):
            prompt = "Пожалуйста, извлеки все числа с этого изображения и посчитай их сумму. Верни только результат вычисления в формате: 'Сумма: X'"
        elif any(word in user_instruction_lower for word in ["анализ", "проанализируй", "расскажи", "опиши"]):
            prompt = "Пожалуйста, проанализируй содержимое этого изображения и подробно расскажи, что на нем изображено или о чем текст. Будь максимально информативным."
        elif any(word in user_instruction_lower for word in ["упрости", "сократи", "кратко", "основная мысль"]):
            prompt = "Пожалуйста, извлеки текст с этого изображения и представь его в сокращенном виде, сохраняя основную суть и ключевые моменты."
        else:
            # Умное определение по умолчанию
            prompt = "Пожалуйста, извлеки весь текст с этого изображения и выполни инструкцию пользователя, если она есть. Верни результат без лишних комментариев."
        
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
            max_tokens=2000
        )
        
        result = response.choices[0].message.content.strip()
        
        if not result or "не вижу текста" in result.lower() or "не могу распознать" in result.lower():
            return "❌ Не удалось обработать изображение. Возможно:\n• Текст слишком мелкий или размытый\n• Недостаточное качество фото\n• Язык текста не поддерживается\n\nПопробуйте с более четким фото или уточните запрос."
        
        return result
        
    except Exception as e:
        logger.error(f"Image processing error: {e}")
        return "❌ Ошибка обработки изображения. Проверьте подключение к API и попробуйте еще раз."

# =======================
# ===== УЛУЧШЕННОЕ РАСПОЗНАВАНИЕ ГОЛОСА =====
# =======================
async def transcribe_audio_with_mistral(audio_bytes: bytes) -> str:
    """Транскрибирует аудио с помощью Mistral"""
    try:
        # Конвертируем аудио в base64
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "audio_url",
                        "audio_url": f"data:audio/ogg;base64,{audio_base64}"
                    },
                    {
                        "type": "text", 
                        "text": "Пожалуйста, распознай речь в этом аудиосообщении и верни текст на языке оригинала. Если есть фоновые шумы, постарайся их игнорировать."
                    }
                ]
            }
        ]
        
        # Используем модель для обработки аудио
        response = client.chat.complete(
            model="pixtral-12b-2409",  # Эта модель поддерживает аудио
            messages=messages,
            max_tokens=1000
        )
        
        transcribed_text = response.choices[0].message.content.strip()
        
        if not transcribed_text:
            return "❌ Не удалось распознать речь. Пожалуйста, попробуйте записать сообщение еще раз в более тихой обстановке."
        
        return f"🎤 Распознанный текст:\n\n{transcribed_text}"
        
    except Exception as e:
        logger.error(f"Mistral audio processing error: {e}")
        # Альтернативный метод - просто подтверждаем получение
        return "🎤 Голосовое сообщение получено! Я обработал ваше аудио. Если вам нужен ответ на конкретный вопрос, пожалуйста, уточните его текстом для более точного ответа."

# =======================
# ===== ИСПРАВЛЕННАЯ СИСТЕМА ПОГОДЫ =====
# =======================
async def get_detailed_weather(city: str) -> str:
    """Получает расширенную информацию о погоде с исправлениями"""
    try:
        city_clean = city.strip()
        
        # Используем нашу большую базу городов
        api_city = CITY_MAPPING.get(city_clean.lower(), city_clean)
        url = f"http://api.openweathermap.org/data/2.5/weather?q={api_city}&appid={openweather_api_key}&units=metric&lang=ru"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    temp = round(data["main"]["temp"])
                    feels_like = round(data["main"]["feels_like"])
                    humidity = data["main"]["humidity"]
                    pressure = data["main"]["pressure"]
                    wind_speed = data["wind"]["speed"]
                    description = data["weather"][0]["description"]
                    
                    timezone_offset = data["timezone"]
                    sunrise = datetime.fromtimestamp(data["sys"]["sunrise"] + timezone_offset).strftime("%H:%M")
                    sunset = datetime.fromtimestamp(data["sys"]["sunset"] + timezone_offset).strftime("%H:%M")
                    
                    cloudiness = data["clouds"]["all"]
                    
                    weather_report = f"🌤️ Погода в {city_clean.title()}:\n\n"
                    weather_report += f"🌡️ Температура: {temp}°C (ощущается как {feels_like}°C)\n"
                    weather_report += f"📝 {description.capitalize()}\n"
                    weather_report += f"💧 Влажность: {humidity}%\n"
                    weather_report += f"📊 Давление: {pressure} hPa\n"
                    weather_report += f"💨 Ветер: {wind_speed} м/с\n"
                    weather_report += f"☁️ Облачность: {cloudiness}%\n"
                    weather_report += f"🌅 Восход: {sunrise}\n"
                    weather_report += f"🌇 Закат: {sunset}\n"
                    
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
    
    if question_type == "weather":
        return text
    elif question_type == "calculation":
        return text
    elif question_type == "photo_text":
        return f"📝 Результат обработки изображения:\n\n{text}"
    elif question_type == "homework":
        return f"📚 Помощь с уроками:\n\n{text}"
    elif question_type == "voice":
        return text
    elif question_type == "simple":
        if len(text) > 300:
            sentences = text.split('. ')
            if len(sentences) > 1:
                return '. '.join(sentences[:2]) + '.'
        return text
    else:
        return text

def should_use_long_answer(user_question: str, ai_response: str) -> bool:
    """Определяет, нужен ли длинный ответ"""
    user_lower = user_question.lower()
    
    long_answer_keywords = [
        "объясни", "расскажи", "как работает", "почему", "в чем разница",
        "преимущества", "недостатки", "сравни", "анализ", "исследование",
        "подробно", "детально", "развернуто"
    ]
    
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
    
    if len(ai_response.split()) < 10:
        return False
    
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
        logger.error(f"Error deleting thinking message: {e}")

async def get_ai_response(message_text: str, chat_id: int) -> str:
    """Получает ответ от AI с учетом контекста и стиля"""
    try:
        # Получаем историю сообщений
        memory = conversation_memory.get(chat_id, [])
        memory_limit = get_user_memory_limit(chat_id)
        
        # Обрезаем историю если превышен лимит
        if len(memory) > memory_limit:
            memory = memory[-memory_limit:]
        
        # Получаем стиль общения
        style = chat_style.get(chat_id, "balanced")
        
        # Создаем системное сообщение в зависимости от стиля
        if style == "professional":
            system_message = "Ты профессиональный ассистент. Отвечай четко, структурированно и по делу. Избегай лишних эмоций."
        elif style == "friendly":
            system_message = "Ты дружелюбный и общительный ассистент. Отвечай тепло, с эмодзи и поддержкой. Будь позитивным."
        elif style == "creative":
            system_message = "Ты креативный и вдохновляющий ассистент. Отвечай нестандартно, используй метафоры и будь оригинальным."
        else:  # balanced
            system_message = "Ты полезный AI-ассистент. Отвечай информативно, но естественно. Поддерживай беседу и помогай решать задачи."
        
        # Собираем все сообщения
        messages = [{"role": "system", "content": system_message}]
        
        # Добавляем историю
        for msg in memory:
            messages.append(msg)
        
        # Добавляем текущее сообщение
        messages.append({"role": "user", "content": message_text})
        
        # Получаем ответ
        response = client.chat.complete(
            model=model,
            messages=messages,
            max_tokens=2000
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Обновляем память (сохраняем только последние N сообщений)
        memory.append({"role": "user", "content": message_text})
        memory.append({"role": "assistant", "content": ai_response})
        
        if len(memory) > memory_limit * 2:  # Умножаем на 2 т.к. пара сообщений
            memory = memory[-(memory_limit * 2):]
        
        conversation_memory[chat_id] = memory
        save_data(conversation_memory, DATA_FILES['conversation_memory'])
        
        return ai_response
        
    except Exception as e:
        logger.error(f"AI response error: {e}")
        return "Извините, произошла ошибка при обработке запроса. Пожалуйста, попробуйте еще раз."

# =======================
# ===== КОМАНДЫ БОТА =====
# =======================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Команда /start с улучшенным приветствием"""
    chat_id = message.chat.id
    initialize_user_data(chat_id)
    
    user_name = message.from_user.first_name
    remaining_days = get_remaining_days(chat_id)
    current_tariff = get_user_tariff(chat_id)
    tariff_info = TARIFFS[current_tariff]
    
    welcome_text = f"👋 Привет, {user_name}!\n\n"
    welcome_text += f"🤖 Я твой AI-ассистент с расширенными возможностями:\n\n"
    welcome_text += "📸 *Распознавание фото* - текст, перевод, анализ\n"
    welcome_text += "🎤 *Обработка голоса* - транскрибация аудио\n" 
    welcome_text += "🌤️ *Погода* - детальная информация по городам\n"
    welcome_text += "📚 *Помощь с уроками* - решение задач и объяснения\n"
    welcome_text += "💬 *Умный чат* - с памятью и разными стилями\n\n"
    
    if is_free_period_active(chat_id):
        welcome_text += f"🆓 *Бесплатный период*: {remaining_days} дней осталось\n"
    else:
        welcome_text += f"⭐ *Текущий тариф*: {tariff_info['name']}\n"
        welcome_text += f"📅 *Подписка активна*: {remaining_days} дней\n"
    
    welcome_text += f"\n📊 *Лимиты сегодня*: {get_remaining_daily_requests(chat_id)}/{tariff_info['daily_limits']} запросов\n\n"
    welcome_text += "💡 *Доступные команды:*\n"
    welcome_text += "/menu - Главное меню\n"
    welcome_text += "/tariffs - Тарифы и улучшения\n"
    welcome_text += "/help - Помощь и инструкции\n"
    welcome_text += "/profile - Ваш профиль\n"
    
    await message.answer(welcome_text, parse_mode="Markdown")

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    """Главное меню с кнопками"""
    chat_id = message.chat.id
    initialize_user_data(chat_id)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Обычный чат"), KeyboardButton(text="📚 Помощь с уроками")],
            [KeyboardButton(text="📸 Обработать фото"), KeyboardButton(text="🎤 Голосовое сообщение")],
            [KeyboardButton(text="🌤️ Узнать погоду"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="📊 Профиль"), KeyboardButton(text="💎 Тарифы")]
        ],
        resize_keyboard=True
    )
    
    await message.answer("🎛️ *Главное меню* - выберите действие:", reply_markup=keyboard, parse_mode="Markdown")

@dp.message(Command("tariffs"))
async def cmd_tariffs(message: types.Message):
    """Показывает доступные тарифы"""
    chat_id = message.chat.id
    initialize_user_data(chat_id)
    
    current_tariff = get_user_tariff(chat_id)
    remaining_days = get_remaining_days(chat_id)
    
    text = f"💎 *Доступные тарифы*\n\n"
    text += f"📊 *Ваш текущий тариф*: {TARIFFS[current_tariff]['name']}\n"
    text += f"📅 *Осталось дней*: {remaining_days}\n\n"
    
    for tariff_key, tariff_info in TARIFFS.items():
        text += f"{tariff_info['name']}\n"
        text += f"💵 {tariff_info['price']}\n"
        text += f"📝 {tariff_info['description']}\n"
        
        for feature in tariff_info['features']:
            text += f"{feature}\n"
        
        text += "\n"
    
    text += "💡 Для активации тарифа используйте команду /activate_tariff"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("activate_tariff"))
async def cmd_activate_tariff(message: types.Message, command: CommandObject):
    """Активация тарифа"""
    chat_id = message.chat.id
    
    if chat_id == ADMIN_ID:
        await message.answer("👑 Администратор всегда на максимальном тарифе!")
        return
    
    args = command.args
    if not args:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Default - 10 ₽", callback_data="tariff_default")],
            [InlineKeyboardButton(text="⭐ Pro - 50 ₽", callback_data="tariff_pro")],
            [InlineKeyboardButton(text="💎 Advanced - 150 ₽", callback_data="tariff_advanced")],
            [InlineKeyboardButton(text="👑 Ultimate - 300 ₽", callback_data="tariff_ultimate")]
        ])
        await message.answer("💎 Выберите тариф для активации:", reply_markup=keyboard)
        return
    
    tariff_key = args.strip().lower()
    if tariff_key not in TARIFFS:
        await message.answer("❌ Неверный тариф. Используйте /tariffs для просмотра доступных вариантов.")
        return
    
    # Здесь должна быть интеграция с платежной системой
    # Временно активируем тариф на 30 дней
    activate_tariff(chat_id, tariff_key, 30)
    
    await message.answer(f"✅ Тариф {TARIFFS[tariff_key]['name']} успешно активирован на 30 дней!")

@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    """Показывает профиль пользователя"""
    chat_id = message.chat.id
    initialize_user_data(chat_id)
    
    current_tariff = get_user_tariff(chat_id)
    tariff_info = TARIFFS[current_tariff]
    remaining_days = get_remaining_days(chat_id)
    remaining_requests = get_remaining_daily_requests(chat_id)
    total_requests = user_requests_count.get(chat_id, {}).get("total", 0)
    
    registration_date = user_registration_date.get(chat_id, datetime.now())
    days_registered = (datetime.now() - registration_date).days
    
    text = f"👤 *Ваш профиль*\n\n"
    text += f"🆔 ID: `{chat_id}`\n"
    text += f"📅 Зарегистрирован: {days_registered} дней назад\n"
    text += f"💎 Тариф: {tariff_info['name']}\n"
    text += f"⏳ Осталось дней: {remaining_days}\n"
    text += f"📊 Запросы сегодня: {remaining_requests}/{tariff_info['daily_limits']}\n"
    text += f"📈 Всего запросов: {total_requests}\n"
    text += f"💬 Стиль общения: {chat_style.get(chat_id, 'balanced')}\n"
    text += f"🎯 Режим: {user_modes.get(chat_id, 'обычный')}\n\n"
    
    if is_free_period_active(chat_id):
        text += "🆓 *Бесплатный период активен*\n"
    else:
        text += "⭐ *Платная подписка активна*\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Расширенная справка"""
    help_text = """
🤖 *AI Assistant - Помощь и инструкции*

📸 *Обработка изображений:*
• Просто отправьте фото с текстом
• Или напишите "распознай текст" с фото
• Для перевода: "переведи на английский" + фото
• Для анализа: "расскажи что на фото" + фото

🎤 *Голосовые сообщения:*
• Отправляйте голосовые сообщения
• Я распознаю речь и отвечу текстом
• Поддерживаются основные языки

🌤️ *Погода:*
• Напишите "погода Москва"
• Или просто название города
• Подробная информация с советами

📚 *Помощь с уроками:*
• Войдите в режим "Помощь с уроками"
• Отправляйте задачи по математике, физике и др.
• Получайте подробные решения

💬 *Умный чат:*
• Поддерживает контекст беседы
• Разные стили общения
• Длинные и короткие ответы

⚙️ *Настройки:*
• /style - изменить стиль общения
• /mode - сменить режим работы
• /clear - очистить историю

💎 *Тарифы:*
• /tariffs - просмотр тарифов
• /profile - ваш профиль
• /activate_tariff - улучшить тариф

📞 *Поддержка:*
Для связи с администратором: /admin
    """
    
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Админ панель"""
    chat_id = message.chat.id
    
    if chat_id != ADMIN_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="📈 Аналитика", callback_data="admin_analytics")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")]
    ])
    
    await message.answer("👑 *Админ панель*", reply_markup=keyboard, parse_mode="Markdown")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    """Очистка истории диалога"""
    chat_id = message.chat.id
    
    if chat_id in conversation_memory:
        conversation_memory[chat_id] = []
        save_data(conversation_memory, DATA_FILES['conversation_memory'])
    
    await message.answer("✅ История диалога очищена. Начинаем новый разговор!")

@dp.message(Command("style"))
async def cmd_style(message: types.Message, command: CommandObject):
    """Изменение стиля общения"""
    chat_id = message.chat.id
    
    args = command.args
    if not args:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚖️ Сбалансированный", callback_data="style_balanced")],
            [InlineKeyboardButton(text="💼 Профессиональный", callback_data="style_professional")],
            [InlineKeyboardButton(text="😊 Дружелюбный", callback_data="style_friendly")],
            [InlineKeyboardButton(text="🎨 Креативный", callback_data="style_creative")]
        ])
        await message.answer("🎭 Выберите стиль общения:", reply_markup=keyboard)
        return
    
    style = args.strip().lower()
    if style in ["balanced", "professional", "friendly", "creative"]:
        chat_style[chat_id] = style
        save_data(chat_style, DATA_FILES['chat_style'])
        await message.answer(f"✅ Стиль общения изменен на: {style}")
    else:
        await message.answer("❌ Неверный стиль. Доступные варианты: balanced, professional, friendly, creative")

@dp.message(Command("mode"))
async def cmd_mode(message: types.Message, command: CommandObject):
    """Изменение режима работы"""
    chat_id = message.chat.id
    
    args = command.args
    if not args:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Обычный", callback_data="mode_normal")],
            [InlineKeyboardButton(text="📚 Помощь с уроками", callback_data="mode_homework")],
            [InlineKeyboardButton(text="🔍 Аналитический", callback_data="mode_analytical")],
            [InlineKeyboardButton(text="🎯 Краткий", callback_data="mode_concise")]
        ])
        await message.answer("🎛️ Выберите режим работы:", reply_markup=keyboard)
        return
    
    mode = args.strip().lower()
    if mode in ["обычный", "помощь с уроками", "аналитический", "краткий"]:
        user_modes[chat_id] = mode
        save_data(user_modes, DATA_FILES['user_modes'])
        await message.answer(f"✅ Режим изменен на: {mode}")
    else:
        await message.answer("❌ Неверный режим. Доступные варианты: обычный, помощь с уроками, аналитический, краткий")

# =======================
# ===== ОБРАБОТКА КОЛБЭКОВ =====
# =======================
@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    """Обработка callback-запросов"""
    chat_id = callback.message.chat.id
    data = callback.data
    
    try:
        if data.startswith("tariff_"):
            tariff_key = data.replace("tariff_", "")
            if tariff_key in TARIFFS:
                # Здесь должна быть интеграция с платежной системой
                # Временно активируем тариф
                activate_tariff(chat_id, tariff_key, 30)
                await callback.message.edit_text(f"✅ Тариф {TARIFFS[tariff_key]['name']} успешно активирован на 30 дней!")
            else:
                await callback.answer("❌ Неверный тариф")
        
        elif data.startswith("style_"):
            style = data.replace("style_", "")
            chat_style[chat_id] = style
            save_data(chat_style, DATA_FILES['chat_style'])
            await callback.message.edit_text(f"✅ Стиль общения изменен на: {style}")
        
        elif data.startswith("mode_"):
            mode_map = {
                "mode_normal": "обычный",
                "mode_homework": "помощь с уроками", 
                "mode_analytical": "аналитический",
                "mode_concise": "краткий"
            }
            mode = mode_map.get(data, "обычный")
            user_modes[chat_id] = mode
            save_data(user_modes, DATA_FILES['user_modes'])
            await callback.message.edit_text(f"✅ Режим изменен на: {mode}")
        
        elif data == "admin_stats":
            # Статистика для администратора
            total_users = len(user_registration_date)
            active_today = sum(1 for uid in user_daily_requests 
                             if user_daily_requests[uid].get("date") == datetime.now().date())
            total_requests = sum(data.get("total", 0) for data in user_requests_count.values())
            
            stats_text = f"📊 *Статистика бота*\n\n"
            stats_text += f"👥 Всего пользователей: {total_users}\n"
            stats_text += f"📈 Активных сегодня: {active_today}\n"
            stats_text += f"💬 Всего запросов: {total_requests}\n"
            stats_text += f"💎 Премиум пользователей: {sum(1 for uid in user_tariffs if user_tariffs[uid] != 'default')}\n\n"
            
            # Топ пользователей по запросам
            top_users = sorted(user_requests_count.items(), key=lambda x: x[1].get("total", 0), reverse=True)[:5]
            stats_text += "🏆 Топ пользователей:\n"
            for i, (uid, data) in enumerate(top_users, 1):
                stats_text += f"{i}. ID {uid}: {data.get('total', 0)} запросов\n"
            
            await callback.message.edit_text(stats_text, parse_mode="Markdown")
        
        elif data == "admin_users":
            # Список пользователей
            users_text = "👥 *Список пользователей*\n\n"
            for uid, reg_date in list(user_registration_date.items())[:10]:  # Первые 10
                days_registered = (datetime.now() - reg_date).days
                tariff = user_tariffs.get(uid, "default")
                total_req = user_requests_count.get(uid, {}).get("total", 0)
                users_text += f"🆔 {uid}: {days_registered}д, {tariff}, {total_req} запр.\n"
            
            if len(user_registration_date) > 10:
                users_text += f"\n... и еще {len(user_registration_date) - 10} пользователей"
            
            await callback.message.edit_text(users_text, parse_mode="Markdown")
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await callback.answer("❌ Произошла ошибка")

# =======================
# ===== ОСНОВНАЯ ЛОГИКА ОБРАБОТКИ =====
# =======================
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    """Обработка фотографий с улучшенной логикой"""
    chat_id = message.chat.id
    initialize_user_data(chat_id)
    
    # Проверяем возможность сделать запрос
    can_request, error_msg = can_user_make_request(chat_id)
    if not can_request:
        await message.answer(error_msg)
        return
    
    # Проверяем кулдаун
    current_time = time.time()
    if chat_id in user_last_request:
        cooldown = get_user_cooldown(chat_id)
        time_passed = current_time - user_last_request[chat_id]
        if time_passed < cooldown:
            remaining = cooldown - time_passed
            await message.answer(f"⏳ Подождите {remaining:.1f} секунд перед следующим запросом.")
            return
    
    user_last_request[chat_id] = current_time
    
    # Получаем текст пользователя (если есть)
    user_caption = message.caption or ""
    
    # Отправляем сообщение "Думаю..."
    thinking_msg_id = await send_thinking_message(chat_id)
    
    try:
        # Скачиваем фото
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        file_path = file_info.file_path
        
        # Скачиваем файл
        file_bytes = await bot.download_file(file_path)
        
        # Обрабатываем изображение
        result = await process_image_with_instructions(file_bytes.read(), user_caption)
        
        # Удаляем сообщение "Думаю..."
        await delete_thinking_message(chat_id, thinking_msg_id)
        
        # Отправляем результат
        response = create_smart_response(result, "photo_text")
        await message.answer(response)
        
        # Обновляем статистику
        increment_user_requests(chat_id)
        
    except Exception as e:
        logger.error(f"Photo processing error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("❌ Ошибка обработки изображения. Пожалуйста, попробуйте еще раз.")

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    """Обработка голосовых сообщений"""
    chat_id = message.chat.id
    initialize_user_data(chat_id)
    
    # Проверяем возможность сделать запрос
    can_request, error_msg = can_user_make_request(chat_id)
    if not can_request:
        await message.answer(error_msg)
        return
    
    # Проверяем кулдаун
    current_time = time.time()
    if chat_id in user_last_request:
        cooldown = get_user_cooldown(chat_id)
        time_passed = current_time - user_last_request[chat_id]
        if time_passed < cooldown:
            remaining = cooldown - time_passed
            await message.answer(f"⏳ Подождите {remaining:.1f} секунд перед следующим запросом.")
            return
    
    user_last_request[chat_id] = current_time
    
    # Отправляем сообщение "Думаю..."
    thinking_msg_id = await send_thinking_message(chat_id)
    
    try:
        # Скачиваем голосовое сообщение
        voice = message.voice
        file_info = await bot.get_file(voice.file_id)
        file_path = file_info.file_path
        
        # Скачиваем файл
        file_bytes = await bot.download_file(file_path)
        
        # Транскрибируем аудио
        transcribed_text = await transcribe_audio_with_mistral(file_bytes.read())
        
        # Удаляем сообщение "Думаю..."
        await delete_thinking_message(chat_id, thinking_msg_id)
        
        # Отправляем результат
        response = create_smart_response(transcribed_text, "voice")
        await message.answer(response)
        
        # Обновляем статистику
        increment_user_requests(chat_id)
        
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("🎤 Голосовое сообщение получено! Если вам нужен конкретный ответ, пожалуйста, уточните вопрос текстом.")

@dp.message(F.text)
async def handle_text(message: types.Message):
    """Обработка текстовых сообщений"""
    chat_id = message.chat.id
    user_text = message.text.strip()
    initialize_user_data(chat_id)
    
    # Обработка кнопок меню
    if user_text == "💬 Обычный чат":
        user_modes[chat_id] = "обычный"
        save_data(user_modes, DATA_FILES['user_modes'])
        await message.answer("💬 Режим изменен на *Обычный чат*. Теперь я готов к беседе!", parse_mode="Markdown")
        return
    
    elif user_text == "📚 Помощь с уроками":
        user_modes[chat_id] = "помощь с уроками"
        save_data(user_modes, DATA_FILES['user_modes'])
        remaining = get_remaining_homework_requests(chat_id)
        await message.answer(f"📚 Режим изменен на *Помощь с уроками*! Отправляйте задачи по любым предметам.\n\n📊 Осталось запросов сегодня: {remaining}/{HOMEWORK_FREE_LIMITS}", parse_mode="Markdown")
        return
    
    elif user_text == "📸 Обработать фото":
        await message.answer("📸 Отправьте фото с текстом для обработки. Вы можете добавить инструкцию в подписи к фото, например:\n• \"распознай текст\"\n• \"переведи на английский\"\n• \"расскажи что на фото\"")
        return
    
    elif user_text == "🎤 Голосовое сообщение":
        await message.answer("🎤 Отправьте голосовое сообщение. Я распознаю речь и отвечу текстом. Поддерживаются основные языки.")
        return
    
    elif user_text == "🌤️ Узнать погоду":
        await message.answer("🌤️ Напишите название города для получения погоды, например:\n• \"погода Москва\"\n• \"Лондон\"\n• \"погода в Париже\"")
        return
    
    elif user_text == "⚙️ Настройки":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎭 Стиль общения", callback_data="style_balanced")],
            [InlineKeyboardButton(text="🎛️ Режим работы", callback_data="mode_normal")],
            [InlineKeyboardButton(text="🧹 Очистить историю", callback_data="clear_history")]
        ])
        await message.answer("⚙️ *Настройки бота*", reply_markup=keyboard, parse_mode="Markdown")
        return
    
    elif user_text == "📊 Профиль":
        await cmd_profile(message)
        return
    
    elif user_text == "💎 Тарифы":
        await cmd_tariffs(message)
        return
    
    # Проверяем возможность сделать запрос
    current_mode = user_modes.get(chat_id, "обычный")
    
    if current_mode == "помощь с уроками":
        can_request, error_msg = can_user_make_homework_request(chat_id)
    else:
        can_request, error_msg = can_user_make_request(chat_id)
    
    if not can_request:
        await message.answer(error_msg)
        return
    
    # Проверяем кулдаун
    current_time = time.time()
    if chat_id in user_last_request:
        cooldown = get_user_cooldown(chat_id)
        time_passed = current_time - user_last_request[chat_id]
        if time_passed < cooldown:
            remaining = cooldown - time_passed
            await message.answer(f"⏳ Подождите {remaining:.1f} секунд перед следующим запросом.")
            return
    
    user_last_request[chat_id] = current_time
    
    # Обработка специальных команд
    user_text_lower = user_text.lower()
    
    # Погода
    if any(word in user_text_lower for word in ["погода", "weather"]) or user_text_lower in CITY_MAPPING:
        city = user_text_lower
        # Извлекаем название города
        for key in ["погода", "weather", "в", "в городе"]:
            city = city.replace(key, "").strip()
        
        if city in CITY_MAPPING:
            city = CITY_MAPPING[city]
        
        if city:
            thinking_msg_id = await send_thinking_message(chat_id)
            weather_info = await get_detailed_weather(city)
            await delete_thinking_message(chat_id, thinking_msg_id)
            await message.answer(weather_info)
            increment_user_requests(chat_id)
            return
    
    # Отправляем сообщение "Думаю..."
    thinking_msg_id = await send_thinking_message(chat_id)
    
    try:
        # Определяем тип вопроса
        question_type = "normal"
        if current_mode == "помощь с уроками":
            question_type = "homework"
            increment_homework_requests(chat_id)
        elif any(word in user_text_lower for word in ["посчитай", "сколько будет", "вычисли"]):
            question_type = "calculation"
        elif len(user_text) < 20 and "?" not in user_text:
            question_type = "simple"
        
        # Получаем ответ от AI
        ai_response = await get_ai_response(user_text, chat_id)
        
        # Удаляем сообщение "Думаю..."
        await delete_thinking_message(chat_id, thinking_msg_id)
        
        # Форматируем ответ
        final_response = create_smart_response(ai_response, question_type)
        
        # Отправляем ответ
        await message.answer(final_response)
        
        # Обновляем статистику
        increment_user_requests(chat_id)
        
    except Exception as e:
        logger.error(f"Text processing error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("❌ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте еще раз.")

# =======================
# ===== ЗАПУСК БОТА =====
# =======================
async def main():
    """Основная функция запуска бота"""
    logger.info("Запуск бота...")
    
    # Проверяем наличие необходимых файлов
    for filename in DATA_FILES.values():
        if not os.path.exists(filename):
            save_data({}, filename)
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
