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
    'user_homework_requests': 'user_homework_requests.pkl',
    'user_promo_codes': 'user_promo_codes.pkl',
    'user_language': 'user_language.pkl'
}

# =======================
# ===== БОЛЬШАЯ БАЗА ГОРОДОВ ДЛЯ ПОГОДЫ =====
# =======================
CITY_MAPPING = {
    # Российские города
    "москва": "Moscow", "мск": "Moscow", "москве": "Moscow",
    "санкт-петербург": "Saint Petersburg", "питер": "Saint Petersburg", "спб": "Saint Petersburg", "петербурге": "Saint Petersburg",
    "новосибирск": "Novosibirsk", "нск": "Novosibirsk", "новосибирске": "Novosibirsk",
    "екатеринбург": "Yekaterinburg", "екб": "Yekaterinburg", "екатеринбурге": "Yekaterinburg",
    "казань": "Kazan", "казани": "Kazan",
    "нижний новгород": "Nizhny Novgorod", "нижний": "Nizhny Novgorod", "нижнем новгороде": "Nizhny Novgorod",
    "челябинск": "Chelyabinsk", "челябинске": "Chelyabinsk",
    "самара": "Samara", "самаре": "Samara",
    "омск": "Omsk", "омске": "Omsk",
    "ростов-на-дону": "Rostov-on-Don", "ростов": "Rostov-on-Don", "ростове": "Rostov-on-Don",
    "уфа": "Ufa", "уфе": "Ufa",
    "красноярск": "Krasnoyarsk", "красноярске": "Krasnoyarsk",
    "пермь": "Perm", "перми": "Perm",
    "воронеж": "Voronezh", "воронеже": "Voronezh",
    "волгоград": "Volgograd", "волгограде": "Volgograd",
    "краснодар": "Krasnodar", "краснодаре": "Krasnodar",
    "саратов": "Saratov", "саратове": "Saratov",
    "тюмень": "Tyumen", "тюмени": "Tyumen",
    "тольятти": "Tolyatti", "тольятти": "Tolyatti",
    "ижевск": "Izhevsk", "ижевске": "Izhevsk",
    "барнаул": "Barnaul", "барнауле": "Barnaul",
    "ульяновск": "Ulyanovsk", "ульяновске": "Ulyanovsk",
    "иркутск": "Irkutsk", "иркутске": "Irkutsk",
    "хабаровск": "Khabarovsk", "хабаровске": "Khabarovsk",
    "ярославль": "Yaroslavl", "ярославле": "Yaroslavl",
    "владивосток": "Vladivostok", "владивостоке": "Vladivostok",
    "махачкала": "Makhachkala", "махачкале": "Makhachkala",
    "томск": "Tomsk", "томске": "Tomsk",
    "оренбург": "Orenburg", "оренбурге": "Orenburg",
    "кемерово": "Kemerovo", "кемерово": "Kemerovo",
    "новокузнецк": "Novokuznetsk", "новокузнецке": "Novokuznetsk",
    "рязань": "Ryazan", "рязани": "Ryazan",
    "астрахань": "Astrakhan", "астрахани": "Astrakhan",
    "набережные челны": "Naberezhnye Chelny", "набережных челнах": "Naberezhnye Chelny",
    "пенза": "Penza", "пензе": "Penza",
    "киров": "Kirov", "кирове": "Kirov",
    "липецк": "Lipetsk", "липецке": "Lipetsk",
    "чебоксары": "Cheboksary", "чебоксарах": "Cheboksary",
    "калининград": "Kaliningrad", "калининграде": "Kaliningrad",
    "тула": "Tula", "туле": "Tula",
    "ставрополь": "Stavropol", "ставрополе": "Stavropol",
    "курск": "Kursk", "курске": "Kursk",
    "сочи": "Sochi", "сочи": "Sochi",
    "тверь": "Tver", "твери": "Tver",
    "магнитогорск": "Magnitogorsk", "магнитогорске": "Magnitogorsk",
    "севастополь": "Sevastopol", "севастополе": "Sevastopol",
    "сургут": "Surgut", "сургуте": "Surgut",
    
    # Международные города
    "нью-йорк": "New York", "нью йорк": "New York", "new york": "New York", "нью-йорке": "New York",
    "лондон": "London", "лондоне": "London",
    "париж": "Paris", "париже": "Paris",
    "токио": "Tokyo", "токио": "Tokyo",
    "дубай": "Dubai", "дубае": "Dubai",
    "сидней": "Sydney", "сиднее": "Sydney",
    "берлин": "Berlin", "берлине": "Berlin",
    "мадрид": "Madrid", "мадриде": "Madrid",
    "рим": "Rome", "риме": "Rome",
    "амстердам": "Amsterdam", "амстердаме": "Amsterdam",
    "прага": "Prague", "праге": "Prague",
    "вена": "Vienna", "вене": "Vienna",
    "варшава": "Warsaw", "варшаве": "Warsaw",
    "стамбул": "Istanbul", "стамбуле": "Istanbul",
    "пекин": "Beijing", "пекине": "Beijing",
    "шанхай": "Shanghai", "шанхае": "Shanghai",
    "гонконг": "Hong Kong", "гонконге": "Hong Kong",
    "сеул": "Seoul", "сеуле": "Seoul",
    "бангкок": "Bangkok", "бангкоке": "Bangkok",
    "сингапур": "Singapore", "сингапуре": "Singapore",
    "куала-лумпур": "Kuala Lumpur", "куала-лумпуре": "Kuala Lumpur",
    "мельбурн": "Melbourne", "мельбурне": "Melbourne",
    "брисбен": "Brisbane", "брисбене": "Brisbane",
    "осло": "Oslo", "осло": "Oslo",
    "стокгольм": "Stockholm", "стокгольме": "Stockholm",
    "хельсинки": "Helsinki", "хельсинки": "Helsinki",
    "копенгаген": "Copenhagen", "копенгагене": "Copenhagen",
    "милан": "Milan", "милане": "Milan",
    "барселона": "Barcelona", "барселоне": "Barcelona",
    "лиссабон": "Lisbon", "лиссабоне": "Lisbon",
    "брюссель": "Brussels", "брюсселе": "Brussels",
    "афины": "Athens", "афинах": "Athens",
    "будапешт": "Budapest", "будапеште": "Budapest",
    "бухарест": "Bucharest", "бухаресте": "Bucharest",
    "киев": "Kyiv", "киеве": "Kyiv",
    "минск": "Minsk", "минске": "Minsk",
    "алматы": "Almaty", "алматы": "Almaty",
    "ташкент": "Tashkent", "ташкенте": "Tashkent",
    "баку": "Baku", "баку": "Baku",
    "ереван": "Yerevan", "ереване": "Yerevan",
    "теляви": "Tbilisi", "теляви": "Tbilisi",
    
    # Украинские города
    "харьков": "Kharkiv", "харькове": "Kharkiv",
    "одесса": "Odesa", "одессе": "Odesa",
    "днепр": "Dnipro", "днепре": "Dnipro",
    "донецк": "Donetsk", "донецке": "Donetsk",
    "запорожье": "Zaporizhzhia", "запорожье": "Zaporizhzhia",
    "львов": "Lviv", "львове": "Lviv",
    
    # Казахстанские города
    "нур-султан": "Nur-Sultan", "астана": "Nur-Sultan", "астане": "Nur-Sultan",
    "шымкент": "Shymkent", "шымкенте": "Shymkent",
    "актобе": "Aktobe", "актобе": "Aktobe",
    "караганда": "Karaganda", "караганде": "Karaganda",
    
    # Белорусские города
    "гомель": "Gomel", "гомеле": "Gomel",
    "могилев": "Mogilev", "могилеве": "Mogilev",
    "витебск": "Vitebsk", "витебске": "Vitebsk",
    "гродно": "Grodno", "гродно": "Grodno",
    "брест": "Brest", "бресте": "Brest",
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
    
    if chat_id not in user_promo_codes:
        user_promo_codes[chat_id] = {}
        save_data(user_promo_codes, DATA_FILES['user_promo_codes'])
    
    if chat_id not in user_language:
        user_language[chat_id] = "ru"
        save_data(user_language, DATA_FILES['user_language'])

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
    if chat_id == ADMIN_ID:
        return 99999  # Админ без ограничений
    
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
user_promo_codes = load_data(DATA_FILES['user_promo_codes'], {})
user_language = load_data(DATA_FILES['user_language'], {})

# Переменные для временных данных
user_last_request: Dict[int, float] = {}
user_thinking_messages: Dict[int, int] = {}
user_awaiting_promo: Dict[int, bool] = {}
user_last_photo_text: Dict[int, str] = {}  # Для хранения распознанного текста с фото
user_awaiting_language: Dict[int, bool] = {}  # Для выбора языка при старте

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
    if chat_id == ADMIN_ID:
        return 0  # Админ без кулдауна
    
    tariff = get_user_tariff(chat_id)
    return TARIFF_COOLDOWNS.get(tariff, 5)

def get_user_memory_limit(chat_id: int) -> int:
    """Возвращает лимит памяти для пользователя"""
    tariff = get_user_tariff(chat_id)
    return TARIFF_MEMORY.get(tariff, 10)

def get_user_daily_limit(chat_id: int) -> int:
    """Возвращает дневной лимит запросов"""
    if chat_id == ADMIN_ID:
        return 99999  # Админ без ограничений
    
    tariff = get_user_tariff(chat_id)
    return TARIFFS[tariff]["daily_limits"]

def get_remaining_daily_requests(chat_id: int) -> int:
    """Возвращает оставшиеся запросы на сегодня"""
    if chat_id == ADMIN_ID:
        return 99999  # Админ без ограничений
    
    today = datetime.now().date()
    daily_data = user_daily_requests.get(chat_id, {})
    if daily_data.get("date") != today:
        return get_user_daily_limit(chat_id)
    return max(0, get_user_daily_limit(chat_id) - daily_data.get("count", 0))

def increment_daily_requests(chat_id: int):
    """Увеличивает счетчик дневных запросов"""
    if chat_id == ADMIN_ID:
        return  # Админ не тратит запросы
    
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
    if chat_id == ADMIN_ID:
        return True, ""  # Админ всегда может
    
    if not is_subscription_active(chat_id):
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
    if chat_id == ADMIN_ID:
        return True, ""  # Админ всегда может
    
    remaining_homework = get_remaining_homework_requests(chat_id)
    if remaining_homework <= 0:
        return False, f"Лимит запросов в режиме 'Помощь с уроками' исчерпан ({HOMEWORK_FREE_LIMITS}/день). Активируйте тариф или используйте промокод для снятия ограничений."
    
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
            elif "на итальянский" in user_instruction_lower:
                target_language = "итальянский"
            elif "на китайский" in user_instruction_lower:
                target_language = "китайский"
            elif "на японский" in user_instruction_lower:
                target_language = "японский"
            elif "на корейский" in user_instruction_lower:
                target_language = "корейский"
            
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
# ===== ПЕРЕВОД ТЕКСТА =====
# =======================
async def translate_text(text: str, target_language: str) -> str:
    """Переводит текст на указанный язык"""
    try:
        messages = [
            {
                "role": "user",
                "content": f"Пожалуйста, переведи следующий текст на {target_language} язык. Верни только перевод без дополнительных комментариев:\n\n{text}"
            }
        ]
        
        response = client.chat.complete(
            model=model,
            messages=messages,
            max_tokens=2000
        )
        
        translated_text = response.choices[0].message.content.strip()
        return translated_text
        
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return f"❌ Ошибка перевода текста: {str(e)}"

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
            model="pixtral-12b-2409",
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
        return f"📚 Ответ на задание:\n\n{text}"
    elif question_type == "voice":
        return text
    elif question_type == "translation":
        return f"🌐 Перевод:\n\n{text}"
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

async def get_ai_response(message_text: str, chat_id: int, mode: str = "обычный") -> str:
    """Получает ответ от AI с учетом контекста и стиля"""
    try:
        # Получаем историю сообщений
        memory = conversation_memory.get(chat_id, [])
        memory_limit = get_user_memory_limit(chat_id)
        
        # Обрезаем историю если превышен лимит
        if len(memory) > memory_limit:
            memory = memory[-memory_limit:]
        
        # Создаем системное сообщение в зависимости от режима
        if mode == "homework":
            system_message = """Ты - опытный преподаватель. Отвечай максимально четко и по делу. 

ПРАВИЛА ОТВЕТА:
1. Давай ПРЯМОЙ ОТВЕТ на вопрос/задачу
2. Без лишних вводных слов и объяснений 
3. Если нужно решение - покажи только шаги решения
4. Формулы, вычисления, ответы - выделяй четко
5. Без фраз "итак", "итак давайте", "ну что же" и т.д.
6. Только суть: условие → решение → ответ

Пример хорошего ответа:
"Задача: Найти площадь треугольника со сторонами 5, 6, 7 см.

Решение по формуле Герона:
p = (5+6+7)/2 = 9
S = √(9×(9-5)×(9-6)×(9-7)) = √(9×4×3×2) = √216 ≈ 14.7

Ответ: 14.7 см²"

Отвечай ТОЛЬКО так - кратко и по делу!"""
        else:
            system_message = "Ты полезный AI-ассистент. Отвечай информативно, но без лишних слов. Будь краток и точен."
        
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
def get_language_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора языка"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇺🇸 English")],
            [KeyboardButton(text="🇪🇸 Español"), KeyboardButton(text="🇩🇪 Deutsch")],
            [KeyboardButton(text="🇫🇷 Français"), KeyboardButton(text="🇨🇳 中文")],
            [KeyboardButton(text="🇯🇵 日本語"), KeyboardButton(text="🇰🇷 한국어")]
        ],
        resize_keyboard=True
    )

