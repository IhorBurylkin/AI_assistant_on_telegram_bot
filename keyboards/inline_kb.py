import calendar
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from services.db_utils import read_user_all_data
from config import DEFAULT_LANGUAGES, MESSAGES, MODELS, MODELS_FOR_MENU, LIMITS, WHITE_LIST, WEBAPP_URL
from logs import log_info
from services.utils import time_until_midnight_utc
from datetime import datetime

async def get_settings_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES
    
    # Get context state and determine icon
    context_enabled = user_data.get("context_enabled")
    context_icon = "✅" if context_enabled else "❌"
    # Get web_enabled state
    web_enabled = user_data.get("web_enabled")
    web_icon = "✅" if web_enabled else "❌"
    
    # Form inline settings menu
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_set_model'], callback_data="settings:set_model")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_context'].format(context_icon), callback_data="settings:toggle_context")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_web_search'].format(web_icon), callback_data="settings:web_enabled")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_answer'], callback_data="settings:set_answer")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_role'], callback_data="settings:role")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_generation'], callback_data="settings:generation")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_interface_language'], callback_data="settings:interface_language")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_close'], callback_data="settings:close")]
    ])
    await log_info(f"Inline settings menu successfully created for user {chat_id}", type_e="info")
    return kb

async def get_options_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    # Form inline options menu
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['clear_context'], callback_data="options:clear_context")],
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['generate_image'], callback_data="options:generate_image")],
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['add_check'], callback_data="options:add_check")],
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['close'], callback_data="settings:close")]
    ])
    await log_info(f"Inline options menu successfully created for user {chat_id}", type_e="info")
    return kb

async def get_profile_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    # Form inline profile menu
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['profile']['limits'], callback_data="profile:usage_limit")],
        #[InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['profile']['calendar'], callback_data="profile:calendar")],
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['profile']['close'], callback_data="settings:close")]
    ])
    await log_info(f"Inline profile menu successfully created for user {chat_id}", type_e="info")
    return kb

async def get_model_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    # Get current model and web_enabled status
    set_model = user_data.get("model")
    web_enabled = user_data.get("web_enabled")

    buttons = []

    # Adjust model if web_enabled is on
    if web_enabled:
        if set_model == "gpt-4o-mini-search-preview":
            set_model = "gpt-4o-mini"
        elif set_model == "gpt-4o-search-preview":
            set_model = "gpt-4o"

    # Create buttons for model selection
    for i, option in enumerate(MODELS):
        icon = "✅" if set_model == option else ""
        buttons.append([InlineKeyboardButton(
            text=f"{MODELS_FOR_MENU[i]} {icon}",
            callback_data=f"model:{option}"
        )])

    # Add "Back" button
    buttons.append([InlineKeyboardButton(
        text=MESSAGES[lang]['settings_back'], callback_data="settings:back"
    )])

    await log_info(f"Inline model selection menu successfully created for user {chat_id}", type_e="info")
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_answer_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    # Get set answer value
    set_answer = user_data.get("set_answer")
    
    # Define answer options and form buttons
    options = ["minimal", "moderate", "increased", "maximum"]
    buttons = []
    for i, option in enumerate(options):
        icon = "✅" if set_answer == option else ""
        buttons.append([InlineKeyboardButton(
            text=f"{MESSAGES[lang]['set_answer'][i]} {icon}",
            callback_data=f"answer:{option}"
        )])
    
    # Add "Back" button
    buttons.append([InlineKeyboardButton(
        text=MESSAGES[lang]['settings_back'],
        callback_data="settings:back"
    )])
    
    await log_info(f"Inline 'answer' menu successfully created for user {chat_id}", type_e="info")
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_role_inline(chat_id: int) -> InlineKeyboardMarkup:

    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    # Get user role and role lists from messages
    role_from_db = user_data.get("role")
    roles_list = MESSAGES[lang]['set_role']
    roles_system_list = MESSAGES[lang]['set_role_system']

    # Asynchronous function to get current role index
    async def get_current_role(text: str) -> int:
        try:
            return roles_system_list.index(text)
        except ValueError:
            return 4  # default value

    current_role_index = await get_current_role(role_from_db)
    current_role = roles_list[current_role_index]

    # Form inline buttons for each role
    buttons = []
    for role_name in roles_list:
        icon = "✅" if role_name == current_role else ""
        buttons.append([InlineKeyboardButton(
            text=f"{role_name} {icon}",
            callback_data=f"role:{role_name}"
        )])

    # Add "Back" button
    buttons.append([InlineKeyboardButton(
        text=MESSAGES[lang]['settings_back'],
        callback_data="settings:back"
    )])

    await log_info(f"Inline roles menu successfully created for user {chat_id}", type_e="info")
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_generation_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    resolutions = MESSAGES[lang]["set_resolution"]
    qualities = MESSAGES[lang]["set_quality"]

    # Get current generation value
    current_resolution = user_data.get("resolution", resolutions[0])
    quality_code = user_data.get("quality", "standard")  # DB value: "standard" or "hd"

    # Mapping for user display
    quality_map = {
        "standard": qualities[0],  # "Normal"
        "hd": qualities[1]         # "High"
    }
    current_quality = quality_map.get(quality_code, qualities[0])

    # Helper function to add checkmarks
    def with_checkmark(value, current):
        return f"{value} ✅" if value.lower() == current.lower() else value
    # Form inline buttons for each generation option

    # Resolution buttons
    res_buttons = [
        InlineKeyboardButton(
            text=with_checkmark(val, current_resolution),
            callback_data=f"generation:resolution:{val}"
        )
        for val in resolutions
    ]

    # Quality buttons
    qual_buttons = [
        InlineKeyboardButton(
            text=with_checkmark(val, current_quality),
            callback_data=f"generation:quality:{val.lower()}"
        )
        for val in qualities
    ]

    # Add "Back" button
    back_button = [
        InlineKeyboardButton(
            text=MESSAGES[lang]['settings_back'],
            callback_data="settings:back"
        )
    ]
    # Form inline keyboard
    inline_keyboard = [
        res_buttons,
        qual_buttons,
        back_button
    ]

    await log_info(f"Inline 'generation' menu successfully created for user {chat_id}", type_e="info")
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

