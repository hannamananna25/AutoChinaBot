import logging
import sys
import asyncio
import signal
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatMemberStatus
from datetime import datetime
import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
import re
from xml.etree import ElementTree as ET
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Константы
DELIVERY_COST = 165000
CUSTOMS_CLEARANCE = 80000
SITE_URL = "https://autozakaz-dv.ru/"
TELEGRAM_URL = "https://t.me/autozakazdv"
GUAZI_URL = "https://www.guazi.com"
BASE_RECYCLING_FEE_INDIVIDUAL = 20000
BASE_RECYCLING_FEE_LEGAL = 150000
CHANNEL_ID = -1002265390233

# Константы для электромобилей
ELECTRIC_DUTY_RATE = 0.15
BASE_RECYCLING_FEE_ELECTRIC_INDIVIDUAL_NEW = 3400
BASE_RECYCLING_FEE_ELECTRIC_INDIVIDUAL_OLD = 5200
BASE_RECYCLING_FEE_ELECTRIC_LEGAL_NEW = 667400
BASE_RECYCLING_FEE_ELECTRIC_LEGAL_OLD = 1174000

# Актуальные ставки акциза для электромобилей (руб/л.с.) на 2025 год
EXCISE_RATES_ELECTRIC = {
    (0, 90): 0,
    (90, 150): 58,
    (150, 200): 557,
    (200, 300): 912,
    (300, 400): 1555,
    (400, 500): 1609,
    (500, float('inf')): 1662
}

# Актуальные ставки акциза для ДВС (бензин/дизель) на 2025 год
EXCISE_RATES_ICE = {
    (0, 90): 0,
    (90, 150): 61,
    (150, 200): 583,
    (200, 300): 955,
    (300, 400): 1628,
    (400, 500): 1685,
    (500, float('inf')): 1740
}

SITE_IMAGE_URL = "https://autozakaz-dv.ru/local/templates/autozakaz/images/logo_header.png"

# Инициализация бота с хранилищем состояний
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# Состояния бота
class Form(StatesGroup):
    price = State()
    year_month = State()
    engine_type = State()
    engine_volume = State()
    engine_power = State()
    importer_type = State()
    personal_use = State()

# Клавиатуры
def start_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="START")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚗 Рассчитать стоимость авто")],
            [KeyboardButton(text="📊 Курсы валют"), KeyboardButton(text="ℹ️ О боте")]
        ],
        resize_keyboard=True
    )

def importer_type_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Физическое лицо"), KeyboardButton(text="🏢 Юридическое лицо")],
            [KeyboardButton(text="↩ Назад")]
        ],
        resize_keyboard=True
    )

def personal_use_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Для личного пользования"), KeyboardButton(text="💰 Для перепродажи")],
            [KeyboardButton(text="↩ Назад")]
        ],
        resize_keyboard=True
    )

def engine_type_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛢️ Бензиновый"), KeyboardButton(text="⛽ Дизельный")],
            [KeyboardButton(text="🔋 Электрический")],
            [KeyboardButton(text="↩ Назад")]
        ],
        resize_keyboard=True
    )

def subscribe_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/auto_v_kitae")],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")]
        ]
    )

# Проверка подписки на канал
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        ]
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}", exc_info=True)
        return True  # Временно всегда возвращаем True для теста

# Получение курсов валют (асинхронная версия)
async def get_currency_rates():
    try:
        url = 'https://www.cbr.ru/scripts/XML_daily.asp'
        today = datetime.now().strftime("%d/%m/%Y")
        params = {'date_req': today}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=15) as response:
                response.raise_for_status()
                content = await response.text()
                root = ET.fromstring(content)
                rates = {}
                
                for valute in root.findall('Valute'):
                    char_code = valute.find('CharCode').text
                    if char_code in ['USD', 'EUR', 'CNY']:
                        nominal = int(valute.find('Nominal').text)
                        value = float(valute.find('Value').text.replace(',', '.'))
                        rates[char_code] = value / nominal
        
        default_rates = {'USD': 80.0, 'EUR': 90.0, 'CNY': 11.0}
        for currency in ['USD', 'EUR', 'CNY']:
            if currency not in rates:
                rates[currency] = default_rates[currency]
                logger.warning(f"Курс {currency} не найден, использовано значение по умолчанию")
        
        return rates
        
    except Exception as e:
        logger.error(f"Ошибка получения курсов: {e}", exc_info=True)
        return {'USD': 80.0, 'EUR': 90.0, 'CNY': 11.0}

def parse_engine_volume(input_str):
    try:
        clean_input = input_str.replace(' ', '').replace(',', '.')
        if '.' in clean_input:
            return int(float(clean_input) * 1000)
        return int(clean_input)
    except:
        return None

def format_engine_volume(volume_cc):
    liters = volume_cc / 1000
    return f"{volume_cc} см³ ({liters:.1f} л)" if liters != int(liters) else f"{volume_cc} см³ ({int(liters)} л)"

def format_number(value):
    return "{0:,}".format(int(value)).replace(",", ".")

