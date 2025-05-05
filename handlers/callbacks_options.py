import requests
from services import telegram_bot_init
from aiogram import Router, types
from aiogram.enums import ChatType, ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from config.config import DEFAULT_LANGUAGES, MESSAGES, CHECKS_ANALYTICS, SUPPORTED_IMAGE_EXTENSIONS
from logs.log import logs
from services.handle_message import handle_message
from services.utils import map_keys, dict_to_str, dict_to_str_for_webapp
from keyboards.reply_kb import get_persistent_menu
from handlers.callbacks_data import PromptState, PromtImageState, CheckImageState, MemoryInputFile
from keyboards.inline_kb_options import get_options_inline, get_generate_image_inline, get_add_check_inline, get_continue_add_check_accept_inline, get_add_check_accept_inline
from services.db_utils import read_user_all_data, write_user_to_json, update_user_data, clear_user_context
import services.telegram_bot_init as bot_tg
from services.telegram_bot_init import initialize_bots

callbacks_options_router = Router()

return_message = {}

@callbacks_options_router.callback_query(lambda call: call.data.startswith("options:"))
async def process_options_callback(query: types.CallbackQuery, state: FSMContext):
    try:
        chat_id = query.message.chat.id if query.message.chat.type == ChatType.PRIVATE else query.from_user.id

        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language") or DEFAULT_LANGUAGES

        current_resolution = user_data.get("resolution")
        quality = user_data.get("quality")
        current_quality = MESSAGES[lang]["set_quality"][0] if quality == "standard" else MESSAGES[lang]["set_quality"][1]

        data = query.data.split(":")[1]

        if data == "clear_context":
            await clear_user_context(chat_id)
            await logs(f"Context for user {chat_id} successfully cleared.", type_e="info")
            await query.answer(text=MESSAGES[lang]['context_cleared'], show_alert=False)

        elif data == "generate_image":
            # Show inline keyboard
            inline_generate_image_kb = await get_generate_image_inline(chat_id)
            message_sended = await query.message.edit_text(
                MESSAGES[lang]['generation_image_text'].format(current_resolution, current_quality),
                reply_markup=inline_generate_image_kb
            )

            # Set state waiting for text
            await state.set_state(PromtImageState.waiting_for_input_promt)
            await update_user_data(chat_id, "message_id", message_sended.message_id)
            await query.answer()

        elif data == "add_check":
            # Show inline keyboard
            inline_add_check_kb = await get_add_check_inline(chat_id)
            message_sended = await query.message.edit_text(
                MESSAGES[lang]['add_check_text'],
                reply_markup=inline_add_check_kb
            )
            await state.set_state(CheckImageState.waiting_for_image_input)
            await update_user_data(chat_id, "message_id", message_sended.message_id)
            await query.answer()

        elif data == "accept":
            await state.clear()
            list_of_dict_for_db = await map_keys(return_message, chat_id, lang)
            for dict_to_db in list_of_dict_for_db:
                check_successful_writing = await write_user_to_json(CHECKS_ANALYTICS, dict_to_db)
            persistent_menu = await get_persistent_menu(chat_id)
            if check_successful_writing:    
                await query.message.answer(text=MESSAGES[lang]['inline_kb']['options']['accept'], reply_markup=persistent_menu)
                await query.message.delete()
                continue_add_check_accept_inline = await get_continue_add_check_accept_inline(chat_id)
                await query.message.answer(
                    MESSAGES[lang]['inline_kb']['options']['continue'],
                    reply_markup=continue_add_check_accept_inline
                )
                await update_user_data(chat_id, "message_id", 0)
                return
            else:
                await query.message.answer(
                    text=f"<b>System: </b>{MESSAGES[lang]['inline_kb']['options']['error']}",
                    reply_markup=persistent_menu
                )
                await query.message.delete()
                return

        elif data == "cancel":
            # Cancel text input state
            await state.clear()
            persistent_menu = await get_persistent_menu(chat_id)
            await query.message.answer(text=MESSAGES[lang]['inline_kb']['options']['cancel'], reply_markup=persistent_menu)
            await query.message.delete()
            return

        elif data == "back":
            inline_options_kb = await get_options_inline(chat_id)
            await query.message.edit_text(
                MESSAGES[lang]['inline_kb']['options']['options_title'],
                reply_markup=inline_options_kb
            )
            await query.answer()
            await state.clear()
            return
        elif data == "close":
            await state.clear()
            await query.message.delete()
            await query.answer()
            await update_user_data(chat_id, "message_id", 0)
            return

        await logs(f"Options callback processed for chat_id {chat_id} with data: {data}", type_e="info")

    except Exception as e:
        await logs(f"Error in process_options_callback for chat_id {chat_id}: {e}", type_e="error")
        raise

