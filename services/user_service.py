import asyncio
import os
import html
import openai
from tika import parser
from aiogram import types
from aiogram.enums import ParseMode, ChatType
from aiogram.types import ReplyKeyboardRemove
from services.openai_api import generate_ai_response
from services.utils import download_photo, convert_audio, count_tokens_for_user_text, check_user_limits, split_str_to_dict, parse_ai_result_response
from services.db_utils import (
    read_user_all_data,
    update_user_data,
    update_chat_history,
    get_chat_history
)
from keyboards.reply_kb import get_persistent_menu
from config import DEFAULT_LANGUAGES, PRODUCT_KEYS, SUPPORTED_EXTENSIONS, SUPPORTED_IMAGE_EXTENSIONS, MESSAGES, BOT_USERNAME
from logs import log_info


async def handle_message(message: types.Message, generation_type: str = None, bot_instance=None):
    """
    Unified function for processing incoming messages.
    Preserves original logic, adds asynchronous logging through log_info,
    protects code with try/except blocks and ensures proper cleanup of temporary files.
    
    Args:
        message: The message to process
        generation_type: Optional type of generation (image or check)
        bot_instance: Bot instance to use for file operations
    """
    try:
        # Get bot instance from message if not provided
        if bot_instance is None:
            bot_instance = message.bot
            
        # Determine chat_id based on chat type
        chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
        await log_info(f"Starting processing message from chat {chat_id}", type_e="info")

        # Extract user data
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

        # If image generation is required - change model
        if generation_type == "image":
            user_model = "dall-e-3"
        elif generation_type == "check":
            user_model = "AI_bot"

        # Initialize variables
        user_text = ""
        signature = message.caption if message.caption else None
        image_path = None

        # Process voice message
        if message.content_type == "voice":
            ogg_file, wav_file = None, None
            try:
                user_id = message.from_user.id
                ogg_file = f"{user_id}.ogg"
                wav_file = f"{user_id}.wav"
                file_info = await bot_instance.get_file(message.voice.file_id)
                await bot_instance.download_file(file_info.file_path, destination=ogg_file)
                await log_info(f"Voice file downloaded for {chat_id}", type_e="info")

                # Convert OGG -> WAV
                await convert_audio(ogg_file, wav_file)
                await log_info(f"Audio conversion completed for {chat_id}", type_e="info")

                # Recognize text with Whisper
                with open(wav_file, "rb") as audio:
                    transcript = openai.Audio.transcribe("whisper-1", audio)
                user_text = transcript.get("text", "")
                await log_info(f"Voice message text recognized for {chat_id}: {user_text}", type_e="info")
            except Exception as e:
                await log_info(f"Error processing voice message for {chat_id}: {e}", type_e="error")
                return
            finally:
                if ogg_file and os.path.exists(ogg_file):
                    os.remove(ogg_file)
                if wav_file and os.path.exists(wav_file):
                    os.remove(wav_file)

        # Process photo
        elif message.content_type == "photo":
            try:
                if generation_type == "check":
                    return [f"<b>System: </b>{MESSAGES.get(lang, {}).get(
                                                                        'load_original_image_file', 
                                                                        'Please upload the image in original quality (without compression), send it as a file (document).'
                                                                        )}", chat_id]
                image_path = f"{chat_id}_image.jpg"
                await download_photo(message.photo[-1], image_path, bot=bot_instance)
                await log_info(f"Photo successfully uploaded for {chat_id} to {image_path}", type_e="info")
                # Can add image text recognition
            except Exception as e:
                await log_info(f"Error uploading photo for {chat_id}: {e}", type_e="error")
                return

        # Process text message
        elif message.content_type == "text":
            text = message.text
            cleaned_text = text.replace(f"@{BOT_USERNAME}", "").strip()
            user_text = cleaned_text
            await log_info(f"Text message from {chat_id}: {user_text}", type_e="info")

        # Process documents
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
                file_info = await bot_instance.get_file(document.file_id)
                downloaded_file = await bot_instance.download_file(file_info.file_path)
                with open(image_path, "wb") as new_file:
                    # If downloaded_file is BytesIO, extract bytes with getvalue()
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
                    file_info = await bot_instance.get_file(document.file_id)
                    await bot_instance.download_file(file_info.file_path, destination=local_file)
                    parsed = await asyncio.to_thread(parser.from_file, local_file)
                    user_text = parsed.get("content", "").strip()
                    if not user_text:
                        await message.answer(
                            f"<b>System: </b>{MESSAGES.get(lang, {}).get('empty_file', 'Empty file')}",
                            parse_mode=ParseMode.HTML
                        )
                        return
                    await log_info(f"Document successfully parsed for {chat_id}", type_e="info")
                except Exception as e:
                    await log_info(f"Chat {chat_id} - error parsing file: {e}", type_e="error")
                    await message.answer(
                        f"<b>System: </b>{MESSAGES.get(lang, {}).get('error', 'Error')}",
                        parse_mode=ParseMode.HTML
                    )
                    return
                finally:
                    if os.path.exists(local_file):
                        os.remove(local_file)
        else:
            await log_info(f"Chat {chat_id} - content type {message.content_type} is not processed", type_e="info")
            return

        # Add signature if exists
        if signature:
            user_text = f"{signature}:\n{user_text}"

        # Update user history
        await update_chat_history(chat_id, {"role": "user", "content": user_text})
        user_text_saved = [{"role": "user", "content": user_text}]
        await log_info(f"Chat {chat_id} - user request saved", type_e="info")

        # Send "Processing..." message
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
        await log_info(f"Chat {chat_id} - processing start message sent", type_e="info")

        # Check user limits
        if await check_user_limits(user_limits, chat_id):
            try:
                if generation_type == "image":
                    # Generate image
                    ai_response = await generate_ai_response(
                        user_model, conversation=user_text, size=resolution, quality=quality
                    )
                    await log_info(f"Chat {chat_id} - model response received (image): {ai_response}", type_e="info")
                    
                    # If response is not a valid URL (e.g. error message), send it to user
                    if not ai_response.startswith("http"):
                        await processing_message.delete()
                        await message.answer(ai_response, parse_mode=ParseMode.HTML)
                        return [ai_response, chat_id]

                    updated_data = await read_user_all_data(chat_id)
                    req_count = updated_data.get("requests")
                    req_count += 1
                    await update_user_data(chat_id, "requests", req_count)

                    # Delete "Processing..." message and return result
                    await processing_message.delete()
                    return [ai_response, chat_id]
                elif generation_type == "check":
                    # Check text
                    vision_response = await generate_ai_response(
                        user_model, content_type=message.content_type, image_path=image_path
                    )
                    await log_info(f"Chat {chat_id} - model response received (preliminary): {vision_response}", type_e="info")

                    user_model = "deepseek-chat"
                    vision_role = MESSAGES[lang]['set_vision_role']
                    struckture_data = MESSAGES[lang]['check_struckture_data']
                    conversation_api = [{"role": "system", "content": vision_role}]
                    user_vision_response= [{"role": "user", "content": vision_response}]
                    conversation_api.extend(user_vision_response)
                    ai_response = await generate_ai_response(
                        user_model, set_answer, conversation=conversation_api
                    )
                    await log_info(f"Chat {chat_id} - model response received (check): {ai_response}", type_e="info")

                    product_info = None
                    response_data = {}
                    split_ai_response = await split_str_to_dict(ai_response, split_only_line=True)
                    for key, value in split_ai_response.items():
                        if key in PRODUCT_KEYS:
                            product_info = value
                        else:
                            response_data[key] = value
                    vision_sort_role = MESSAGES[lang]['set_vision_sort_role']
                    conversation_api = [{"role": "system", "content": vision_sort_role}]
                    user_vision_sort_response= [{"role": "user", "content": product_info}]
                    conversation_api.extend(user_vision_sort_response)
                    ai_sort_response = await generate_ai_response(
                        user_model, set_answer, conversation=conversation_api
                    )
                    await log_info(f"Chat {chat_id} - model response received (finish check): {ai_sort_response}", type_e="info")

                    ai_result_response = {}
                    for key in struckture_data:
                        if key in PRODUCT_KEYS and product_info is not None:
                            ai_result_response[key] = f"\n{ai_sort_response}"
                        else:
                            ai_result_response[key] = response_data.get(key, "")

                    result =  await parse_ai_result_response(ai_result_response, lang)
                    print(ai_sort_response)
                    print(ai_result_response)
                    # Delete "Processing..." message and return result
                    await processing_message.delete()
                    return [ai_result_response, chat_id, result]
                else:
                    # Form history for request
                    conversation_api = [{"role": "system", "content": role}]
                    if context_enabled:
                        conversation_api.extend(await get_chat_history(chat_id))
                    else:
                        conversation_api.extend(user_text_saved)

                    # Request response from model
                    ai_response = await generate_ai_response(
                        user_model, set_answer, web_enabled, message.content_type, conversation_api, image_path
                    )
                    await log_info(f"Chat {chat_id} - model response received: {ai_response}", type_e="info")

                    # Update history with response
                    await update_chat_history(chat_id, {"role": "assistant", "content": ai_response})

                    # Count tokens
                    tokens_from_ai = await count_tokens_for_user_text(ai_response, user_model)
                    tokens_from_user = await count_tokens_for_user_text(
                        str(conversation_api[1]["content"]) if len(conversation_api) > 1 else user_text,
                        user_model
                    )
                    token_count_total = tokens_from_ai + tokens_from_user
                    await log_info(f"Chat {chat_id} - total token count: {token_count_total}", type_e="info")

                    # Update user limits
                    updated_data = await read_user_all_data(chat_id)
                    tokens = updated_data.get("tokens")
                    req_count = updated_data.get("requests")
                    tokens += token_count_total
                    req_count += 1
                    await update_user_data(chat_id, "tokens", tokens)
                    await update_user_data(chat_id, "requests", req_count)

                    # Delete "Processing..." message and return response
                    await processing_message.delete()
                    safe_text = html.escape(ai_response)
                    return [f"<b>AI:</b> {safe_text}", chat_id]

            except Exception as api_error:
                await log_info(f"Chat {chat_id} - API error: {api_error}", type_e="error")
                try:
                    await processing_message.delete()
                except Exception as delete_error:
                    await log_info(f"Error deleting 'Processing...' message: {delete_error}", type_e="error")
                return [f"<b>System: </b>{MESSAGES.get(lang, {}).get('error', 'An error occurred')}", chat_id]
        else:
            # Limits exceeded
            try:
                await processing_message.delete()
            except Exception as delete_error:
                await log_info(f"Error deleting 'Processing...' message: {delete_error}", type_e="error")
            return [f"<b>System: </b>{MESSAGES.get(lang, {}).get('limit_reached', 'Request limit exceeded')}", chat_id]

    except Exception as general_error:
        await log_info(f"Error in handle_message for chat {chat_id}: {general_error}", type_e="error")
        raise