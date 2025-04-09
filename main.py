import asyncio
import tracemalloc
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
from bot import dp, bot, info_bot, dp_info_bot
from keyboards import inline_kb, reply_kb
from services.db_utils import init_db_tables
from services.db_utils import create_connection, close_connection
from handlers.messages import messages_router
from handlers.callbacks import callbacks_router
from handlers.commands import commands_router

async def set_commands():
    # Команды для личных чатов
    private_commands = [
        BotCommand(command="start", description="Launch the bot"),
        # BotCommand(command="settings", description="Change bot settings"),
        # BotCommand(command="limits", description="Usage limit"),
        BotCommand(command="help", description="Info on working withe the bot")
    ]
    
    # Команды для групповых чатов
    group_commands = [
        BotCommand(command="start", description="Launch the bot"),
        BotCommand(command="help", description="Info on working withe the bot")
    ]
    
    await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())

async def main():
    try:
        await create_connection()
        await init_db_tables()
        await set_commands()
        dp.include_router(commands_router)
        dp.include_router(callbacks_router)
        dp.include_router(messages_router)
        await asyncio.gather(
            dp.start_polling(bot),
            dp_info_bot.start_polling(info_bot)
        )
    finally:
        await close_connection()

if __name__ == '__main__':
    try:
        tracemalloc.start()
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Программа завершена пользователем")