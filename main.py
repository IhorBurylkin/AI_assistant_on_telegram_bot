import asyncio
import tracemalloc
import contextlib
import signal
import sys
import os
import asyncio
import traceback
import threading
import django
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
from services import sysmonitoring, telegram_bot_init, db_utils
from handlers import callbacks_settings, callbacks_options, callbacks_profile, commands, messages
from logs.log import logs
from pathlib import Path
from hypercorn.asyncio import serve
from hypercorn.config import Config
from hypercorn.middleware import ProxyFixMiddleware
from config.config import DEBUG_WEBAPP

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
        await db_utils.create_pool()
        await db_utils.create_connection()
        yield
    finally:
        try:
            await db_utils.close_connection()
        except Exception:
            pass
        try:
            await db_utils.close_pool()
        except Exception:
            pass
        for b in (bot, info_bot):
            if hasattr(b, "session"):
                await b.session.close()

async def run_web_app(shutdown_event: asyncio.Event):
    BASE_DIR = Path(__file__).resolve().parent
    DJANGO_PROJECT_ROOT = BASE_DIR / "webapp"
    sys.path.insert(0, str(DJANGO_PROJECT_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")
    await logs(f"Web server has Debug mode: {DEBUG_WEBAPP}", type_e="info")
    django.setup()

    from webapp.asgi import application
    asgi_app = ProxyFixMiddleware(application, mode="legacy", trusted_hops=1)

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
        await logs("Django/Hypercorn web server has stopped", type_e="info")

async def on_startup_bot(bot):
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands(bot)

async def main():
    tracemalloc.start()

    bot, dp, info_bot, info_dp = await telegram_bot_init.initialize_bots()

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()
    if sys.platform == "win32":
        signal.signal(signal.SIGINT,  lambda *_: shutdown_event.set())
        signal.signal(signal.SIGTERM, lambda *_: shutdown_event.set())
    else:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, shutdown_event.set)
            except (NotImplementedError, ValueError):
                pass

    async with database_connection(bot, info_bot):
        await db_utils.init_db_tables()

        dp.include_router(commands.commands_router)
        dp.include_router(callbacks_settings.callbacks_settings_router)
        dp.include_router(callbacks_options.callbacks_options_router)
        dp.include_router(callbacks_profile.callbacks_profile_router)
        dp.include_router(messages.messages_router)

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

        th = threading.Thread(
        target=sysmonitoring.main,
        name="sysmon",
        daemon=True
        )
        th.start()

        await shutdown_event.wait()
        await logs("Shutdown signal received", type_e="info")

        await dp.stop_polling()
        await info_dp.stop_polling()

        with contextlib.suppress(asyncio.CancelledError):
            await web_task

        await asyncio.gather(poll_main, poll_info, return_exceptions=True)

    await logs("Cleanup finished, exiting.", type_e="info")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    else:
        sys.exit(0)