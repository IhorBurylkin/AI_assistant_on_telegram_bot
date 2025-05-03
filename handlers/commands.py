import datetime
from aiogram import types, F, Router
from aiogram.filters import Command
from aiogram.enums import ParseMode, ChatType
from aiogram.types import ReplyKeyboardRemove
from services.db_utils import read_user_all_data, write_user_to_json, user_exists
from config.config import MESSAGES, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGES, USERS_FILE_PATH, CHECKS_ANALYTICS, CHATGPT_MODEL, LIMITS, WHITE_LIST, LOGGING_SETTINGS_TO_SEND
from logs.log import logs, send_info_msg
from keyboards.reply_kb import get_persistent_menu
from keyboards.inline_kb_settings import get_settings_inline
from keyboards.inline_kb_options import get_options_inline
from keyboards.inline_kb_profile import get_profile_inline

commands_router = Router()

@commands_router.message(Command("start"))
async def send_welcome(message: types.Message):
    try:
        # Log command receipt
        await logs(f"Received /start command from user {message.from_user.id}", type_e="info")
        
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
        user_lang = message.from_user.language_code
        lang = user_lang if user_lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGES
        date_requests = datetime.date.fromisoformat("2025-03-09")
        
        # Check user existence
        chat_id_exists = await user_exists(chat_id)
        await logs(f"Checking existence of user {chat_id}: {'found' if chat_id_exists else 'not found'}", type_e="info")
        
        if chat_id_exists == False:
            if chat_id in WHITE_LIST:
                lst = "white_list" 
            else: 
                lst = "default_list"
            user_data = {
                "user_id": chat_id,
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
                "message_id": 0
            }
            await write_user_to_json(USERS_FILE_PATH, user_data)
            await logs(f"Created new user {chat_id} with chat_id {chat_id}", type_e="info")
            await send_info_msg(text=f'Type message: Info\nNew user: {user_data["username"]}\nUser ID: {user_data["chat_id"]}', message_thread_id=LOGGING_SETTINGS_TO_SEND["message_thread_id"])
        
        # Send message based on chat type
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            remove_keyboard = ReplyKeyboardRemove()
            await message.reply(MESSAGES[lang]['welcome_group'], reply_markup=remove_keyboard)
            await logs(f"Sent welcome message in group chat {chat_id}", type_e="info")
        else:
            persistent_menu = await get_persistent_menu(chat_id)
            await message.reply(MESSAGES[lang]["welcome"], reply_markup=persistent_menu)
            await logs(f"Sent welcome message in private chat {chat_id}", type_e="info")
    except Exception as e:
        await logs(f"Error in send_welcome: {e}", type_e="error")
        raise

@commands_router.message(Command("help"))
async def command_help(message: types.Message):
    try:
        # Determine chat_id based on chat type
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
        
        # Get user's language; if not found, use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Send message based on chat type
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            remove_keyboard = ReplyKeyboardRemove()
            await message.reply(MESSAGES[lang]['help_group'], reply_markup=remove_keyboard)
        else:
            persistent_menu = await get_persistent_menu(chat_id)
            await message.answer(MESSAGES[lang]['help'], reply_markup=persistent_menu)
        
        await logs(f"Command /help successfully executed for chat_id {chat_id}", type_e="info")
    except Exception as e:
        await logs(f"Error in command_help: {e}", type_e="error")
        raise

@commands_router.message(lambda message: message.text in [MESSAGES[lang]["settings_title"] for lang in SUPPORTED_LANGUAGES])
async def command_settings_reply_kb(message: types.Message):
    try:
        # Determine chat_id based on chat type
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id

        # Get inline settings menu for this user
        inline_menu = await get_settings_inline(chat_id)

        # Get user's language; if not found, use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Send message with settings menu in private chats
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.answer(MESSAGES[lang]['settings_title'], reply_markup=inline_menu)

        await logs(f"Command settings successfully executed for chat_id {chat_id}", type_e="info")
    except Exception as e:
        await logs(f"Error in command_settings: {e}", type_e="error")
        raise

@commands_router.message(lambda message: message.text in [MESSAGES[lang]["reply_kb"]["options"] for lang in SUPPORTED_LANGUAGES])
async def command_options(message: types.Message):
    try:
        # Determine chat_id based on chat type
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id

        # Get user's language; if not found, use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Get inline settings menu for this user
        inline_menu = await get_options_inline(chat_id)

        # Send message with settings menu in private chats
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.answer(MESSAGES[lang]['inline_kb']['options']['options_title'], reply_markup=inline_menu)
        
        await logs(f"Command options successfully executed for chat_id {chat_id}", type_e="info")
    except Exception as e:
        await logs(f"Error in command_options: {e}", type_e="error")
        raise

@commands_router.message(lambda message: message.text in [MESSAGES[lang]["reply_kb"]["profile"] for lang in SUPPORTED_LANGUAGES])
async def command_profile(message: types.Message):
    try:
        # Determine chat_id
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id

        # Get user data: language, web_enabled status and model
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES
        
        # Get inline profile menu for this user
        inline_menu = await get_profile_inline(chat_id)
        # Send message with profile menu in private chats
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.answer(MESSAGES[lang]['inline_kb']['profile']['profile_title'], reply_markup=inline_menu)
        await logs(f"Command profile successfully executed for chat_id {chat_id}", type_e="info")
    except Exception as e:
        await logs(f"Error in command_profile: {e}", type_e="error")
        raise