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

# Установить переменную окружения, если не настроено
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/home/user/Projects/keys/google/api_i.burilkin.json'

async def generate_ai_response(user_model, set_answer=None, web_enabled=None, content_type=None, conversation=None, image_path=None, size=None, quality=None) -> str:
    """
    Генерирует ответ от модели в зависимости от типа модели, контента и настроек пользователя.
    :param conversation: Список сообщений (история диалога)
    :param user_model: Выбранная модель
    :param set_answer: Параметры ответа (например, [temperature, top_p])
    :param web_enabled: Флаг включения web-режима
    :param content_type: Тип контента сообщения (например, "photo")
    :param image_path: Путь к файлу изображения (если content_type == "photo")
    :param size: Размер изображения (например, "1024x1024")
    :param quality: Качество изображения (если поддерживается API)
    :return: Ответ модели в виде строки или URL изображения
    """
    response = None
    image_response = None
    try:
        # Настройка ключей и URL API в зависимости от модели
        if user_model in ["gpt-4o-mini", "gpt-4o", "gpt-4o-mini-search-preview", "gpt-4o-search-preview", "dall-e-3"]:
            openai.api_key = OPENAI_API_KEY
            openai.api_base = "https://api.openai.com/v1"
        elif user_model in ["deepseek-chat", "deepseek-reasoner"]:
            openai.api_key = DEEPSEEK_API_KEY
            openai.api_base = "https://api.deepseek.com"
        # Если модель принадлежит базовому семейству MODELS
        if user_model in MODELS:
            # Обработка для фотографий
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
                    await log_info(f"Отправка фото-запроса в модель {user_model} с изображением из {image_path}", type_e="info")
                    response = await openai.ChatCompletion.acreate(
                        model=user_model,
                        messages=conversation_photo,
                        max_tokens=1000
                    )
                else:
                    error_msg = "Не указан image_path для контента типа photo"
                    await log_info(error_msg, type_e="error")
                    raise ValueError(error_msg)
            else:
                await log_info(f"Отправка текстового запроса в модель {user_model}", type_e="info")
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
                await log_info(f"Отправка фото-запроса в модель {user_model} (search-preview)", type_e="info")
                response = await openai.ChatCompletion.acreate(
                    model=user_model,
                    messages=conversation,
                    max_tokens=1000
                )
            else:
                await log_info(f"Отправка текстового запроса в модель {user_model} (search-preview) с web_search_options", type_e="info")
                response = await openai.ChatCompletion.acreate(
                    model=user_model,
                    web_search_options={},
                    messages=conversation,
                    max_tokens=1000
                )
        elif user_model == "dall-e-3":
            # Устанавливаем API-ключ, если он ещё не установлен
            await log_info("Генерация изображения через модель dall-e-3", type_e="info")
            image_response = await openai.Image.acreate(
                model=user_model,
                prompt=conversation,
                size=size,
                quality=quality,
                n=1,
            )
            image_url = image_response['data'][0]['url']
            await log_info(f"Получен URL изображения: {image_url}", type_e="info")
        elif user_model == "gemini-2.0-flash":
            await log_info("Генерация ответа через Gemini API", type_e="info")
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
                    Загружает изображение, отправляет его в Google Vision для распознавания,
                    преобразует результат в словарь и извлекает строки текста.
                    
                    :param image_path: Путь к изображению
                    :param y_threshold: Порог группировки по координате Y (по умолчанию 15)
                    :return: Список строк с извлеченным текстом
                    """
                    client = vision.ImageAnnotatorClient()

                    # Асинхронно загружаем изображение в память
                    async with aiofiles.open(image_path, "rb") as image_file:
                        content = await image_file.read()

                    image = vision.Image(content=content)
                    response = client.document_text_detection(image=image)
                    # Преобразуем протобуферный ответ в словарь
                    json_data = MessageToDict(response._pb.full_text_annotation)
                    
                    # Извлекаем строки из полученного словаря
                    lines = extract_lines_from_data(json_data, y_threshold)
                    return lines

                def extract_lines_from_data(data: dict, y_threshold: int = 15) -> list:
                    """
                    Извлекает строки текста из словаря, полученного из Google Vision.
                    
                    :param data: Словарь с распознанным текстом (из full_text_annotation)
                    :param y_threshold: Порог группировки по координате Y
                    :return: Список строк с текстом
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

                    # Сортируем слова по группам по координате y и x
                    words_with_coords.sort(key=lambda w: (round(w['y'] / y_threshold) * y_threshold, w['x']))
                    lines_dict = defaultdict(list)
                    for word in words_with_coords:
                        y_group = round(word['y'] / y_threshold) * y_threshold
                        lines_dict[y_group].append((word['x'], word['text']))

                    # Собираем строки, сортируя слова по координате x
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
                error_msg = "Не указан image_path для контента типа photo"
                await log_info(error_msg, type_e="error")
                raise ValueError(error_msg)

        # Проверяем, получен ли ответ от API
        if response:
            if user_model in ["gemini-2.0-flash"]:
                await log_info("Успешно получен ответ от Gemini API", type_e="info")
                return response.text if hasattr(response, "text") else "Ошибка обработки Gemini API"
            else:
                await log_info("Успешно получен ответ от OpenAI", type_e="info")
                return response["choices"][0]["message"]["content"]
        elif image_response:
            await log_info("Успешно получено изображение от OpenAI", type_e="info")
            return image_url
        else:
            error_message = "Ошибка обработки запроса: нет ответа от API"
            await log_info(error_message, type_e="error")
            raise ValueError(error_message)
    except Exception as e:
        await log_info(f"Ошибка в generate_ai_response: {e}", type_e="error")
        raise