# Расчет пошлины
def calculate_duty(price_rub: float, age_months: int, engine_volume_cc: int, 
                  is_individual: bool, eur_rate: float, is_electric: bool,
                  is_personal_use: bool) -> float:
    
    if is_electric:
        return price_rub * ELECTRIC_DUTY_RATE
    
    if not is_individual or not is_personal_use:
        return price_rub * 0.20
    
    if age_months <= 36:
        price_eur = price_rub / eur_rate
        
        if price_eur <= 8500:
            rate_percent = 0.54
            min_rate_eur = 2.5
        elif price_eur <= 16700:
            rate_percent = 0.48
            min_rate_eur = 3.5
        elif price_eur <= 42250:
            rate_percent = 0.48
            min_rate_eur = 5.5
        elif price_eur <= 84500:
            rate_percent = 0.48
            min_rate_eur = 7.5
        elif price_eur <= 169000:
            rate_percent = 0.48
            min_rate_eur = 15
        else:
            rate_percent = 0.48
            min_rate_eur = 20
            
        duty_by_percent = price_rub * rate_percent
        duty_by_volume = min_rate_eur * eur_rate * engine_volume_cc
        return max(duty_by_percent, duty_by_volume)
        
    elif 36 < age_months <= 60:
        if engine_volume_cc <= 1000:
            eur_per_cc = 1.5
        elif engine_volume_cc <= 1500:
            eur_per_cc = 1.7
        elif engine_volume_cc <= 1800:
            eur_per_cc = 2.5
        elif engine_volume_cc <= 2300:
            eur_per_cc = 2.7
        elif engine_volume_cc <= 3000:
            eur_per_cc = 3.0
        else:
            eur_per_cc = 3.6
        return eur_per_cc * engine_volume_cc * eur_rate
        
    else:
        if engine_volume_cc <= 1000:
            eur_per_cc = 3.0
        elif engine_volume_cc <= 1500:
            eur_per_cc = 3.2
        elif engine_volume_cc <= 1800:
            eur_per_cc = 3.5
        elif engine_volume_cc <= 2300:
            eur_per_cc = 4.8
        elif engine_volume_cc <= 3000:
            eur_per_cc = 5.0
        else:
            eur_per_cc = 5.7
        return eur_per_cc * engine_volume_cc * eur_rate

# Расчет утильсбора
def calculate_recycling(age_months: int, engine_volume_cc: int, is_individual: bool, 
                       is_personal_use: bool, is_electric: bool) -> float:
    if is_electric:
        if is_individual and is_personal_use:
            return BASE_RECYCLING_FEE_ELECTRIC_INDIVIDUAL_NEW if age_months <= 36 else BASE_RECYCLING_FEE_ELECTRIC_INDIVIDUAL_OLD
        else:
            return BASE_RECYCLING_FEE_ELECTRIC_LEGAL_NEW if age_months <= 36 else BASE_RECYCLING_FEE_ELECTRIC_LEGAL_OLD
    
    if is_individual and is_personal_use and engine_volume_cc <= 3000:
        if age_months <= 36:
            return 3400
        else:
            return 5200
            
    is_new = age_months <= 36
    
    if engine_volume_cc <= 1000:
        coefficient = 1.42 if is_new else 5.3
    elif engine_volume_cc <= 2000:
        coefficient = 2.21 if is_new else 8.26
    elif engine_volume_cc <= 3000:
        coefficient = 4.22 if is_new else 16.12
    elif engine_volume_cc <= 3500:
        coefficient = 5.73 if is_new else 28.5
    else:
        coefficient = 9.08 if is_new else 35.01
        
    return BASE_RECYCLING_FEE_LEGAL * coefficient

# Расчет акциза для электромобилей по мощности в л.с.
def calculate_excise_electric(power_hp: float) -> float:
    for (min_power, max_power), rate in EXCISE_RATES_ELECTRIC.items():
        if min_power < power_hp <= max_power:
            return power_hp * rate
    return 0

# Расчет акциза для ДВС (бензин/дизель) по мощности в л.с.
def calculate_excise_ice(power_hp: float) -> float:
    for (min_power, max_power), rate in EXCISE_RATES_ICE.items():
        if min_power < power_hp <= max_power:
            return power_hp * rate
    return 0

# Обработчики сообщений
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    try:
        # Временно отключим проверку подписки для теста
        # if not await is_subscribed(message.from_user.id):
        #     await message.answer(
        #         "📢 Для использования бота необходимо подписаться на наш канал!\n"
        #         "После подписки нажмите кнопку '✅ Я подписался'",
        #         reply_markup=subscribe_keyboard()
        #     )
        #     return
        
        await message.answer(
            "🚗 <b>AutoZakazDV Calculator</b>\n\n"
            "Добро пожаловать! Актуальные расчеты стоимости авто из Китая\n\n"
            "Нажмите START для начала работы",
            parse_mode="HTML",
            reply_markup=start_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в start_handler: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

@dp.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_handler(callback_query: types.CallbackQuery):
    try:
        # Временно отключим проверку подписки для теста
        # if await is_subscribed(callback_query.from_user.id):
        #     await callback_query.message.delete()
        #     await callback_query.message.answer(
        #         "✅ Спасибо за подписку! Теперь вы можете использовать бота.\n"
        #         "Нажмите START для начала работы.",
        #         reply_markup=start_keyboard()
        #     )
        # else:
        #     await callback_query.answer(
        #         "❌ Вы еще не подписались на канал! Пожалуйста, подпишитесь и повторите проверку.",
        #         show_alert=True
        #     )
        await callback_query.message.delete()
        await callback_query.message.answer(
            "✅ Спасибо за подписку! Теперь вы можете использовать бота.\n"
            "Нажмите START для начала работы.",
            reply_markup=start_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в check_subscription_handler: {e}", exc_info=True)

@dp.message(lambda m: m.text == "START")
async def start_command_handler(message: types.Message):
    try:
        # Временно отключим проверку подписки для теста
        # if not await is_subscribed(message.from_user.id):
        #     await message.answer(
        #         "📢 Для использования бота необходимо подписаться на наш канал!\n"
        #         "После подписки нажмите кнопку '✅ Я подписался'",
        #         reply_markup=subscribe_keyboard()
        #     )
        #     return
        
        await message.answer(
            "🚗 <b>AutoZakazDV Calculator</b>\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка в start_command_handler: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

# Основная функция
async def main():
    logger.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logger.info("Starting bot...")
    asyncio.run(main())
