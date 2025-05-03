import base64
from logs.log import logs
from services.db_utils import update_user_data
from ai_handlers.open_ai import openai_api_photo_check_analysis_request
from ai_handlers.deepseek import deepseek_api_text_request
from config.config import MODELS_OPEN_AI, MODELS_DEEPSEEK, MESSAGES, PRODUCT_KEYS
from logs.errors import OpenAIServiceError, ApplicationError

async def analysis_check_from_photo(chat_id, lang, user_model, set_answer, role, user_limits, image_path) -> str:
    """
    Function to process photo messages and get AI response.
    :param image_path: Path to the downloaded image
    :return: AI response
    """
    try:
        conversation_api = role
        ai_response, usage_tokens = await openai_api_photo_check_analysis_request(lang, user_model, set_answer, conversation_api, image_path)

        await logs(f"Chat {chat_id} - usage tokens count: {usage_tokens}", type_e="info")

        tokens, req_count, date_requests = user_limits
        tokens += usage_tokens
        req_count += 1
        await update_user_data(chat_id, "tokens", tokens)
        await update_user_data(chat_id, "requests", req_count)
    except OpenAIServiceError:
        raise
    except Exception as e:
        raise ApplicationError("Error in analysis_check.") from e
    finally:
        return ai_response
    
async def analysis_check_from_text(chat_id, lang, user_model, web_enabled, set_answer, vision_role_one_req, user_limits, user_text_input) -> str:
    try:
        user_text = [{"role": "user", "content": user_text_input}]
        conversation_api = [{"role": "system", "content": vision_role_one_req}]
        conversation_api.extend(user_text)
        await logs(f"Chat {chat_id} - user request saved", type_e="info")
        ai_response, usage_tokens = await deepseek_api_text_request(lang, user_model, set_answer, web_enabled, conversation_api)

        await logs(f"Chat {chat_id} - model response received: {ai_response}", type_e="info")
        await logs(f"Chat {chat_id} - usage tokens count: {usage_tokens}", type_e="info")

        tokens, req_count, date_requests = user_limits
        tokens += usage_tokens
        req_count += 1
        await update_user_data(chat_id, "tokens", tokens)
        await update_user_data(chat_id, "requests", req_count)
    except OpenAIServiceError:
        raise
    except Exception as e:
        raise ApplicationError("Error in analysis_check.") from e
    finally:
        return ai_response