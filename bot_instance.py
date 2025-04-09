from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

TELEGRAM_BOT_TOKEN = "7237137858:AAHMbUb1O222Y_QcEVuNxOcJaIbKJgKprug"#"7715169582:AAFzSVnoseybC6x1MhcBgk1FqHBgkPziXSk"
session = AiohttpSession()
storage = MemoryStorage()

bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    session=session,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=storage)

TELEGRAM_INFO_BOT_TOKEN = "7247288830:AAFT_yb7x8qoK6CAsnL6rLaAoJeDnfHt5KQ"#"7477184454:AAFgfg11Wu5aBFPA_elJeOpJ9d2K8yYHZ-Q"
session_info_bot = AiohttpSession()
storage_info = MemoryStorage()

info_bot = Bot(
    token=TELEGRAM_INFO_BOT_TOKEN,
    session=session_info_bot,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp_info_bot = Dispatcher(storage=storage_info)