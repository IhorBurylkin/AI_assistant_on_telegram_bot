import asyncio
import os
import html
import openai
from tika import parser
from aiogram import types
from aiogram.enums import ParseMode, ChatType
from aiogram.types import ReplyKeyboardRemove
from services.openai_api import generate_ai_response
from services.utils import download_photo, convert_audio, count_tokens_for_user_text, check_user_limits
from services.db_utils import (
    read_user_all_data,
    update_user_data,
    update_chat_history,
    get_chat_history
)
from keyboards.reply_kb import get_persistent_menu
from config import DEFAULT_LANGUAGES, SUPPORTED_EXTENSIONS, SUPPORTED_IMAGE_EXTENSIONS, MESSAGES, BOT_USERNAME
from logs import log_info


async def handle_message(message: types.Message, generation_type: str = None):
    """
    Унифицированная функция обработки входящих сообщений.
    Сохраняет исходную логику, добавляет асинхронное логирование через log_info,
    защищает код блоками try/except и обеспечивает корректную очистку временных файлов.
    """
    try:
        # Определяем chat_id в зависимости от типа чата
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
        await log_info(f"Начало обработки сообщения от чата {chat_id}", type_e="info")

        # Извлекаем данные пользователя
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language") or DEFAULT_LANGUAGES
        context_enabled = user_data.get("context_enabled", False)
        web_enabled = user_data.get("web_enabled", False)
        user_model = user_data.get("model")
        set_answer = user_data.get("set_answer_value")
        tokens = user_data.get("tokens")
        req_count = user_data.get("requests")
        date_requests = user_data.get("date_requests")
        role = user_data.get("role")
        resolution = user_data.get("resolution", "1024x1024")
        quality = user_data.get("quality", "standard")
        user_limits = [tokens, req_count, date_requests]

        # Если требуется генерация изображения – меняем модель
        if generation_type == "image":
            user_model = "dall-e-3"
        elif generation_type == "check":
            user_model = "AI_bot"

        # Инициализация переменных
        user_text = ""
        signature = message.caption if message.caption else None
        image_path = None

        # Обработка голосового сообщения
        if message.content_type == "voice":
            ogg_file, wav_file = None, None
            try:
                user_id = message.from_user.id
                ogg_file = f"{user_id}.ogg"
                wav_file = f"{user_id}.wav"
                file_info = await message.bot.get_file(message.voice.file_id)
                await message.bot.download_file(file_info.file_path, destination=ogg_file)
                await log_info(f"Скачан голосовой файл для {chat_id}", type_e="info")

                # Конвертируем OGG -> WAV
                await convert_audio(ogg_file, wav_file)
                await log_info(f"Конвертация аудио завершена для {chat_id}", type_e="info")

                # Распознаём текст через Whisper
                with open(wav_file, "rb") as audio:
                    transcript = openai.Audio.transcribe("whisper-1", audio)
                user_text = transcript.get("text", "")
                await log_info(f"Распознан текст голосового сообщения для {chat_id}: {user_text}", type_e="info")
            except Exception as e:
                await log_info(f"Ошибка обработки голосового сообщения у {chat_id}: {e}", type_e="error")
                return
            finally:
                if ogg_file and os.path.exists(ogg_file):
                    os.remove(ogg_file)
                if wav_file and os.path.exists(wav_file):
                    os.remove(wav_file)

        # Обработка фото
        elif message.content_type == "photo":
            try:
                if generation_type == "check":
                    await message.answer(
                        f"<b>System: </b>{MESSAGES.get(lang, {}).get('load_original_image_file', 'Please upload the image in original quality (without compression), send it as a file (document).')}",
                        parse_mode=ParseMode.HTML
                    )
                    return
                image_path = f"{chat_id}_image.jpg"
                await download_photo(message.photo[-1], image_path)
                await log_info(f"Фото успешно загружено для {chat_id} в {image_path}", type_e="info")
                # Можно добавить распознавание текста на изображении
            except Exception as e:
                await log_info(f"Ошибка загрузки фото у {chat_id}: {e}", type_e="error")
                return

        # Обработка текстового сообщения
        elif message.content_type == "text":
            text = message.text
            cleaned_text = text.replace(f"@{BOT_USERNAME}", "").strip()
            user_text = cleaned_text
            await log_info(f"Текстовое сообщение от {chat_id}: {user_text}", type_e="info")

        # Обработка документов
        elif message.content_type == "document":
            document = message.document
            file_name = document.file_name
            if generation_type == "check":
                if not any(file_name.lower().endswith(ext) for ext in SUPPORTED_IMAGE_EXTENSIONS):
                    await message.answer(
                        f"<b>System: </b>{MESSAGES.get(lang, {}).get('unsupported_file', 'Unsupported file format').format(SUPPORTED_IMAGE_EXTENSIONS)}",
                        parse_mode=ParseMode.HTML
                    )
                    return
                image_path = f"{chat_id}_image.jpg"
                file_info = await message.bot.get_file(document.file_id)
                downloaded_file = await message.bot.download_file(file_info.file_path)
                with open(image_path, "wb") as new_file:
                    # Если downloaded_file является BytesIO, извлекаем байты с помощью getvalue()
                    if hasattr(downloaded_file, "getvalue"):
                        new_file.write(downloaded_file.getvalue())
                    else:
                        new_file.write(downloaded_file)
            else:
                if not any(file_name.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                    await message.answer(
                        f"<b>System: </b>{MESSAGES.get(lang, {}).get('unsupported_file', 'Unsupported file format').format(SUPPORTED_EXTENSIONS)}",
                        parse_mode=ParseMode.HTML
                    )
                    return

                local_file = f"{chat_id}_{file_name}"
                try:
                    file_info = await message.bot.get_file(document.file_id)
                    await message.bot.download_file(file_info.file_path, destination=local_file)
                    parsed = await asyncio.to_thread(parser.from_file, local_file)
                    user_text = parsed.get("content", "").strip()
                    if not user_text:
                        await message.answer(
                            f"<b>System: </b>{MESSAGES.get(lang, {}).get('empty_file', 'Empty file')}",
                            parse_mode=ParseMode.HTML
                        )
                        return
                    await log_info(f"Документ успешно распарсен для {chat_id}", type_e="info")
                except Exception as e:
                    await log_info(f"Chat {chat_id} - ошибка при парсинге файла: {e}", type_e="error")
                    await message.answer(
                        f"<b>System: </b>{MESSAGES.get(lang, {}).get('error', 'Error')}",
                        parse_mode=ParseMode.HTML
                    )
                    return
                finally:
                    if os.path.exists(local_file):
                        os.remove(local_file)
        else:
            await log_info(f"Chat {chat_id} - тип контента {message.content_type} не обрабатывается", type_e="info")
            return

        # Добавляем подпись, если есть
        if signature:
            user_text = f"{signature}:\n{user_text}"

        # Обновляем историю пользователя
        await update_chat_history(chat_id, {"role": "user", "content": user_text})
        user_text_saved = [{"role": "user", "content": user_text}]
        await log_info(f"Chat {chat_id} - пользовательский запрос сохранён", type_e="info")

        # Отправляем сообщение "Обрабатывается..."
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            remove_keyboard = ReplyKeyboardRemove()
            processing_message = await message.answer(
                MESSAGES.get(lang, {}).get("processing", "Processing...").format(user_model),
                reply_markup=remove_keyboard
            )
        else:
            processing_message = await message.answer(
                MESSAGES.get(lang, {}).get("processing", "Processing...").format(user_model),
                reply_markup=await get_persistent_menu(chat_id)
            )
        await log_info(f"Chat {chat_id} - отправлено сообщение о начале обработки", type_e="info")

        # Проверяем лимиты пользователя
        if await check_user_limits(user_limits, chat_id):
            try:
                if generation_type == "image":
                    # Генерация изображения
                    ai_response = await generate_ai_response(
                        user_model, conversation=user_text, size=resolution, quality=quality
                    )
                    await log_info(f"Chat {chat_id} - получен ответ модели (изображение): {ai_response}", type_e="info")
                    
                    # Если ответ не является корректным URL (например, сообщение об ошибке), отправляем его пользователю
                    if not ai_response.startswith("http"):
                        await processing_message.delete()
                        await message.answer(ai_response, parse_mode=ParseMode.HTML)
                        return [ai_response, chat_id]

                    updated_data = await read_user_all_data(chat_id)
                    req_count = updated_data.get("requests")
                    req_count += 1
                    await update_user_data(chat_id, "requests", req_count)

                    # Удаляем сообщение "Обрабатывается..." и возвращаем результат
                    await processing_message.delete()
                    return [ai_response, chat_id]
                elif generation_type == "check":
                    # Проверка текста
                    vision_response = await generate_ai_response(
                        user_model, content_type=message.content_type, image_path=image_path
                    )
                    await log_info(f"Chat {chat_id} - получен ответ модели (предварительный): {vision_response}", type_e="info")

                    user_model = "gpt-4o-mini"
                    vision_role = MESSAGES[lang]['set_vision_role']
                    conversation_api = [{"role": "system", "content": vision_role}]
                    user_vision_response= [{"role": "user", "content": vision_response}]
                    conversation_api.extend(user_vision_response)
                    ai_response = await generate_ai_response(
                        user_model, set_answer, conversation=conversation_api
                    )
                    await log_info(f"Chat {chat_id} - получен ответ модели (проверка): {ai_response}", type_e="info")

                    # Удаляем сообщение "Обрабатывается..." и возвращаем результат
                    await processing_message.delete()
                    return [ai_response, chat_id]
                else:
                    # Формируем историю для запроса
                    conversation_api = [{"role": "system", "content": role}]
                    if context_enabled:
                        conversation_api.extend(await get_chat_history(chat_id))
                    else:
                        conversation_api.extend(user_text_saved)

                    # Запрашиваем ответ у модели
                    ai_response = await generate_ai_response(
                        user_model, set_answer, web_enabled, message.content_type, conversation_api, image_path
                    )
                    await log_info(f"Chat {chat_id} - получен ответ модели: {ai_response}", type_e="info")

                    # Обновляем историю с ответом
                    await update_chat_history(chat_id, {"role": "assistant", "content": ai_response})

                    # Подсчитываем токены
                    tokens_from_ai = await count_tokens_for_user_text(ai_response, user_model)
                    tokens_from_user = await count_tokens_for_user_text(
                        str(conversation_api[1]["content"]) if len(conversation_api) > 1 else user_text,
                        user_model
                    )
                    token_count_total = tokens_from_ai + tokens_from_user
                    await log_info(f"Chat {chat_id} - общее количество токенов: {token_count_total}", type_e="info")

                    # Обновляем лимиты пользователя
                    updated_data = await read_user_all_data(chat_id)
                    tokens = updated_data.get("tokens")
                    req_count = updated_data.get("requests")
                    tokens += token_count_total
                    req_count += 1
                    await update_user_data(chat_id, "tokens", tokens)
                    await update_user_data(chat_id, "requests", req_count)

                    # Удаляем сообщение "Обрабатывается..." и возвращаем ответ
                    await processing_message.delete()
                    safe_text = html.escape(ai_response)
                    return [f"<b>AI:</b> {safe_text}", chat_id]

            except Exception as api_error:
                await log_info(f"Chat {chat_id} - ошибка обращения к API: {api_error}", type_e="error")
                try:
                    await processing_message.delete()
                except Exception as delete_error:
                    await log_info(f"Ошибка при удалении 'Обрабатывается...': {delete_error}", type_e="error")
                return [f"<b>System: </b>{MESSAGES.get(lang, {}).get('error', 'Произошла ошибка')}", chat_id]
        else:
            # Лимиты превышены
            try:
                await processing_message.delete()
            except Exception as delete_error:
                await log_info(f"Ошибка при удалении 'Обрабатывается...': {delete_error}", type_e="error")
            return [f"<b>System: </b>{MESSAGES.get(lang, {}).get('limit_reached', 'Превышен лимит запросов')}", chat_id]

    except Exception as general_error:
        await log_info(f"Ошибка в handle_message для чата {chat_id}: {general_error}", type_e="error")
        raise
