import requests
from aiogram import types, Router, F
from aiogram.enums import ChatType, ParseMode
from services.db_utils import read_user_all_data, update_user_data, clear_user_context, update_checks_analytics_columns, write_user_to_json
from services.utils import get_current_datetime, dict_to_str, map_keys, split_str_to_dict
from config import MESSAGES, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGES, CHECKS_ANALYTICS, CHATGPT_MODEL
from aiogram.types import ForceReply
from aiogram.fsm.context import FSMContext
from io import BytesIO
from logs import log_info
from services.user_service import handle_message
from keyboards.reply_kb import get_persistent_menu
from keyboards.inline_kb import (
    get_settings_inline, 
    get_model_inline, 
    get_answer_inline, 
    get_role_inline, 
    get_language_inline, 
    get_options_inline, 
    get_profile_inline, 
    get_limits_inline, 
    get_generation_inline, 
    get_generate_image_inline,
    get_add_check_inline,
    get_add_check_accept_inline,
    get_continue_add_check_accept_inline,
    get_calendar
    ) 
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.state import State, StatesGroup
from aiogram.types.input_file import InputFile as AbstractInputFile

callbacks_router = Router()

message_to_db = {}
list_of_dict = []

class CheckState(StatesGroup):
    waiting_for_input = State()
    check_data = State()

class PromptState(StatesGroup):
    waiting_for_input = State()

class MemoryInputFile(AbstractInputFile):
    def __init__(self, file: BytesIO, filename: str):
        self.file = file
        self.filename = filename

    def read(self, *args, **kwargs):
        # If the first argument is not int or None, ignore it
        if args and not isinstance(args[0], (int, type(None))):
            return self.file.read()
        return self.file.read(*args, **kwargs)

@callbacks_router.callback_query(lambda call: call.data.startswith("settings:"))
async def process_settings_callback(query: types.CallbackQuery):
    try:
        # Determine chat_id based on chat type
        chat_id = query.message.chat.id if query.message.chat.type == ChatType.PRIVATE else query.from_user.id

        # Get user's language, if not found - use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Determine command from callback_data
        data = query.data.split(":")[1]

        if data == "set_model":
            inline_model_kb = await get_model_inline(chat_id)
            await query.message.edit_text(MESSAGES[lang]['choose_model'], reply_markup=inline_model_kb)
            await query.answer()
        elif data == "toggle_context":
            current = user_data.get("context_enabled")
            new_value = not current
            await update_user_data(chat_id, "context_enabled", new_value)
            if new_value == True:
                await query.answer(text=MESSAGES[lang]['context_enabled'], show_alert=False)
            else:
                await query.answer(text=MESSAGES[lang]['context_disabled'], show_alert=False)
            new_markup = await get_settings_inline(chat_id)
            # If markup changed, update it
            if query.message.reply_markup != new_markup:
                await query.message.edit_reply_markup(reply_markup=new_markup)
            else:
                await log_info("⚠️ Markup didn't change, update cancelled.", type_e="warning")
        elif data == "web_enabled":
            user_data = await read_user_all_data(chat_id)
            user_model = user_data.get("model")
            current = user_data.get("web_enabled")
            new_value = not current
            await update_user_data(chat_id, "web_enabled", new_value)
            if new_value:
                if user_model == "gpt-4o-mini":
                    user_model = "gpt-4o-mini-search-preview"
                elif user_model == "gpt-4o":
                    user_model = "gpt-4o-search-preview"
            else:
                if user_model == "gpt-4o-mini-search-preview":
                    user_model = "gpt-4o-mini"
                elif user_model == "gpt-4o-search-preview":
                    user_model = "gpt-4o"
            if new_value == True:
                await query.answer(text=MESSAGES[lang]['web_enabled'], show_alert=False)
                await update_user_data(chat_id, "model", user_model)
                print("web_enabled", new_value, user_model)
            else:
                await query.answer(text=MESSAGES[lang]['web_disabled'], show_alert=False)
                await update_user_data(chat_id, "model", user_model)
                print("web_disenabled", new_value, user_model)
            new_markup = await get_settings_inline(chat_id)
            # If markup changed, update it
            if query.message.reply_markup != new_markup:
                await query.message.edit_reply_markup(reply_markup=new_markup)
            else:
                await log_info("⚠️ Markup didn't change, update cancelled.", type_e="warning")
        elif data == "set_answer":
            inline_answer_kb = await get_answer_inline(chat_id)
            await query.message.edit_text(MESSAGES[lang]['answer_selection'], reply_markup=inline_answer_kb)
            await query.answer()
        elif data == "role":
            inline_role_kb = await get_role_inline(chat_id)
            await query.message.edit_text(MESSAGES[lang]['role_selection'], reply_markup=inline_role_kb)
            await query.answer()
        elif data == "generation":
            inline_generation_kb = await get_generation_inline(chat_id)
            await query.message.edit_text(MESSAGES[lang]['generation_selection'], reply_markup=inline_generation_kb)
            await query.answer()
        elif data == "interface_language":
            inline_lang_kb = await get_language_inline(chat_id)
            await query.message.edit_text(MESSAGES[lang]['language_selection'], reply_markup=inline_lang_kb)
            await query.answer()
        elif data == "close":
            await query.message.delete()
            await query.answer()
        elif data == "back":
            inline_settings_kb = await get_settings_inline(chat_id)
            await query.message.edit_text(MESSAGES[lang]['settings_title'], reply_markup=inline_settings_kb)
            await query.answer()

        await log_info(f"Settings callback processed for chat_id {chat_id} with data: {data}", type_e="info")
    except Exception as e:
        await log_info(f"Error in process_settings_callback for chat_id {chat_id}: {e}", type_e="error")
        raise

