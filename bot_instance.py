import telebot
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from telebot.apihelper import ApiTelegramException
from config.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_INFO_BOT_TOKEN,
    TELEGRAM_BOT_TOKEN_ALTERNATIVE,
    TELEGRAM_INFO_BOT_TOKEN_ALTERNATIVE,
)
from logs import log_info, set_info_bot

# Initialize global variables
bot = None
dp = None
info_bot = None
dp_info_bot = None

async def create_bot(token, parse_mode=ParseMode.HTML):
    """Create a bot instance with a new session"""
    session = AiohttpSession()
    return Bot(token=token, session=session, default=DefaultBotProperties(parse_mode=parse_mode))


async def test_polling(token: str) -> bool:
    # Простой вариант без потоков/процессов:
    try:
        await log_info(f"Testing token {token} for polling", type_e="info")
        bot = telebot.TeleBot(token, parse_mode=ParseMode.HTML)
        bot.remove_webhook()
        bot.get_updates(limit=1, timeout=1)
        await log_info(f"Token {token} is available for polling", type_e="info")
        return True
    except ApiTelegramException as e:
        if e.error_code == 409:
            await log_info(f"Token {token} has webhook conflict", type_e="warning")
            return False
        else:
            await log_info(f"Error testing polling: {e}", type_e="error")
            return False

async def initialize_bots():
    """Initialize bots with direct polling test"""
    global bot, dp, info_bot, dp_info_bot
    
    storage = MemoryStorage()
    storage_info = MemoryStorage()
    
    # Test main bot tokens
    main_token = TELEGRAM_BOT_TOKEN
    info_token = TELEGRAM_INFO_BOT_TOKEN
    if not await test_polling(main_token):
        await log_info("Main token conflict and no connection, using alternative", type_e="warning")
        if not  await test_polling(info_token):
            await log_info("Info token has conflict, trying alternative", type_e="warning")
            main_token = TELEGRAM_BOT_TOKEN_ALTERNATIVE
            info_token = TELEGRAM_INFO_BOT_TOKEN_ALTERNATIVE
    
    # Create bots with selected tokens
    bot = await create_bot(main_token)
    dp = Dispatcher(storage=storage)
    
    info_bot = await create_bot(info_token)
    dp_info_bot = Dispatcher(storage=storage_info)
    set_info_bot(info_bot)
    
    return bot, dp, info_bot, dp_info_bot

async def cleanup_bots():
    """Close bot sessions"""
    global bot, info_bot
    try:
        if bot:
            await bot.session.close()
        if info_bot:
            await info_bot.session.close()
        await log_info("Bot sessions closed", type_e="info")
    except Exception as e:
        await log_info(f"Error during cleanup: {e}", type_e="error")