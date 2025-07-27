import logging
import sys
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatMemberStatus
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
import re
from xml.etree import ElementTree as ET
from aiohttp import web

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
BASE_EXCISE_RATE = 61
CHANNEL_ID = -1002265390233

# Константы для электромобилей
ELECTRIC_DUTY_RATE = 0.15
BASE_RECYCLING_FEE_ELECTRIC_INDIVIDUAL_NEW = 3400
BASE_RECYCLING_FEE_ELECTRIC_INDIVIDUAL_OLD = 5200
BASE_RECYCLING_FEE_ELECTRIC_LEGAL_NEW = 667400
BASE_RECYCLING_FEE_ELECTRIC_LEGAL_OLD = 1174000

EXCISE_RATES_ELECTRIC = {
    (0, 90): 0,
    (90, 150): 49,
    (150, 200): 492,
    (200, 300): 804,
    (300, 400): 1369,
    (400, 500): 1418,
    (500, float('inf')): 1466
}

SITE_IMAGE_URL = "https://autozakaz-dv.ru/local/templates/autozakaz/images/logo_header.png"

# Инициализация бота
bot = Bot(token=TOKEN)
dp = Dispatcher()

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
        return False

# Получение курсов валют
def get_currency_rates():
    try:
        url = 'https://www.cbr.ru/scripts/XML_daily.asp'
        today = datetime.now().strftime("%d/%m/%Y")
        params = {'date_req': today}
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
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

def calculate_excise(engine_power_hp: int) -> float:
    return engine_power_hp * BASE_EXCISE_RATE

def calculate_excise_electric(power_hp: int) -> float:
    for (min_power, max_power), rate in EXCISE_RATES_ELECTRIC.items():
        if min_power < power_hp <= max_power:
            return power_hp * rate
    return 0

# Обработчики сообщений
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    try:
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "📢 Для использования бота необходимо подписаться на наш канал!\n"
                "После подписки нажмите кнопку '✅ Я подписался'",
                reply_markup=subscribe_keyboard()
            )
            return
        
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
        if await is_subscribed(callback_query.from_user.id):
            await callback_query.message.delete()
            await callback_query.message.answer(
                "✅ Спасибо за подписку! Теперь вы можете использовать бота.\n"
                "Нажмите START для начала работы.",
                reply_markup=start_keyboard()
            )
        else:
            await callback_query.answer(
                "❌ Вы еще не подписались на канал! Пожалуйста, подпишитесь и повторите проверку.",
                show_alert=True
            )
    except Exception as e:
        logger.error(f"Ошибка в check_subscription_handler: {e}", exc_info=True)

