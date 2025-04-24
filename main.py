import asyncio
import tracemalloc
import contextlib
import signal
import sys
import asyncio
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
from bot_instance import initialize_bots
from services.db_utils import create_connection, close_connection, create_pool, close_pool, init_db_tables
from handlers.messages import messages_router
from handlers.callbacks import callbacks_router
from handlers.commands import commands_router
from logs.log import log_info
from asgiref.wsgi import WsgiToAsgi
from app import app as flask_app
from hypercorn.asyncio import serve
from hypercorn.config import Config
from hypercorn.middleware import ProxyFixMiddleware

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
async def database_connection(bot, info_bot):
    try:
        await create_pool()
        await create_connection()
        yield
    finally:
        try:
            await close_connection()
        except Exception:
            pass
        try:
            await close_pool()
        except Exception:
            pass
        for b in (bot, info_bot):
            if hasattr(b, "session"):
                await b.session.close()

async def run_web_app(shutdown_event: asyncio.Event):
    asgi_app = WsgiToAsgi(flask_app)
    asgi_app = ProxyFixMiddleware(asgi_app, mode="legacy", trusted_hops=1)

    config = Config()
    config.bind = ["0.0.0.0:5000"]
    config.accesslog = "-"
    config.access_log_format = "%(h)s %(R)s -> %(s)s %(b)sB in %(D)sμs"

    try:
        await serve(
            asgi_app,
            config,
            shutdown_trigger=shutdown_event.wait
        )
    finally:
        await log_info("Flask/Hypercorn web server has stopped", type_e="info")

async def on_startup_bot(bot):
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands(bot)

async def main():
    tracemalloc.start()

    bot, dp, info_bot, info_dp = await initialize_bots()

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)

    async with database_connection(bot, info_bot):
        await init_db_tables()

        dp.include_router(commands_router)
        dp.include_router(callbacks_router)
        dp.include_router(messages_router)

        poll_main = asyncio.create_task(
            dp.start_polling(
                bot,
                on_startup=lambda: on_startup_bot(bot),
                handle_signals=False,
                close_bot_session=False,
            )
        )
        poll_info = asyncio.create_task(
            info_dp.start_polling(
                info_bot,
                on_startup=lambda: on_startup_bot(info_bot),
                handle_signals=False,
                close_bot_session=False,
            )
        )

        web_task = asyncio.create_task(run_web_app(shutdown_event))

        await log_info("All services started", type_e="info")

        await shutdown_event.wait()
        await log_info("Shutdown signal received", type_e="info")

        await dp.stop_polling()
        await info_dp.stop_polling()

        with contextlib.suppress(asyncio.CancelledError):
            await web_task

        await asyncio.gather(poll_main, poll_info, return_exceptions=True)

    await log_info("Cleanup finished, exiting.", type_e="info")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
    else:
        sys.exit(0)
