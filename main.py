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
    'user_subscription_end': 'user_subscription_end.pkl',
    'user_response_preferences': 'user_response_preferences.pkl'
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
        (DATA_FILES['user_subscription_end'], user_subscription_end),
        (DATA_FILES['user_response_preferences'], user_response_preferences)
    ]:
        save_data(data_key, filename)

def load_all_data():
    """Загружает все данные"""
    global user_registration_date, conversation_memory, chat_style, user_requests_count
    global user_modes, user_tariffs, user_subscription_end, user_response_preferences
    
    user_registration_date = load_data(DATA_FILES['user_registration_date'], {})
    conversation_memory = load_data(DATA_FILES['conversation_memory'], {})
    chat_style = load_data(DATA_FILES['chat_style'], {})
    user_requests_count = load_data(DATA_FILES['user_requests_count'], {})
    user_modes = load_data(DATA_FILES['user_modes'], {})
    user_tariffs = load_data(DATA_FILES['user_tariffs'], {})
    user_subscription_end = load_data(DATA_FILES['user_subscription_end'], {})
    user_response_preferences = load_data(DATA_FILES['user_response_preferences'], {})

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
# ===== УМНАЯ СИСТЕМА ОТВЕТОВ =====
# =======================
def should_use_detailed_response(user_text: str, ai_response: str) -> bool:
    """Определяет, нужен ли детальный развернутый ответ"""
    user_lower = user_text.lower()
    
    # Если пользователь явно просит развернутый ответ
    detailed_keywords = [
        'подробно', 'подробный', 'развернуто', 'развернутый', 'подробнее', 
        'расскажи подробно', 'объясни подробно', 'опиши подробно', 'детально',
        'полный ответ', 'разверни', 'расширь', 'углубленно', 'тщательно'
    ]
    
    if any(phrase in user_lower for phrase in detailed_keywords):
        return True
    
    # Если пользователь задает сложный вопрос с несколькими аспектами
    complex_indicators = [
        'как сделать', 'как работает', 'объясни', 'расскажи о', 'что такое',
        'в чем разница', 'сравни', 'перечисли', 'опиши процесс', 'каковы',
        'какие есть', 'расскажи про', 'объясни принцип'
    ]
    
    if any(indicator in user_lower for indicator in complex_indicators):
        return True
    
    # Если в ответе есть сложная структура (списки, перечисления)
    if any(marker in ai_response for marker in ['\n•', '\n-', '\n1.', '\n2.', '\n3.', 'Во-первых', 'Во-вторых', 'В-третьих']):
        return True
    
    # Если пользователь задает несколько вопросов в одном сообщении
    if user_lower.count('?') >= 2:
        return True
    
    # Если вопрос требует объяснения или инструкции
    if any(word in user_lower for word in ['инструкция', 'руководство', 'как настроить', 'как использовать']):
        return True
    
    return False

def should_use_concise_response(user_text: str) -> bool:
    """Определяет, когда нужен краткий ответ"""
    user_lower = user_text.lower()
    
    # Простые вопросы и команды
    concise_indicators = [
        'привет', 'как дела', 'что нового', 'спасибо', 'пока',
        'сколько времени', 'какая дата', 'погода', 'курс валют',
        'посчитай', 'выбери', 'случайный', 'сюрприз'
    ]
    
    if any(indicator in user_lower for indicator in concise_indicators):
        return True
    
    # Короткие фактологические вопросы
    if len(user_text) < 30 and user_text.endswith('?'):
        return True
    
    # Простые запросы на информацию
    simple_questions = [
        'кто такой', 'что это', 'где находится', 'когда', 'сколько стоит'
    ]
    
    if any(question in user_lower for question in simple_questions):
        return True
    
    return False

def get_response_style_preference(chat_id: int) -> str:
    """Возвращает предпочтения пользователя по стилю ответов"""
    return user_response_preferences.get(chat_id, "auto")  # auto, concise, detailed

def set_response_style_preference(chat_id: int, style: str):
    """Устанавливает предпочтения пользователя по стилю ответов"""
    user_response_preferences[chat_id] = style
    save_data(user_response_preferences, DATA_FILES['user_response_preferences'])

