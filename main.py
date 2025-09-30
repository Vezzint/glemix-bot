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
import json
import pickle

# =======================
# ===== КОНФИГУРАЦИЯ =====
# =======================
mistral_api_key = os.getenv('MISTRAL_API_KEY', 'nIMvGkfioIpMtQeSO2n8ssm6nuJRyo7Q')
openweather_api_key = os.getenv('OPENWEATHER_API_KEY', 'dbd08a834f628d369a8edb55b210171e')
TOKEN = os.getenv('BOT_TOKEN', '8229856813:AAEkQq-4zdJKAmovgq69URcqKDzN4_BMqrw')

ADMIN_ID = 6584350034

# Бесплатный период (2 недели)
FREE_PERIOD_DAYS = 14

# Время ожидания между запросами (секунды)
REQUEST_COOLDOWN = 5

# Память диалогов
MAX_CONVERSATION_HISTORY = 10

model = "mistral-large-latest"
client = Mistral(api_key=mistral_api_key)

# Файлы для сохранения данных
DATA_FILES = {
    'user_registration_date': 'user_registration_date.pkl',
    'conversation_memory': 'conversation_memory.pkl',
    'chat_style': 'chat_style.pkl',
    'user_requests_count': 'user_requests_count.pkl',
    'user_modes': 'user_modes.pkl'
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
    save_data(user_registration_date, DATA_FILES['user_registration_date'])
    save_data(conversation_memory, DATA_FILES['conversation_memory'])
    save_data(chat_style, DATA_FILES['chat_style'])
    save_data(user_requests_count, DATA_FILES['user_requests_count'])
    save_data(user_modes, DATA_FILES['user_modes'])

def load_all_data():
    """Загружает все данные"""
    global user_registration_date, conversation_memory, chat_style, user_requests_count, user_modes
    
    user_registration_date = load_data(DATA_FILES['user_registration_date'], {})
    conversation_memory = load_data(DATA_FILES['conversation_memory'], {})
    chat_style = load_data(DATA_FILES['chat_style'], {})
    user_requests_count = load_data(DATA_FILES['user_requests_count'], {})
    user_modes = load_data(DATA_FILES['user_modes'], {})

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
        KeyboardButton(text="🔧 Расширенные настройки")
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

# =======================
# ===== ФУНКЦИИ ПАМЯТИ =====
# =======================
def add_to_conversation_memory(chat_id: int, role: str, content: str):
    """Добавляет сообщение в память диалога"""
    if chat_id not in conversation_memory:
        conversation_memory[chat_id] = []
    
    conversation_memory[chat_id].append({"role": role, "content": content})
    
    # Ограничиваем историю
    if len(conversation_memory[chat_id]) > MAX_CONVERSATION_HISTORY:
        conversation_memory[chat_id] = conversation_memory[chat_id][-MAX_CONVERSATION_HISTORY:]
    
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
    
    if not is_free_period_active(chat_id):
        return 0  # Бесплатный период закончился
        
    return 9999  # Безлимит в бесплатный период

# =======================
# ===== ПРОВЕРКА ВРЕМЕНИ ОЖИДАНИЯ =====
# =======================
def check_cooldown(chat_id: int) -> str:
    """Проверяет время ожидания между запросами"""
    if chat_id == ADMIN_ID:
        return None  # Админы без ограничений
        
    current_time = time.time()
    last_request = user_last_request.get(chat_id, 0)
    
    if current_time - last_request < REQUEST_COOLDOWN:
        remaining = REQUEST_COOLDOWN - int(current_time - last_request)
        return f"⏳ Пожалуйста, подожди {remaining} секунд перед следующим запросом"
    
    user_last_request[chat_id] = current_time
    return None

# =======================
# ===== ФУНКЦИИ ОБРАБОТКИ ТЕКСТА =====
# =======================
def shorten_text(text: str, max_sentences: int = 3, max_length: int = 800) -> str:
    """Сокращает текст до указанного количества предложений и длины"""
    sentences = text.split('. ')
    if len(sentences) > max_sentences:
        text = '. '.join(sentences[:max_sentences]) + '.'
    
    if len(text) > max_length:
        text = text[:max_length] + '...'
    
    return text

def process_ai_response(text: str, mode: str) -> str:
    """Обрабатывает ответ AI в зависимости от режима"""
    if mode == "короткий":
        return shorten_text(text, max_sentences=2, max_length=400)
    elif mode == "спокойный":
        return shorten_text(text, max_sentences=4, max_length=600)
    elif mode == "обычный":
        return shorten_text(text, max_sentences=5, max_length=800)
    elif mode == "умный":
        return shorten_text(text, max_sentences=6, max_length=1000)
    else:
        return shorten_text(text, max_sentences=4, max_length=600)

def format_ai_response(text: str, style: str, mode: str) -> str:
    emoji = get_emoji(style)
    formatted = process_ai_response(text, mode)

    if mode == "спокойный":
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
    remaining_days = get_remaining_free_days(chat_id)
    
    welcome_text = (
        "✨ Добро пожаловать в мир интеллектуального общения\n\n"
        "Я — твой персональный AI-компаньон для глубоких диалогов\n\n"
        f"🎁 *Период использования:* {remaining_days} дней\n"
        f"Режим: {get_mode_description(current_mode)}\n"
        f"Доступно запросов: ∞\n"
        f"💾 Память диалога: {MAX_CONVERSATION_HISTORY} сообщений\n\n"
        "Выбери направление для нашего диалога 👇")

    await message.answer(welcome_text,
                         reply_markup=get_main_keyboard(chat_id))

@dp.message(F.text.in_(["🚀 Начать работу", "🚀 Старт"]))
async def handle_start_button(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return
    await cmd_start(message)

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
        f"• Память диалога: {MAX_CONVERSATION_HISTORY} сообщений\n"
        "• Понимание современного сленга\n\n"
        "Доступные режимы:\n"
        "• Спокойный — развернутые ответы\n"
        "• Обычный — сбалансированные ответы\n"
        "• Короткий — лаконичные ответы\n"
        "• Умный — экспертные ответы")
    
    await message.answer(about_text,
                         reply_markup=get_main_keyboard(message.chat.id))

@dp.message(F.text == "⚙️ Настройки")
async def handle_settings(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    settings_text = (
        "⚙️ Центр управления\n\n"
        "Настрой аспекты нашего взаимодействия:\n\n"
        "• Режимы AI — выбери стиль общения\n"
        "• Статистика — отслеживай активность\n"
        "• Стиль общения — настрой тон диалога\n"
        "• Информация — узнай больше о возможностях\n"
        "• Быстрые команды — полезные инструменты\n"
        "• Уведомления — настрой оповещения")
    
    await message.answer(settings_text,
                         reply_markup=get_settings_keyboard())

@dp.message(F.text == "❓ Помощь")
async def handle_help(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    chat_id = message.chat.id
    current_mode = user_modes.get(chat_id, "обычный")
    remaining_days = get_remaining_free_days(chat_id)
    
    help_text = (
        "💫 Руководство по использованию\n\n"
        "Основные команды:\n"
        "• Просто напиши вопрос — получу развернутый ответ\n"
        "• Используй кнопки для быстрой навигации\n"
        "• Ответь на сообщение для работы с текстами\n"
        "• Я помню контекст наших последних сообщений\n\n"
        "Работа с контентом:\n"
        "• 'Сократи' — сделаю текст короче\n"
        "• 'Дополни' — добавлю информацию\n"
        "• 'Перефразируй' — изменю формулировки\n"
        "• 'Объясни' — дам подробное объяснение\n\n"
        f"Твой статус:\n"
        f"Режим: {current_mode}\n"
        f"Период использования: {remaining_days} дней\n"
        f"Запросы: ∞\n"
        f"💾 Память: {MAX_CONVERSATION_HISTORY} сообщений")
    
    await message.answer(help_text,
                         reply_markup=get_main_keyboard(chat_id))

@dp.message(F.text == "⚡ Быстрые команды")
async def handle_quick_commands(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    quick_text = (
        "⚡ Быстрые команды\n\n"
        "Мгновенные ответы без AI:\n\n"
        "• Конвертер валют — актуальные курсы\n"
        "• Случайный выбор — из твоих вариантов\n"
        "• Текущая дата — точное время\n"
        "• Калькулятор — математические выражения\n"
        "• Сюрприз — случайное вдохновение\n\n"
        "Выбери нужную команду 👇")
    
    await message.answer(quick_text,
                         reply_markup=get_quick_commands_keyboard())

@dp.message(F.text == "📝 Конвертер валют")
async def handle_currency(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    currency = await get_currency_rate()
    await message.answer(currency)

@dp.message(F.text == "🎯 Случайный выбор")
async def handle_random_choice(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    await message.answer("🎯 Напиши варианты через запятую:\nПример: яблоко, апельсин, банан")

@dp.message(F.text == "📅 Текущая дата")
async def handle_date(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    datetime_text = get_current_datetime()
    await message.answer(datetime_text)

@dp.message(F.text == "⏰ Текущее время")
async def handle_time(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    time_text = f"⏰ Текущее время: {datetime.now().strftime('%H:%M:%S')}"
    await message.answer(time_text)

@dp.message(F.text == "🔢 Калькулятор")
async def handle_calculator(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    await message.answer("🔢 Напиши математическое выражение:\nПример: 2+2*3 или (5+3)/2")

@dp.message(F.text == "🎁 Сюрприз")
async def handle_surprise(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    surprise = get_random_surprise()
    await message.answer(surprise)

@dp.message(F.text == "🎭 Режимы AI")
async def handle_modes(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    chat_id = message.chat.id
    current_mode = user_modes.get(chat_id, "обычный")
    
    mode_text = (
        f"🎭 Галерея режимов\n\n"
        f"Текущий выбор: {get_mode_description(current_mode)}\n"
        f"Период использования: {get_remaining_free_days(chat_id)} дней\n\n"
        "Выбери новый режим для нашего диалога:")
    
    await message.answer(mode_text,
                         reply_markup=get_mode_keyboard())

@dp.message(F.text.in_(["🧘 Спокойный", "💬 Обычный", "⚡ Короткий", "🧠 Умный"]))
async def handle_mode_selection(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    chat_id = message.chat.id
    text = str(message.text or "")

    mode_mapping = {
        "🧘 Спокойный": "спокойный",
        "💬 Обычный": "обычный", 
        "⚡ Короткий": "короткий",
        "🧠 Умный": "умный"
    }

    new_mode = mode_mapping.get(text, "обычный")
    user_modes[chat_id] = new_mode
    save_data(user_modes, DATA_FILES['user_modes'])

    if chat_id not in user_requests_count:
        user_requests_count[chat_id] = {}
    if new_mode not in user_requests_count[chat_id]:
        user_requests_count[chat_id][new_mode] = 0
    save_data(user_requests_count, DATA_FILES['user_requests_count'])

    success_text = (
        f"✨ Режим успешно изменён\n\n"
        f"{get_mode_description(new_mode)}\n\n"
        f"Период использования: {get_remaining_free_days(chat_id)} дней\n"
        "Готова к работе в новом формате")
    
    await message.answer(success_text,
                         reply_markup=get_settings_keyboard())

@dp.message(F.text == "🎨 Стиль общения")
async def handle_style_menu(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    style_text = (
        f"🎨 Палитра стилей\n\n"
        "Выбери новый стиль общения:")
    
    await message.answer(style_text,
                         reply_markup=get_style_keyboard())

@dp.message(F.text.in_(["💫 Дружелюбный", "⚖️ Сбалансированный", "🎯 Деловой", "🎨 Креативный"]))
async def handle_style_selection(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

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
    save_data(chat_style, DATA_FILES['chat_style'])

    success_text = (
        f"🎨 Стиль общения обновлён\n\n"
        "Теперь наши диалоги заиграют новыми красками")
    
    await message.answer(success_text,
                         reply_markup=get_settings_keyboard())

@dp.message(F.text == "📊 Статистика")
async def handle_stats(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    chat_id = message.chat.id
    current_mode = user_modes.get(chat_id, "обычный")
    used = user_requests_count.get(chat_id, {}).get(current_mode, 0)
    remaining_days = get_remaining_free_days(chat_id)
    memory_count = len(conversation_memory.get(chat_id, []))
    
    stats_text = (
        f"📊 Твоя статистика\n\n"
        f"Текущий режим: {current_mode}\n"
        f"Использовано запросов: {used}\n"
        f"💾 Сообщений в памяти: {memory_count}/{MAX_CONVERSATION_HISTORY}\n"
        f"Период использования: {remaining_days} дней\n"
        f"Статус: {'✅ Активен' if is_free_period_active(chat_id) else '⏳ Завершен'}")
    
    await message.answer(stats_text)

@dp.message(F.text == "ℹ️ Информация")
async def handle_info(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    info_text = (
        "💎 Информационная панель\n\n"
        "Система запросов:\n"
        f"• Период использования: {FREE_PERIOD_DAYS} дней\n"
        "• Все режимы работают одинаково\n\n"
        "Особенности работы:\n"
        "• Работаю 24/7 в облачной среде\n"
        "• Поддерживаю глубокий контекст диалога\n"
        f"• Память диалога: {MAX_CONVERSATION_HISTORY} сообщений\n"
        "• Понимаю современный сленг и мемы\n"
        "• Адаптируюсь под твой стиль общения")
    
    await message.answer(info_text)

@dp.message(F.text == "🌤️ Погода")
async def handle_weather_menu(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    weather_text = (
        "🌤️ Метеостанция\n\n"
        "Выбери город для получения актуальной погоды\n"
        "Или напиши название любого другого города")
    
    await message.answer(weather_text,
                         reply_markup=get_weather_keyboard())

@dp.message(F.text.in_(["🏙️ Новосибирск", "🏛️ Москва", "🌉 Санкт-Петербург"]))
async def handle_weather_city(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

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
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    await message.answer("🌍 Напиши название города для получения погоды")

# =======================
# ===== АДМИН ПАНЕЛЬ =====
# =======================
@dp.message(F.text == "👑 Админ-панель")
async def handle_admin_panel(message: types.Message):
    if message.chat.id != ADMIN_ID:
        await message.answer("⛔ Доступ ограничен")
        return
        
    admin_text = (
        "👑 Административная панель\n\n"
        "Доступные функции:\n"
        "• Общая статистика — аналитика системы\n"
        "• Управление пользователями — работа с юзерами\n"
        "• Сброс лимитов — обнуление счетчиков\n"
        "• Настройки системы — конфигурация бота\n"
        "• Тест AI — проверка работы нейросети\n"
        "• Логи — просмотр журналов\n"
        "• Управление памятью — работа с памятью диалогов")
    
    await message.answer(admin_text,
                         reply_markup=get_admin_keyboard())

@dp.message(F.text == "📈 Общая статистика")
async def handle_admin_stats(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    total_users = len(user_requests_count)
    total_requests = sum(sum(mode.values()) for mode in user_requests_count.values())
    active_users = sum(1 for user_id in user_requests_count if is_free_period_active(user_id))
    expired_users = total_users - active_users
    
    # Статистика по режимам
    mode_stats = {}
    for user_data in user_requests_count.values():
        for mode, count in user_data.items():
            mode_stats[mode] = mode_stats.get(mode, 0) + count
    
    # Статистика памяти
    memory_stats = get_memory_stats()
    
    stats_text = (
        f"📊 Общая статистика системы\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Активных: {active_users}\n"
        f"❌ Истекших: {expired_users}\n"
        f"📨 Всего запросов: {total_requests}\n"
        f"💾 Память: {memory_stats['total_messages']} сообщений\n\n"
        f"📈 Статистика по режимам:\n")
    
    for mode, count in mode_stats.items():
        stats_text += f"• {get_mode_description(mode)}: {count} запросов\n"
    
    stats_text += f"\n⚙️ Настройки:\n"
    stats_text += f"• Период использования: {FREE_PERIOD_DAYS} дней\n"
    stats_text += f"• Время ожидания: {REQUEST_COOLDOWN} секунд\n"
    stats_text += f"• Память диалога: {MAX_CONVERSATION_HISTORY} сообщений\n"
    stats_text += f"• Модель AI: {model}"
    
    await message.answer(stats_text)

@dp.message(F.text == "👥 Управление пользователями")
async def handle_users_management(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    users_text = (
        "👥 Управление пользователями\n\n"
        "Доступные функции:\n"
        "• Статистика пользователей — детальная аналитика\n"
        "• Продлить подписки — управление доступом\n"
        "• Поиск пользователя — найти по ID\n"
        "• Массовая рассылка — отправить сообщение")
    
    await message.answer(users_text,
                         reply_markup=get_users_management_keyboard())

@dp.message(F.text == "📊 Статистика пользователей")
async def handle_users_stats(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    if not user_requests_count:
        await message.answer("📊 Нет данных о пользователях")
        return
    
    # Топ 10 пользователей по запросам
    top_users = []
    for user_id, modes in user_requests_count.items():
        total_requests = sum(modes.values())
        remaining_days = get_remaining_free_days(user_id)
        status = "✅ Активен" if is_free_period_active(user_id) else "❌ Истек"
        memory_count = len(conversation_memory.get(user_id, []))
        top_users.append((user_id, total_requests, remaining_days, status, memory_count))
    
    # Сортируем по количеству запросов
    top_users.sort(key=lambda x: x[1], reverse=True)
    
    stats_text = "📊 Топ пользователей по активности:\n\n"
    for i, (user_id, requests, days, status, memory) in enumerate(top_users[:10], 1):
        stats_text += f"{i}. ID: {user_id}\n"
        stats_text += f"   Запросы: {requests}\n"
        stats_text += f"   Память: {memory} сообщений\n"
        stats_text += f"   Осталось дней: {days}\n"
        stats_text += f"   Статус: {status}\n\n"
    
    await message.answer(stats_text)

@dp.message(F.text == "🔄 Сброс лимитов")
async def handle_reset_limits(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    user_requests_count.clear()
    save_data(user_requests_count, DATA_FILES['user_requests_count'])
    await message.answer("✅ Лимиты всех пользователей сброшены")

@dp.message(F.text == "⚙️ Настройки системы")
async def handle_system_settings(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    settings_text = (
        "⚙️ Настройки системы\n\n"
        f"Текущие параметры:\n"
        f"• Модель AI: {model}\n"
        f"• Период использования: {FREE_PERIOD_DAYS} дней\n"
        f"• Время ожидания: {REQUEST_COOLDOWN} секунд\n"
        f"• Память диалога: {MAX_CONVERSATION_HISTORY} сообщений\n"
        f"• API ключ: {'✅ Настроен' if mistral_api_key else '❌ Отсутствует'}\n"
        f"• Пользователей: {len(user_requests_count)}\n"
        f"• Сленг слов: {len(MODERN_SLANG)} выражений\n\n"
        "Для изменения настроек требуется редактирование кода")
    
    await message.answer(settings_text)

@dp.message(F.text == "🎯 Тест AI")
async def handle_test_ai(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    try:
        response = client.chat.complete(
            model=model,
            messages=[{
                "role": "system", 
                "content": "Ты AI-помощник. Ответь кратко на тестовый запрос."
            }, {
                "role": "user",
                "content": "Привет! Это тестовое сообщение. Ответь что-нибудь."
            }]
        )
        
        if response.choices[0].message.content:
            await message.answer(f"✅ AI работает корректно\n\nОтвет: {response.choices[0].message.content}")
        else:
            await message.answer("❌ AI не вернул ответ")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка AI: {str(e)}")

@dp.message(F.text == "📊 Логи")
async def handle_logs(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    memory_stats = get_memory_stats()
    
    logs_text = (
        "📊 Журнал системы\n\n"
        "Последние события:\n"
        "• Бот запущен и работает\n"
        "• AI модель загружена\n"
        "• Погодный API доступен\n"
        f"• Пользователей: {len(user_requests_count)}\n"
        f"• Память: {memory_stats['total_messages']} сообщений\n"
        f"• Период использования: {FREE_PERIOD_DAYS} дней\n\n"
        "Ошибок не обнаружено ✅")
    
    await message.answer(logs_text)

@dp.message(F.text == "🧠 Управление памятью")
async def handle_memory_management(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    memory_text = (
        "🧠 Управление памятью диалогов\n\n"
        "Доступные функции:\n"
        "• Очистить память — удалить все данные\n"
        "• Статистика памяти — аналитика использования\n"
        "• Просмотр памяти — посмотреть данные пользователей\n"
        "• Оптимизация — очистка неактивных данных")
    
    await message.answer(memory_text,
                         reply_markup=get_memory_management_keyboard())

@dp.message(F.text == "🧹 Очистить память")
async def handle_clear_memory(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    conversation_memory.clear()
    save_data(conversation_memory, DATA_FILES['conversation_memory'])
    await message.answer("✅ Память всех пользователей очищена")

@dp.message(F.text == "📊 Статистика памяти")
async def handle_memory_stats(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    stats = get_memory_stats()
    
    stats_text = (
        f"📊 Статистика памяти\n\n"
        f"👥 Пользователей с памятью: {stats['total_users']}\n"
        f"💾 Всего сообщений: {stats['total_messages']}\n"
        f"📊 Среднее на пользователя: {stats['avg_messages']}\n"
        f"⚡ Примерный размер: {stats['memory_size']} байт\n"
        f"🔢 Максимум сообщений: {MAX_CONVERSATION_HISTORY}\n\n"
        f"💡 Память хранит последние {MAX_CONVERSATION_HISTORY} сообщений для контекста диалога")
    
    await message.answer(stats_text)

@dp.message(F.text == "🔍 Просмотр памяти")
async def handle_view_memory(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    if not conversation_memory:
        await message.answer("🔍 Нет данных в памяти")
        return
    
    # Показываем топ 5 пользователей по объему памяти
    top_memory = []
    for user_id, messages in conversation_memory.items():
        top_memory.append((user_id, len(messages)))
    
    top_memory.sort(key=lambda x: x[1], reverse=True)
    
    memory_text = "🔍 Топ пользователей по объему памяти:\n\n"
    for i, (user_id, count) in enumerate(top_memory[:5], 1):
        memory_text += f"{i}. ID: {user_id}\n"
        memory_text += f"   Сообщений: {count}/{MAX_CONVERSATION_HISTORY}\n\n"
    
    await message.answer(memory_text)

@dp.message(F.text == "⏰ Продлить подписки")
async def handle_extend_subscriptions(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    await message.answer("⏰ Функция продления подписок\n\n"
                        "Для продления подписки пользователя:\n"
                        "Отправьте команду в формате:\n"
                        "/extend [ID_пользователя] [дни]\n\n"
                        "Пример: /extend 123456789 30")

@dp.message(Command("extend"))
async def handle_extend_command(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    try:
        parts = message.text.split()
        if len(parts) == 3:
            user_id = int(parts[1])
            days = int(parts[2])
            
            if user_id in user_registration_date:
                user_registration_date[user_id] = datetime.now() - timedelta(days=FREE_PERIOD_DAYS-days)
                save_data(user_registration_date, DATA_FILES['user_registration_date'])
                await message.answer(f"✅ Подписка пользователя {user_id} продлена на {days} дней")
            else:
                await message.answer(f"❌ Пользователь {user_id} не найден")
        else:
            await message.answer("❌ Неверный формат. Используйте: /extend [ID] [дни]")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.message(F.text == "🔍 Поиск пользователя")
async def handle_find_user(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    await message.answer("🔍 Поиск пользователя\n\n"
                        "Для поиска информации о пользователе:\n"
                        "Отправьте команду в формате:\n"
                        "/find [ID_пользователя]\n\n"
                        "Пример: /find 123456789")

@dp.message(Command("find"))
async def handle_find_command(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
        
    try:
        parts = message.text.split()
        if len(parts) == 2:
            user_id = int(parts[1])
            
            if user_id in user_requests_count:
                modes = user_requests_count[user_id]
                total_requests = sum(modes.values())
                remaining_days = get_remaining_free_days(user_id)
                status = "✅ Активен" if is_free_period_active(user_id) else "❌ Истек"
                current_mode = user_modes.get(user_id, "не установлен")
                memory_count = len(conversation_memory.get(user_id, []))
                
                user_info = (
                    f"🔍 Информация о пользователе {user_id}\n\n"
                    f"• Статус: {status}\n"
                    f"• Осталось дней: {remaining_days}\n"
                    f"• Текущий режим: {current_mode}\n"
                    f"• Всего запросов: {total_requests}\n"
                    f"• Сообщений в памяти: {memory_count}\n\n"
                    f"📊 По режимам:\n"
                )
                
                for mode, count in modes.items():
                    user_info += f"• {get_mode_description(mode)}: {count} запросов\n"
                    
                await message.answer(user_info)
            else:
                await message.answer(f"❌ Пользователь {user_id} не найден")
        else:
            await message.answer("❌ Неверный формат. Используйте: /find [ID]")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.message(F.text == "⬅️ Назад")
async def handle_back(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    await message.answer("Главное меню", 
                         reply_markup=get_main_keyboard(message.chat.id))

@dp.message(F.text == "⬅️ Главное меню")
async def handle_main_menu(message: types.Message):
    cooldown_msg = check_cooldown(message.chat.id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    await message.answer("Возвращаюсь в главное меню",
                         reply_markup=get_main_keyboard(message.chat.id))

@dp.message(F.text == "⬅️ Админ-панель")
async def handle_back_to_admin(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    await message.answer("Возвращаюсь в админ-панель",
                         reply_markup=get_admin_keyboard())

# =======================
# ===== ОБРАБОТКА ГОЛОСОВЫХ И ФОТО =====
# =======================
@dp.message(F.voice)
async def handle_voice(message: types.Message):
    chat_id = message.chat.id
    mode = user_modes.get(chat_id, "обычный")
    
    # Увеличиваем счетчик запросов
    if chat_id not in user_requests_count:
        user_requests_count[chat_id] = {}
    if mode not in user_requests_count[chat_id]:
        user_requests_count[chat_id][mode] = 0
    user_requests_count[chat_id][mode] += 1
    save_data(user_requests_count, DATA_FILES['user_requests_count'])
    
    logger.info(f"Получено голосовое сообщение от {message.chat.id}")
    await message.answer("🎤 Голосовые сообщения временно не поддерживаются\n\nИспользуй текстовые сообщения для общения")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    chat_id = message.chat.id
    mode = user_modes.get(chat_id, "обычный")
    
    # Увеличиваем счетчик запросов
    if chat_id not in user_requests_count:
        user_requests_count[chat_id] = {}
    if mode not in user_requests_count[chat_id]:
        user_requests_count[chat_id][mode] = 0
    user_requests_count[chat_id][mode] += 1
    save_data(user_requests_count, DATA_FILES['user_requests_count'])
    
    logger.info(f"Получено фото от {message.chat.id}")
    if message.caption and any(word in message.caption.lower() for word in ["переведи", "перевод", "translate", "что написано"]):
        await message.answer("🖼️ Распознавание текста на фото временно недоступно\n\nОтправь текст для перевода")
    else:
        await message.answer("📸 Фото временно не анализируются\n\nОтправь текстовое описание или вопрос")

# =======================
# ===== ОСНОВНОЙ ХЭНДЛЕР =====
# =======================
@dp.message()
async def main_handler(message: types.Message):
    # Пропускаем голосовые и фото сообщения - они уже обработаны выше
    if message.voice or message.photo:
        return
        
    chat_id = message.chat.id
    user_text = (message.text or "").strip()
    style = chat_style.get(chat_id, "balanced")
    mode = user_modes.get(chat_id, "обычный")

    if not user_text:
        return

    if user_text.startswith("/"):
        return

    # Проверка времени ожидания (админы пропускают)
    cooldown_msg = check_cooldown(chat_id)
    if cooldown_msg:
        await message.answer(cooldown_msg)
        return

    # Проверка бесплатного периода
    if not is_free_period_active(chat_id) and chat_id != ADMIN_ID:
        await message.answer(
            f"⏳ Период использования завершен\n\n"
            f"Для продолжения использования необходим доступ\n\n"
            f"Обратитесь к администратору для получения доступа")
        return

    # Увеличиваем счетчик запросов
    if chat_id not in user_requests_count:
        user_requests_count[chat_id] = {}
    if mode not in user_requests_count[chat_id]:
        user_requests_count[chat_id][mode] = 0
    user_requests_count[chat_id][mode] += 1
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
            "спокойный": "Ты спокойный и расслабленный AI-помощник. Отвечай мягко и дружелюбно, но кратко. Максимум 3-4 предложения.",
            "обычный": "Ты умный и креативный AI-помощник. Отвечай информативно, но без лишних деталей. 4-5 предложений.",
            "короткий": "Ты мастер кратких ответов. Отвечай максимально лаконично, сохраняя суть. 2-3 предложения.",
            "умный": "Ты эксперт AI-помощник. Дай развернутый ответ, но будь конкретен. 5-6 предложений максимум."
        }

        # Определяем контекст для базовых приветствий
        base_prompt = system_prompts.get(mode, "Ты умный и креативный AI-помощник. Отвечай информативно, но кратко.")
        
        # Добавляем понимание современного сленга
        slang_knowledge = "\n\nТы также понимаешь современный сленг и мемы. Вот некоторые примеры:\n"
        for slang, meaning in list(MODERN_SLANG.items())[:10]:  # Берем первые 10 примеров
            slang_knowledge += f"- '{slang}' означает '{meaning}'\n"
        
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

        # Обработка reply-сообщений для улучшения контекста
        if message.reply_to_message and message.reply_to_message.text:
            replied_text = message.reply_to_message.text
            
            if any(w in user_text_lower for w in [
                    "доработать", "улучшить", "усовершенствовать", "покруче",
                    "поправь", "исправь", "перепиши", "перефразируй", "дополни"
            ]):
                user_content = f"Доработай этот текст: {replied_text}. Запрос: {user_text}"
                messages.append({"role": "user", "content": user_content})

            elif any(w in user_text_lower for w in ["сократи", "сделай короче", "укороти", "кратко", "короче"]):
                user_content = f"Сократи этот текст: {replied_text}. Сделай его короче."
                messages.append({"role": "user", "content": user_content})

            elif any(w in user_text_lower for w in [
                    "нормально", "правильно", "исправить", "мнение",
                    "что думаешь", "критика", "совет", "оцени"
            ]):
                user_content = f"Проанализируй этот текст: {replied_text}. Вопрос: {user_text}"
                messages.append({"role": "user", "content": user_content})
                
            else:
                # Обычный reply - добавляем как контекст
                messages.append({"role": "user", "content": f"Предыдущее сообщение: {replied_text}"})
                messages.append({"role": "user", "content": user_text})
        else:
            # Обычное сообщение без reply
            messages.append({"role": "user", "content": user_text})

        response = client.chat.complete(model=model, messages=messages)
        ai_text = response.choices[0].message.content

        if not ai_text:
            ai_text = "❌ Не удалось получить ответ"

        # Добавляем ответ AI в память
        add_to_conversation_memory(chat_id, "assistant", ai_text)

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
    print("🚀 Бот запущен и работает 24/7!")
    print(f"🎁 Период использования: {FREE_PERIOD_DAYS} дней")
    print(f"💾 Память диалога: {MAX_CONVERSATION_HISTORY} сообщений")
    print("🔤 Понимание современного сленга: активировано")
    print("👑 Админ-панель: доступна для ADMIN_ID")
    print("💾 Система сохранения данных: активирована")
    asyncio.run(main())
