import datetime
from aiogram import types, F, Router
from aiogram.filters import Command
from aiogram.enums import ParseMode, ChatType
from aiogram.types import ReplyKeyboardRemove
from services.db_utils import read_user_all_data, update_user_data, write_user_to_json, clear_user_context, user_exists, add_columns_checks_analytics
from services.utils import time_until_midnight_utc
from config.config import MESSAGES, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGES, USERS_FILE_PATH, CHECKS_ANALYTICS, CHATGPT_MODEL, LIMITS, WHITE_LIST, LOGGING_SETTINGS_TO_SEND
from logs.log import log_info, send_info_msg
from keyboards.reply_kb import get_persistent_menu
from keyboards.inline_kb import get_settings_inline, get_profile_inline, get_options_inline

commands_router = Router()

@commands_router.message(Command("start"))
async def send_welcome(message: types.Message):
    try:
        # Log command receipt
        await log_info(f"Received /start command from user {message.from_user.id}", type_e="info")
        
        user_id = message.from_user.id
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
        user_lang = message.from_user.language_code
        lang = user_lang if user_lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGES
        date_requests = datetime.date.fromisoformat("2025-03-09")
        
        # Check user existence
        user_id_exists = await user_exists(user_id)
        await log_info(f"Checking existence of user {user_id}: {'found' if user_id_exists else 'not found'}", type_e="info")
        
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
                "message_id": 0
            }
            await write_user_to_json(USERS_FILE_PATH, user_data)
            await log_info(f"Created new user {user_id} with chat_id {chat_id}", type_e="info")
            await send_info_msg(text=f'Type message: Info\nNew user: {user_data["username"]}\nUser ID: {user_data["user_id"]}', message_thread_id=LOGGING_SETTINGS_TO_SEND["message_thread_id"])
        
        # Send message based on chat type
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            remove_keyboard = ReplyKeyboardRemove()
            await message.reply(MESSAGES[lang]['welcome_group'], reply_markup=remove_keyboard)
            await log_info(f"Sent welcome message in group chat {chat_id}", type_e="info")
        else:
            persistent_menu = await get_persistent_menu(chat_id)
            await message.reply(MESSAGES[lang]["welcome"], reply_markup=persistent_menu)
            await log_info(f"Sent welcome message in private chat {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Error in send_welcome: {e}", type_e="error")
        raise

@commands_router.message(Command("setmodel"))
async def cmd_set_model(message: types.Message):
    try:
        # Determine chat_id based on chat type
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id

        # Get user's language and web_enabled status
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        web_enabled = user_data.get("web_enabled")
        # If language not found, use default value (e.g., "en")
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

        await log_info(f"ChatGPT model changed to: {CHATGPT_MODEL}", type_e="info")

        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.reply(
                MESSAGES[lang]['model_changed'].format(CHATGPT_MODEL),
                reply_markup=await get_persistent_menu(chat_id)
            )
        await update_user_data(chat_id, "model", CHATGPT_MODEL)
    except Exception as e:
        await log_info(f"Error in cmd_set_model: {e}", type_e="error")
        raise

@commands_router.message(Command("settings"))
async def command_settings(message: types.Message):
    try:
        # Determine chat_id: in private chat use message.chat.id, otherwise - message.from_user.id
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
        
        # Get inline settings menu for this user
        inline_menu = await get_settings_inline(chat_id)
        
        # Read user's language; if not found, use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES
        
        # If chat is not a group, send message with settings menu
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.answer(MESSAGES[lang]['settings_title'], reply_markup=inline_menu)
        
        await log_info(f"Settings menu sent for user {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Error in command_settings: {e}", type_e="error")
        raise

@commands_router.message(Command("clearcontext"))
async def command_clear_context(message: types.Message):
    try:
        # Determine chat_id based on chat type
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
        
        # Get user's language; if language not found, use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Clear user's context in JSON file
        await clear_user_context(chat_id)
        await log_info(f"Context for user {chat_id} successfully cleared.", type_e="info")
        
        # Send confirmation message for private chats
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            persistent_menu = await get_persistent_menu(chat_id)
            await message.answer(
                f"<b>System: </b>{MESSAGES[lang]['context_cleared']}",
                reply_markup=persistent_menu,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        await log_info(f"Error in command_clear_context: {e}", type_e="error")
        raise

@commands_router.message(Command("limits"))
async def command_limits(message: types.Message):
    try:
        # Calculate time until midnight
        remaining_time = await time_until_midnight_utc()
        total_seconds = int(remaining_time.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        formatted_time = f"{hours:02d}:{minutes:02d}"

        # Determine chat_id and get user's language
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
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

        # Send message based on chat type
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.answer(message_to_send)
        else:
            persistent_menu = await get_persistent_menu(chat_id)
            await message.answer(message_to_send, reply_markup=persistent_menu)

        await log_info(f"Command /limits successfully executed for chat_id {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Error in command_limits: {e}", type_e="error")
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
        
        await log_info(f"Command /help successfully executed for chat_id {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Error in command_help: {e}", type_e="error")
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

        await log_info(f"Command settings successfully executed for chat_id {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Error in command_settings: {e}", type_e="error")
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
        
        await log_info(f"Command options successfully executed for chat_id {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Error in command_options: {e}", type_e="error")
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
        await log_info(f"Command profile successfully executed for chat_id {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Error in command_profile: {e}", type_e="error")
        raise