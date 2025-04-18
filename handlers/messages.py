import json
from aiogram import types, F, Router
from aiogram.enums import ChatType, ParseMode
from aiogram.enums.content_type import ContentType
from aiogram.types import Message
from services.db_utils import update_user_data, read_user_all_data
from config import BOT_USERNAME, DEFAULT_LANGUAGES
from handlers.callbacks import get_persistent_menu
from logs import log_info
from services.user_service import handle_message

messages_router = Router()

@messages_router.message(F.chat.type == ChatType.PRIVATE)
async def private_message_handler(message: types.Message):
    try:
        # Determine chat_id
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id

        if message.reply_to_message:
            # Get user's language; if not found, use default value
            user_data = await read_user_all_data(chat_id)
            lang = user_data.get("language")
            if not lang:
                lang = DEFAULT_LANGUAGES

            # Extract role from message text, removing extra spaces
            custom_role = message.text.strip()

            # Update user data with new role
            await update_user_data(chat_id, "role", custom_role)

            # Get persistent menu for user
            persistent_menu = await get_persistent_menu(chat_id)

            # Form confirmation message
            confirmation_text = (
                f"<b>System: </b>Your role has been set: {custom_role}"
                if lang == "ru"
                else f"<b>System: </b>Your role has been set: {custom_role}"
            )
            await message.answer(
                text=confirmation_text,
                reply_markup=persistent_menu,
                parse_mode=ParseMode.HTML
            )
            await log_info(f"User role {chat_id} updated to: {custom_role}", type_e="info")
        else:
            # Process other messages through handle_message function
            return_message = await handle_message(message)
            # Assuming handle_message returns a tuple (message, chat_id)
            message_to, new_chat_id = return_message[0], return_message[1]
            persistent_menu = await get_persistent_menu(new_chat_id)
            await message.answer(
                message_to,
                reply_markup=persistent_menu,
                parse_mode=ParseMode.HTML
            )
            await log_info(f"Message processed for user {new_chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Error in private_message_handler for user {chat_id}: {e}", type_e="error")
        raise

@messages_router.message(
    F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]) &
    (
        (F.text and F.text.contains(f"@{BOT_USERNAME}")) |
        (F.caption and F.caption.contains(f"@{BOT_USERNAME}")) |
        (F.content_type.in_(["voice", "audio"]))
    )
)
async def group_message_handler(message: types.Message):
    try:
        return_message = await handle_message(message)
        message_to = return_message[0]
        await message.reply(message_to, parse_mode=ParseMode.HTML)
        await log_info(f"Group message processed for chat {message.chat.id}", type_e="info")
    except Exception as e:
        await log_info(f"Error in group_message_handler for chat {message.chat.id}: {e}", type_e="error")
        raise

@messages_router.message(F.content_type == ContentType.WEB_APP_DATA)
async def handle_web_app_data(message: Message):
    try:
        raw = message.web_app_data.data
        data = json.loads(raw)
        text = "✅ Данные приняты:\n" + json.dumps(data, ensure_ascii=False, indent=2)
        print(text)
        await log_info(f"Web App Data processed for user {message.from_user.id}", type_e="info")
    except Exception as e:
        await log_info(f"Error in web_app_data_handler for user {message.from_user.id}: {e}", type_e="error")
        raise