@dp.message(lambda m: m.text == "START")
async def start_command_handler(message: types.Message):
    try:
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "📢 Для использования бота необходимо подписаться на наш канал!\n"
                "После подписки нажмите кнопку '✅ Я подписался'",
                reply_markup=subscribe_keyboard()
            )
            return
        
        await message.answer(
            "🚗 <b>AutoZakazDV Calculator</b>\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка в start_command_handler: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

@dp.message(Command("calculate"))
@dp.message(lambda m: m.text == "🚗 Рассчитать стоимость авто")
async def calculate_handler(message: types.Message, state: FSMContext):
    try:
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "📢 Для использования калькулятора необходимо подписаться на наш канал!\n"
                "После подписки нажмите кнопку '✅ Я подписался'",
                reply_markup=subscribe_keyboard()
            )
            return
        
        await state.set_state(Form.price)
        await message.answer(
            "💰 Введите стоимость автомобиля в CNY (например 150000):",
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        logger.error(f"Ошибка в calculate_handler: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

@dp.message(Form.price)
async def price_handler(message: types.Message, state: FSMContext):
    try:
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "📢 Для продолжения расчета необходимо подписаться на наш канал!\n"
                "После подписки нажмите кнопку '✅ Я подписался'",
                reply_markup=subscribe_keyboard()
            )
            return
        
        price = float(message.text.replace(' ', '').replace(',', '.'))
        if price <= 0: 
            await message.answer("❌ Ошибка! Стоимость должна быть положительным числом.")
            return
            
        await state.update_data(price=price)
        await state.set_state(Form.year_month)
        await message.answer("📅 Введите год и месяц выпуска (формат: ГГГГ.ММ, например: 2021.05):")
    except ValueError:
        await message.answer("❌ Ошибка! Введите корректную сумму (например: 86000)")
    except Exception as e:
        logger.error(f"Ошибка в price_handler: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, начните расчет заново.")

@dp.message(Form.year_month)
async def year_month_handler(message: types.Message, state: FSMContext):
    try:
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "📢 Для продолжения расчета необходимо подписаться на наш канал!\n"
                "После подписки нажмите кнопку '✅ Я подписался'",
                reply_markup=subscribe_keyboard()
            )
            return
        
        year, month = map(float, message.text.split('.'))
        current_date = datetime.now()
        
        if not (1990 <= year <= current_date.year) or not (1 <= month <= 12):
            await message.answer("❌ Ошибка! Некорректная дата выпуска.")
            return
            
        manufacture_date = datetime(int(year), int(month), 1)
        age_months = (current_date.year - manufacture_date.year) * 12 + (current_date.month - manufacture_date.month)
        
        await state.update_data(year_month=(year, month), age_months=age_months)
        await state.set_state(Form.engine_type)
        await message.answer("🔧 Выберите тип двигателя:", reply_markup=engine_type_keyboard())
    except Exception as e:
        logger.error(f"Ошибка в year_month_handler: {e}", exc_info=True)
        await message.answer("❌ Ошибка формата! Введите как ГГГГ.ММ (например: 2021.05)")
        await state.set_state(Form.year_month)

@dp.message(Form.engine_type)
async def engine_type_handler(message: types.Message, state: FSMContext):
    try:
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "📢 Для продолжения расчета необходимо подписаться на наш канал!\n"
                "После подписки нажмите кнопку '✅ Я подписался'",
                reply_markup=subscribe_keyboard()
            )
            return
        
        engine_types = ["🛢️ Бензиновый", "⛽ Дизельный", "🔋 Электрический"]
        if message.text not in engine_types:
            await message.answer("❌ Пожалуйста, выберите тип двигателя из предложенных вариантов",
                               reply_markup=engine_type_keyboard())
            return
        
        await state.update_data(engine_type=message.text)
        
        if message.text in ["🛢️ Бензиновый", "⛽ Дизельный"]:
            await state.set_state(Form.engine_volume)
            await message.answer("⚙️ Введите объем двигателя в кубических сантиметрах (например: 2000) или в литрах (например: 2.0):")
        else:
            await state.set_state(Form.engine_power)
            await message.answer("⚡ Введите мощность двигателя в кВт (например: 120):")
    except Exception as e:
        logger.error(f"Ошибка в engine_type_handler: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        await state.set_state(Form.engine_type)

@dp.message(Form.engine_volume)
async def engine_volume_handler(message: types.Message, state: FSMContext):
    try:
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "📢 Для продолжения расчета необходимо подписаться на наш канал!\n"
                "После подписки нажмите кнопку '✅ Я подписался'",
                reply_markup=subscribe_keyboard()
            )
            return
        
        volume_cc = parse_engine_volume(message.text)
        if volume_cc is None or volume_cc <= 0:
            await message.answer("❌ Ошибка! Введите объем цифрами (например: 1.6 или 1600)")
            return
        
        await state.update_data(engine_volume_cc=volume_cc)
        await state.set_state(Form.engine_power)
        await message.answer("⚙️ Введите мощность двигателя в л.с. (например: 150):")
    except Exception as e:
        logger.error(f"Ошибка в engine_volume_handler: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, введите объем снова.")
        await state.set_state(Form.engine_volume)

