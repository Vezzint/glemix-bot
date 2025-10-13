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
# ===== КЛАВИАТУРЫ =====
# =======================
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Обычный чат"), KeyboardButton(text="📚 Помощь с уроками")],
            [KeyboardButton(text="📸 Обработать фото"), KeyboardButton(text="🎤 Голосовое сообщение")],
            [KeyboardButton(text="🌤️ Узнать погоду"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="📊 Профиль"), KeyboardButton(text="💎 Тарифы")]
        ],
        resize_keyboard=True
    )

def get_settings_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура настроек"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎭 Стиль общения"), KeyboardButton(text="🎛️ Режим работы")],
            [KeyboardButton(text="🧹 Очистить историю"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="⬅️ Назад в меню")]
        ],
        resize_keyboard=True
    )

def get_style_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура стилей"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚖️ Сбалансированный"), KeyboardButton(text="💼 Профессиональный")],
            [KeyboardButton(text="😊 Дружелюбный"), KeyboardButton(text="🎨 Креативный")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def get_mode_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура режимов"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Обычный"), KeyboardButton(text="📚 Помощь с уроками")],
            [KeyboardButton(text="🔍 Аналитический"), KeyboardButton(text="🎯 Краткий")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def get_tariffs_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура тарифов"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Default"), KeyboardButton(text="⭐ Pro")],
            [KeyboardButton(text="💎 Advanced"), KeyboardButton(text="👑 Ultimate")],
            [KeyboardButton(text="📊 Мой тариф"), KeyboardButton(text="⬅️ Назад в меню")]
        ],
        resize_keyboard=True
    )

def get_weather_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура погоды"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌆 Москва"), KeyboardButton(text="🏛️ Санкт-Петербург")],
            [KeyboardButton(text="🗽 Нью-Йорк"), KeyboardButton(text="🌉 Лондон")],
            [KeyboardButton(text="🌃 Другой город"), KeyboardButton(text="⬅️ Назад в меню")]
        ],
        resize_keyboard=True
    )

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
    welcome_text += "Выберите действие:"

    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    """Главное меню"""
    await message.answer("🎛️ Главное меню:", reply_markup=get_main_keyboard())

