import logging
import asyncio
import services
from config import LOGGING_FILE_PATH, LOGGING_SETTINGS_TO_SEND
_initialized = False

async def init_logging():
    global _initialized
    if _initialized:
        return

    await asyncio.sleep(0)  # Для соблюдения асинхронного интерфейса

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOGGING_FILE_PATH, encoding="utf-8")
        ]
    )
    _initialized = True

async def log_info(message: str, type_e: str, *args, **kwargs: str):
    await init_logging()
    if "info" in type_e:  
        logging.info(message, *args, extra=kwargs)
    elif "error" in type_e:
        logging.error(message, *args, extra=kwargs)
        await services.utils.send_info_msg(text=f'Type message: Error\n{message}\n{args}\n{kwargs}', message_thread_id=LOGGING_SETTINGS_TO_SEND["message_thread_id"])
    elif "warning" in type_e:
        logging.warning(message, *args, extra=kwargs)
        await services.utils.send_info_msg(text=f'Type message: Warning\n{message}\n{args}\n{kwargs}', message_thread_id=LOGGING_SETTINGS_TO_SEND["message_thread_id"])