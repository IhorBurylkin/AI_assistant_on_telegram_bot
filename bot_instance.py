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
from logs import log_info, set_info_bot

# Create sessions
session = AiohttpSession()
session_info_bot = AiohttpSession()

# Create storage
storage = MemoryStorage()
storage_info = MemoryStorage()

# Initialize global bot variables - will be set during initialization
bot = None
dp = None
info_bot = None
dp_info_bot = None

async def initialize_bots():
    """
    Initialize bot instances with redundancy check.
    Returns initialized bot and dispatcher instances and sets global variables.
    """
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
        
        # Set info_bot in logging module
        set_info_bot(info_bot)
        
        await log_info("Bot instances initialized with redundancy check", type_e="info")
        
        # Return the instances for use in other modules
        return bot, dp, info_bot, dp_info_bot
        
    except Exception as e:
        await log_info(f"Error in bot initialization: {e}", type_e="error")
        
        # Fallback to primary tokens if initialization fails
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
        
        # Set info_bot in logging module
        set_info_bot(info_bot)
        
        await log_info("Using fallback bot initialization", type_e="warning")
        
        # Return the instances for use in other modules
        return bot, dp, info_bot, dp_info_bot

# Initialize bots at module level if needed
# This will set the global variables but won't be used in main.py
# which will call initialize_bots() directly
async def _init_bots_globals():
    global bot, dp, info_bot, dp_info_bot
    # Only initialize if not already done
    if not bot or not info_bot:
        try:
            bot, dp, info_bot, dp_info_bot = await initialize_bots()
        except Exception as e:
            print(f"Warning: Failed to initialize bots at module level: {e}")

# Create an event loop and run the initialization
# This ensures the global variables are set for modules that import them directly
try:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_init_bots_globals())
except RuntimeError:
    # Handle case where there's no running event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_init_bots_globals())
except Exception as e:
    print(f"Warning: Error during initial bot initialization: {e}")
    
    # Fallback initialization for global variables if everything fails
    if not bot:
        bot = Bot(
            token=TELEGRAM_BOT_TOKEN,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        dp = Dispatcher(storage=storage)
    
    if not info_bot:
        info_bot = Bot(
            token=TELEGRAM_INFO_BOT_TOKEN,
            session=session_info_bot,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        dp_info_bot = Dispatcher(storage=storage_info)
    
    print("Warning: Using fallback bot initialization")