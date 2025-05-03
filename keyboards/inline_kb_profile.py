import calendar
from datetime import date
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.db_utils import read_user_all_data
from config.config import DEFAULT_LANGUAGES, MESSAGES, LIMITS, WHITE_LIST
from handlers.callbacks_data import PeriodCB, DateCB, ReportСB
from services.utils import time_until_midnight_utc
from logs.log import logs

async def get_profile_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    # Form inline profile menu
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['profile']['limits'], callback_data="profile:usage_limit")],
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['profile']['check_report'], callback_data="profile:check_report")],
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['profile']['close'], callback_data="settings:close")]
    ])
    await logs(f"Inline profile menu successfully created for user {chat_id}", type_e="info")
    return kb

async def get_limits_inline(chat_id: int) -> InlineKeyboardMarkup:
    try:
        # Calculate time until midnight
        remaining_time = await time_until_midnight_utc()
        total_seconds = int(remaining_time.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        formatted_time = f"{hours:02d}:{minutes:02d}"

        # Determine chat_id and get user's language
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Get number of requests and tokens, list of limits and category
        tokens = user_data.get("tokens")
        requests = user_data.get("requests")
        which_list = user_data.get("in_limit_list")

        lost_req = LIMITS[which_list][0] - requests
        lost_tokens = LIMITS[which_list][1] - tokens

        # Form message with limits
        if chat_id in WHITE_LIST:
            message_to_send = (
                f"{MESSAGES[lang]['limits'].format(lost_req, lost_tokens, formatted_time)}\n\n"
                f"{MESSAGES[lang]['white_list']}"
            )
        else:
            message_to_send = MESSAGES[lang]['limits'].format(lost_req, lost_tokens, formatted_time)

        # Form inline menu with limits
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=MESSAGES[lang]['settings_back'], callback_data="profile:back")]
        ])

        await logs(f"Inline limits successfully executed for chat_id {chat_id}", type_e="info")
        return kb, message_to_send
    except Exception as e:
        await logs(f"Error in command_limits: {e}", type_e="error")
        raise

async def get_check_report_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    # Form inline menu for check report
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['calendar']['today'], callback_data=PeriodCB(mode="preset", value="today").pack()),
        InlineKeyboardButton(text=MESSAGES[lang]['calendar']['week'], callback_data=PeriodCB(mode="preset", value="week").pack())],
        [InlineKeyboardButton(text=MESSAGES[lang]['calendar']['current_month'], callback_data=PeriodCB(mode="preset", value="current_month").pack()),
         InlineKeyboardButton(text=MESSAGES[lang]['calendar']['last_month'], callback_data=PeriodCB(mode="preset", value="last_month").pack())],
        [InlineKeyboardButton(text=MESSAGES[lang]['calendar']['year'], callback_data=PeriodCB(mode="preset", value="year").pack()),
         InlineKeyboardButton(text=MESSAGES[lang]['calendar']['your_period'], callback_data=PeriodCB(mode="custom", value="your_period").pack())],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_back'], callback_data="profile:back")]
    ])
    await logs(f"Inline check report menu successfully created for user {chat_id}", type_e="info")
    return kb

async def create_day_keyboard(year: int, month: int, chat_id: int, lang: str):
    """
    Asynchronously builds InlineKeyboardMarkup:
     1) header of weekdays (localized)
     2) grid of dates with placeholders
     3) last row of navigation << Month YYYY >>
    """
    try:
        months = MESSAGES[lang]["calendar"]["months"]
        weekdays = MESSAGES[lang]["calendar"]["weekdays"]

        builder = InlineKeyboardBuilder()

        for wd in weekdays:
            builder.button(
                text=wd,
                callback_data=DateCB(action="ignore", year=year, month=month, day=0).pack()
            )

        cal = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
        for week in cal:
            for d in week:
                if d == 0:
                    text, act = " ", "ignore"
                else:
                    text, act = str(d), "set_day"

                builder.button(
                    text=text,
                    callback_data=DateCB(action=act, year=year, month=month, day=d).pack()
                )

        builder.adjust(7)

        prev_month = month - 1 or 12
        prev_year = year - 1 if month == 1 else year
        next_month = month + 1 if month < 12 else 1
        next_year = year + 1 if month == 12 else year

        btn_prev = InlineKeyboardButton(
            text="<<",
            callback_data=DateCB(action="prev_month", year=prev_year, month=prev_month, day=0).pack()
        )
        btn_mid = InlineKeyboardButton(
            text=f"{months[month-1]} {year}",
            callback_data=DateCB(action="ignore", year=year, month=month, day=0).pack()
        )
        btn_next = InlineKeyboardButton(
            text=">>",
            callback_data=DateCB(action="next_month", year=next_year, month=next_month, day=0).pack()
        )
        btn_back = InlineKeyboardButton(
            text=MESSAGES[lang]['inline_kb']['profile']['back'],
            callback_data="profile:check_report"
        )

        builder.row(btn_prev, btn_mid, btn_next)
        builder.row(btn_back)
        await logs(f"Inline calendar successfully created for user {chat_id}", type_e="info")

        return builder.as_markup()
    except Exception as e:
        await logs(f"Error in create_day_keyboard: {e}", type_e="error")
        raise

async def get_report_inline(chat_id: int, lang: str, start_date, end_date) -> InlineKeyboardMarkup:
    try:
        async def format_date(user_date: date) -> str:
            return user_date.strftime("%Y-%m-%d") if isinstance(user_date, date) else user_date
        
        # Get user's language; if not found, use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES
        start_date = await format_date(start_date)
        end_date = await format_date(end_date)

        # Form inline menu for report
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['profile']['check_report_send_in_chat'], 
                                  callback_data=ReportСB(report_type="send_in_chat", start_date=start_date, end_date=end_date).pack())],
            #  InlineKeyboardButton(text="PDF", callback_data=ReportСB(report_type="pdf", start_date=start_date, end_date=end_date).pack())],
            # [InlineKeyboardButton(text="Excel", callback_data=ReportСB(report_type="excel", start_date=start_date, end_date=end_date).pack()),
            #  InlineKeyboardButton(text="CSV", callback_data=ReportСB(report_type="csv", start_date=start_date, end_date=end_date).pack())],
            [InlineKeyboardButton(text=MESSAGES[lang]['settings_back'], callback_data="profile:back")]
        ])
        await logs(f"Inline report menu successfully created for user {chat_id}", type_e="info")
        return kb
    except Exception as e:
        await logs(f"Error in get_report_inline: {e}", type_e="error")
        raise