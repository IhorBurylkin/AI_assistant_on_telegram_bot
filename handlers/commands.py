import datetime
from aiogram import types, F, Router
from aiogram.filters import Command
from aiogram.enums import ParseMode, ChatType
from aiogram.types import ReplyKeyboardRemove
from services.db_utils import read_user_all_data, update_user_data, write_user_to_json, clear_user_context, user_exists
from services.utils import time_until_midnight_utc, send_info_msg
from config import MESSAGES, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGES, USERS_FILE_PATH, CHATGPT_MODEL, LIMITS, WHITE_LIST, LOGGING_SETTINGS_TO_SEND
from logs import log_info
from handlers.callbacks import get_persistent_menu, get_settings_inline, get_options_inline, get_profile_inline

commands_router = Router()

@commands_router.message(Command("start"))
async def send_welcome(message: types.Message):
    try:
        # Логирование получения команды
        await log_info(f"Получена команда /start от пользователя {message.from_user.id}", type_e="info")
        
        user_id = message.from_user.id
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
        user_lang = message.from_user.language_code
        lang = user_lang if user_lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGES
        date_requests = datetime.date.fromisoformat("2025-03-09")
        
        # Проверяем наличие пользователя
        user_id_exists = await user_exists(user_id)
        await log_info(f"Проверка существования пользователя {user_id}: {'найден' if user_id_exists else 'не найден'}", type_e="info")
        
        if user_id_exists == False:
            if user_id in WHITE_LIST:
                lst = "white_list" 
            else: 
                lst = "default_list"
            user_data = {
                "user_id": user_id,
                "username": message.from_user.username,
                "first_name": message.from_user.first_name,
                "last_name": message.from_user.last_name,
                "language": message.from_user.language_code,
                "context_enabled": False,
                "web_enabled": False,
                "set_answer": "minimal",
                "set_answer_temp": 0.1, 
                "set_answer_top_p": 0.9,
                "model": "gpt-4o-mini",
                "tokens": 0,
                "requests": 0,
                "date_requests": date_requests,
                "role": MESSAGES[lang]['set_role_system'][0],
                "have_tokens": 1000,
                "in_limit_list": lst,
                "resolution": "1024x1024",
                "quality": "standard",
            }
            await write_user_to_json(USERS_FILE_PATH, user_data)
            await log_info(f"Создан новый пользователь {user_id} с chat_id {chat_id}", type_e="info")
            await send_info_msg(text=f'Type message: Info\nNew user: {user_data["username"]}\nUser ID: {user_data["user_id"]}', message_thread_id=LOGGING_SETTINGS_TO_SEND["message_thread_id"])
        
        # Отправка сообщения в зависимости от типа чата
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            remove_keyboard = ReplyKeyboardRemove()
            await message.reply(MESSAGES[lang]['welcome_group'], reply_markup=remove_keyboard)
            await log_info(f"Отправлено приветственное сообщение в групповом чате {chat_id}", type_e="info")
        else:
            persistent_menu = await get_persistent_menu(chat_id)
            await message.reply(MESSAGES[lang]["welcome"], reply_markup=persistent_menu)
            await log_info(f"Отправлено приветственное сообщение в приватном чате {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка в send_welcome: {e}", type_e="error")
        raise

@commands_router.message(Command("setmodel"))
async def cmd_set_model(message: types.Message):
    try:
        # Определяем chat_id в зависимости от типа чата
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id

        # Получаем язык пользователя и статус web_enabled
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        web_enabled = user_data.get("web_enabled")
        # Если язык не найден, используем значение по умолчанию (например, "en")
        if not lang:
            lang = DEFAULT_LANGUAGES

        global CHATGPT_MODEL
        parts = message.text.split()
        if len(parts) < 2:
            reply_text = (
                MESSAGES[lang]['set_model_instructions'] + "\n" +
                MESSAGES[lang]['model_changed'].format(CHATGPT_MODEL)
            )
            await message.reply(reply_text, reply_markup=await get_persistent_menu(chat_id))
            return

        new_model = parts[1]
        CHATGPT_MODEL = new_model

        if web_enabled:
            if CHATGPT_MODEL == "gpt-4o-mini":
                CHATGPT_MODEL = "gpt-4o-mini-search-preview"
            elif CHATGPT_MODEL == "gpt-4o":
                CHATGPT_MODEL = "gpt-4o-search-preview"

        await log_info(f"Модель ChatGPT изменена на: {CHATGPT_MODEL}", type_e="info")

        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.reply(
                MESSAGES[lang]['model_changed'].format(CHATGPT_MODEL),
                reply_markup=await get_persistent_menu(chat_id)
            )
        await update_user_data(chat_id, "model", CHATGPT_MODEL)
    except Exception as e:
        await log_info(f"Ошибка в cmd_set_model: {e}", type_e="error")
        raise

@commands_router.message(Command("settings"))
async def command_settings(message: types.Message):
    try:
        # Определяем chat_id: в приватном чате берем message.chat.id, иначе - message.from_user.id
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
        
        # Получаем inline-меню настроек для данного пользователя
        inline_menu = await get_settings_inline(chat_id)
        
        # Читаем язык пользователя; если не найден, используем значение по умолчанию
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES
        
        # Если чат не является групповым, отправляем сообщение с меню настроек
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.answer(MESSAGES[lang]['settings_title'], reply_markup=inline_menu)
        
        await log_info(f"Меню настроек отправлено для пользователя {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка в command_settings: {e}", type_e="error")
        raise

