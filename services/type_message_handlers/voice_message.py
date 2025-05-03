from logs.log import logs
from config.config import MESSAGES, MODELS_OPEN_AI, MODELS_DEEPSEEK
from ai_handlers.open_ai import openai_api_voice_request
from services.db_utils import update_chat_history, read_chat_history, update_user_data
from logs.errors import OpenAIServiceError, ApplicationError

async def voice_message_ai_response(chat_id, lang, user_model, context_enabled, web_enabled, set_answer, role, user_limits, user_text, audio_path: str) -> str:
    """
    Function to process voice messages and get AI response.
    :param wav_file: Path to the downloaded WAV file
    :return: AI response
    """
    try:
        await update_chat_history(chat_id, {"role": "user", "content": user_text})
        user_text_saved = [{"role": "user", "content": user_text}]
        await logs(f"Chat {chat_id} - user request saved", type_e="info")

        conversation_api = [{"role": "system", "content": role}]
        if context_enabled:
            conversation_api.extend(await read_chat_history(chat_id))
        else:
            conversation_api.extend(user_text_saved)
        if user_model in MODELS_OPEN_AI:
            ai_response = await openai_api_voice_request(lang, audio_path)
        elif user_model in MODELS_DEEPSEEK:
            return f"<b>System: </b>{MESSAGES.get(lang, {}).get('error_422', 'An error occurred')}"

        await logs(f"Chat {chat_id} - model response received: {ai_response}", type_e="info")
        await update_chat_history(chat_id, {"role": "assistant", "content": ai_response})

        tokens, req_count, date_requests = user_limits
        tokens += 0
        req_count += 1
        await update_user_data(chat_id, "tokens", tokens)
        await update_user_data(chat_id, "requests", req_count)
        return f"<b>AI: </b>{ai_response}"
    except OpenAIServiceError:
        raise
    except Exception as e:
        raise ApplicationError("Error in voice_message_ai_response.") from e