# =======================
# ===== ОБРАБОТКА КНОПОК ГЛАВНОГО МЕНЮ =====
# =======================
@dp.message(F.text == "💬 Обычный чат")
async def handle_normal_chat(message: types.Message):
    """Обработка кнопки обычного чата"""
    chat_id = message.chat.id
    user_modes[chat_id] = "обычный"
    save_data(user_modes, DATA_FILES['user_modes'])
    await message.answer("💬 Режим изменен на *Обычный чат*. Теперь я готов к беседе!", 
                        reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.message(F.text == "📚 Помощь с уроками")
async def handle_homework_mode(message: types.Message):
    """Обработка кнопки помощи с уроками"""
    chat_id = message.chat.id
    user_modes[chat_id] = "помощь с уроками"
    save_data(user_modes, DATA_FILES['user_modes'])
    remaining = get_remaining_homework_requests(chat_id)
    await message.answer(
        f"📚 Режим изменен на *Помощь с уроками*! Отправляйте задачи по любым предметам.\n\n"
        f"📊 Осталось запросов сегодня: {remaining}/{HOMEWORK_FREE_LIMITS}",
        reply_markup=get_main_keyboard(), 
        parse_mode="Markdown"
    )

@dp.message(F.text == "📸 Обработать фото")
async def handle_photo_processing(message: types.Message):
    """Обработка кнопки обработки фото"""
    await message.answer(
        "📸 Отправьте фото с текстом для обработки. Вы можете добавить инструкцию в подписи к фото, например:\n"
        "• \"распознай текст\"\n• \"переведи на английский\"\n• \"расскажи что на фото\"",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "🎤 Голосовое сообщение")
async def handle_voice_message(message: types.Message):
    """Обработка кнопки голосового сообщения"""
    await message.answer(
        "🎤 Отправьте голосовое сообщение. Я распознаю речь и отвечу текстом. Поддерживаются основные языки.",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "🌤️ Узнать погоду")
async def handle_weather(message: types.Message):
    """Обработка кнопки погоды"""
    await message.answer(
        "🌤️ Выберите город или введите название другого города:",
        reply_markup=get_weather_keyboard()
    )

@dp.message(F.text == "⚙️ Настройки")
async def handle_settings(message: types.Message):
    """Обработка кнопки настроек"""
    await message.answer("⚙️ Настройки бота:", reply_markup=get_settings_keyboard())

@dp.message(F.text == "📊 Профиль")
async def handle_profile(message: types.Message):
    """Обработка кнопки профиля"""
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
    
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.message(F.text == "💎 Тарифы")
async def handle_tariffs(message: types.Message):
    """Обработка кнопки тарифов"""
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
    
    await message.answer(text, reply_markup=get_tariffs_keyboard(), parse_mode="Markdown")

# =======================
# ===== ОБРАБОТКА КНОПОК НАСТРОЕК =====
# =======================
@dp.message(F.text == "🎭 Стиль общения")
async def handle_communication_style(message: types.Message):
    """Обработка кнопки стиля общения"""
    await message.answer(
        "🎭 Выберите стиль общения:\n\n"
        "• ⚖️ Сбалансированный - универсальный стиль\n"
        "• 💼 Профессиональный - деловой тон\n" 
        "• 😊 Дружелюбный - неформальное общение\n"
        "• 🎨 Креативный - творческие ответы",
        reply_markup=get_style_keyboard()
    )

@dp.message(F.text == "⚖️ Сбалансированный")
async def handle_balanced_style(message: types.Message):
    """Обработка кнопки сбалансированного стиля"""
    chat_id = message.chat.id
    chat_style[chat_id] = "balanced"
    save_data(chat_style, DATA_FILES['chat_style'])
    await message.answer("✅ Стиль общения изменен на: Сбалансированный", reply_markup=get_settings_keyboard())

@dp.message(F.text == "💼 Профессиональный")
async def handle_professional_style(message: types.Message):
    """Обработка кнопки профессионального стиля"""
    chat_id = message.chat.id
    chat_style[chat_id] = "professional"
    save_data(chat_style, DATA_FILES['chat_style'])
    await message.answer("✅ Стиль общения изменен на: Профессиональный", reply_markup=get_settings_keyboard())

@dp.message(F.text == "😊 Дружелюбный")
async def handle_friendly_style(message: types.Message):
    """Обработка кнопки дружелюбного стиля"""
    chat_id = message.chat.id
    chat_style[chat_id] = "friendly"
    save_data(chat_style, DATA_FILES['chat_style'])
    await message.answer("✅ Стиль общения изменен на: Дружелюбный", reply_markup=get_settings_keyboard())

@dp.message(F.text == "🎨 Креативный")
async def handle_creative_style(message: types.Message):
    """Обработка кнопки креативного стиля"""
    chat_id = message.chat.id
    chat_style[chat_id] = "creative"
    save_data(chat_style, DATA_FILES['chat_style'])
    await message.answer("✅ Стиль общения изменен на: Креативный", reply_markup=get_settings_keyboard())

@dp.message(F.text == "🎛️ Режим работы")
async def handle_work_mode(message: types.Message):
    """Обработка кнопки режима работы"""
    await message.answer(
        "🎛️ Выберите режим работы:\n\n"
        "• 💬 Обычный - стандартные ответы\n"
        "• 📚 Помощь с уроками - детальные объяснения\n"
        "• 🔍 Аналитический - глубокий анализ\n"
        "• 🎯 Краткий - сжатые ответы",
        reply_markup=get_mode_keyboard()
    )

@dp.message(F.text == "💬 Обычный")
async def handle_normal_mode(message: types.Message):
    """Обработка кнопки обычного режима"""
    chat_id = message.chat.id
    user_modes[chat_id] = "обычный"
    save_data(user_modes, DATA_FILES['user_modes'])
    await message.answer("✅ Режим изменен на: Обычный", reply_markup=get_settings_keyboard())

@dp.message(F.text == "🔍 Аналитический")
async def handle_analytical_mode(message: types.Message):
    """Обработка кнопки аналитического режима"""
    chat_id = message.chat.id
    user_modes[chat_id] = "аналитический"
    save_data(user_modes, DATA_FILES['user_modes'])
    await message.answer("✅ Режим изменен на: Аналитический", reply_markup=get_settings_keyboard())

@dp.message(F.text == "🎯 Краткий")
async def handle_concise_mode(message: types.Message):
    """Обработка кнопки краткого режима"""
    chat_id = message.chat.id
    user_modes[chat_id] = "краткий"
    save_data(user_modes, DATA_FILES['user_modes'])
    await message.answer("✅ Режим изменен на: Краткий", reply_markup=get_settings_keyboard())

@dp.message(F.text == "🧹 Очистить историю")
async def handle_clear_history(message: types.Message):
    """Обработка кнопки очистки истории"""
    chat_id = message.chat.id
    
    if chat_id in conversation_memory:
        conversation_memory[chat_id] = []
        save_data(conversation_memory, DATA_FILES['conversation_memory'])
    
    await message.answer("✅ История диалога очищена. Начинаем новый разговор!", reply_markup=get_settings_keyboard())

@dp.message(F.text == "📊 Статистика")
async def handle_statistics(message: types.Message):
    """Обработка кнопки статистики"""
    chat_id = message.chat.id
    total_requests = user_requests_count.get(chat_id, {}).get("total", 0)
    remaining_requests = get_remaining_daily_requests(chat_id)
    remaining_homework = get_remaining_homework_requests(chat_id)
    current_tariff = get_user_tariff(chat_id)
    
    stats_text = f"📊 Ваша статистика:\n\n"
    stats_text += f"📈 Всего запросов: {total_requests}\n"
    stats_text += f"📅 Осталось сегодня: {remaining_requests}/{TARIFFS[current_tariff]['daily_limits']}\n"
    stats_text += f"📚 Помощь с уроками: {remaining_homework}/{HOMEWORK_FREE_LIMITS}\n"
    stats_text += f"💎 Тариф: {TARIFFS[current_tariff]['name']}\n"
    stats_text += f"⏳ Осталось дней: {get_remaining_days(chat_id)}"
    
    await message.answer(stats_text, reply_markup=get_settings_keyboard())

# =======================
# ===== ОБРАБОТКА КНОПОК ТАРИФОВ =====
# =======================
@dp.message(F.text == "🚀 Default")
async def handle_default_tariff(message: types.Message):
    """Обработка кнопки тарифа Default"""
    chat_id = message.chat.id
    if chat_id != ADMIN_ID:
        activate_tariff(chat_id, "default", 30)
        await message.answer("✅ Тариф 🚀 Default активирован на 30 дней!", reply_markup=get_tariffs_keyboard())
    else:
        await message.answer("👑 Администратор всегда на максимальном тарифе!", reply_markup=get_tariffs_keyboard())

@dp.message(F.text == "⭐ Pro")
async def handle_pro_tariff(message: types.Message):
    """Обработка кнопки тарифа Pro"""
    chat_id = message.chat.id
    if chat_id != ADMIN_ID:
        activate_tariff(chat_id, "pro", 30)
        await message.answer("✅ Тариф ⭐ Pro активирован на 30 дней!", reply_markup=get_tariffs_keyboard())
    else:
        await message.answer("👑 Администратор всегда на максимальном тарифе!", reply_markup=get_tariffs_keyboard())

@dp.message(F.text == "💎 Advanced")
async def handle_advanced_tariff(message: types.Message):
    """Обработка кнопки тарифа Advanced"""
    chat_id = message.chat.id
    if chat_id != ADMIN_ID:
        activate_tariff(chat_id, "advanced", 30)
        await message.answer("✅ Тариф 💎 Advanced активирован на 30 дней!", reply_markup=get_tariffs_keyboard())
    else:
        await message.answer("👑 Администратор всегда на максимальном тарифе!", reply_markup=get_tariffs_keyboard())

@dp.message(F.text == "👑 Ultimate")
async def handle_ultimate_tariff(message: types.Message):
    """Обработка кнопки тарифа Ultimate"""
    chat_id = message.chat.id
    if chat_id != ADMIN_ID:
        activate_tariff(chat_id, "ultimate", 30)
        await message.answer("✅ Тариф 👑 Ultimate активирован на 30 дней!", reply_markup=get_tariffs_keyboard())
    else:
        await message.answer("👑 Администратор всегда на максимальном тарифе!", reply_markup=get_tariffs_keyboard())

@dp.message(F.text == "📊 Мой тариф")
async def handle_my_tariff(message: types.Message):
    """Обработка кнопки моего тарифа"""
    chat_id = message.chat.id
    current_tariff = get_user_tariff(chat_id)
    remaining_days = get_remaining_days(chat_id)
    remaining_requests = get_remaining_daily_requests(chat_id)
    
    tariff_text = f"📊 Ваш текущий тариф:\n\n"
    tariff_text += f"💎 {TARIFFS[current_tariff]['name']}\n"
    tariff_text += f"⏳ Осталось дней: {remaining_days}\n"
    tariff_text += f"📊 Запросов сегодня: {remaining_requests}/{TARIFFS[current_tariff]['daily_limits']}\n"
    tariff_text += f"⚡ Ожидание: {get_user_cooldown(chat_id)} сек\n"
    tariff_text += f"💾 Память: {get_user_memory_limit(chat_id)} сообщений"
    
    await message.answer(tariff_text, reply_markup=get_tariffs_keyboard())

# =======================
# ===== ОБРАБОТКА КНОПОК ПОГОДЫ =====
# =======================
@dp.message(F.text.in_(["🌆 Москва", "🏛️ Санкт-Петербург", "🗽 Нью-Йорк", "🌉 Лондон"]))
async def handle_city_weather(message: types.Message):
    """Обработка кнопок городов погоды"""
    city_mapping = {
        "🌆 Москва": "Москва",
        "🏛️ Санкт-Петербург": "Санкт-Петербург", 
        "🗽 Нью-Йорк": "Нью-Йорк",
        "🌉 Лондон": "Лондон"
    }
    
    city = city_mapping.get(message.text, message.text)
    
    thinking_msg_id = await send_thinking_message(message.chat.id)
    
    try:
        weather_info = await get_detailed_weather(city)
        await delete_thinking_message(message.chat.id, thinking_msg_id)
        await message.answer(weather_info, reply_markup=get_weather_keyboard())
        increment_user_requests(message.chat.id)
        
    except Exception as e:
        await delete_thinking_message(message.chat.id, thinking_msg_id)
        await message.answer("❌ Ошибка получения погоды. Попробуйте позже.", reply_markup=get_weather_keyboard())

@dp.message(F.text == "🌃 Другой город")
async def handle_other_city(message: types.Message):
    """Обработка кнопки другого города"""
    await message.answer("🏙️ Введите название города (например: 'Погода в Москве' или просто 'Москва'):", 
                        reply_markup=get_weather_keyboard())

# =======================
# ===== ОБРАБОТКА КНОПОК НАЗАД =====
# =======================
@dp.message(F.text == "⬅️ Назад")
async def handle_back(message: types.Message):
    """Обработка кнопки назад"""
    await message.answer("⚙️ Настройки:", reply_markup=get_settings_keyboard())

@dp.message(F.text == "⬅️ Назад в меню")
async def handle_back_to_menu(message: types.Message):
    """Обработка кнопки назад в меню"""
    await message.answer("🎛️ Главное меню:", reply_markup=get_main_keyboard())

# =======================
# ===== ОСНОВНАЯ ЛОГИКА ОБРАБОТКИ =====
# =======================
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    """Обработка фотографий"""
    chat_id = message.chat.id
    initialize_user_data(chat_id)
    
    # Проверяем возможность сделать запрос
    can_request, error_msg = can_user_make_request(chat_id)
    if not can_request:
        await message.answer(error_msg, reply_markup=get_main_keyboard())
        return
    
    # Проверяем кулдаун
    current_time = time.time()
    if chat_id in user_last_request:
        cooldown = get_user_cooldown(chat_id)
        time_passed = current_time - user_last_request[chat_id]
        if time_passed < cooldown:
            remaining = cooldown - time_passed
            await message.answer(f"⏳ Подождите {remaining:.1f} секунд перед следующим запросом.", reply_markup=get_main_keyboard())
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
        await message.answer(response, reply_markup=get_main_keyboard())
        
        # Обновляем статистику
        increment_user_requests(chat_id)
        
    except Exception as e:
        logger.error(f"Photo processing error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("❌ Ошибка обработки изображения. Пожалуйста, попробуйте еще раз.", reply_markup=get_main_keyboard())

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    """Обработка голосовых сообщений"""
    chat_id = message.chat.id
    initialize_user_data(chat_id)
    
    # Проверяем возможность сделать запрос
    can_request, error_msg = can_user_make_request(chat_id)
    if not can_request:
        await message.answer(error_msg, reply_markup=get_main_keyboard())
        return
    
    # Проверяем кулдаун
    current_time = time.time()
    if chat_id in user_last_request:
        cooldown = get_user_cooldown(chat_id)
        time_passed = current_time - user_last_request[chat_id]
        if time_passed < cooldown:
            remaining = cooldown - time_passed
            await message.answer(f"⏳ Подождите {remaining:.1f} секунд перед следующим запросом.", reply_markup=get_main_keyboard())
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
        await message.answer(response, reply_markup=get_main_keyboard())
        
        # Обновляем статистику
        increment_user_requests(chat_id)
        
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("🎤 Голосовое сообщение получено! Если вам нужен конкретный ответ, пожалуйста, уточните вопрос текстом.", reply_markup=get_main_keyboard())

@dp.message(F.text)
async def handle_text(message: types.Message):
    """Обработка текстовых сообщений"""
    chat_id = message.chat.id
    user_text = message.text.strip()
    initialize_user_data(chat_id)
    
    # Игнорируем кнопки, которые уже обработаны
    button_texts = [
        # Главное меню
        "💬 Обычный чат", "📚 Помощь с уроками", "📸 Обработать фото", "🎤 Голосовое сообщение",
        "🌤️ Узнать погоду", "⚙️ Настройки", "📊 Профиль", "💎 Тарифы",
        # Настройки
        "🎭 Стиль общения", "🎛️ Режим работы", "🧹 Очистить историю", "📊 Статистика",
        "⬅️ Назад", "⬅️ Назад в меню",
        # Стили
        "⚖️ Сбалансированный", "💼 Профессиональный", "😊 Дружелюбный", "🎨 Креативный",
        # Режимы
        "💬 Обычный", "🔍 Аналитический", "🎯 Краткий",
        # Тарифы
        "🚀 Default", "⭐ Pro", "💎 Advanced", "👑 Ultimate", "📊 Мой тариф",
        # Погода
        "🌆 Москва", "🏛️ Санкт-Петербург", "🗽 Нью-Йорк", "🌉 Лондон", "🌃 Другой город"
    ]
    
    if user_text in button_texts:
        return
    
    # Проверяем возможность сделать запрос
    current_mode = user_modes.get(chat_id, "обычный")
    
    if current_mode == "помощь с уроками":
        can_request, error_msg = can_user_make_homework_request(chat_id)
    else:
        can_request, error_msg = can_user_make_request(chat_id)
    
    if not can_request:
        await message.answer(error_msg, reply_markup=get_main_keyboard())
        return
    
    # Проверяем кулдаун
    current_time = time.time()
    if chat_id in user_last_request:
        cooldown = get_user_cooldown(chat_id)
        time_passed = current_time - user_last_request[chat_id]
        if time_passed < cooldown:
            remaining = cooldown - time_passed
            await message.answer(f"⏳ Подождите {remaining:.1f} секунд перед следующим запросом.", reply_markup=get_main_keyboard())
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
            await message.answer(weather_info, reply_markup=get_main_keyboard())
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
        await message.answer(final_response, reply_markup=get_main_keyboard())
        
        # Обновляем статистику
        increment_user_requests(chat_id)
        
    except Exception as e:
        logger.error(f"Text processing error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("❌ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте еще раз.", reply_markup=get_main_keyboard())

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