def process_ai_response(text: str, user_text: str, chat_id: int) -> str:
    """Умная обработка ответа AI в зависимости от контекста и предпочтений"""
    
    # Получаем предпочтения пользователя
    user_preference = get_response_style_preference(chat_id)
    
    # Если пользователь явно выбрал стиль
    if user_preference == "concise":
        return make_response_concise(text, user_text)
    elif user_preference == "detailed":
        return text  # Возвращаем полный ответ
    
    # Автоматическое определение (по умолчанию)
    
    # Если нужен детальный ответ
    if should_use_detailed_response(user_text, text):
        return text  # Полный ответ без сокращений
    
    # Если нужен краткий ответ
    if should_use_concise_response(user_text):
        return make_response_concise(text, user_text)
    
    # По умолчанию - сбалансированный ответ
    return make_response_balanced(text, user_text)

def make_response_concise(text: str, user_text: str) -> str:
    """Создает краткий лаконичный ответ"""
    # Убираем лишние вступления
    lines = text.split('\n')
    clean_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Пропускаем общие фразы
        skip_phrases = [
            'конечно', 'разумеется', 'безусловно', 'определенно',
            'я с удовольствием', 'позвольте мне', 'хорошо, давайте'
        ]
        
        if any(phrase in line.lower() for phrase in skip_phrases) and len(lines) > 1:
            continue
            
        clean_lines.append(line)
    
    # Берем первые 2-3 предложения для краткого ответа
    if clean_lines:
        first_line = clean_lines[0]
        sentences = first_line.split('. ')
        
        if len(sentences) > 2:
            concise_sentences = sentences[:2]
            # Убедимся, что ответ не слишком короткий
            if len('. '.join(concise_sentences)) > 50:
                result = '. '.join(concise_sentences) + '.'
            else:
                # Если слишком коротко, добавим еще одно предложение
                result = '. '.join(sentences[:3]) + '.'
        else:
            result = first_line
        
        # Добавляем вторую строку если она содержит важную информацию
        if len(clean_lines) > 1 and len(result) < 150:
            second_line = clean_lines[1]
            if len(second_line) > 20:  # Не добавляем очень короткие строки
                result += '\n\n' + second_line
        
        # Ограничиваем общую длину
        if len(result) > 400:
            result = result[:400] + '...'
            
        return result
    
    return text

def make_response_balanced(text: str, user_text: str) -> str:
    """Создает сбалансированный ответ - не слишком короткий, не слишком длинный"""
    # Для сбалансированного ответа оставляем больше контента
    lines = text.split('\n')
    if len(lines) <= 3:
        return text  # Если ответ и так короткий
    
    # Берем первые 3-4 строки или до 600 символов
    balanced_lines = []
    total_length = 0
    
    for line in lines:
        if total_length + len(line) < 600 and len(balanced_lines) < 4:
            balanced_lines.append(line)
            total_length += len(line)
        else:
            break
    
    result = '\n'.join(balanced_lines)
    
    # Если обрезали, добавляем индикатор
    if len(result) < len(text):
        result += '\n\n...'
    
    return result

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
        KeyboardButton(text="📝 Стиль ответов")
    ], [
        KeyboardButton(text="⚡ Быстрые команды"),
        KeyboardButton(text="🔔 Уведомления")
    ], [KeyboardButton(text="⬅️ Назад")]],
                               resize_keyboard=True)