@commands_router.message(Command("clearcontext"))
async def command_clear_context(message: types.Message):
    try:
        # Определяем chat_id в зависимости от типа чата
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
        
        # Получаем язык пользователя; если язык не найден, используем значение по умолчанию
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Очищаем контекст пользователя в файле JSON
        await clear_user_context(chat_id)
        await log_info(f"Контекст для пользователя {chat_id} успешно очищен.", type_e="info")
        
        # Отправляем подтверждающее сообщение для приватных чатов
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            persistent_menu = await get_persistent_menu(chat_id)
            await message.answer(
                f"<b>System: </b>{MESSAGES[lang]['context_cleared']}",
                reply_markup=persistent_menu,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        await log_info(f"Ошибка в command_clear_context: {e}", type_e="error")
        raise

@commands_router.message(Command("limits"))
async def command_limits(message: types.Message):
    try:
        # Вычисляем время до полуночи
        remaining_time = await time_until_midnight_utc()
        total_seconds = int(remaining_time.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        formatted_time = f"{hours:02d}:{minutes:02d}"

        # Определяем chat_id и получаем язык пользователя
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Получаем количество запросов и токенов, список лимитов и категорию
        tokens = user_data.get("tokens")
        requests = user_data.get("requests")
        which_list = user_data.get("in_limit_list")

        lost_req = LIMITS[which_list][0] - requests
        lost_tokens = LIMITS[which_list][1] - tokens

        # Формируем сообщение с лимитами
        if chat_id in WHITE_LIST:
            message_to_send = (
                f"{MESSAGES[lang]['limits'].format(lost_req, lost_tokens, formatted_time)}\n\n"
                f"{MESSAGES[lang]['white_list']}"
            )
        else:
            message_to_send = MESSAGES[lang]['limits'].format(lost_req, lost_tokens, formatted_time)

        # Отправляем сообщение в зависимости от типа чата
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.answer(message_to_send)
        else:
            persistent_menu = await get_persistent_menu(chat_id)
            await message.answer(message_to_send, reply_markup=persistent_menu)

        await log_info(f"Команда /limits успешно выполнена для chat_id {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка в command_limits: {e}", type_e="error")
        raise

@commands_router.message(Command("help"))
async def command_help(message: types.Message):
    try:
        # Определяем chat_id в зависимости от типа чата
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
        
        # Получаем язык пользователя; если не найден, используем значение по умолчанию
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Отправляем сообщение в зависимости от типа чата
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            remove_keyboard = ReplyKeyboardRemove()
            await message.reply(MESSAGES[lang]['help_group'], reply_markup=remove_keyboard)
        else:
            persistent_menu = await get_persistent_menu(chat_id)
            await message.answer(MESSAGES[lang]['help'], reply_markup=persistent_menu)
        
        await log_info(f"Команда /help успешно выполнена для chat_id {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка в command_help: {e}", type_e="error")
        raise

@commands_router.message(lambda message: message.text in [MESSAGES[lang]["settings_title"] for lang in SUPPORTED_LANGUAGES])
async def command_settings_reply_kb(message: types.Message):
    try:
        # Определяем chat_id в зависимости от типа чата
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id

        # Получаем inline-меню настроек для данного пользователя
        inline_menu = await get_settings_inline(chat_id)

        # Получаем язык пользователя; если не найден, используем значение по умолчанию
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Отправляем сообщение с меню настроек в приватных чатах
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.answer(MESSAGES[lang]['settings_title'], reply_markup=inline_menu)

        await log_info(f"Команда settings успешно выполнена для chat_id {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка в command_settings: {e}", type_e="error")
        raise

@commands_router.message(lambda message: message.text in [MESSAGES[lang]["reply_kb"]["options"] for lang in SUPPORTED_LANGUAGES])
async def command_options(message: types.Message):
    try:
        # Определяем chat_id в зависимости от типа чата
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id

        # Получаем язык пользователя; если не найден, используем значение по умолчанию
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Получаем inline-меню настроек для данного пользователя
        inline_menu = await get_options_inline(chat_id)

        # Отправляем сообщение с меню настроек в приватных чатах
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.answer(MESSAGES[lang]['inline_kb']['options']['options_title'], reply_markup=inline_menu)
        
        await log_info(f"Команда options успешно выполнена для chat_id {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка в command_options: {e}", type_e="error")
        raise

@commands_router.message(lambda message: message.text in [MESSAGES[lang]["reply_kb"]["profile"] for lang in SUPPORTED_LANGUAGES])
async def command_profile(message: types.Message):
    try:
        # Определяем chat_id
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id

        # Получаем данные пользователя: язык, статус web_enabled и модель
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES
        
        # Получаем inline-меню профиля для данного пользователя
        inline_menu = await get_profile_inline(chat_id)
        # Отправляем сообщение с меню профиля в приватных чатах
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.answer(MESSAGES[lang]['inline_kb']['profile']['profile_title'], reply_markup=inline_menu)
        await log_info(f"Команда profile успешно выполнена для chat_id {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка в command_profile: {e}", type_e="error")
        raise