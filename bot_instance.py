import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_INFO_BOT_TOKEN,
    TELEGRAM_BOT_TOKEN_ALTERNATIVE,
    TELEGRAM_INFO_BOT_TOKEN_ALTERNATIVE,
)
from services.token_checker import check_and_select_tokens
from logs import log_info

# Create sessions
session = AiohttpSession()
session_info_bot = AiohttpSession()

# Create storage
storage = MemoryStorage()
storage_info = MemoryStorage()

# Initialize bot variables
bot = None
dp = None
info_bot = None
dp_info_bot = None

async def initialize_bots():
    global bot, dp, info_bot, dp_info_bot
    
    try:
        # Check and select appropriate tokens
        main_token = await check_and_select_tokens(
            TELEGRAM_BOT_TOKEN, 
            TELEGRAM_BOT_TOKEN_ALTERNATIVE, 
            "main"
        )
        info_token = await check_and_select_tokens(
            TELEGRAM_INFO_BOT_TOKEN, 
            TELEGRAM_INFO_BOT_TOKEN_ALTERNATIVE, 
            "info"
        )
        
        # Create bot instances
        bot = Bot(
            token=main_token,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        dp = Dispatcher(storage=storage)
        
        info_bot = Bot(
            token=info_token,
            session=session_info_bot,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        dp_info_bot = Dispatcher(storage=storage_info)
        
        await log_info("Bot instances initialized with redundancy check", type_e="info")
    except Exception as e:
        await log_info(f"Error in bot initialization: {e}", type_e="error")
        raise

# Run the initialization
loop = asyncio.get_event_loop()
loop.run_until_complete(initialize_bots())

# Fallback in case initialization fails
if not bot or not info_bot:
    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=storage)
    
    info_bot = Bot(
        token=TELEGRAM_INFO_BOT_TOKEN,
        session=session_info_bot,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp_info_bot = Dispatcher(storage=storage_info)
    print("Warning: Using fallback bot initialization")