import base64
import openai
import img2pdf
import os
import json
from openai import AsyncOpenAI
from config.config import OPENAI_API_KEY, DEFAULT_MODEL_FOR_VISION
from logs.log import logs
from logs.errors import OpenAIServiceError

client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url="https://api.openai.com/v1")

async def openai_api_text_moderations(text):
    try:
        response = await client.moderations.create(
            input=text,
            model="omni-moderation-latest"
        )
        return response.results[0].flagged, response.results[0].categories
    except openai.APIError as e:
        await logs(f"Error in openai_api_text_moderations: {e}", type_e="error")
        raise OpenAIServiceError(
            status_code=e.status_code,
            code=getattr(e, "code", None),
            message=str(e),
            original=e
        ) from e
    
async def openai_api_photo_moderations(image_path, user_text):
    try:
        with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")
        response = await client.moderations.create(
            model="omni-moderation-latest",
            input=[
                {"type": "text", "text": f"{user_text}"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                },
            ],
        )
        return response.results[0].flagged, response.results[0].categories
    except openai.APIError as e:
        await logs(f"Error in openai_api_photo_moderations: {e}", type_e="error")
        raise OpenAIServiceError(
            status_code=e.status_code,
            code=getattr(e, "code", None),
            message=str(e),
            original=e
        ) from e

async def openai_api_text_request(lang, user_model, set_answer, web_enabled, conversation) -> str:
    """
    Function to process text messages and get AI response using OpenAI API.
    :param user_text: User input text
    :return: AI response
    """
    try:
        if web_enabled:
            response = await client.responses.create(
                model=user_model,
                input=conversation,
                tools=[{"type": "web_search"}]
            )
            if response.output and response.output[0].status == "completed":
                answer_parts = []
                for block in response.output[1].content:
                    answer_parts.append(block.text)
                text = "".join(answer_parts)
                tokens = response.usage.total_tokens
                return text, tokens
            return "", response.usage.total_tokens

        response = await client.chat.completions.create(
            model=user_model,
            messages=conversation,
            max_tokens=1000,
            temperature=float(set_answer[0]) if set_answer else 0.7,
            top_p=float(set_answer[1])     if set_answer else 1.0
        )
        text = response.choices[0].message.content
        tokens = response.usage.total_tokens
        return text, tokens

    except openai.APIError as e:
        await logs(f"Error in openai_api_text_request: {e}", type_e="error")
        raise OpenAIServiceError(
            status_code=e.status_code,
            code=getattr(e, "code", None),
            message=str(e),
            original=e
        ) from e

async def openai_api_photo_request(lang, user_model, set_answer, web_enabled, conversation, image_path):
    try:
        with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")
        conversation_photo = [{
            "role": "user",
            "content": [
                {"type": "text", "text": str(conversation)},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }]
        await logs(f"Sending photo request to model {user_model} with image from {image_path}", type_e="info")
        response = await client.chat.completions.create(
            model=user_model,
            messages=conversation_photo,
            max_tokens=1000
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
    
async def openai_api_voice_request(lang, audio_path):
    try:
        with open(audio_path, "rb") as audio:
            transcript = await client.audio.transcriptions.create(model="whisper-1", file = audio)
        await logs(f"Audio transcription completed for {audio_path}", type_e="info")
        return transcript.text
    except openai.APIError as e:
        await logs(f"Error in openai_api_voice_request: {e}", type_e="error")
        raise OpenAIServiceError(
            status_code=e.status_code,
            code=getattr(e, "code", None),
            message=str(e),
            original=e
        ) from e
    
async def openai_api_generate_image(lang, user_model, resolution, quality, user_text: str) -> str:
    """
    Function to process text messages and get AI response using OpenAI API.
    :param user_text: User input text
    :return: AI response
    """
    try:
        response = await client.images.generate(
            model=user_model,
            prompt=user_text,
            n=1,
            size=resolution,
            quality=quality
        )
        return response.data[0].url
    except openai.APIError as e:
        await logs(f"Error in openai_api_generate_image: {e}", type_e="error")
        raise OpenAIServiceError(
            status_code=e.status_code,
            code=getattr(e, "code", None),
            message=str(e),
            original=e
        ) from e
    
async def openai_api_photo_check_analysis_request(lang, user_model, set_answer, conversation, image_path):
    try:
        base_file_name, ext = os.path.splitext(image_path)
        pdf_file_name = base_file_name + ".pdf"

        with open(pdf_file_name,"wb") as f:
            f.write(img2pdf.convert([image_path]))

        file = await client.files.create(
            file=open(pdf_file_name, "rb"),
            purpose="user_data"
        )

        response = await client.chat.completions.create(
            model=DEFAULT_MODEL_FOR_VISION,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "file", "file": {"file_id": file.id}},
                        {"type": "text", "text": conversation}
                    ]
                }
            ]
        )
        
        await logs(f"Text extraction completed for {image_path}", type_e="info")
        return response.choices[0].message.content, response.usage.total_tokens
    except openai.APIError as e:
        await logs(f"Error in openai_api_photo_check_analysis_request: {e}", type_e="error")
        raise OpenAIServiceError(
            status_code=e.status_code,
            code=getattr(e, "code", None),
            message=str(e),
            original=e
        ) from e
    finally:
        if os.path.exists(pdf_file_name):
            os.remove(pdf_file_name)