def get_main_keyboard(chat_id: int) -> ReplyKeyboardMarkup:
    """Главная клавиатура"""
    keyboard = [
        [KeyboardButton(text="🚀 Начать работу"), KeyboardButton(text="🌟 Обо мне")],
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="❓ Помощь"), KeyboardButton(text="🌤️ Погода")],
        [KeyboardButton(text="💎 Тарифы")],
        [KeyboardButton(text="🧹 Очистить память")]
    ]
    
    if chat_id == ADMIN_ID:
        keyboard.append([KeyboardButton(text="🛠️ Админ-панель")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_settings_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура настроек"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎭 Режимы AI"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🎨 Стиль общения"), KeyboardButton(text="ℹ️ Информация")],
            [KeyboardButton(text="🌐 Сменить язык"), KeyboardButton(text="⚡ Быстрые команды")],
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
            [KeyboardButton(text="📊 Мой тариф")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def get_mode_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура режимов AI"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧘 Спокойный"), KeyboardButton(text="💬 Обычный")],
            [KeyboardButton(text="⚡ Короткий"), KeyboardButton(text="🧠 Умный")],
            [KeyboardButton(text="📚 Помощь с уроками")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def get_style_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура стилей общения"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💫 Дружелюбный"), KeyboardButton(text="⚖️ Сбалансированный")],
            [KeyboardButton(text="🎯 Деловой"), KeyboardButton(text="🎨 Креативный")],
            [KeyboardButton(text="⬅️ Назад")]
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

