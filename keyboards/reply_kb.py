from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from services.db_utils import read_user_all_data
from config import DEFAULT_LANGUAGES, MESSAGES
from logs import log_info

async def get_persistent_menu(chat_id: int, user_settings=None) -> ReplyKeyboardMarkup:
    try:
        # Получаем язык пользователя; если не найден, используем значение по умолчанию
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # # Если пользовательские настройки не переданы, читаем значение web_enabled из базы данных
        # if user_settings is None:
        #     user_settings = user_data.get("web_enabled")

        # # Определяем текст кнопки для web_enabled
        # button_web = "🌐 - ✅" if user_settings else "🌐 - ❌"

        # Формируем постоянное меню
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
        
        await log_info(f"Persistent menu сформировано для пользователя {chat_id}", type_e="info")
        return menu
    except Exception as e:
        await log_info(f"Ошибка в get_persistent_menu для пользователя {chat_id}: {e}", type_e="error")
        # В случае ошибки возвращаем пустое меню
        return ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True, one_time_keyboard=False, is_persistent=True)