@callbacks_options_router.message(PromtImageState.waiting_for_input_promt)
async def handle_text_input(message: types.Message, state: FSMContext):
    await logs(f"[FSM] Prompt generatio image received from {message.chat.id}: {message.text}", type_e="debug")

    chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id

    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language") or DEFAULT_LANGUAGES
    struckture_data = MESSAGES[lang]['check_struckture_data']
    message_id_for_deletion = user_data.get("message_id") or None
    if message_id_for_deletion and message_id_for_deletion != 0:
            try:
                await telegram_bot_init.bot.delete_message(
                chat_id=chat_id, 
                message_id=message_id_for_deletion
            )
            except TelegramBadRequest as e:
                await logs(f"Error deleting message with ID {message_id_for_deletion}: {e}", type_e="error")
    
    if message.content_type == types.ContentType.TEXT:
        # Process request through handle_message function (generation_type="image")
        return_message = await handle_message(message, tools_type="image")
        # Assuming handle_message returns a tuple (message, chat_id)
        persistent_menu = await get_persistent_menu(chat_id)
        
        # Check: if message_to doesn't start with "http", consider it an error message
        if not return_message.startswith("http"):
            await message.answer(
                text=return_message,
                parse_mode=ParseMode.HTML,
                reply_markup=persistent_menu
            )
            await logs(f"[FSM] Generated message is not a URL: {return_message}", type_e="error")
            await state.clear()
            return

        # Request image from received URL
        image_response = requests.get(return_message)
        if image_response.status_code == 200:
            from io import BytesIO
            image_bytes = BytesIO(image_response.content)
            input_file = MemoryInputFile(image_bytes, filename=f"{chat_id}.png")
            await message.answer_photo(
                photo=input_file,
                reply_markup=persistent_menu,
                parse_mode=ParseMode.HTML
            )
        else:
            # Handle other error codes
            await message.answer(
                text=f"<b>System:</b> {MESSAGES[lang]['error_load_image']}",
                parse_mode=ParseMode.HTML,
                reply_markup=persistent_menu
            )
            await logs(f"[FSM] Error {image_response.status_code} loading image: {return_message}", type_e="error")
        
        await state.clear()
        await logs(f"Image generation message processed for user {chat_id}", type_e="info")

