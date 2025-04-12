import openai
import base64
import google.generativeai as genai
from config import OPENAI_API_KEY, DEEPSEEK_API_KEY, GEMINI_API_KEY, MODELS
from logs import log_info
import aiofiles
import io
import os
import json
from collections import defaultdict
from google.cloud import vision
from google.protobuf.json_format import MessageToDict
from services.utils import open_cv_image_processing

# Set environment variable if not configured
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/home/user/Projects/keys/google/api_i.burilkin.json'

async def generate_ai_response(user_model, set_answer=None, web_enabled=None, content_type=None, conversation=None, image_path=None, size=None, quality=None) -> str:
    """
    Generates a response from the model based on the type of model, content, and user settings.
    :param conversation: List of messages (dialogue history)
    :param user_model: Selected model
    :param set_answer: Response parameters (e.g., [temperature, top_p])
    :param web_enabled: Web mode enable flag
    :param content_type: Message content type (e.g., "photo")
    :param image_path: Path to the image file (if content_type == "photo")
    :param size: Image size (e.g., "1024x1024")
    :param quality: Image quality (if supported by the API)
    :return: Model response as a string or image URL
    """
    response = None
    image_response = None
    try:
        # Configure keys and API URL based on model
        if user_model in ["gpt-4o-mini", "gpt-4o", "gpt-4o-mini-search-preview", "gpt-4o-search-preview", "dall-e-3"]:
            openai.api_key = OPENAI_API_KEY
            openai.api_base = "https://api.openai.com/v1"
        elif user_model in ["deepseek-chat", "deepseek-reasoner"]:
            openai.api_key = DEEPSEEK_API_KEY
            openai.api_base = "https://api.deepseek.com"
        # If model belongs to base MODELS family
        if user_model in MODELS:
            # Processing for photos
            if content_type == "photo" and user_model in ["gpt-4o-mini", "gpt-4o"]:
                if image_path:
                    with open(image_path, "rb") as image_file:
                        base64_image = base64.b64encode(image_file.read()).decode("utf-8")
                    conversation_photo = [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": str(conversation)},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }]
                    await log_info(f"Sending photo request to model {user_model} with image from {image_path}", type_e="info")
                    response = await openai.ChatCompletion.acreate(
                        model=user_model,
                        messages=conversation_photo,
                        max_tokens=1000
                    )
                else:
                    error_msg = "No image_path specified for photo content type"
                    await log_info(error_msg, type_e="error")
                    raise ValueError(error_msg)
            else:
                await log_info(f"Sending text request to model {user_model}", type_e="info")
                response = await openai.ChatCompletion.acreate(
                    model=user_model,
                    messages=conversation,
                    temperature=float(set_answer[0]) if set_answer else 0.7,
                    max_tokens=1000,
                    top_p=float(set_answer[1]) if set_answer else 1.0
                )
        elif user_model in ["gpt-4o-mini-search-preview", "gpt-4o-search-preview"]:
            if content_type == "photo":
                if web_enabled:
                    if user_model == "gpt-4o-mini-search-preview":
                        user_model = "gpt-4o-mini"
                    elif user_model == "gpt-4o-search-preview":
                        user_model = "gpt-4o"
                await log_info(f"Sending photo request to model {user_model} (search-preview)", type_e="info")
                response = await openai.ChatCompletion.acreate(
                    model=user_model,
                    messages=conversation,
                    max_tokens=1000
                )
            else:
                await log_info(f"Sending text request to model {user_model} (search-preview) with web_search_options", type_e="info")
                response = await openai.ChatCompletion.acreate(
                    model=user_model,
                    web_search_options={},
                    messages=conversation,
                    max_tokens=1000
                )
        elif user_model == "dall-e-3":
            # Set API key if not already set
            await log_info("Generating image via dall-e-3 model", type_e="info")
            image_response = await openai.Image.acreate(
                model=user_model,
                prompt=conversation,
                size=size,
                quality=quality,
                n=1,
            )
            image_url = image_response['data'][0]['url']
            await log_info(f"Image URL received: {image_url}", type_e="info")
        elif user_model == "gemini-2.0-flash":
            await log_info("Generating response via Gemini API", type_e="info")
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=conversation,
                config={
                    "temperature": float(set_answer[0]) if set_answer else 0.7,
                    "top_p": float(set_answer[1]) if set_answer else 1.0
                }
            )
        elif user_model == "AI_bot":
            if image_path:
                async def process_image(image_path: str, y_threshold: int = 15) -> list:
                    """
                    Loads an image, sends it to Google Vision for recognition,
                    converts the result to a dictionary and extracts text lines.
                    
                    :param image_path: Path to the image
                    :param y_threshold: Y-coordinate grouping threshold (default 15)
                    :return: List of lines with extracted text
                    """
                    client = vision.ImageAnnotatorClient()

                    # Asynchronously load image into memory
                    async with aiofiles.open(image_path, "rb") as image_file:
                        content = await image_file.read()

                    image = vision.Image(content=content)
                    response = client.document_text_detection(image=image)
                    # Convert protobuf response to dictionary
                    json_data = MessageToDict(response._pb.full_text_annotation)
                    
                    # Extract lines from the dictionary
                    lines = extract_lines_from_data(json_data, y_threshold)
                    return lines

                def extract_lines_from_data(data: dict, y_threshold: int = 15) -> list:
                    """
                    Extracts text lines from a dictionary obtained from Google Vision.
                    
                    :param data: Dictionary with recognized text (from full_text_annotation)
                    :param y_threshold: Y-coordinate grouping threshold
                    :return: List of lines with text
                    """
                    words_with_coords = []
                    pages = data.get("pages", [])
                    for page in pages:
                        for block in page.get("blocks", []):
                            for paragraph in block.get("paragraphs", []):
                                for word in paragraph.get("words", []):
                                    symbols = word.get("symbols", [])
                                    word_text = "".join([s.get("text", "") for s in symbols])
                                    vertices = word.get("boundingBox", {}).get("vertices", [])
                                    if vertices:
                                        x = vertices[0].get("x", 0)
                                        y = vertices[0].get("y", 0)
                                        words_with_coords.append({
                                            "text": word_text,
                                            "x": x,
                                            "y": y
                                        })

                    # Sort words by y and x coordinate groups
                    words_with_coords.sort(key=lambda w: (round(w['y'] / y_threshold) * y_threshold, w['x']))
                    lines_dict = defaultdict(list)
                    for word in words_with_coords:
                        y_group = round(word['y'] / y_threshold) * y_threshold
                        lines_dict[y_group].append((word['x'], word['text']))

                    # Assemble lines, sorting words by x coordinate
                    lines = []
                    for y in sorted(lines_dict):
                        line = " ".join([text for x, text in sorted(lines_dict[y], key=lambda tup: tup[0])])
                        lines.append(line)
                    return lines
                image_path = await open_cv_image_processing(image_path)
                result_lines = await process_image(image_path)
                result = "\n".join(result_lines)
                return result
            else:
                error_msg = "No image_path specified for photo content type"
                await log_info(error_msg, type_e="error")
                raise ValueError(error_msg)

        # Check if a response was received from the API
        if response:
            if user_model in ["gemini-2.0-flash"]:
                await log_info("Response successfully received from Gemini API", type_e="info")
                return response.text if hasattr(response, "text") else "Error processing Gemini API"
            else:
                await log_info("Response successfully received from OpenAI", type_e="info")
                return response["choices"][0]["message"]["content"]
        elif image_response:
            await log_info("Image successfully received from OpenAI", type_e="info")
            return image_url
        else:
            error_message = "Error processing request: no response from API"
            await log_info(error_message, type_e="error")
            raise ValueError(error_message)
    except Exception as e:
        await log_info(f"Error in generate_ai_response: {e}", type_e="error")
        raise