@dp.message(Form.engine_power)
async def engine_power_handler(message: types.Message, state: FSMContext):
    try:
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "📢 Для продолжения расчета необходимо подписаться на наш канал!\n"
                "После подписки нажмите кнопку '✅ Я подписался'",
                reply_markup=subscribe_keyboard()
            )
            return
        
        power = int(message.text)
        if power <= 0: 
            await message.answer("❌ Ошибка! Мощность должна быть положительным числом.")
            return
            
        await state.update_data(engine_power=power)
        await state.set_state(Form.importer_type)
        await message.answer("👤 Выберите тип импортера:", reply_markup=importer_type_keyboard())
    except ValueError:
        data = await state.get_data()
        unit = "кВт" if data.get('engine_type') == "🔋 Электрический" else "л.с."
        await message.answer(f"❌ Ошибка! Введите мощность цифрами (например: 150) в {unit}")
    except Exception as e:
        logger.error(f"Ошибка в engine_power_handler: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, введите мощность снова.")
        await state.set_state(Form.engine_power)

@dp.message(Form.importer_type)
async def importer_type_handler(message: types.Message, state: FSMContext):
    try:
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "📢 Для продолжения расчета необходимо подписаться на наш канал!\n"
                "После подписки нажмите кнопку '✅ Я подписался'",
                reply_markup=subscribe_keyboard()
            )
            return
        
        if message.text not in ["👤 Физическое лицо", "🏢 Юридическое лицо"]:
            await message.answer("❌ Пожалуйста, выберите тип из предложенных вариантов",
                               reply_markup=importer_type_keyboard())
            return
        
        is_individual = message.text == "👤 Физическое лицо"
        await state.update_data(importer_type=is_individual)
        
        if is_individual:
            await state.set_state(Form.personal_use)
            await message.answer("🎯 Выберите цель использования автомобиля:", reply_markup=personal_use_keyboard())
        else:
            data = await state.get_data()
            await calculate_and_send_result(message, state, data, is_individual, is_personal_use=False)
    except Exception as e:
        logger.error(f"Ошибка в importer_type_handler: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        await state.set_state(Form.importer_type)

@dp.message(Form.personal_use)
async def personal_use_handler(message: types.Message, state: FSMContext):
    try:
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "📢 Для продолжения расчета необходимо подписаться на наш канал!\n"
                "После подписки нажмите кнопку '✅ Я подписался'",
                reply_markup=subscribe_keyboard()
            )
            return
        
        if message.text not in ["✅ Для личного пользования", "💰 Для перепродажи"]:
            await message.answer("❌ Пожалуйста, выберите цель из предложенных вариантов",
                               reply_markup=personal_use_keyboard())
            return
        
        is_personal_use = message.text == "✅ Для личного пользования"
        data = await state.get_data()
        await calculate_and_send_result(message, state, data, is_individual=True, is_personal_use=is_personal_use)
    except Exception as e:
        logger.error(f"Ошибка в personal_use_handler: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        await state.set_state(Form.personal_use)

async def calculate_and_send_result(message: types.Message, state: FSMContext, data: dict, is_individual: bool, is_personal_use: bool):
    try:
        rates = get_currency_rates()
        price_rub = data['price'] * rates['CNY']
        eur_rate = rates['EUR']
        
        is_electric = data.get('engine_type') == "🔋 Электрический"
        engine_volume_cc = data.get('engine_volume_cc', 0) if not is_electric else 0
        engine_power_hp = data.get('engine_power', 0)
        
        if is_electric:
            engine_power_hp = engine_power_hp * 1.35962
        
        duty = calculate_duty(price_rub, data['age_months'], engine_volume_cc, 
                             is_individual, eur_rate, is_electric, is_personal_use)
        
        recycling = calculate_recycling(data['age_months'], engine_volume_cc, 
                                      is_individual, is_personal_use, is_electric)
        
        excise = 0
        if is_electric:
            excise = calculate_excise_electric(engine_power_hp)
        elif not is_individual:
            excise = calculate_excise(data.get('engine_power', 0))
        
        vat_base = price_rub + duty + excise
        vat = vat_base * 0.2 if (is_electric or not is_individual) else 0
        
        total = price_rub + duty + recycling + vat + excise + DELIVERY_COST + CUSTOMS_CLEARANCE
        
        years = data['age_months'] // 12
        months = data['age_months'] % 12
        age_str = f"{years} г. {months} мес." if months else f"{years} лет"
        
        importer_type = "Физическое лицо" if is_individual else "Юридическое лицо"
        if is_individual:
            purpose = "личное пользование" if is_personal_use else "перепродажа"
            importer_type += f" ({purpose})"
        
        result = (
            f"📊 <b>Результат расчета</b> (актуально на {datetime.now().strftime('%d.%m.%Y')}):\n\n"
            f"💰 <b>Стоимость авто:</b> {format_number(data['price'])} CNY ({format_number(price_rub)} руб.)\n"
            f"📈 <b>Курсы:</b> CNY: {rates['CNY']:.2f} руб., EUR: {rates['EUR']:.2f} руб.\n"
            f"⏳ <b>Дата выпуска:</b> {data['year_month'][0]:.0f}.{data['year_month'][1]:.0f} ({age_str})\n"
            f"🔋 <b>Тип двигателя:</b> {data['engine_type']}\n"
        )
        
        if data['engine_type'] in ["🛢️ Бензиновый", "⛽ Дизельный"]:
            result += f"🔧 <b>Объем двигателя:</b> {format_engine_volume(engine_volume_cc)}\n"
            result += f"⚡ <b>Мощность двигателя:</b> {data.get('engine_power', 0)} л.с.\n"
        else:
            result += f"⚡ <b>Мощность двигателя:</b> {data.get('engine_power', 0)} кВт ({engine_power_hp:.1f} л.с.)\n"
        
        result += f"👤 <b>Импортер:</b> {importer_type}\n\n"
        result += f"📝 <b>Таможенные платежи:</b>\n"
        result += f"- Пошлина: {format_number(duty)} руб.\n"
        
        if is_electric and excise > 0:
            result += f"- Акциз: {format_number(excise)} руб. (мощность {engine_power_hp:.1f} л.с.)\n"
        elif not is_electric and not is_individual and excise > 0:
            result += f"- Акциз: {format_number(excise)} руб.\n"
        
        if vat > 0:
            result += f"- НДС (20%): {format_number(vat)} руб.\n"
        
        result += f"- Утильсбор: {format_number(recycling)} руб.\n"
        
        result += (
            f"\n🚚 <b>Дополнительно:</b>\n"
            f"- Доставка до Уссурийска: {format_number(DELIVERY_COST)} руб.\n"
            f"- Таможенное оформление: {format_number(CUSTOMS_CLEARANCE)} руб.\n\n"
            f"💵 <b>ИТОГО к оплате:</b> {format_number(total)} руб.\n\n"
            f"<a href='{SITE_URL}'>С уважением, Авто Заказ ДВ</a>\n\n"
            f"<a href='{TELEGRAM_URL}'>📩 Заказать авто</a>\n"
            f"<a href='{GUAZI_URL}'>🔍 Поиск авто на Guazi.com</a>"
        )
        
        if is_electric and is_individual and is_personal_use:
            result += "\n\nℹ️ <i>Для электромобилей физлиц: льготный утильсбор применяется при условиях: "
            result += "1 авто в год, без продажи в течение 12 месяцев</i>"
        elif is_electric:
            result += "\n\nℹ️ <i>Для электромобилей: акциз применяется при мощности >90 л.с., НДС 20% обязателен для всех</i>"
        elif not is_individual:
            result += "\n\nℹ️ <i>Для ДВС юридических лиц: учтены пошлина, акциз, НДС и утильсбор</i>"
        
        await message.answer(result, parse_mode="HTML", reply_markup=main_menu())
        
        site_info = (
            "С уважением, Авто Заказ ДВ\n\n"
            f"<a href='{TELEGRAM_URL}'>- Заказать авто</a>\n"
            f"<a href='{SITE_URL}'>autozakaz-dv.ru</a>\n"
            "Главная"
        )
        
        await message.answer_photo(
            photo=SITE_IMAGE_URL,
            caption=site_info,
            parse_mode="HTML"
        )
        
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в calculate_and_send_result: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка при расчете стоимости. Пожалуйста, попробуйте еще раз.")
        await state.clear()

@dp.message(lambda m: m.text == "📊 Курсы валют")
async def show_rates_handler(message: types.Message):
    try:
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "📢 Для просмотра курсов валют необходимо подписаться на наш канал!\n"
                "После подписки нажмите кнопку '✅ Я подписался'",
                reply_markup=subscribe_keyboard()
            )
            return
        
        rates = get_currency_rates()
        await message.answer(
            f"📊 <b>Текущие курсы ЦБ РФ</b>:\n\n"
            f"🇺🇸 USD: {rates['USD']:.2f} руб.\n"
            f"🇪🇺 EUR: {rates['EUR']:.2f} руб.\n"
            f"🇨🇳 CNY: {rates['CNY']:.2f} руб.\n\n"
            f"🔄 Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка в show_rates_handler: {e}", exc_info=True)
        await message.answer("⚠️ Не удалось получить курсы валют. Пожалуйста, попробуйте позже.")