@callbacks_options_router.message(CheckImageState.waiting_for_image_input)
async def handle_text_input(message: types.Message, state: FSMContext):
    global return_message
    await logs(f"[FSM] Image received from {message.chat.id}: {message.text}", type_e="debug")

    chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id

    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language") or DEFAULT_LANGUAGES
    struckture_data = MESSAGES[lang]['check_struckture_data']
    message_id_for_deletion = user_data.get("message_id") or None
    if message_id_for_deletion and message_id_for_deletion != 0:
            try:
                await telegram_bot_init.bot.delete_message(
                chat_id=chat_id, 
                message_id=message_id_for_deletion
            )
            except TelegramBadRequest as e:
                await logs(f"Error deleting message with ID {message_id_for_deletion}: {e}", type_e="error")

    if message.content_type == types.ContentType.PHOTO:
        await message.answer(
                        f"<b>System: </b>{MESSAGES.get(lang, {}).get('unsupported_file', 'Unsupported file format').format(SUPPORTED_IMAGE_EXTENSIONS)}",
                        parse_mode=ParseMode.HTML
                    )
    elif message.content_type == types.ContentType.DOCUMENT:
        try:
            # Process request through handle_message function (generation_type="check")
            return_message = await handle_message(message, tools_type="check", ai_handler="api_vision")

            if return_message is None:
                await bot_tg.bot.delete_message(
                    chat_id=chat_id, 
                    message_id=message_id_for_deletion
                )
                await bot_tg.bot.send_message(
                    chat_id=chat_id, 
                    text=f"<b>System: </b>{MESSAGES.get(lang, {}).get('no_answer', 'No answer available.')}", 
                    parse_mode=ParseMode.HTML
                )
                return

            message_to_web_app = [return_message[k] for k in struckture_data]
            message_to_web_app[4] = await dict_to_str_for_webapp(message_to_web_app[4])
            message_to = await dict_to_str(return_message)
            persistent_menu = await get_persistent_menu(chat_id)
            inline_add_check_accept_kb = await get_add_check_accept_inline(chat_id, message_to_web_app)
            message_sended = await message.answer(
                text=message_to,
                reply_markup=inline_add_check_accept_kb,
                parse_mode=ParseMode.HTML
            )
            await update_user_data(chat_id, "message_id", message_sended.message_id)
        except Exception as e:
            await logs(f"Error processing document message: {e}", type_e="error")
    await state.clear()

async def process_user_input_list(user_text_input: list):
    global return_message
    try:
        chat_id = user_text_input[7]
        user_text_input.pop()
        print(user_text_input, type(user_text_input))
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language") or DEFAULT_LANGUAGES
        message_id_for_deletion = user_data.get("message_id") or None
        struckture_data = MESSAGES[lang]['check_struckture_data']
        if bot_tg is None:
            await initialize_bots()
        if message_id_for_deletion and message_id_for_deletion != 0:
            try:
                await bot_tg.bot.delete_message(
                chat_id=chat_id, 
                message_id=message_id_for_deletion
            )
            except TelegramBadRequest as e:
                await logs(f"Error deleting message with ID {message_id_for_deletion}: {e}", type_e="error")

        message_raw = "\n".join(f"{key}: {user_text_input[i]}" for i, key in enumerate(struckture_data))
        temporary_message = await bot_tg.bot.send_message(
            chat_id=chat_id, 
            text=f"Data received, processing...\n{message_raw}", 
            parse_mode=ParseMode.HTML)
        
        return_message = await handle_message(temporary_message, tools_type="check", user_input_list=user_text_input)
        if return_message is None:
            await bot_tg.bot.delete_message(
                chat_id=chat_id, 
                message_id=temporary_message.message_id
            )
            await bot_tg.bot.send_message(
                chat_id=chat_id, 
                text=f"<b>System: </b>{MESSAGES.get(lang, {}).get('no_answer', 'No answer available.')}", 
                parse_mode=ParseMode.HTML
            )
            return
        await bot_tg.bot.delete_message(
            chat_id=chat_id, 
            message_id=temporary_message.message_id
        )    
        message_to_web_app = [return_message[k] for k in struckture_data]
        message_to_web_app[4] = await dict_to_str_for_webapp(message_to_web_app[4])
        message_to = await dict_to_str(return_message)
        persistent_menu = await get_persistent_menu(chat_id)
        inline_add_check_accept_kb = await get_add_check_accept_inline(chat_id, message_to_web_app)
        message_sended = await bot_tg.bot.send_message(chat_id=chat_id, text=message_to, reply_markup=inline_add_check_accept_kb, parse_mode=ParseMode.HTML)
        await update_user_data(chat_id, "message_id", message_sended.message_id)
        
        await logs(f"User input list processed for chat_id {chat_id}", type_e="info")
    except Exception as e:
        await logs(f"Error processing user input list for chat_id {chat_id}: {e}", type_e="error")
        raise