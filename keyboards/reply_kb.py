from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from services.db_utils import read_user_all_data
from config import DEFAULT_LANGUAGES, MESSAGES
from logs import log_info

async def get_persistent_menu(chat_id: int, user_settings=None) -> ReplyKeyboardMarkup:
    try:
        # Get user's language; if not found, use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # # If user settings not passed, read web_enabled value from database
        # if user_settings is None:
        #     user_settings = user_data.get("web_enabled")

        # # Define button text for web_enabled
        # button_web = "🌐 - ✅" if user_settings else "🌐 - ❌"

        # Form persistent menu
        menu = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=MESSAGES[lang]['reply_kb']['settings']),
                    KeyboardButton(text=MESSAGES[lang]['reply_kb']['options']),
                    KeyboardButton(text=MESSAGES[lang]['reply_kb']['profile']),
                ]
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
            is_persistent=True
        )
        
        await log_info(f"Persistent menu created for user {chat_id}", type_e="info")
        return menu
    except Exception as e:
        await log_info(f"Error in get_persistent_menu for user {chat_id}: {e}", type_e="error")
        # In case of error return empty menu
        return ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True, one_time_keyboard=False, is_persistent=True)