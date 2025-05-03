from aiogram import types, F, Router
from aiogram.enums import ChatType, ParseMode
from config.config import BOT_USERNAME
from keyboards.reply_kb import get_persistent_menu
from logs.log import logs
from services.handle_message import handle_message

messages_router = Router()

@messages_router.message(F.chat.type == ChatType.PRIVATE)
async def private_message_handler(message: types.Message):
    try:
        # Determine chat_id
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
        # Process other messages through handle_message function
        return_message = await handle_message(message)
        persistent_menu = await get_persistent_menu(chat_id)
        await message.answer(
            return_message,
            reply_markup=persistent_menu,
            parse_mode=ParseMode.HTML
        )
        await logs(f"Message processed for user {chat_id}", type_e="info")
    except Exception as e:
        await logs(f"Error in private_message_handler for user {chat_id}: {e}", type_e="error")

@messages_router.message(
    F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]) &
    (
        (F.text and F.text.contains(f"@{BOT_USERNAME}")) |
        (F.caption and F.caption.contains(f"@{BOT_USERNAME}")) |
        (F.content_type.in_(["voice"]))
    )
)
async def group_message_handler(message: types.Message):
    try:
        return_message = await handle_message(message)
        await message.reply(return_message, parse_mode=ParseMode.HTML)
        await logs(f"Group message processed for chat {message.chat.id}", type_e="info")
    except Exception as e:
        await logs(f"Error in group_message_handler for chat {message.chat.id}: {e}", type_e="error")