import telebot
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from telebot.apihelper import ApiTelegramException
from config.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_INFO_BOT_TOKEN
)
from logs.log import logs, set_info_bot

# Initialize global variables
bot = None
dp = None
info_bot = None
dp_info_bot = None

async def create_bot(token, parse_mode=ParseMode.HTML):
    """Create a bot instance with a new session"""
    session = AiohttpSession()
    return Bot(token=token, session=session, default=DefaultBotProperties(parse_mode=parse_mode))

async def initialize_bots():
    """Initialize bots with direct polling test"""
    global bot, dp, info_bot, dp_info_bot
    
    storage = MemoryStorage()
    storage_info = MemoryStorage()
    
    # Test main bot tokens
    main_token = TELEGRAM_BOT_TOKEN
    info_token = TELEGRAM_INFO_BOT_TOKEN
    
    # Create bots with selected tokens
    bot = await create_bot(main_token)
    dp = Dispatcher(storage=storage)
    
    info_bot = await create_bot(info_token)
    dp_info_bot = Dispatcher(storage=storage_info)

    return bot, dp, info_bot, dp_info_bot

async def cleanup_bots():
    """Close bot sessions"""
    global bot, info_bot
    try:
        if bot:
            await bot.session.close()
        if info_bot:
            await info_bot.session.close()
        await logs("Bot sessions closed", type_e="info")
    except Exception as e:
        await logs(f"Module: telegram__bot_init. Error during cleanup: {e}", type_e="error")