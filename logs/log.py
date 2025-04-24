import logging
import asyncio
import os
from config.config import LOGGING_FILE_PATH, LOGGING_SETTINGS_TO_SEND
_initialized = False

# Updated to avoid circular imports
_info_bot = None

async def init_logging():
    global _initialized
    if _initialized:
        return

    await asyncio.sleep(0)  # To maintain asynchronous interface

    # Ensure log directory exists
    log_dir = os.path.dirname(LOGGING_FILE_PATH)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOGGING_FILE_PATH, encoding="utf-8")
        ]
    )
    _initialized = True

def set_info_bot(bot):
    """Set the info bot instance to use for logging"""
    global _info_bot
    _info_bot = bot


async def send_info_msg(text=None, message_thread_id=None, info_bot=None, chat_id=None):
    """
    Function for sending a message to the logging bot
    """
    if chat_id is None:
        chat_id = LOGGING_SETTINGS_TO_SEND["chat_id"]
        
    try:
        # Only proceed if we have a bot instance
        if info_bot is not None:
            if LOGGING_SETTINGS_TO_SEND["permission"] and LOGGING_SETTINGS_TO_SEND["message_thread_id"] not in [None, 0]:
                await info_bot.send_message(chat_id=chat_id, text=text, message_thread_id=LOGGING_SETTINGS_TO_SEND["message_thread_id"])
            else:
                await info_bot.send_message(chat_id=chat_id, text=text)
        else:
            # Log that we couldn't send the message due to missing bot instance
            logging.warning("Could not send info message - info_bot instance not provided")
    except Exception as e:
        await log_info(f"Error sending message: {e}", type_e="error")

async def log_info(message: str, type_e: str, *args, **kwargs: str):
    await init_logging()
    if "info" in type_e:  
        logging.info(message, *args, extra=kwargs)
    elif "error" in type_e:
        logging.error(message, *args, extra=kwargs)
        # Import here to avoid circular import
        await send_info_msg(
            text=f'Type message: Error\n{message}\n{args}\n{kwargs}', 
            message_thread_id=LOGGING_SETTINGS_TO_SEND["message_thread_id"],
            info_bot=_info_bot
        )
    elif "warning" in type_e:
        logging.warning(message, *args, extra=kwargs)
        # Import here to avoid circular import
        await send_info_msg(
            text=f'Type message: Warning\n{message}\n{args}\n{kwargs}', 
            message_thread_id=LOGGING_SETTINGS_TO_SEND["message_thread_id"],
            info_bot=_info_bot
        )