@dp.message(lambda m: m.text == "ℹ️ О боте")
async def about_handler(message: types.Message):
    try:
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "📢 Для просмотра информации о боте необходимо подписаться на наш канал!\n"
                "После подписки нажмите кнопку '✅ Я подписался'",
                reply_markup=subscribe_keyboard()
            )
            return
        
        await message.answer(
            f"🤖 <b>AutoZakazDV Calculator Bot</b>\n\n"
            f"Этот бот помогает рассчитать стоимость растаможки автомобилей из Китая.\n\n"
            f"<a href='{SITE_URL}'>🌐 Сайт компании</a>\n"
            f"<a href='{TELEGRAM_URL}'>📞 Наш Telegram</a>\n"
            f"<a href='{GUAZI_URL}'>🚗 Поиск авто на Guazi.com</a>\n\n"
            f"Для начала расчета нажмите START",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка в about_handler: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")

@dp.message(lambda m: m.text == "Очистить чат" or m.text == "/clean")
async def clear_chat_handler(message: types.Message):
    try:
        await message.answer(
            "Чат очищен. Нажмите START для начала работы.",
            reply_markup=start_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в clear_chat_handler: {e}", exc_info=True)

@dp.message()
async def unknown_command_handler(message: types.Message):
    try:
        if not await is_subscribed(message.from_user.id):
            await message.answer(
                "📢 Для использования бота необходимо подписаться на наш канал!\n"
                "После подписки нажмите кнопку '✅ Я подписался'",
                reply_markup=subscribe_keyboard()
            )
            return
        
        await message.answer(
            "Я не понимаю эту команду. Нажмите START для начала работы.",
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        logger.error(f"Ошибка в unknown_command_handler: {e}", exc_info=True)

# Обработчик ошибок
async def global_error_handler(update: types.Update, exception: Exception):
    logger.error(f"Глобальная ошибка: {exception}", exc_info=True)
    return True

# HTTP сервер
async def health_check(request):
    return web.Response(text="Bot is running")

app = web.Application()
app.add_routes([web.get('/', health_check)])

async def start_webapp():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8000)
    await site.start()
    logger.info("HTTP server started on port 8000")

# Запуск приложения
async def main():
    # Регистрация обработчика ошибок
    dp.errors.register(global_error_handler)
    
    # Запуск HTTP сервера
    asyncio.create_task(start_webapp())
    
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    logger.info("Starting bot...")
    asyncio.run(main())