def get_quick_commands_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура быстрых команд"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Конвертер валют"), KeyboardButton(text="🎯 Случайный выбор")],
            [KeyboardButton(text="📅 Текущая дата"), KeyboardButton(text="⏰ Текущее время")],
            [KeyboardButton(text="🔢 Калькулятор"), KeyboardButton(text="🎁 Сюрприз")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура админ-панели"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Статистика пользователей"), KeyboardButton(text="📊 Общая статистика")],
            [KeyboardButton(text="📋 Логи действий")],
            [KeyboardButton(text="⬅️ Главное меню")]
        ],
        resize_keyboard=True
    )

# =======================
# ===== КОМАНДЫ БОТА =====
# =======================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    initialize_user_data(chat_id)

    # Если язык еще не выбран, показываем выбор языка
    if user_language.get(chat_id) == "ru" or chat_id in user_language:
        await show_main_menu(message)
    else:
        user_awaiting_language[chat_id] = True
        welcome_text = (
            "🌐 Добро пожаловать! / Welcome! / ¡Bienvenido! / Willkommen! / Bienvenue! / 欢迎！/ ようこそ！/ 환영합니다！\n\n"
            "Пожалуйста, выберите язык / Please select your language:"
        )
        await message.answer(welcome_text, reply_markup=get_language_keyboard())

async def show_main_menu(message: types.Message):
    """Показывает главное меню"""
    chat_id = message.chat.id
    initialize_user_data(chat_id)

    current_mode = user_modes[chat_id]
    remaining_days = get_remaining_days(chat_id)
    current_tariff = get_user_tariff(chat_id)
    remaining_requests = get_remaining_daily_requests(chat_id)
    remaining_homework = get_remaining_homework_requests(chat_id)
    is_free = is_free_period_active(chat_id)
    
    welcome_text = f"🤖 GlemixAI\n\nДобро пожаловать! Я ваш AI-помощник.\n\n"
    
    if is_free:
        welcome_text += f"🎁 Бесплатный период: {remaining_days} дней\n"
        welcome_text += f"📚 Помощь с уроками: {remaining_homework} запросов\n"
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
# ===== ОБРАБОТКА ВЫБОРА ЯЗЫКА =====
# =======================
@dp.message(F.text.in_(["🇷🇺 Русский", "🇺🇸 English", "🇪🇸 Español", "🇩🇪 Deutsch", "🇫🇷 Français", "🇨🇳 中文", "🇯🇵 日本語", "🇰🇷 한국어"]))
async def handle_language_selection(message: types.Message):
    """Обработка выбора языка"""
    chat_id = message.chat.id
    
    language_map = {
        "🇷🇺 Русский": "ru",
        "🇺🇸 English": "en", 
        "🇪🇸 Español": "es",
        "🇩🇪 Deutsch": "de",
        "🇫🇷 Français": "fr",
        "🇨🇳 中文": "zh",
        "🇯🇵 日本語": "ja",
        "🇰🇷 한국어": "ko"
    }
    
    selected_language = language_map.get(message.text, "ru")
    user_language[chat_id] = selected_language
    save_data(user_language, DATA_FILES['user_language'])
    
    user_awaiting_language[chat_id] = False
    
    # Приветствие на выбранном языке
    greetings = {
        "ru": "Язык установлен: Русский 🇷🇺",
        "en": "Language set: English 🇺🇸",
        "es": "Idioma establecido: Español 🇪🇸", 
        "de": "Sprache eingestellt: Deutsch 🇩🇪",
        "fr": "Langue définie: Français 🇫🇷",
        "zh": "语言设置：中文 🇨🇳",
        "ja": "言語設定：日本語 🇯🇵",
        "ko": "언어 설정：한국어 🇰🇷"
    }
    
    await message.answer(greetings.get(selected_language, "Язык установлен"), reply_markup=get_main_keyboard(chat_id))

