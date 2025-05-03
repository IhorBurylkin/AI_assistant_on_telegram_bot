import os
import asyncio
import aiofiles
import json
import regex
from tika import parser
from aiogram import types
from aiogram.enums import ChatType
from config.config import BOT_USERNAME, DEFAULT_LANGUAGES, MESSAGES, SUPPORTED_EXTENSIONS, PRODUCT_KEYS
from logs.log import logs
from services.db_utils import read_user_all_data
from keyboards.reply_kb import get_persistent_menu
from services.utils import check_user_limits, resize_image, convert_audio
from services.type_message_handlers.text_message import text_message_ai_response
from services.type_message_handlers.photo_message import photo_message_ai_response
from services.type_message_handlers.voice_message import voice_message_ai_response
from services.type_message_handlers.document_message import document_message_ai_response
from services.type_message_handlers.generate_image import generate_image_ai_response
from services.type_message_handlers.analysis_check import analysis_check_from_photo, analysis_check_from_text
from logs.errors import OpenAIServiceError, ApplicationError

processing_message = None

async def handle_message(message: types.Message, tools_type = None, ai_handler = None, user_input_list = None):
    async def extract_with_recursive_regex(s: str) -> str:
        pattern = r'\{(?:[^{}]|(?R))*\}'     
        m = regex.search(pattern, s)
        return m.group(0) if m else ""

    async def vision_resp(chat_id, lang, user_model, set_answer, vision_role_one_req, user_limits, image_path):
        try:
            json_text = await analysis_check_from_photo(chat_id, lang, user_model, set_answer, vision_role_one_req, user_limits, image_path)
            clear_json = await extract_with_recursive_regex(json_text)
            ai_response = json.loads(clear_json)
            await logs(f"Chat {chat_id} - model response received (vision_resp): {ai_response}{type(ai_response)}", type_e="info")
            return ai_response
        except Exception as e:
            await logs(f"Error in first_resp: {e} for {json_text}{type(json_text)}", type_e="error")

    async def text_resp(chat_id, lang, user_model, set_answer, vision_role_one_req, user_limits, user_input_list):
        try:
            user_model="deepseek-chat"
            json_text = await analysis_check_from_text(chat_id, lang, user_model, web_enabled, set_answer, vision_role_one_req, user_limits, user_input_list)
            clear_json = await extract_with_recursive_regex(json_text)
            ai_response = json.loads(clear_json)
            await logs(f"Chat {chat_id} - model response received (text_resp): {ai_response}{type(ai_response)}", type_e="info")
            return ai_response
        except Exception as e:
            await logs(f"Error in text_resp: {e}", type_e="error")
            return f"<b>System: </b>{MESSAGES.get(lang, {}).get('error', 'An error occurred')}"
        
    chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
    signature = message.caption if message.caption else None
    user_text = ""
    result_answer_from_ai = None

    await logs(f"Starting handle message from chat {chat_id}", type_e="info")

    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language", DEFAULT_LANGUAGES)
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


    vision_role = MESSAGES[lang]['set_vision_role']
    vision_sort_role = MESSAGES[lang]['set_vision_sort_role']
    vision_role_one_req = MESSAGES[lang]['set_vision_role_one_req']
    struckture_data = MESSAGES[lang]['check_struckture_data']

    user_model="dall-e-3" if tools_type == "image" else user_model
    user_model="AI_bot" if tools_type == "check" else user_model

    try:
        if await check_user_limits(user_limits, chat_id):
            global processing_message
            if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                remove_keyboard = types.ReplyKeyboardRemove()
                processing_message = await message.answer(
                    MESSAGES.get(lang, {}).get("processing", "Processing...").format(user_model),
                    reply_markup=remove_keyboard
                )
            else:
                processing_message = await message.answer(
                    MESSAGES.get(lang, {}).get("processing", "Processing...").format(user_model),
                    reply_markup=await get_persistent_menu(chat_id)
                )
            await logs(f"Chat {chat_id} - processing start message sent", type_e="info")

            if message.content_type == "text" and tools_type == None:
                text = message.text
                cleaned_text = text.replace(f"@{BOT_USERNAME}", "").strip()
                user_text = cleaned_text
                await logs(f"Text message from {chat_id}: {user_text}", type_e="info")
                result_answer_from_ai = await text_message_ai_response(chat_id, lang, user_model, context_enabled, web_enabled, set_answer, role, user_limits, user_text)

            elif message.content_type == "text" and tools_type == "image":
                text = message.text
                cleaned_text = text.replace(f"@{BOT_USERNAME}", "").strip()
                user_text = cleaned_text
                await logs(f"Text message from {chat_id}: {user_text}", type_e="info")
                result_answer_from_ai = await generate_image_ai_response(chat_id, lang, user_model, resolution, quality, user_limits, user_text)

            elif message.content_type == "text" and tools_type == "check":
                try:
                    user_text_input = "\n".join(f"{key}: {user_input_list[i]}" for i, key in enumerate(struckture_data))
                    result_answer_from_ai = await text_resp(chat_id, lang, user_model, set_answer, vision_role_one_req, user_limits, user_text_input)
                except Exception as e:
                    await logs(f"Error in text_resp: {e}", type_e="error")
                    return f"<b>System: </b>{MESSAGES.get(lang, {}).get('error', 'An error occurred')}"
            
            elif message.content_type == "photo":
                try:
                    image_path = f"{chat_id}_image.jpg"
                    file_info = await message.bot.get_file(message.photo[-1] .file_id)
                    await message.bot.download_file(file_info.file_path, destination=image_path)
                    await resize_image(image_path)
                    if signature:
                        user_text = f"{signature}:\n{user_text}"
                    result_answer_from_ai = await photo_message_ai_response(chat_id, lang, user_model, context_enabled, web_enabled, set_answer, role, user_limits, user_text, image_path)
                    await logs(f"Photo successfully uploaded for {chat_id} to {image_path}", type_e="info")
                finally:
                    if os.path.exists(image_path):
                        os.remove(image_path)

            elif message.content_type == "voice":
                try:
                    user_id = message.from_user.id
                    ogg_file = f"{user_id}.ogg"
                    wav_file = f"{user_id}.wav"
                    file_info = await message.bot.get_file(message.voice.file_id)
                    await message.bot.download_file(file_info.file_path, destination=ogg_file)
                    await logs(f"Voice file downloaded for {chat_id}", type_e="info")

                    await convert_audio(ogg_file, wav_file)
                    await logs(f"Audio conversion completed for {chat_id}", type_e="info")
                    result_answer_from_ai = await voice_message_ai_response(chat_id, lang, user_model, context_enabled, web_enabled, set_answer, role, user_limits, user_text, wav_file)
                    await logs(f"Voice message AI response for {chat_id}: {result_answer_from_ai}", type_e="info")
                finally:
                    if os.path.exists(ogg_file):
                        os.remove(ogg_file)
                    if os.path.exists(wav_file):
                        os.remove(wav_file)

            elif message.content_type == "document" and tools_type == None:
                document = message.document
                file_name = document.file_name
                doc_file = f"{chat_id}_{file_name}"
                try:
                    if not any(file_name.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                        await processing_message.delete()
                        return f"<b>System: </b>{MESSAGES.get(lang, {}).get('unsupported_file', 'Unsupported file format').format(SUPPORTED_EXTENSIONS)}"
                    file_info = await message.bot.get_file(document.file_id)
                    await message.bot.download_file(file_info.file_path, destination=doc_file)
                    parsed = await asyncio.to_thread(parser.from_file, doc_file)
                    user_text = parsed.get("content", "").strip()
                    if not user_text:
                        return f"<b>System: </b>{MESSAGES.get(lang, {}).get('empty_file', 'Empty file')}"
                    await logs(f"Document successfully parsed for {chat_id}", type_e="info")
                    result_answer_from_ai = await document_message_ai_response(chat_id, lang, user_model, context_enabled, web_enabled, set_answer, role, user_limits, user_text)
                    await logs(f"Document message AI response for {chat_id}: {result_answer_from_ai}", type_e="info")
                finally:
                    if os.path.exists(doc_file):
                        os.remove(doc_file)
            
            elif message.content_type == "document" and tools_type == "check":
                image_path = f"{chat_id}_image.jpg"
                try:
                    if ai_handler == "api_vision":
                        try:
                            file_info = await message.bot.get_file(message.document.file_id)
                            downloaded_file = await message.bot.download_file(file_info.file_path)
                            async with aiofiles.open(image_path, "wb") as new_file:
                                if hasattr(downloaded_file, "getvalue"):
                                    await new_file.write(downloaded_file.getvalue())
                                    await logs(f"Document successfully downloaded: {image_path}", type_e="info")
                                else:
                                    await new_file.write(downloaded_file)
                            result_answer_from_ai = await vision_resp(chat_id, lang, user_model, set_answer, vision_role_one_req, user_limits, image_path)
                        except Exception as e:
                            await logs(f"Error in vision_resp: {e}", type_e="error")
                            return f"<b>System: </b>{MESSAGES.get(lang, {}).get('error', 'An error occurred')}"
                finally:
                    if os.path.exists(image_path):
                        os.remove(image_path)
            
            if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                await processing_message.delete()
            else:
                await processing_message.delete()
            await logs(f"Chat {chat_id} - processing message deleted", type_e="info")

            if result_answer_from_ai is not None:
                return result_answer_from_ai
            else:
                return None
        else:
            try:
                await processing_message.delete()
            except Exception as delete_error:
                await logs(f"Module: handle_message. Error deleting 'Processing...' message: {delete_error}", type_e="error")
            return f"<b>System: </b>{MESSAGES.get(lang, {}).get('limit_reached', 'Request limit exceeded')}"
    except OpenAIServiceError as e:
        await logs(f"Error in handle_message: {e}", type_e="error") 
        await processing_message.delete()
        if e.status_code == 429:
            return f"<b>System: </b>{MESSAGES.get(lang, {}).get('error_429', f'{e.status_code}: {e.code}')}"
        elif e.status_code == 422:
            return f"<b>System: </b>{MESSAGES.get(lang, {}).get('error_422', f'{e.status_code}: {e.code}')}"
        elif e.status_code == 400:
            return f"<b>System: </b>{MESSAGES.get(lang, {}).get('error_400', f'{e.status_code}: {e.code}')}"
        else:
            return f"<b>System: </b>OpenAI error {e.status_code} / {e.code}"
    except ApplicationError as e:
        await logs(f"Error in handle_message for chat {chat_id} with {message.content_type}: {e}", type_e="error")
        await processing_message.delete()
        return f"<b>System: </b>{MESSAGES.get(lang, {}).get('error', 'An error occurred')}"
