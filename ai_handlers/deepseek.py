import openai
from openai import AsyncOpenAI
from config.config import DEEPSEEK_API_KEY, MESSAGES
from logs.log import logs
from logs.errors import OpenAIServiceError

client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")

async def deepseek_api_text_request(lang, user_model, set_answer, web_enabled, conversation) -> str:
    """
    Function to process text messages and get AI response using OpenAI API.
    :param user_text: User input text
    :return: AI response
    """
    try:
        # Here you would typically call your AI model or service to get a response
        # For demonstration, we'll just echo the user text
        response = await client.chat.completions.create(
            model=user_model,
            messages=conversation,
            temperature=float(set_answer[0]) if set_answer else 0.7,
            max_tokens=1000,
        )
        return response.choices[0].message.content, response.usage.total_tokens
    except openai.APIError as e:
        await logs(f"Error in openai_api_photo_request: {e}", type_e="error")
        raise OpenAIServiceError(
            status_code=e.status_code,
            code=getattr(e, "code", None),
            message=str(e),
            original=e
        ) from e
    