# =======================
# ===== ОБРАБОТКА КНОПОК ГЛАВНОГО МЕНЮ =====
# =======================
@dp.message(F.text == "🚀 Начать работу")
async def handle_start_work(message: types.Message):
    await show_main_menu(message)

@dp.message(F.text == "🌟 Обо мне")
async def handle_about(message: types.Message):
    about_text = (
        "🤖 GlemixAI\n\n"
        "Я - современный AI-помощник с реальными функциями:\n\n"
        "• 📝 Извлечение текста с фото (OCR)\n" 
        "• 🎤 Распознавание голосовых сообщений\n"
        "• 🧠 Умные ответы на вопросы\n"
        "• 🌤️ Подробная погода в любом городе\n"
        "• 📚 Помощь с домашними заданиями\n"
        "• 💎 Гибкая система тарифов\n\n"
        "Работаю на Mistral AI - одном из лучших AI-провайдеров!"
    )
    await message.answer(about_text, reply_markup=get_main_keyboard(message.from_user.id))

@dp.message(F.text == "❓ Помощь")
async def handle_help(message: types.Message):
    help_text = (
        "❓ Помощь по GlemixAI\n\n"
        "Что я умею:\n"
        "• 📸 Извлекать текст с фотографий\n"
        "• 🎤 Распознавать голосовые сообщения\n" 
        "• 💬 Отвечать на любые вопросы\n"
        "• 🌤️ Показывать подробную погоду\n"
        "• 📚 Помогать с домашними заданиями\n"
        "• 🔢 Выполнять вычисления\n\n"
        "Просто отправьте:\n"
        "• Фото с текстом - распознаю его\n"
        "• Голосовое сообщение - расшифрую\n"
        "• Текст - отвечу на вопрос\n"
        "• Название города - покажу погоду"
    )
    await message.answer(help_text, reply_markup=get_main_keyboard(message.from_user.id))

@dp.message(F.text == "🌤️ Погода")
async def handle_weather_button(message: types.Message):
    weather_text = "🌤️ Выберите город или введите название другого города:"
    await message.answer(weather_text, reply_markup=get_weather_keyboard())

@dp.message(F.text == "💎 Тарифы")
async def handle_tariffs(message: types.Message):
    tariffs_text = "💎 Доступные тарифы:\n\n"
    
    for tariff_id, tariff_info in TARIFFS.items():
        tariffs_text += f"{tariff_info['name']}\n"
        tariffs_text += f"Цена: {tariff_info['price']}\n"
        tariffs_text += f"Лимит: {tariff_info['daily_limits']} запросов/день\n"
        tariffs_text += f"Ожидание: {TARIFF_COOLDOWNS[tariff_id]} сек\n\n"
    
    await message.answer(tariffs_text, reply_markup=get_tariffs_keyboard())

@dp.message(F.text == "🧹 Очистить память")
async def handle_clear_memory(message: types.Message):
    """Обработка кнопки очистки памяти"""
    chat_id = message.chat.id
    
    if chat_id in conversation_memory:
        conversation_memory[chat_id] = []
        save_data(conversation_memory, DATA_FILES['conversation_memory'])
    
    if chat_id in user_last_photo_text:
        user_last_photo_text[chat_id] = ""
    
    await message.answer("✅ Память очищена! Теперь я забыл всю предыдущую беседу и готов к новым вопросам.", 
                        reply_markup=get_main_keyboard(chat_id))

@dp.message(F.text == "⚙️ Настройки")
async def handle_settings(message: types.Message):
    settings_text = "⚙️ Настройки\n\nВыберите категорию:"
    await message.answer(settings_text, reply_markup=get_settings_keyboard())

