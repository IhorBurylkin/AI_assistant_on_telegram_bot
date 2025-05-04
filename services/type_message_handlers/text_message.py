from logs.log import logs
from ai_handlers.open_ai import openai_api_text_request, openai_api_text_moderations
from ai_handlers.deepseek import deepseek_api_text_request
from services.db_utils import update_chat_history, read_chat_history, update_user_data
from config.config import MODELS_OPEN_AI, MODELS_DEEPSEEK, MESSAGES
from logs.errors import OpenAIServiceError, ApplicationError

async def text_message_ai_response(chat_id, lang, user_model, context_enabled, web_enabled, set_answer, role, user_limits, user_text: str) -> str:
    """
    Function to process text messages and get AI response.
    :param user_text: User input text
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

        flagged, categories = await openai_api_text_moderations(user_text)
        print(f"\n\nModeration result: {flagged}, {categories}\n\n", type(categories))
        print(list(categories))
        if flagged == False:
            if user_model in MODELS_OPEN_AI:
                ai_response, usage_tokens = await openai_api_text_request(lang, user_model, set_answer, web_enabled, conversation_api)
            elif user_model in MODELS_DEEPSEEK:
                ai_response, usage_tokens = await deepseek_api_text_request(lang, user_model, set_answer, web_enabled, conversation_api)
        else:
            true_categories = [name for name, flag in categories if flag]
            ai_response = MESSAGES.get(lang, {}).get("error_moderations", 
                "Unfortunately, your message was rejected by the moderation system. Please try rephrasing it and try again.  \nCategory: {}").format("".join(true_categories))
            usage_tokens = 0

        await logs(f"Chat {chat_id} - model response received: {ai_response}", type_e="info")
        await update_chat_history(chat_id, {"role": "assistant", "content": ai_response})

        await logs(f"Chat {chat_id} - usage tokens count: {usage_tokens}", type_e="info")

        tokens, req_count, date_requests = user_limits
        tokens += usage_tokens
        req_count += 1
        await update_user_data(chat_id, "tokens", tokens)
        await update_user_data(chat_id, "requests", req_count)

        return f"<b>AI: </b>{ai_response}"
    except OpenAIServiceError:
        raise
    except Exception as e:
        raise ApplicationError("Error in text_message_ai_response.") from e