def get_response_style_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="🤖 Автоматический"),
        KeyboardButton(text="📝 Краткий")
    ], [
        KeyboardButton(text="📚 Подробный"),
        KeyboardButton(text="⚖️ Сбалансированный")
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

# ... остальные клавиатуры остаются без изменений ...

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
        "memory_size": total_messages * 100
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
        return 9999
    
    if not is_subscription_active(chat_id):
        return 0
        
    return 9999

# =======================
# ===== ПРОВЕРКА ВРЕМЕНИ ОЖИДАНИЯ =====
# =======================
def check_cooldown(chat_id: int) -> str:
    """Проверяет время ожидания между запросами"""
    if chat_id == ADMIN_ID:
        return None
        
    current_time = time.time()
    last_request = user_last_request.get(chat_id, 0)
    
    cooldown = get_user_cooldown(chat_id)
    
    if current_time - last_request < cooldown:
        remaining = cooldown - int(current_time - last_request)
        return f"⏳ Пожалуйста, подожди {remaining} секунд перед следующим запросом"
    
    user_last_request[chat_id] = current_time
    return None

def format_ai_response(text: str, style: str, user_text: str, chat_id: int) -> str:
    """Форматирует ответ AI с учетом стиля и предпочтений"""
    emoji = get_emoji(style)
    processed_text = process_ai_response(text, user_text, chat_id)
    return f"{emoji} {processed_text}"

async def send_long_message(message: types.Message, text: str, style: str = "balanced", user_text: str = "", chat_id: int = 0, chunk_size: int = 4000):
    """Отправляет длинное сообщение с умным форматированием"""
    formatted = format_ai_response(text, style, user_text, chat_id)
    for i in range(0, len(formatted), chunk_size):
        try:
            await message.answer(formatted[i:i + chunk_size])
        except TelegramBadRequest:
            await message.answer(text[i:i + chunk_size])

# =======================
# ===== ПОГОДА И БЫСТРЫЕ КОМАНДЫ =====
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

# ... быстрые команды остаются без изменений ...

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
        "💡 *Совет:* Напиши 'подробнее' в любом ответе, чтобы получить развернутое объяснение!\n\n"
        "Выбери направление для нашего диалога 👇")

    await message.answer(welcome_text,
                         reply_markup=get_main_keyboard(chat_id))

