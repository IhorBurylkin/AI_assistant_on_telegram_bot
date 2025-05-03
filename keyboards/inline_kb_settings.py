from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.db_utils import read_user_all_data
from config.config import DEFAULT_LANGUAGES, MESSAGES, MODELS, MODELS_FOR_MENU, LIMITS, WHITE_LIST, WEBAPP_URL
from logs.log import logs

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
    await logs(f"Inline settings menu successfully created for user {chat_id}", type_e="info")
    return kb

async def get_model_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    # Get current model and web_enabled status
    set_model = user_data.get("model")

    groups = [
        MODELS[0:3],
        MODELS[3:5],
        MODELS[5:7],
    ]
    label_groups = [
        MODELS_FOR_MENU[0:3],
        MODELS_FOR_MENU[3:5],
        MODELS_FOR_MENU[5:7],
    ]

    # Create buttons for model selection
    inline_rows = []
    for model_group, label_group in zip(groups, label_groups):
        row = []
        for option, label in zip(model_group, label_group):
            icon = "✅" if set_model == option else ""
            row.append(InlineKeyboardButton(
                text=f"{label} {icon}".strip(),
                callback_data=f"model:{option}"
            ))
        inline_rows.append(row)

    # Add "Back" button
    inline_rows.append([InlineKeyboardButton(
        text=MESSAGES[lang]['settings_back'], callback_data="settings:back"
    )])

    await logs(f"Inline model selection menu successfully created for user {chat_id}", type_e="info")
    return InlineKeyboardMarkup(inline_keyboard=inline_rows)

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
    
    await logs(f"Inline 'answer' menu successfully created for user {chat_id}", type_e="info")
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
            return 4 # default value

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

    await logs(f"Inline roles menu successfully created for user {chat_id}", type_e="info")
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_user_role_inline(chat_id: int) -> InlineKeyboardMarkup:
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=MESSAGES[lang]['settings_back'],
            callback_data="settings:role"
        )]
    ])

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
    async def with_checkmark(value, current):
        return f"{value} ✅" if value.lower() == current.lower() else value
    # Form inline buttons for each generation option

    # Resolution buttons
    res_buttons = [
        InlineKeyboardButton(
            text=await with_checkmark(val, current_resolution),
            callback_data=f"generation:resolution:{val}"
        )
        for val in resolutions
    ]

    # Quality buttons
    qual_buttons = [
        InlineKeyboardButton(
            text=await with_checkmark(val, current_quality),
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

    await logs(f"Inline 'generation' menu successfully created for user {chat_id}", type_e="info")
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
    await logs(f"Inline languages menu successfully created for user {chat_id}", type_e="info")
    return kb