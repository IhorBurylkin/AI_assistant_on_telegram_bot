from functools import lru_cache
import json

def load_config(file_path: str):
    """
    Function for loading configuration from a JSON file
    :param file_path: Path to the file
    :return: Configuration
    """
    try:
        with open(file_path, mode="r", encoding="utf-8") as f:
            content = f.read()
        print(f"File {file_path} successfully loaded.")    
        return json.loads(content)
    except FileNotFoundError:
        print(f"File {file_path} not found.")
        return
    except json.JSONDecodeError as e:
        print(f"JSON decoding error in {file_path}: {e}")
        return
    except Exception as e:
        print(f"Unexpected error when loading {file_path}: {e}")
        return

@lru_cache(maxsize=2)
def get_settings(file_path: str):
    """
    Loads settings once and caches the result.
    """
    return load_config(file_path)  

config = get_settings("config/config.json")

CHATGPT_MODEL = config.get("CHATGPT_MODEL")
CONFIG_FILE_PATH = config.get("CONFIG_FILE_PATH")
USERS_FILE_PATH = "chat_ids"#config.get("USERS_FILE_PATH")
CHECKS_ANALYTICS = "checks_analytics"
CHAT_HISTORIES_FILE_PATH = "context"#config.get("CHAT_HISTORIES_FILE_PATH")
LOGGING_FILE_PATH = config.get("LOGGING_FILE_PATH")
LOGGING_SETTINGS_TO_SEND = config.get("LOGGING_SETTINGS_TO_SEND")
TELEGRAM_BOT_TOKEN = config.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_TOKEN_ALTERNATIVE = config.get("TELEGRAM_BOT_TOKEN_ALTERNATIVE")
TELEGRAM_INFO_BOT_TOKEN = config.get("TELEGRAM_INFO_BOT_TOKEN")
TELEGRAM_INFO_BOT_TOKEN_ALTERNATIVE = config.get("TELEGRAM_INFO_BOT_TOKEN_ALTERNATIVE")
BOT_USERNAME = config.get("BOT_USERNAME")
WEBAPP_URL = config.get("WEBAPP_URL")
OPENAI_API_KEY = config.get("OPENAI_API_KEY")
DEEPSEEK_API_KEY = config.get("DEEPSEEK_API_KEY")
GEMINI_API_KEY = config.get("GEMINI_API_KEY")
GOOGLE_CREDENTIALS_PATH = config.get("GOOGLE_APPLICATION_CREDENTIALS")
PRODUCT_KEYS = config.get("PRODUCT_KEYS")
PRODUCT_KEYS_FOR_PARSE = config.get("PRODUCT_KEYS_FOR_PARSE")
SUPPORTED_EXTENSIONS = config.get("SUPPORTED_EXTENSIONS")
SUPPORTED_IMAGE_EXTENSIONS = config.get("SUPPORTED_IMAGE_EXTENSIONS")
SUPPORTED_LANGUAGES = config.get("SUPPORTED_LANGUAGES")
DEFAULT_LANGUAGES = config.get("DEFAULT_LANGUAGES")
MODELS = config.get("MODELS")
MODELS_FOR_MENU = config.get("MODELS_FOR_MENU")
MODELS_TEXT = config.get("MODELS_TEXT")
MESSAGES = config.get("MESSAGES")
WHITE_LIST = config.get("white_list")
DB_DSN = config.get("DB_DSN")

LIMITS = {
        "default_list": [10, 1000],
        "x5": [50, 5000],
        "x10": [100, 10000],
        "x100": [1000, 100000],
        "white_list": [9999, 999999]
    }