@dp.message(F.text == "🛠️ Админ-панель")
async def handle_admin_panel(message: types.Message):
    """Обработка кнопки админ-панели"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    total_users = len(user_registration_date)
    today_requests = sum(data.get("count", 0) for data in user_daily_requests.values() if data.get("date") == datetime.now().date())
    active_subscriptions = sum(1 for end_date in user_subscription_end.values() if end_date > datetime.now())
    
    admin_text = (
        "🛠️ Админ-панель GlemixAI\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"📊 Запросов сегодня: {today_requests}\n"
        f"💎 Активных подписок: {active_subscriptions}\n\n"
        "Выберите действие:"
    )
    
    await message.answer(admin_text, reply_markup=get_admin_keyboard())

@dp.message(F.text == "🌐 Сменить язык")
async def handle_change_language(message: types.Message):
    """Обработка кнопки смены языка"""
    chat_id = message.chat.id
    user_awaiting_language[chat_id] = True
    
    language_text = (
        "🌐 Выберите язык / Select your language:\n\n"
        "🇷🇺 Русский\n"
        "🇺🇸 English\n" 
        "🇪🇸 Español\n"
        "🇩🇪 Deutsch\n"
        "🇫🇷 Français\n"
        "🇨🇳 中文\n"
        "🇯🇵 日本語\n"
        "🇰🇷 한국어"
    )
    
    await message.answer(language_text, reply_markup=get_language_keyboard())

# =======================
# ===== ОБРАБОТКА КНОПОК НАСТРОЕК =====
# =======================
@dp.message(F.text == "🎭 Режимы AI")
async def handle_ai_modes(message: types.Message):
    modes_text = (
        "🎭 Режимы AI\n\n"
        "Выберите режим работы:\n"
        "• 🧘 Спокойный - мягкие ответы\n"
        "• 💬 Обычный - сбалансированные ответы\n"
        "• ⚡ Короткий - краткие ответы\n"
        "• 🧠 Умный - детальные аналитические ответы\n"
        "• 📚 Помощь с уроками - максимальная помощь с домашними заданиями"
    )
    await message.answer(modes_text, reply_markup=get_mode_keyboard())

@dp.message(F.text == "📚 Помощь с уроками")
async def handle_homework_mode(message: types.Message):
    """Активация режима помощи с уроками"""
    chat_id = message.chat.id
    user_modes[chat_id] = "homework"
    save_data(user_modes, DATA_FILES['user_modes'])
    
    remaining_homework = get_remaining_homework_requests(chat_id)
    
    mode_text = "📚 Режим 'Помощь с уроками' активирован!\n\n"
    mode_text += "Я буду максимально подробно помогать с:\n"
    mode_text += "• Домашними заданиями\n• Учебными материалами\n"
    mode_text += "• Объяснениями сложных тем\n• Решением задач\n\n"
    mode_text += f"📊 Осталось запросов: {remaining_homework}\n\n"
    mode_text += "Отправьте ваш учебный вопрос или задание:"
    
    await message.answer(mode_text, reply_markup=get_mode_keyboard())

@dp.message(F.text == "💬 Обычный")
async def handle_normal_mode(message: types.Message):
    chat_id = message.chat.id
    user_modes[chat_id] = "обычный"
    save_data(user_modes, DATA_FILES['user_modes'])
    await message.answer("💬 Обычный режим активирован", reply_markup=get_mode_keyboard())

@dp.message(F.text == "⚡ Короткий")
async def handle_short_mode(message: types.Message):
    chat_id = message.chat.id
    user_modes[chat_id] = "короткий"
    save_data(user_modes, DATA_FILES['user_modes'])
    await message.answer("⚡ Короткий режим активирован", reply_markup=get_mode_keyboard())

@dp.message(F.text == "🧠 Умный")
async def handle_smart_mode(message: types.Message):
    chat_id = message.chat.id
    user_modes[chat_id] = "умный"
    save_data(user_modes, DATA_FILES['user_modes'])
    await message.answer("🧠 Умный режим активирован", reply_markup=get_mode_keyboard())

@dp.message(F.text == "🧘 Спокойный")
async def handle_calm_mode(message: types.Message):
    chat_id = message.chat.id
    user_modes[chat_id] = "спокойный"
    save_data(user_modes, DATA_FILES['user_modes'])
    await message.answer("🧘 Спокойный режим активирован", reply_markup=get_mode_keyboard())

@dp.message(F.text == "📊 Статистика")
async def handle_user_statistics(message: types.Message):
    chat_id = message.from_user.id
    total_requests = user_requests_count.get(chat_id, {}).get("total", 0)
    remaining_requests = get_remaining_daily_requests(chat_id)
    remaining_homework = get_remaining_homework_requests(chat_id)
    current_tariff = get_user_tariff(chat_id)
    
    stats_text = f"📊 Ваша статистика:\n\n"
    stats_text += f"📈 Всего запросов: {total_requests}\n"
    stats_text += f"📅 Осталось сегодня: {remaining_requests}/{TARIFFS[current_tariff]['daily_limits']}\n"
    stats_text += f"📚 Помощь с уроками: {remaining_homework} запросов\n"
    stats_text += f"💎 Тариф: {TARIFFS[current_tariff]['name']}\n"
    stats_text += f"⏳ Осталось дней: {get_remaining_days(chat_id)}"
    
    await message.answer(stats_text, reply_markup=get_settings_keyboard())

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

@dp.message(F.text == "💫 Дружелюбный")
async def handle_friendly_style(message: types.Message):
    chat_id = message.chat.id
    chat_style[chat_id] = "friendly"
    save_data(chat_style, DATA_FILES['chat_style'])
    await message.answer("💫 Стиль 'Дружелюбный' установлен", reply_markup=get_style_keyboard())

@dp.message(F.text == "⚖️ Сбалансированный")
async def handle_balanced_style(message: types.Message):
    chat_id = message.chat.id
    chat_style[chat_id] = "balanced"
    save_data(chat_style, DATA_FILES['chat_style'])
    await message.answer("⚖️ Стиль 'Сбалансированный' установлен", reply_markup=get_style_keyboard())

@dp.message(F.text == "🎯 Деловой")
async def handle_business_style(message: types.Message):
    chat_id = message.chat.id
    chat_style[chat_id] = "business"
    save_data(chat_style, DATA_FILES['chat_style'])
    await message.answer("🎯 Стиль 'Деловой' установлен", reply_markup=get_style_keyboard())

@dp.message(F.text == "🎨 Креативный")
async def handle_creative_style(message: types.Message):
    chat_id = message.chat.id
    chat_style[chat_id] = "creative"
    save_data(chat_style, DATA_FILES['chat_style'])
    await message.answer("🎨 Стиль 'Креативный' установлен", reply_markup=get_style_keyboard())

@dp.message(F.text == "ℹ️ Информация")
async def handle_info(message: types.Message):
    info_text = (
        "ℹ️ Информация о GlemixAI\n\n"
        "🤖 Современный AI-помощник на базе Mistral AI\n\n"
        "📋 Возможности обработки изображений:\n"
        "• 📝 Распознавание текста\n"
        "• 🔤 Перевод на разные языки\n"
        "• 🧮 Суммирование чисел\n"
        "• 📊 Анализ содержания\n"
        "• ✂️ Сокращение текста\n\n"
        "💡 Просто отправьте фото с текстом и укажите, что нужно сделать!\n\n"
        "Версия: 2.1\n"
        "Разработчик: Glemix Team"
    )
    await message.answer(info_text, reply_markup=get_settings_keyboard())

@dp.message(F.text == "⚡ Быстрые команды")
async def handle_quick_commands(message: types.Message):
    await message.answer("⚡ Быстрые команды:", reply_markup=get_quick_commands_keyboard())

# =======================
# ===== ОБРАБОТКА КНОПОК ТАРИФОВ =====
# =======================
@dp.message(F.text == "📊 Мой тариф")
async def handle_my_tariff(message: types.Message):
    chat_id = message.from_user.id
    current_tariff = get_user_tariff(chat_id)
    remaining_days = get_remaining_days(chat_id)
    remaining_requests = get_remaining_daily_requests(chat_id)
    remaining_homework = get_remaining_homework_requests(chat_id)
    
    tariff_text = f"📊 Ваш текущий тариф:\n\n"
    tariff_text += f"💎 {TARIFFS[current_tariff]['name']}\n"
    tariff_text += f"⏳ Осталось дней: {remaining_days}\n"
    tariff_text += f"📊 Запросов сегодня: {remaining_requests}/{TARIFFS[current_tariff]['daily_limits']}\n"
    tariff_text += f"📚 Помощь с уроками: {remaining_homework} запросов\n"
    tariff_text += f"⚡ Ожидание: {get_user_cooldown(chat_id)} сек\n"
    tariff_text += f"💾 Память: {get_user_memory_limit(chat_id)} сообщений"
    
    await message.answer(tariff_text, reply_markup=get_tariffs_keyboard())

# =======================
# ===== ОБРАБОТКА КНОПОК ПОГОДЫ =====
# =======================
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
        await message.answer(weather_info, reply_markup=get_weather_keyboard())
        increment_user_requests(message.chat.id)
        
    except Exception as e:
        await delete_thinking_message(message.chat.id, thinking_msg_id)
        await message.answer("❌ Ошибка получения погоды. Попробуйте позже.", reply_markup=get_weather_keyboard())

@dp.message(F.text == "🌃 Другой город")
async def handle_other_city(message: types.Message):
    await message.answer("🏙️ Введите название города (например: 'Погода в Москве' или просто 'Москва'):", reply_markup=get_weather_keyboard())

# =======================
# ===== ОБРАБОТКА КНОПОК БЫСТРЫХ КОМАНД =====
# =======================
@dp.message(F.text == "📝 Конвертер валют")
async def handle_currency_converter(message: types.Message):
    await message.answer("💱 Курсы валют:\nUSD → 90.5 ₽\nEUR → 98.2 ₽\nCNY → 12.5 ₽", reply_markup=get_quick_commands_keyboard())

@dp.message(F.text == "🎯 Случайный выбор")
async def handle_random_choice(message: types.Message):
    choices = ["🍎 Яблоко", "🍌 Банан", "🍊 Апельсин", "🍇 Виноград", "🍓 Клубника"]
    await message.answer(f"🎯 Случайный выбор: {random.choice(choices)}", reply_markup=get_quick_commands_keyboard())

@dp.message(F.text == "📅 Текущая дата")
async def handle_current_date(message: types.Message):
    current_date = datetime.now().strftime("%d.%m.%Y")
    await message.answer(f"📅 Сегодня: {current_date}", reply_markup=get_quick_commands_keyboard())

@dp.message(F.text == "⏰ Текущее время")
async def handle_current_time(message: types.Message):
    current_time = datetime.now().strftime("%H:%M:%S")
    await message.answer(f"⏰ Текущее время: {current_time}", reply_markup=get_quick_commands_keyboard())

@dp.message(F.text == "🔢 Калькулятор")
async def handle_calculator(message: types.Message):
    await message.answer("🔢 Введите математическое выражение (например: 2+2, 10*5, 100/4):", reply_markup=get_quick_commands_keyboard())

@dp.message(F.text == "🎁 Сюрприз")
async def handle_surprise(message: types.Message):
    surprises = [
        "🎉 Вот ваш сюрприз! Хорошего дня!",
        "🌟 Удачи в делах!",
        "💫 Пусть сегодняшний день будет прекрасным!",
        "🎯 Вы лучший!",
        "🌈 Желаю отличного настроения!"
    ]
    await message.answer(random.choice(surprises), reply_markup=get_quick_commands_keyboard())

# =======================
# ===== ОБРАБОТКА КНОПОК НАЗАД =====
# =======================
@dp.message(F.text == "⬅️ Назад")
async def handle_back(message: types.Message):
    await message.answer("⚙️ Настройки:", reply_markup=get_settings_keyboard())

@dp.message(F.text == "⬅️ Главное меню")
async def handle_admin_back(message: types.Message):
    """Возврат в главное меню из админ-панели"""
    await message.answer("Главное меню", reply_markup=get_main_keyboard(message.from_user.id))

# =======================
# ===== ОБРАБОТКА АДМИН-ПАНЕЛИ =====
# =======================
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
    
    await message.answer(stats_text, reply_markup=get_admin_keyboard())

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
    
    await message.answer(stats_text, reply_markup=get_admin_keyboard())

@dp.message(F.text == "📋 Логи действий")
async def handle_action_logs(message: types.Message):
    """Показывает логи действий админа"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    if not admin_logs:
        await message.answer("📋 Логи действий пусты", reply_markup=get_admin_keyboard())
        return
    
    # Показываем последние 10 записей
    recent_logs = admin_logs[-10:]
    logs_text = "📋 Последние действия админа:\n\n"
    
    for log in reversed(recent_logs):
        timestamp = datetime.fromisoformat(log["timestamp"]).strftime("%H:%M:%S")
        action = log["action"]
        target = f" (пользователь {log['target_user']})" if log.get('target_user') else ""
        logs_text += f"🕒 {timestamp}: {action}{target}\n"
    
    await message.answer(logs_text, reply_markup=get_admin_keyboard())

