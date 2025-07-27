# Обновленные константы для акциза электромобилей
EXCISE_RATE_PER_KW = 1740  # 1740 рублей за 0.75 кВт
KW_PER_UNIT = 0.75

# Функция для расчета акциза электромобилей
def calculate_excise_electric(power_kw: float) -> float:
    """Расчет акциза для электромобилей по актуальным ставкам 2025 года"""
    return (power_kw / KW_PER_UNIT) * EXCISE_RATE_PER_KW

# Обновленная функция расчета результата
async def calculate_and_send_result(message: types.Message, state: FSMContext, data: dict, is_individual: bool, is_personal_use: bool):
    try:
        rates = get_currency_rates()
        price_rub = data['price'] * rates['CNY']
        eur_rate = rates['EUR']
        
        is_electric = data.get('engine_type') == "🔋 Электрический"
        engine_volume_cc = data.get('engine_volume_cc', 0) if not is_electric else 0
        
        # Для электромобилей - используем исходные кВт для расчета акциза
        if is_electric:
            # Сохраняем исходную мощность в кВт
            power_kw = data.get('engine_power', 0)
            # Конвертация в л.с. только для отображения
            engine_power_hp = power_kw * 1.35962
            
            # Акциз рассчитываем по исходным кВт!
            excise = calculate_excise_electric(power_kw)
        else:
            # Для ДВС - мощность уже в л.с.
            engine_power_hp = data.get('engine_power', 0)
            # Акциз только для юрлиц
            excise = calculate_excise(engine_power_hp) if not is_individual else 0
        
        duty = calculate_duty(price_rub, data['age_months'], engine_volume_cc, 
                             is_individual, eur_rate, is_electric, is_personal_use)
        
        recycling = calculate_recycling(data['age_months'], engine_volume_cc, 
                                      is_individual, is_personal_use, is_electric)
        
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
            # Для электромобилей показываем и кВт, и л.с.
            result += f"⚡ <b>Мощность двигателя:</b> {data.get('engine_power', 0)} кВт ({engine_power_hp:.1f} л.с.)\n"
        
        result += f"👤 <b>Импортер:</b> {importer_type}\n\n"
        result += f"📝 <b>Таможенные платежи:</b>\n"
        result += f"- Пошлина: {format_number(duty)} руб.\n"
        
        if is_electric and excise > 0:
            result += f"- Акциз: {format_number(excise)} руб. ({EXCISE_RATE_PER_KW} руб./{KW_PER_UNIT} кВт)\n"
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
            result += "\n\nℹ️ <i>Для электромобилей: акциз применяется при любой мощности, НДС 20% обязателен для всех</i>"
        elif not is_individual:
            result += "\n\nℹ️ <i>Для ДВС юридических лиц: учтены пошлина, акциз, НДС и утильсбор</i>"
        
        # Логируем длину сообщения для отладки
        logger.info(f"Длина сообщения: {len(result)} символов")
        
        await message.answer(result, parse_mode="HTML", reply_markup=main_menu())
        
        site_info = (
            "С уважением, Авто Заказ ДВ\n\n"
            f"<a href='{TELEGRAM_URL}'>- Заказать авто</a>\n"
            f"<a href='{SITE_URL}'>autozakaz-dv.ru</a>\n"
            "Главная"
        )
        
        # Временно закомментируем отправку фото для отладки
        # await message.answer_photo(
        #     photo=SITE_IMAGE_URL,
        #     caption=site_info,
        #     parse_mode="HTML"
        # )
        
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в calculate_and_send_result: {e}", exc_info=True)
        logger.error(f"Данные расчета: {data}")
        logger.error(f"Тип импортера: {is_individual}, Цель: {is_personal_use}")
        await message.answer("⚠️ Произошла ошибка при расчете стоимости. Пожалуйста, попробуйте еще раз.")
        await state.clear()
