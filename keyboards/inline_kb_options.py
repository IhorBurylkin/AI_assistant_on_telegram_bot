from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.db_utils import read_user_all_data
from config.config import DEFAULT_LANGUAGES, MESSAGES, WEBAPP_URL
from aiogram.types import WebAppInfo
from logs.log import logs
from urllib.parse import urlencode

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
    await logs(f"Inline options menu successfully created for user {chat_id}", type_e="info")
    return kb

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

    await logs(f"Inline 'generation' menu successfully created for user {chat_id}", type_e="info")
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

async def get_generate_image_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['back'], callback_data="options:back")]
    ])
    await logs(f"Inline image generation menu successfully created for user {chat_id}", type_e="info")
    return kb

async def get_add_check_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    webapp_url_with_chat_id = f"{WEBAPP_URL}check_form/api?chat_id={chat_id}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['manual_entry'], web_app=WebAppInfo(url=webapp_url_with_chat_id)),
        InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['back'], callback_data="options:back")]
    ])
    await logs(f"Inline add check menu successfully created for user {chat_id}", type_e="info")
    return kb

async def get_add_check_accept_inline(chat_id: int, user_text_input: list = None) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    date, time, store, check_id, product, total, currency = user_text_input
    params = {
        'date': date,
        'time': time,
        'store': store,
        'check_id': check_id,
        'product': product,
        'total': total,
        'currency': currency,
        'chat_id': chat_id,
    }
    query_string = urlencode(params)
    web_url_with_all_data = f"{WEBAPP_URL}check_form/api?{query_string}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data="options:accept:"),
        InlineKeyboardButton(text="📝", web_app=WebAppInfo(url=web_url_with_all_data)),
        InlineKeyboardButton(text="❌", callback_data="options:cancel")],
    ])
    await logs(f"Inline check confirmation menu successfully created for user {chat_id}", type_e="info")
    return kb

async def get_continue_add_check_accept_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Get user's language; if not found, use default value
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data="options:add_check:"),
        InlineKeyboardButton(text="❌", callback_data="options:close")],
    ])
    await logs(f"Inline continue check confirmation menu successfully created for user {chat_id}", type_e="info")
    return kb