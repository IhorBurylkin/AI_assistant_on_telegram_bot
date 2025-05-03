from logs.log import logs
from ai_handlers.open_ai import openai_api_generate_image
from services.db_utils import update_user_data
from config.config import MODELS_OPEN_AI, MODELS_DEEPSEEK, MESSAGES
from logs.errors import OpenAIServiceError, ApplicationError

async def generate_image_ai_response(chat_id, lang, user_model, resolution, quality, user_limits, user_text: str) -> str:
    """
    Function to process text messages and get AI response.
    :param user_text: User input text
    :return: AI response
    """
    try:
        await logs(f"Chat {chat_id} - user request to image generate", type_e="info")
        if user_model in MODELS_OPEN_AI:
            ai_response = await openai_api_generate_image(lang, user_model, resolution, quality, user_text)
        elif user_model in MODELS_DEEPSEEK:
            return f"<b>System: </b>{MESSAGES.get(lang, {}).get('error_422', 'An error occurred')}"

        tokens, req_count, date_requests = user_limits
        tokens += 0
        req_count += 1
        await update_user_data(chat_id, "tokens", tokens)
        await update_user_data(chat_id, "requests", req_count)

        return ai_response
    except OpenAIServiceError:
        raise
    except Exception as e:
        raise ApplicationError("Error in text_message_ai_response.") from e