@callbacks_router.callback_query(lambda call: call.data.startswith("options:"))
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
            await log_info(f"Context for user {chat_id} successfully cleared.", type_e="info")
            await query.answer(text=MESSAGES[lang]['context_cleared'], show_alert=False)

        elif data == "generate_image":
            # Show inline keyboard
            inline_generate_image_kb = await get_generate_image_inline(chat_id)
            await query.message.edit_text(
                MESSAGES[lang]['generation_image_text'].format(current_resolution, current_quality),
                reply_markup=inline_generate_image_kb
            )

            # Set state waiting for text
            await state.set_state(PromptState.waiting_for_input)
            await query.answer()

        elif data == "add_check":
            # Show inline keyboard
            inline_add_check_kb = await get_add_check_inline(chat_id)
            await query.message.edit_text(
                MESSAGES[lang]['add_check_text'],
                reply_markup=inline_add_check_kb
            )
            await state.set_state(PromptState.waiting_for_input)
            await query.answer()

        elif data == "accept":
            await state.clear()
            #dict_for_db = await map_keys(message_to_db, chat_id, lang)
            list_of_dict_for_db = await map_keys(list_of_dict, chat_id, lang)
            for dict_to_db in list_of_dict_for_db:
                #dict_for_db['product'] = await split_str_to_dict(dict_for_db['product'], split_only_line=True)
                await write_user_to_json(CHECKS_ANALYTICS, dict_to_db)
            #print(dict_for_db)
            #dict_for_db['product'] = await split_str_to_dict(dict_for_db['product'], split_only_line=True)
            #await write_user_to_json(CHECKS_ANALYTICS, dict_for_db)
            persistent_menu = await get_persistent_menu(chat_id)
            await query.message.answer(text=MESSAGES[lang]['inline_kb']['options']['accept'], reply_markup=persistent_menu)
            await query.message.delete()
            continue_add_check_accept_inline = await get_continue_add_check_accept_inline(chat_id)
            await query.message.answer(
                MESSAGES[lang]['inline_kb']['options']['continue'],
                reply_markup=continue_add_check_accept_inline
            )
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
            return

        await log_info(f"Options callback processed for chat_id {chat_id} with data: {data}", type_e="info")

    except Exception as e:
        await log_info(f"Error in process_options_callback for chat_id {chat_id}: {e}", type_e="error")
        raise