async def get_language_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")],
        [InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="lang:de"),
            InlineKeyboardButton(text="🇪🇸 Español", callback_data="lang:es")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_back'], callback_data="settings:back")]
    ])
    await log_info(f"Inline languages menu successfully created for user {chat_id}", type_e="info")
    return kb

async def get_generate_image_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['back'], callback_data="options:back")]
    ])
    await log_info(f"Inline image generation menu successfully created for user {chat_id}", type_e="info")
    return kb

async def get_add_check_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['manual_entry'], web_app=WebAppInfo(url=WEBAPP_URL)),
        InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['back'], callback_data="options:back")]
    ])
    await log_info(f"Inline add check menu successfully created for user {chat_id}", type_e="info")
    return kb

async def get_add_check_accept_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data="options:accept:"),
        InlineKeyboardButton(text="❌", callback_data="options:cancel")],
    ])
    await log_info(f"Inline check confirmation menu successfully created for user {chat_id}", type_e="info")
    return kb

async def get_continue_add_check_accept_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data="options:add_check:"),
        #InlineKeyboardButton(text="📝", web_app=WEBAPP_URL),
        InlineKeyboardButton(text="❌", callback_data="options:close")],
    ])
    await log_info(f"Inline continue check confirmation menu successfully created for user {chat_id}", type_e="info")
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

        await log_info(f"Inline limits successfully executed for chat_id {chat_id}", type_e="info")
        return kb, message_to_send
    except Exception as e:
        await log_info(f"Error in command_limits: {e}", type_e="error")
        raise

async def get_calendar(chat_id: int) -> InlineKeyboardMarkup:
    """
    Generate a calendar for the user.
    """
    now = datetime.now()
    year = now.year
    month = now.month

    keyboard = InlineKeyboardMarkup(row_width=7)

    prev_year = year - 1
    next_year = year + 1
    row_year = [
        InlineKeyboardButton(text="««", callback_data=f"CHANGE_YEAR:{prev_year}"),
        InlineKeyboardButton(text=str(year), callback_data="IGNORE"),
        InlineKeyboardButton(text="»»", callback_data=f"CHANGE_YEAR:{next_year}")
    ]
    keyboard.row(*row_year)

    if month == 1:
        prev_month = 12
        prev_month_year = year - 1
    else:
        prev_month = month - 1
        prev_month_year = year

    if month == 12:
        next_month = 1
        next_month_year = year + 1
    else:
        next_month = month + 1
        next_month_year = year

    row_month = [
        InlineKeyboardButton(text="<", callback_data=f"CHANGE_MONTH:{prev_month_year}-{prev_month:02d}"),
        InlineKeyboardButton(text=calendar.month_name[month], callback_data="IGNORE"),
        InlineKeyboardButton(text=">", callback_data=f"CHANGE_MONTH:{next_month_year}-{next_month:02d}")
    ]
    keyboard.row(*row_month)

    header = InlineKeyboardButton(text=f"{calendar.month_name[month]} {year}", callback_data="IGNORE")
    keyboard.add(header)

    days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    keyboard.row(*[InlineKeyboardButton(text=day, callback_data="IGNORE") for day in days])

    month_calendar = calendar.monthcalendar(year, month)
    for week in month_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="IGNORE"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                row.append(InlineKeyboardButton(text=str(day), callback_data=f"DAY:{date_str}"))
        keyboard.row(*row)

    return keyboard