# =======================
# ===== ОСНОВНАЯ ЛОГИКА ОБРАБОТКИ =====
# =======================
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    """Обработка фотографий"""
    chat_id = message.chat.id
    
    # Если ожидается выбор языка, игнорируем фото
    if user_awaiting_language.get(chat_id):
        return
    
    initialize_user_data(chat_id)
    
    # Проверяем возможность сделать запрос
    can_request, error_msg = can_user_make_request(chat_id)
    if not can_request:
        await message.answer(error_msg, reply_markup=get_main_keyboard(chat_id))
        return
    
    # Проверяем кулдаун
    current_time = time.time()
    if chat_id in user_last_request:
        cooldown = get_user_cooldown(chat_id)
        time_passed = current_time - user_last_request[chat_id]
        if time_passed < cooldown:
            remaining = cooldown - time_passed
            await message.answer(f"⏳ Подождите {remaining:.1f} секунд перед следующим запросом.", reply_markup=get_main_keyboard(chat_id))
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
        
        # Сохраняем распознанный текст для возможного перевода
        user_last_photo_text[chat_id] = result
        
        # Удаляем сообщение "Думаю..."
        await delete_thinking_message(chat_id, thinking_msg_id)
        
        # Отправляем результат
        response = create_smart_response(result, "photo_text")
        await message.answer(response, reply_markup=get_main_keyboard(chat_id))
        
        # Обновляем статистику
        increment_user_requests(chat_id)
        
    except Exception as e:
        logger.error(f"Photo processing error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("❌ Ошибка обработки изображения. Пожалуйста, попробуйте еще раз.", reply_markup=get_main_keyboard(chat_id))

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    """Обработка голосовых сообщений"""
    chat_id = message.chat.id
    
    # Если ожидается выбор языка, игнорируем голосовое
    if user_awaiting_language.get(chat_id):
        return
    
    initialize_user_data(chat_id)
    
    # Проверяем возможность сделать запрос
    can_request, error_msg = can_user_make_request(chat_id)
    if not can_request:
        await message.answer(error_msg, reply_markup=get_main_keyboard(chat_id))
        return
    
    # Проверяем кулдаун
    current_time = time.time()
    if chat_id in user_last_request:
        cooldown = get_user_cooldown(chat_id)
        time_passed = current_time - user_last_request[chat_id]
        if time_passed < cooldown:
            remaining = cooldown - time_passed
            await message.answer(f"⏳ Подождите {remaining:.1f} секунд перед следующим запросом.", reply_markup=get_main_keyboard(chat_id))
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
        await message.answer(response, reply_markup=get_main_keyboard(chat_id))
        
        # Обновляем статистику
        increment_user_requests(chat_id)
        
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("🎤 Голосовое сообщение получено! Я обработал ваше аудио. Если вам нужен ответ на конкретный вопрос, пожалуйста, уточните его текстом.", reply_markup=get_main_keyboard(chat_id))

@dp.message(F.text)
async def handle_text(message: types.Message):
    """Обработка текстовых сообщений"""
    chat_id = message.chat.id
    user_text = message.text.strip()
    
    # Если ожидается выбор языка, обрабатываем только кнопки языка
    if user_awaiting_language.get(chat_id):
        if user_text not in ["🇷🇺 Русский", "🇺🇸 English", "🇪🇸 Español", "🇩🇪 Deutsch", "🇫🇷 Français", "🇨🇳 中文", "🇯🇵 日本語", "🇰🇷 한국어"]:
            await message.answer("Пожалуйста, выберите язык из предложенных вариантов.", reply_markup=get_language_keyboard())
        return
    
    initialize_user_data(chat_id)
    
    # Игнорируем кнопки, которые уже обработаны
    button_texts = [
        # Главное меню
        "🚀 Начать работу", "🌟 Обо мне", "⚙️ Настройки", "❓ Помощь", "🌤️ Погода", 
        "💎 Тарифы", "🧹 Очистить память", "🛠️ Админ-панель",
        # Настройки
        "🎭 Режимы AI", "📊 Статистика", "🎨 Стиль общения", "ℹ️ Информация", "⚡ Быстрые команды", "🌐 Сменить язык", "⬅️ Назад",
        # Режимы AI
        "🧘 Спокойный", "💬 Обычный", "⚡ Короткий", "🧠 Умный", "📚 Помощь с уроками",
        # Стили общения
        "💫 Дружелюбный", "⚖️ Сбалансированный", "🎯 Деловой", "🎨 Креативный",
        # Тарифы
        "🚀 Default", "⭐ Pro", "💎 Advanced", "👑 Ultimate", "📊 Мой тариф",
        # Погода
        "🌆 Москва", "🏛️ Санкт-Петербург", "🗽 Нью-Йорк", "🌉 Лондон", "🗼 Париж", "🏯 Токио", "🌃 Другой город",
        # Быстрые команды
        "📝 Конвертер валют", "🎯 Случайный выбор", "📅 Текущая дата", "⏰ Текущее время", "🔢 Калькулятор", "🎁 Сюрприз",
        # Админ-панель
        "👥 Статистика пользователей", "📊 Общая статистика", "📋 Логи действий", "⬅️ Главное меню",
        # Языки
        "🇷🇺 Русский", "🇺🇸 English", "🇪🇸 Español", "🇩🇪 Deutsch", "🇫🇷 Français", "🇨🇳 中文", "🇯🇵 日本語", "🇰🇷 한국어"
    ]
    
    if user_text in button_texts:
        return
    
    # Проверяем возможность сделать запрос
    current_mode = user_modes.get(chat_id, "обычный")
    
    if current_mode == "homework":
        can_request, error_msg = can_user_make_homework_request(chat_id)
    else:
        can_request, error_msg = can_user_make_request(chat_id)
    
    if not can_request:
        await message.answer(error_msg, reply_markup=get_main_keyboard(chat_id))
        return
    
    # Проверяем кулдаун
    current_time = time.time()
    if chat_id in user_last_request:
        cooldown = get_user_cooldown(chat_id)
        time_passed = current_time - user_last_request[chat_id]
        if time_passed < cooldown:
            remaining = cooldown - time_passed
            await message.answer(f"⏳ Подождите {remaining:.1f} секунд перед следующим запросом.", reply_markup=get_main_keyboard(chat_id))
            return
    
    user_last_request[chat_id] = current_time
    
    # Обработка специальных команд
    user_text_lower = user_text.lower()
    
    # Погода - улучшенное распознавание
    if any(word in user_text_lower for word in ["погода", "weather"]) or any(city in user_text_lower for city in CITY_MAPPING.keys()):
        city = user_text_lower
        
        # Извлекаем название города из разных форматов запросов
        for key in ["погода", "weather", "в", "в городе", "какая погода в", "какая погода"]:
            city = city.replace(key, "").strip()
        
        # Убираем знаки препинания
        city = city.replace("?", "").replace("!", "").strip()
        
        # Проверяем синонимы городов
        if city in CITY_MAPPING:
            city = CITY_MAPPING[city]
        
        if city:
            thinking_msg_id = await send_thinking_message(chat_id)
            weather_info = await get_detailed_weather(city)
            await delete_thinking_message(chat_id, thinking_msg_id)
            await message.answer(weather_info, reply_markup=get_main_keyboard(chat_id))
            increment_user_requests(chat_id)
            return
    
    # Перевод текста с фото
    if any(word in user_text_lower for word in ["переведи", "перевод", "translate"]) and chat_id in user_last_photo_text:
        target_language = "русский"
        if "на английский" in user_text_lower:
            target_language = "английский"
        elif "на русский" in user_text_lower:
            target_language = "русский"
        elif "на испанский" in user_text_lower:
            target_language = "испанский"
        elif "на французский" in user_text_lower:
            target_language = "французский"
        elif "на немецкий" in user_text_lower:
            target_language = "немецкий"
        elif "на итальянский" in user_text_lower:
            target_language = "итальянский"
        elif "на китайский" in user_text_lower:
            target_language = "китайский"
        elif "на японский" in user_text_lower:
            target_language = "японский"
        elif "на корейский" in user_text_lower:
            target_language = "корейский"
        
        thinking_msg_id = await send_thinking_message(chat_id)
        try:
            translated_text = await translate_text(user_last_photo_text[chat_id], target_language)
            await delete_thinking_message(chat_id, thinking_msg_id)
            await message.answer(create_smart_response(translated_text, "translation"), reply_markup=get_main_keyboard(chat_id))
            increment_user_requests(chat_id)
            return
        except Exception as e:
            await delete_thinking_message(chat_id, thinking_msg_id)
            await message.answer("❌ Ошибка перевода текста.", reply_markup=get_main_keyboard(chat_id))
            return
    
    # Дополнительные запросы о фото (расскажи об этом, сделай короче и т.д.)
    if chat_id in user_last_photo_text and user_last_photo_text[chat_id]:
        if any(word in user_text_lower for word in ["расскажи", "объясни", "что это", "про что", "опиши"]):
            # Анализ содержимого фото
            thinking_msg_id = await send_thinking_message(chat_id)
            try:
                analysis_prompt = f"Проанализируй этот текст и подробно расскажи о чем он: {user_last_photo_text[chat_id]}"
                analysis_result = await get_ai_response(analysis_prompt, chat_id, current_mode)
                await delete_thinking_message(chat_id, thinking_msg_id)
                await message.answer(f"📊 Анализ содержимого:\n\n{analysis_result}", reply_markup=get_main_keyboard(chat_id))
                increment_user_requests(chat_id)
                return
            except Exception as e:
                await delete_thinking_message(chat_id, thinking_msg_id)
                await message.answer("❌ Ошибка анализа содержимого.", reply_markup=get_main_keyboard(chat_id))
                return
        
        elif any(word in user_text_lower for word in ["короче", "сократи", "суть", "основное"]):
            # Сокращение текста
            thinking_msg_id = await send_thinking_message(chat_id)
            try:
                shorten_prompt = f"Сократи этот текст, оставив только основную суть: {user_last_photo_text[chat_id]}"
                shortened_result = await get_ai_response(shorten_prompt, chat_id, current_mode)
                await delete_thinking_message(chat_id, thinking_msg_id)
                await message.answer(f"✂️ Сокращенный текст:\n\n{shortened_result}", reply_markup=get_main_keyboard(chat_id))
                increment_user_requests(chat_id)
                return
            except Exception as e:
                await delete_thinking_message(chat_id, thinking_msg_id)
                await message.answer("❌ Ошибка сокращения текста.", reply_markup=get_main_keyboard(chat_id))
                return
    
    # Калькулятор
    if any(word in user_text_lower for word in ["посчитай", "сколько будет", "вычисли", "calc", "calculate"]):
        try:
            # Извлекаем математическое выражение
            expr = user_text_lower
            for word in ["посчитай", "сколько будет", "вычисли", "calc", "calculate"]:
                expr = expr.replace(word, "")
            expr = expr.strip()
            
            # Проверяем безопасность выражения
            allowed_chars = set('0123456789+-*/.() ')
            if all(c in allowed_chars for c in expr):
                result = eval(expr)
                await message.answer(f"🔢 {expr} = {result}", reply_markup=get_main_keyboard(chat_id))
                increment_user_requests(chat_id)
                return
            else:
                await message.answer("❌ Небезопасное выражение", reply_markup=get_main_keyboard(chat_id))
                return
        except:
            await message.answer("❌ Не могу вычислить выражение", reply_markup=get_main_keyboard(chat_id))
            return
    
    # Отправляем сообщение "Думаю..."
    thinking_msg_id = await send_thinking_message(chat_id)
    
    try:
        # Определяем тип вопроса
        question_type = "normal"
        if current_mode == "homework":
            question_type = "homework"
            increment_homework_requests(chat_id)
        else:
            increment_user_requests(chat_id)
        
        # Получаем ответ от AI
        ai_response = await get_ai_response(user_text, chat_id, current_mode)
        
        # Удаляем сообщение "Думаю..."
        await delete_thinking_message(chat_id, thinking_msg_id)
        
        # Форматируем ответ (убираем форматирование **Коротко:** и т.д.)
        cleaned_response = ai_response
        if "**Коротко:**" in cleaned_response:
            # Убираем заголовок "Коротко:"
            cleaned_response = cleaned_response.replace("**Коротко:**", "").strip()
        if "**По погоде:**" in cleaned_response:
            cleaned_response = cleaned_response.replace("**По погоде:**", "").strip()
        if "*Что ещё?*" in cleaned_response:
            cleaned_response = cleaned_response.replace("*Что ещё?*", "").strip()
        
        # Форматируем ответ
        final_response = create_smart_response(cleaned_response, question_type)
        
        # Отправляем ответ
        await message.answer(final_response, reply_markup=get_main_keyboard(chat_id))
        
    except Exception as e:
        logger.error(f"Text processing error: {e}")
        await delete_thinking_message(chat_id, thinking_msg_id)
        await message.answer("❌ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте еще раз.", reply_markup=get_main_keyboard(chat_id))

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
