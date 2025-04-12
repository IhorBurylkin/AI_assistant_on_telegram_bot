"""
Module for initializing bot instances with token redundancy.

This module handles initialization of the bot instances with token redundancy
by checking if a bot with the primary token is already running.
"""

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
from logs import set_info_bot

# Create sessions and storage
session = AiohttpSession()
session_info_bot = AiohttpSession()
storage = MemoryStorage()
storage_info = MemoryStorage()

async def initialize_bots():
    """
    Initialize bot instances with redundancy check.
    Returns initialized bot and dispatcher instances.
    """
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
        main_bot = Bot(
            token=main_token,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        main_dp = Dispatcher(storage=storage)
        
        info_bot = Bot(
            token=info_token,
            session=session_info_bot,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        info_dp = Dispatcher(storage=storage_info)
        
        # Set info_bot in logging module
        set_info_bot(info_bot)
        
        print("[INFO] Bot instances initialized with redundancy check")
        return main_bot, main_dp, info_bot, info_dp
        
    except Exception as e:
        print(f"[ERROR] Error in bot initialization: {e}")
        
        # Fallback to primary tokens if initialization fails
        main_bot = Bot(
            token=TELEGRAM_BOT_TOKEN,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        main_dp = Dispatcher(storage=storage)
        
        info_bot = Bot(
            token=TELEGRAM_INFO_BOT_TOKEN,
            session=session_info_bot,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        info_dp = Dispatcher(storage=storage_info)
        
        # Set info_bot in logging module
        set_info_bot(info_bot)
        
        print("[WARNING] Using fallback bot initialization")
        return main_bot, main_dp, info_bot, info_dp