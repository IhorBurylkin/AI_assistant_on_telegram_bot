import asyncio
import tracemalloc
import contextlib
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
from bot_instance import initialize_bots
from keyboards import inline_kb, reply_kb
from services.db_utils import init_db_tables
from services.db_utils import create_connection, close_connection
from handlers.messages import messages_router
from handlers.callbacks import callbacks_router
from handlers.commands import commands_router
from logs import log_info

async def set_commands(bot):
    """Set bot commands for different scopes"""
    # Commands for private chats
    private_commands = [
        BotCommand(command="start", description="Launch the bot"),
        # BotCommand(command="settings", description="Change bot settings"),
        # BotCommand(command="limits", description="Usage limit"),
        BotCommand(command="help", description="Info on working with the bot")
    ]
    
    # Commands for group chats
    group_commands = [
        BotCommand(command="start", description="Launch the bot"),
        BotCommand(command="help", description="Info on working with the bot")
    ]
    
    await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())

@contextlib.asynccontextmanager
async def database_connection():
    try:
        await create_connection()
        yield
    finally:
        await close_connection()

async def main():
    try:
        # Initialize bots with redundancy check
        bot, dp, info_bot, info_dp = await initialize_bots()
        
        # Initialize database
        async with database_connection():
            await init_db_tables()
        
            # Set commands for the main bot
            await set_commands(bot)
            
            # Include routers for the main bot
            dp.include_router(commands_router)
            dp.include_router(callbacks_router)
            dp.include_router(messages_router)
            
            # Start polling for both bots
            await log_info("Starting bot polling", type_e="info")
            await asyncio.gather(
                dp.start_polling(bot),
                info_dp.start_polling(info_bot)
            )
    except Exception as e:
        print(f"Error in main function: {e}")
        raise

if __name__ == '__main__':
    try:
        tracemalloc.start()
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program terminated by user")