from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_INFO_BOT_TOKEN,
)

session = AiohttpSession()
storage = MemoryStorage()

bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    session=session,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=storage)

session_info_bot = AiohttpSession()
storage_info = MemoryStorage()

info_bot = Bot(
    token=TELEGRAM_INFO_BOT_TOKEN,
    session=session_info_bot,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp_info_bot = Dispatcher(storage=storage_info)