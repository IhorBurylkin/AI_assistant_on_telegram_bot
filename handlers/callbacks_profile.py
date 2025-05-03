import pandas as pd
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from aiogram import types, Router, F
from aiogram.enums import ChatType
from services.db_utils import read_user_all_data, read_with_period
from logs.log import logs
from config.config import DEFAULT_LANGUAGES, MESSAGES
from keyboards.inline_kb_profile import get_profile_inline, get_limits_inline, get_check_report_inline, get_report_inline, create_day_keyboard
from aiogram.fsm.context import FSMContext
from handlers.callbacks_data import DateCB, PeriodCB, ReportСB, CustomPeriod
from services.report_services import generate_report

callbacks_profile_router = Router()

@callbacks_profile_router.callback_query(lambda call: call.data.startswith("profile:"))
async def process_profile_callback(query: types.CallbackQuery):
    try:
        # Determine chat_id based on chat type
        chat_id = query.message.chat.id if query.message.chat.type == ChatType.PRIVATE else query.from_user.id

        # Get user's language, if not found - use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Determine command from callback_data
        data = query.data.split(":")[1]

        if data == "usage_limit":
            inline_limit_kb, message_to_send = await get_limits_inline(chat_id)
            await query.message.edit_text(message_to_send, reply_markup=inline_limit_kb)
            await query.answer()
        elif data == "back":
            inline_profile_kb = await get_profile_inline(chat_id)
            await query.message.edit_text(MESSAGES[lang]['inline_kb']['profile']['profile_title'], reply_markup=inline_profile_kb)
            await query.answer()
        elif data == "check_report":
            inline_calendar_kb = await get_check_report_inline(chat_id)
            await query.message.edit_text(MESSAGES[lang]['inline_kb']['profile']['check_report_title'], reply_markup=inline_calendar_kb)
            await query.answer()

        await logs(f"Profile callback processed for chat_id {chat_id} with data: {data}", type_e="info")
    except Exception as e:
        await logs(f"Error in process_profile_callback for chat_id {chat_id}: {e}", type_e="error")
        raise

@callbacks_profile_router.callback_query(DateCB.filter())
@callbacks_profile_router.callback_query(PeriodCB.filter(F.mode == "preset"))
@callbacks_profile_router.callback_query(PeriodCB.filter((F.mode == "custom") & (F.value == "your_period")))
async def unified_period_handler(
    query: types.CallbackQuery,
    callback_data: PeriodCB,
    state: FSMContext
):
    """Обработчик и для календаря, и для пресетов, и для запуска кастомного периода."""
    try:
        chat_id = query.message.chat.id if query.message.chat.type == ChatType.PRIVATE else query.from_user.id
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language") or DEFAULT_LANGUAGES
        current_state = await state.get_state()

        new_text: str
        new_markup = None

        async def get_text_and_markup(start, end):
            """Helper function to get text and markup for the message."""
            new_text = f"{MESSAGES[lang]['calendar']['selected_period'].format(start, end)}\n\n{MESSAGES[lang]['inline_kb']['profile']['check_report_title_finally']}"
            new_markup = await get_report_inline(chat_id, lang, start, end)
            return new_text, new_markup

        # 1) Навигация и выбор даты в календаре
        if isinstance(callback_data, DateCB):
            action = callback_data.action
            year, month, day = callback_data.year, callback_data.month, callback_data.day

            # Листаем месяцы
            if action in ("prev_month", "next_month"):
                # текст остаётся тем же, что сейчас в сообщении:
                # либо «Выберите начальную дату», либо «…конечную дату»
                new_text = (
                    MESSAGES[lang]['calendar']['start_date']
                    if current_state == CustomPeriod.waiting_for_start
                    else MESSAGES[lang]['calendar']['end_date']
                )
                await logs(f"Month navigation activated for chat_id {chat_id}", type_e="info")
                new_markup = await create_day_keyboard(year, month, chat_id, lang)

            # Установили начальную дату → переходим к выбору конца
            elif current_state == CustomPeriod.waiting_for_start and action == "set_day":
                start = f"{year}-{month:02d}-{day:02d}"
                await state.update_data(start_date=start)
                await state.set_state(CustomPeriod.waiting_for_end)

                new_text = MESSAGES[lang]['calendar']['end_date']
                await logs(f"Start date set for chat_id {chat_id}: {start}", type_e="info")
                new_markup = await create_day_keyboard(year, month, chat_id, lang)

            # Установили конечную дату → выходим из FSM и показываем результат
            elif current_state == CustomPeriod.waiting_for_end and action == "set_day":
                end = f"{year}-{month:02d}-{day:02d}"
                data = await state.get_data()
                start = data["start_date"]
                await state.clear()

                new_text, new_markup = await get_text_and_markup(start, end)

        # 2) Пресеты («сегодня», «месяц» и т.д.)
        elif isinstance(callback_data, PeriodCB) and callback_data.mode == "preset":
            today = date.today()
            match callback_data.value:
                case "today":
                    start = end = today
                case "week":
                    start, end = today - timedelta(days=6), today
                case "current_month":
                    start, end = today.replace(day=1), today
                case "last_month":
                    start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
                    end   = today.replace(day=1) - timedelta(days=1)
                case "year":
                    start, end = today - relativedelta(years=1), today

            await logs(f"Preset period handler activated for chat_id {chat_id}", type_e="info")
            new_text, new_markup = await get_text_and_markup(start, end)

        # 3) Кастомный старт периода
        elif isinstance(callback_data, PeriodCB) \
            and callback_data.mode == "custom" \
            and callback_data.value == "your_period":
            await state.set_state(CustomPeriod.waiting_for_start)

            new_text = MESSAGES[lang]['calendar']['start_date']
            await logs(f"Custom period handler activated for chat_id {chat_id}", type_e="info")
            new_markup = await create_day_keyboard(
                year     = datetime.now().year,
                month    = datetime.now().month,
                chat_id  = chat_id,
                lang     = lang
            )

        # --- ЕДИНСТВЕННЫЙ вызов edit_text и answer ---
        await query.message.edit_text(new_text, reply_markup=new_markup)
        await query.answer()
        await logs(f"Unified period handler processed for chat_id {chat_id} with data: {callback_data}", type_e="info")
    except Exception as e:
        await logs(f"Error in unified_period_handler for chat_id {chat_id}: {e}", type_e="error")
        raise    

@callbacks_profile_router.callback_query(ReportСB.filter())
async def process_report_callback(query: types.CallbackQuery, callback_data: ReportСB):
    try:
        chat_id = query.message.chat.id if query.message.chat.type == ChatType.PRIVATE else query.from_user.id

        # Get user's language, if not found - use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language") or DEFAULT_LANGUAGES

        # Extract report type from callback data
        report_type = callback_data.report_type
        start_date = callback_data.start_date
        end_date = callback_data.end_date

        if report_type == "send_in_chat":
            # Handle sending report in chat
            data = await read_with_period(chat_id, start_date, end_date)

            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            text = await generate_report(df, start_date, end_date, lang)
        elif report_type == "pdf":
            # Handle PDF report generation
            pass
        elif report_type == "excel":
            # Handle Excel report generation
            pass
        elif report_type == "csv":
            # Handle CSV report generation
            pass

        # Edit message with new text and keyboard
        await query.message.edit_text(text)#MESSAGES[lang]['inline_kb']['profile']['check_report_title_finally'])
        await query.answer()

        await logs(f"Report callback processed for chat_id {chat_id} with report type: {report_type}", type_e="info")
    except Exception as e:
        await logs(f"Error in process_report_callback for chat_id {chat_id}: {e}", type_e="error")
        raise