@dp.message(F.text == "📝 Стиль ответов")
async def handle_response_style(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    chat_id = message.chat.id
    current_style = get_response_style_preference(chat_id)
    
    style_descriptions = {
        "auto": "🤖 Автоматический - я сам выберу оптимальный формат ответа",
        "concise": "📝 Краткий - короткие и лаконичные ответы", 
        "detailed": "📚 Подробный - развернутые объяснения",
        "balanced": "⚖️ Сбалансированный - золотая середина"
    }
    
    style_text = (
        f"📝 Настройка стиля ответов\n\n"
        f"Текущий стиль: {style_descriptions.get(current_style, 'Автоматический')}\n\n"
        f"Выбери предпочтительный стиль моих ответов:\n\n"
        f"• 🤖 Автоматический - умное определение формата\n"
        f"• 📝 Краткий - идеально для быстрых вопросов\n" 
        f"• 📚 Подробный - для сложных тем и объяснений\n"
        f"• ⚖️ Сбалансированный - оптимальное сочетание")
    
    await message.answer(style_text,
                         reply_markup=get_response_style_keyboard())

@dp.message(F.text.in_(["🤖 Автоматический", "📝 Краткий", "📚 Подробный", "⚖️ Сбалансированный"]))
async def handle_response_style_selection(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    chat_id = message.chat.id
    text = str(message.text or "")

    style_mapping = {
        "🤖 Автоматический": "auto",
        "📝 Краткий": "concise", 
        "📚 Подробный": "detailed",
        "⚖️ Сбалансированный": "balanced"
    }

    new_style = style_mapping.get(text, "auto")
    set_response_style_preference(chat_id, new_style)

    success_text = (
        f"✅ Стиль ответов изменен\n\n"
        f"Теперь я буду отвечать в {text.lower()} стиле\n\n"
        f"💡 Это влияет на длину и детализацию моих ответов")
    
    await message.answer(success_text,
                         reply_markup=get_settings_keyboard())

# ... остальные обработчики остаются аналогичными, но с использованием новой системы ответов ...

@dp.message()
async def main_handler(message: types.Message):
    # Пропускаем голосовые и фото сообщения
    if message.voice or message.photo:
        return
        
    chat_id = message.chat.id
    user_text = (message.text or "").strip()
    style = chat_style.get(chat_id, "balanced")

    if not user_text:
        return

    if user_text.startswith("/"):
        return

    # Проверка времени ожидания
    cooldown_msg = check_cooldown(chat_id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    # Проверка подписки
    if not is_subscription_active(chat_id) and chat_id != ADMIN_ID:
        await message.answer(
            f"⏳ Период использования завершен\n\n"
            f"Для продолжения использования необходим доступ\n\n"
            f"Обратитесь к администратору для получения доступа")
        return

    # Увеличиваем счетчик запросов
    if chat_id not in user_requests_count:
        user_requests_count[chat_id] = {}
    user_requests_count[chat_id]["обычный"] = user_requests_count[chat_id].get("обычный", 0) + 1
    save_data(user_requests_count, DATA_FILES['user_requests_count'])

    # Обработка быстрых команд
    user_text_lower = user_text.lower().strip()
    
    if "выбери" in user_text_lower and any(sep in user_text for sep in [",", "или"]):
        choice_text = user_text_lower.replace("выбери", "").strip()
        result = get_random_choice(choice_text)
        await message.answer(result)
        return

    if any(word in user_text_lower for word in ["посчитай", "сколько будет", "="]):
        expr = user_text_lower.replace("посчитай", "").replace("сколько будет", "").replace("=", "").strip()
        result = calculate_expression(expr)
        await message.answer(result)
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
            "спокойный": """Ты спокойный и расслабленный AI-помощник. Отвечай мягко и дружелюбно.
Используй профессиональный язык, не употребляй сленг и мемные выражения. 
Понимай современный сленг, когда его используют пользователи, но сам не используй его в ответах.""",
            
            "обычный": """Ты умный и креативный AI-помощник. Отвечай информативно.
Используй грамотный русский язык, избегай сленга и мемов. 
Ты понимаешь современные выражения, когда их используют пользователи, но в своих ответах придерживайся литературного языка.""",
            
            "короткий": """Ты мастер кратких ответов. Отвечай максимально лаконично, сохраняя суть.
Говори по делу, без сленга и мемных выражений. 
Понимай современный язык пользователей, но отвечай профессионально.""",
            
            "умный": """Ты эксперт AI-помощник. Дай развернутый ответ, но будь конкретен.
Используй академический стиль, избегай сленга и неформальных выражений.
Хотя ты понимаешь современный язык, в ответах используй только литературный русский язык."""
        }

        base_prompt = system_prompts.get("обычный", "Ты умный и креативный AI-помощник. Отвечай информативно. Избегай сленга и мемных выражений.")
        
        slang_knowledge = "\n\nВажно: Ты понимаешь современный сленг и мемы, когда их используют пользователи, но сам НЕ используй эти выражения в своих ответах. Отвечай на грамотном литературном русском языке."

        system_prompt = base_prompt + slang_knowledge

        # Добавляем пользовательское сообщение в память
        add_to_conversation_memory(chat_id, "user", user_text)

        # Получаем контекст диалога
        conversation_context = get_conversation_context(chat_id)
        
        # Создаем сообщения для AI
        messages = [{"role": "system", "content": system_prompt}]
        
        # Добавляем историю диалога
        for msg in conversation_context:
            messages.append(msg)

        # Обработка reply-сообщений
        if message.reply_to_message and message.reply_to_message.text:
            replied_text = message.reply_to_message.text
            messages.append({"role": "user", "content": f"Предыдущее сообщение: {replied_text}"})
            messages.append({"role": "user", "content": user_text})
        else:
            messages.append({"role": "user", "content": user_text})

        response = client.chat.complete(model=model, messages=messages)
        ai_text = response.choices[0].message.content

        if not ai_text:
            ai_text = "❌ Не удалось получить ответ"

        # Добавляем ответ AI в память
        add_to_conversation_memory(chat_id, "assistant", ai_text)

        # Используем умную систему ответов
        await send_long_message(message, str(ai_text), style, user_text, chat_id)

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
    print("🚀 Бот запущен и работает 24/7!")
    print(f"💎 Система тарифов: {len(TARIFFS)} уровня")
    print(f"💾 Сохранение данных: активировано")
    print(f"🤖 Умная система ответов: включена")
    print(f"👑 Админ-панель: доступна для ADMIN_ID")
    print(f"📊 Загружено пользователей: {len(user_registration_date)}")
    print(f"💎 Активных тарифов: {len([uid for uid in user_tariffs if is_subscription_active(uid)])}")
    asyncio.run(main())