@callbacks_router.message(PromptState.waiting_for_input)
async def handle_text_input(message: types.Message, state: FSMContext):
    global message_to_db, list_of_dict
    await log_info(f"[FSM] Prompt received from {message.chat.id}: {message.text}", type_e="debug")

    chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id

    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language") or DEFAULT_LANGUAGES
    
    if message.content_type == types.ContentType.TEXT:
        # Process request through handle_message function (generation_type="image")
        return_message = await handle_message(message, generation_type="image")
        # Assuming handle_message returns a tuple (message, chat_id)
        message_to, new_chat_id = return_message[0], return_message[1]
        persistent_menu = await get_persistent_menu(new_chat_id)
        
        # Check: if message_to doesn't start with "http", consider it an error message
        if not message_to.startswith("http"):
            await message.answer(
                text=message_to,
                parse_mode=ParseMode.HTML,
                reply_markup=persistent_menu
            )
            await log_info(f"[FSM] Generated message is not a URL: {message_to}", type_e="error")
            await state.clear()
            return

        # Request image from received URL
        image_response = requests.get(message_to)
        if image_response.status_code == 200:
            from io import BytesIO
            image_bytes = BytesIO(image_response.content)
            input_file = MemoryInputFile(image_bytes, filename=f"{new_chat_id}.png")
            await message.answer_photo(
                photo=input_file,
                reply_markup=persistent_menu,
                parse_mode=ParseMode.HTML
            )
        else:
            # Handle other error codes
            error_text = f"<b>System:</b> {MESSAGES[lang]['error_load_image']}"
            await message.answer(
                text=error_text,
                parse_mode=ParseMode.HTML,
                reply_markup=persistent_menu
            )
            await log_info(f"[FSM] Error {image_response.status_code} loading image: {message_to}", type_e="error")
        
        await log_info(f"Image generation message processed for user {new_chat_id}", type_e="info")
        
    elif message.content_type == types.ContentType.PHOTO:
        # Process request through handle_message function (generation_type="check")
        return_message = await handle_message(message, generation_type="check")
        # Assuming handle_message returns a tuple (message, chat_id)
        message_to, new_chat_id, list_of_dict = return_message[0], return_message[1], return_message[2]
        persistent_menu = await get_persistent_menu(new_chat_id)
        await message.answer(
            text=message_to,
            reply_markup=persistent_menu,
            parse_mode=ParseMode.HTML
        )
    elif message.content_type == types.ContentType.DOCUMENT:
        # Process request through handle_message function (generation_type="check")
        return_message = await handle_message(message, generation_type="check")
        # Assuming handle_message returns a tuple (message, chat_id)
        message_to_db, new_chat_id, list_of_dict = return_message[0], return_message[1], return_message[2]
        message_to = await dict_to_str(message_to_db)
        persistent_menu = await get_persistent_menu(new_chat_id)
        inline_add_check_accept_kb = await get_add_check_accept_inline(new_chat_id)
        await message.answer(
            text=message_to,
            reply_markup=inline_add_check_accept_kb,
            parse_mode=ParseMode.HTML
        )
    await state.clear()

@callbacks_router.callback_query(lambda call: call.data.startswith("profile:"))
async def process_profile_callback(query: types.CallbackQuery):
    try:
        # Determine chat_id based on chat type
        chat_id = query.message.chat.id if query.message.chat.type == ChatType.PRIVATE else query.from_user.id

        # Get user's language, if not found - use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Determine command from callback_data
        data = query.data.split(":")[1]

        if data == "usage_limit":
            inline_limit_kb, message_to_send = await get_limits_inline(chat_id)
            await query.message.edit_text(message_to_send, reply_markup=inline_limit_kb)
            await query.answer()
        elif data == "back":
            inline_profile_kb = await get_profile_inline(chat_id)
            await query.message.edit_text(MESSAGES[lang]['inline_kb']['profile']['profile_title'], reply_markup=inline_profile_kb)
            await query.answer()
        elif data == "calendar":
            inline_calendar_kb = await get_calendar(chat_id)
            await query.message.edit_text(MESSAGES[lang]['inline_kb']['profile']['calendar'], reply_markup=inline_calendar_kb)
            await query.answer()

        await log_info(f"Profile callback processed for chat_id {chat_id} with data: {data}", type_e="info")
    except Exception as e:
        await log_info(f"Error in process_profile_callback for chat_id {chat_id}: {e}", type_e="error")
        raise

