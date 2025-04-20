import asyncio
import tracemalloc
import contextlib
import subprocess
import signal
import sys
import asyncio
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
from bot_instance import initialize_bots
from keyboards import inline_kb, reply_kb
from services.db_utils import init_db_tables
from services.db_utils import create_connection, close_connection, create_pool
from handlers.messages import messages_router
from handlers.callbacks import callbacks_router
from handlers.commands import commands_router
from logs import log_info
from app import app
from concurrent.futures import ThreadPoolExecutor

async def set_commands(bot):
    """Set bot commands for different scopes"""
    private_commands = [
        BotCommand(command="start", description="Launch the bot"),
        BotCommand(command="help", description="Info on working with the bot")
    ]
    
    group_commands = [
        BotCommand(command="start", description="Launch the bot"),
        BotCommand(command="help", description="Info on working with the bot")
    ]
    
    await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())

@contextlib.asynccontextmanager
async def database_connection():
    try:
        await create_pool()
        await create_connection()
        yield
    finally:
        await close_connection()

async def run_web_app():
    """Run the web application"""
    cmd = ["uvicorn", "asgi:asgi_app", "--host", "127.0.0.1", "--port", "5000"]

    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, lambda: subprocess.run(cmd))

# -------------- polling bots ----------------

async def on_startup_bot(bot):
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands(bot)

async def main():
    try:
        tracemalloc.start()
        # Initialize bots with redundancy check
        bot, dp, info_bot, info_dp = await initialize_bots()
        
        # Initialize database
        async with database_connection():
            await init_db_tables()
            
            # Include routers for the main bot
            dp.include_router(commands_router)
            dp.include_router(callbacks_router)
            dp.include_router(messages_router)

            polling_main = dp.start_polling(bot, on_startup=lambda: on_startup_bot(bot))
            polling_info = info_dp.start_polling(info_bot, on_startup=lambda: on_startup_bot(info_bot))
            web_task = asyncio.create_task(run_web_app())
            
            # Start polling for both bots
            await log_info("Starting bot polling", type_e="info")
            await asyncio.gather(polling_main, polling_info, web_task)
    except Exception as e:
        print(f"Error in main function: {e}")
        raise

if __name__ == '__main__':
    def _shutdown(signum, frame):
        print("\nSIGINT/SIGTERM caught, exiting…")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program terminated by user")