@callbacks_router.callback_query(lambda call: call.data.startswith("model:"))
async def process_set_model_callback(query: types.CallbackQuery):
    try:
        # Determine chat_id based on chat type
        chat_id = query.message.chat.id if query.message.chat.type == ChatType.PRIVATE else query.from_user.id

        # Get current web_enabled status
        user_data = await read_user_all_data(chat_id)
        web_enabled = user_data.get("web_enabled")
        # Extract new model from callback_data
        new_model = query.data.split(":", 1)[1]
        
        # Update global model
        global CHATGPT_MODEL
        CHATGPT_MODEL = new_model

        # If web_enabled is active, adjust model name
        if web_enabled:
            if CHATGPT_MODEL == "gpt-4o-mini":
                CHATGPT_MODEL = "gpt-4o-mini-search-preview"
            elif CHATGPT_MODEL == "gpt-4o":
                CHATGPT_MODEL = "gpt-4o-search-preview"

        # Update user data in storage
        await update_user_data(chat_id, "model", CHATGPT_MODEL)

        # Get user's language; if language not found, use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        await log_info(f"ChatGPT model changed to: {CHATGPT_MODEL} for chat_id {chat_id}", type_e="info")

        # Update inline settings menu and get persistent menu
        inline_menu = await get_settings_inline(chat_id)
        persistent_menu = await get_persistent_menu(chat_id)

        await query.message.edit_text(MESSAGES[lang]['settings_title'])
        await query.message.edit_reply_markup(reply_markup=inline_menu)

        # Send confirmation message in private chat
        if query.message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            # Form message based on language
            response_text = (
                f"<b>System: </b>Model changed to: {new_model}"
                if lang == "ru" else
                f"<b>System: </b>Model changed to: {new_model}"
            )
            await query.message.answer(
                text=response_text,
                show_alert=False,
                reply_markup=persistent_menu,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        await log_info(f"Error in process_set_model_callback for chat_id {chat_id}: {e}", type_e="error")
        raise

@callbacks_router.callback_query(lambda call: call.data.startswith("lang:"))
async def process_lang_callback(query: types.CallbackQuery):
    try:
        chosen_lang = query.data.split(":", 1)[1]
        chat_id = query.message.chat.id if query.message.chat.type == ChatType.PRIVATE else query.from_user.id

        # Update language if supported
        if chosen_lang in SUPPORTED_LANGUAGES:
            await update_user_data(chat_id, "language", chosen_lang)
        
        # Get updated language; if not found, use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Get new inline settings menu and persistent menu
        inline_menu = await get_settings_inline(chat_id)
        persistent_menu = await get_persistent_menu(chat_id)

        # Update message markup
        await query.message.edit_text(MESSAGES[lang]['settings_title'])
        await query.message.edit_reply_markup(reply_markup=inline_menu)

        # Send confirmation message in private chat
        if query.message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            response_text = (
                f"<b>System: </b>Language changed to: {chosen_lang}"
                if lang == "ru" else
                f"<b>System: </b>Language changed to: {chosen_lang}"
            )
            await query.message.answer(
                text=response_text,
                show_alert=False,
                reply_markup=persistent_menu,
                parse_mode=ParseMode.HTML
            )

        await log_info(f"Language changed for user {chat_id} to {chosen_lang}", type_e="info")
    except Exception as e:
        await log_info(f"Error in process_lang_callback for user {chat_id}: {e}", type_e="error")
        raise

@callbacks_router.callback_query(lambda call: call.data.startswith("answer:"))
async def process_answer_callback(query: types.CallbackQuery):
    try:
        # Extract selected answer option
        chosen_set_answer = query.data.split(":", 1)[1]
        options = {
            "minimal": [0.1, 0.9],
            "moderate": [0.3, 0.9],
            "increased": [0.6, 0.9],
            "maximum": [0.9, 1.0]
        }
        selected_value = options.get(chosen_set_answer, [0.1, 0.9])
        
        # Determine chat_id
        chat_id = query.message.chat.id if query.message.chat.type == ChatType.PRIVATE else query.from_user.id
        
        # Update user data: set_answer and set_answer_value
        await update_user_data(chat_id, "set_answer", chosen_set_answer)
        await update_user_data(chat_id, "set_answer_temp", selected_value[0])
        await update_user_data(chat_id, "set_answer_top_p", selected_value[1])
        
        # Get user's language, if not found, use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES
        
        # Get updated inline menu and persistent menu
        inline_menu = await get_settings_inline(chat_id)
        persistent_menu = await get_persistent_menu(chat_id)
        
        # Update message markup
        await query.message.edit_text(MESSAGES[lang]['settings_title'])
        await query.message.edit_reply_markup(reply_markup=inline_menu)
        
        # Send confirmation message in private chat
        if query.message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            response_text = (
                f"<b>System: </b>AI response accuracy: {chosen_set_answer}"
                if lang == "ru"
                else f"<b>System: </b>AI response accuracy: {chosen_set_answer}"
            )
            await query.message.answer(
                text=response_text,
                show_alert=False,
                reply_markup=persistent_menu,
                parse_mode=ParseMode.HTML
            )
        
        await log_info(f"Answer configured for user {chat_id}: {chosen_set_answer}", type_e="info")
    except Exception as e:
        await log_info(f"Error in process_answer_callback for user {chat_id}: {e}", type_e="error")
        raise

@callbacks_router.callback_query(lambda call: call.data.startswith("role:"))
async def process_role_callback(query: types.CallbackQuery):
    try:
        # Determine chat_id
        chat_id = query.message.chat.id if query.message.chat.type == ChatType.PRIVATE else query.from_user.id

        # Get user's language, if not found - use default value
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language") or DEFAULT_LANGUAGES

        # Get current user role (if any)
        role_from_user = user_data.get("role") or ''
        roles_list = MESSAGES[lang]['set_role']
        role_system_list = MESSAGES[lang]['set_role_system']

        # Extract selected role from callback_data
        chosen_set_role = query.data.split(":", 1)[1]

        # If "other role" option is selected (usually last item in list), request input from user
        if chosen_set_role == roles_list[4]:
            await query.message.answer(MESSAGES[lang]['enter_your_role'], reply_markup=ForceReply(selective=True))
            await query.answer()
            return

        # Determine corresponding system role value
        options = {
            roles_list[0]: role_system_list[0],
            roles_list[1]: role_system_list[1],
            roles_list[2]: role_system_list[2],
            roles_list[3]: role_system_list[3],
            roles_list[4]: role_from_user  # if "other role" option, keep current value
        }
        selected_value = options.get(chosen_set_role, role_system_list[0])

        # Update user role
        await update_user_data(chat_id, "role", selected_value)

        # Get updated inline settings menu and persistent menu
        inline_menu = await get_settings_inline(chat_id)
        persistent_menu = await get_persistent_menu(chat_id)

        # Update message markup
        await query.message.edit_text(MESSAGES[lang]['settings_title'])
        await query.message.edit_reply_markup(reply_markup=inline_menu)

        # Send confirmation in private chat
        if query.message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            confirmation_text = (
                f"<b>System: </b>Selected AI role: {selected_value}"
                if lang == "ru" else
                f"<b>System: </b>Selected AI role: {selected_value}"
            )
            await query.message.answer(
                text=confirmation_text,
                reply_markup=persistent_menu,
                parse_mode=ParseMode.HTML
            )

        await query.answer()
        await log_info(f"Role for user {chat_id} updated to: {selected_value}", type_e="info")
    except Exception as e:
        await log_info(f"Error in process_role_callback for user {chat_id}: {e}", type_e="error")
        raise

@callbacks_router.callback_query(lambda call: call.data.startswith("generation:"))
async def process_generation_callback(query: types.CallbackQuery):
    try:
        chat_id = query.message.chat.id if query.message.chat.type == ChatType.PRIVATE else query.from_user.id

        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language") or DEFAULT_LANGUAGES
        current_resolution = user_data.get("resolution", "1024x1024")
        current_quality = user_data.get("quality", "standard")

        parts = query.data.split(":")
        if len(parts) == 3:
            _, setting_type, value = parts
        elif len(parts) == 2 and parts[1] == "back":
            setting_type = "back"
            value = None
        else:
            await query.answer("Invalid data format", show_alert=True)
            return

        if setting_type == "resolution":
            if value != current_resolution:
                await update_user_data(chat_id, "resolution", value)
                current_resolution = value

        elif setting_type == "quality":
            quality_map = {
                "обычная": "standard", "normal": "standard", "standard": "standard",
                "высокая": "hd", "high": "hd", "hd": "hd"
            }
            quality_value = quality_map.get(value.lower(), "standard")
            if quality_value != current_quality:
                await update_user_data(chat_id, "quality", quality_value)
                current_quality = quality_value

        elif setting_type == "back":
            menu = await get_settings_inline(chat_id)
            await query.message.edit_text(MESSAGES[lang]['settings_title'])
            await query.message.edit_reply_markup(reply_markup=menu)
            await query.answer()
            return

        updated_kb = await get_generation_inline(chat_id)
        text = MESSAGES[lang]['generation_selection']

        try:
            if query.message.text != text or query.message.reply_markup != updated_kb:
                await query.message.edit_text(text, reply_markup=updated_kb, parse_mode="Markdown")
            else:
                pass
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise

        await log_info(f"[DALL·E] User {chat_id} updated {setting_type} to {value}", type_e="info")

    except Exception as e:
        await log_info(f"[DALL·E] Error in process_generation_callback for chat_id {chat_id}: {e}", type_e="error")
        raise

@callbacks_router.callback_query(lambda call: call.data.startswith("generation_image:"))
async def process_generation_image_callback(query: types.CallbackQuery):
    try:
        chat_id = query.message.chat.id if query.message.chat.type == ChatType.PRIVATE else query.from_user.id

        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language") or DEFAULT_LANGUAGES
        current_resolution = user_data.get("resolution", "1024x1024")
        current_quality = user_data.get("quality", "standard")

        generation_image = query.data.split(":")

        await query.message.answer(MESSAGES[lang]['enter_your_role'], reply_markup=ForceReply(selective=True))
        await query.answer()

    except Exception as e:
        await log_info(f"[DALL·E] Error in process_generation_image_callback for chat_id {chat_id}: {e}", type_e="error")
        raise