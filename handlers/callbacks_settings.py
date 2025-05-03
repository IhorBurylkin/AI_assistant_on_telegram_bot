from aiogram import Router
from aiogram import types
from aiogram.enums import ChatType
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from config.config import DEFAULT_LANGUAGES, MESSAGES, SUPPORTED_LANGUAGES
from logs.log import logs
from services.db_utils import read_user_all_data, update_user_data
from keyboards.inline_kb_settings import (get_settings_inline, 
                                          get_model_inline, 
                                          get_answer_inline, 
                                          get_role_inline, 
                                          get_generation_inline, 
                                          get_language_inline, 
                                          get_user_role_inline
)
from keyboards.reply_kb import get_persistent_menu
from handlers.callbacks_data import PromptState

callbacks_settings_router = Router()

@callbacks_settings_router.callback_query(lambda call: call.data.startswith("settings:"))
async def process_settings_callback(query: types.CallbackQuery, state: FSMContext):
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
                await logs("Markup didn't change, update cancelled.", type_e="warning")
        elif data == "web_enabled":
            user_data = await read_user_all_data(chat_id)
            user_model = user_data.get("model")
            current = user_data.get("web_enabled")
            new_value = not current
            await update_user_data(chat_id, "web_enabled", new_value)
            if new_value == True:
                await query.answer(text=MESSAGES[lang]['web_enabled'], show_alert=False)
                #await update_user_data(chat_id, "model", user_model)
            else:
                await query.answer(text=MESSAGES[lang]['web_disabled'], show_alert=False)
                #await update_user_data(chat_id, "model", user_model)
            new_markup = await get_settings_inline(chat_id)
            # If markup changed, update it
            if query.message.reply_markup != new_markup:
                await query.message.edit_reply_markup(reply_markup=new_markup)
            else:
                await logs("Markup didn't change, update cancelled.", type_e="warning")
        elif data == "set_answer":
            inline_answer_kb = await get_answer_inline(chat_id)
            await query.message.edit_text(MESSAGES[lang]['answer_selection'], reply_markup=inline_answer_kb)
            await query.answer()
        elif data == "role":
            await state.clear()
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
            return
        elif data == "back":
            inline_settings_kb = await get_settings_inline(chat_id)
            await query.message.edit_text(MESSAGES[lang]['settings_title'], reply_markup=inline_settings_kb)
            await query.answer()
            return

        await logs(f"Settings callback processed for chat_id {chat_id} with data: {data}", type_e="info")
    except Exception as e:
        await logs(f"Error in process_settings_callback for chat_id {chat_id}: {e}", type_e="error")
        raise

@callbacks_settings_router.callback_query(lambda call: call.data.startswith("model:"))
async def process_set_model_callback(query: types.CallbackQuery):
    try:
        # Determine chat_id based on chat type
        chat_id = query.message.chat.id if query.message.chat.type == ChatType.PRIVATE else query.from_user.id

        # Get current web_enabled status
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        user_model = user_data.get("model")
        if not lang:
            lang = DEFAULT_LANGUAGES
        # Extract new model from callback_data
        new_model = query.data.split(":", 1)[1]

        await update_user_data(chat_id, "model", new_model)

        new_markup = await get_model_inline(chat_id)

        # If markup changed, update it
        if query.message.reply_markup is None or \
           query.message.reply_markup.model_dump() != new_markup.model_dump():
            await query.message.edit_reply_markup(reply_markup=new_markup)
        else:
            await logs("Markup didn't change, update cancelled.", type_e="warning")

        if query.message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            response_text = (
                    f"Model changed to: {new_model}"
                    if lang == "ru" else
                    f"Model changed to: {new_model}"
                )
        await query.answer(text=response_text, show_alert=False)
        await logs(f"ChatGPT model changed to: {new_model} for chat_id {chat_id}", type_e="info")
    except Exception as e:
        await logs(f"Error in process_set_model_callback for chat_id {chat_id}: {e}", type_e="error")
        raise

@callbacks_settings_router.callback_query(lambda call: call.data.startswith("answer:"))
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
        new_markup = await get_answer_inline(chat_id)
        
        if query.message.reply_markup is None or \
           query.message.reply_markup.model_dump() != new_markup.model_dump():
            await query.message.edit_reply_markup(reply_markup=new_markup)
        else:
            await logs("Markup didn't change, update cancelled.", type_e="warning")
        
        # Send confirmation message in private chat
        if query.message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            response_text = (
                f"AI response accuracy: {chosen_set_answer}"
                if lang == "ru"
                else f"AI response accuracy: {chosen_set_answer}"
            )
            await query.answer(text=response_text, show_alert=False)
        
        await logs(f"Answer configured for user {chat_id}: {chosen_set_answer}", type_e="info")
    except Exception as e:
        await logs(f"Error in process_answer_callback for user {chat_id}: {e}", type_e="error")
        raise

@callbacks_settings_router.callback_query(lambda call: call.data.startswith("role:"))
async def process_role_callback(query: types.CallbackQuery, state: FSMContext):
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

        user_role_inline = await get_user_role_inline(chat_id)
        if chosen_set_role == roles_list[4]:
            message_sended = await query.message.edit_text(MESSAGES[lang]['enter_your_role'], reply_markup=user_role_inline)
            await update_user_data(chat_id, "message_id", message_sended.message_id)
            await state.set_state(PromptState.waiting_for_input)
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
        new_markup = await get_role_inline(chat_id)

        # Update message markup
        if query.message.reply_markup is None or \
           query.message.reply_markup.model_dump() != new_markup.model_dump():
            await query.message.edit_reply_markup(reply_markup=new_markup)
        else:
            await logs("Markup didn't change, update cancelled.", type_e="warning")

        if query.message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            confirmation_text = (
                f"Selected AI role: {selected_value}"
                if lang == "ru" else
                f"Selected AI role: {selected_value}"
            )
            await query.answer(text=confirmation_text, show_alert=False)

        await logs(f"Role for user {chat_id} updated to: {selected_value}", type_e="info")
    except Exception as e:
        await logs(f"Error in process_role_callback for user {chat_id}: {e}", type_e="error")
        raise

@callbacks_settings_router.callback_query(lambda call: call.data.startswith("generation:"))
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

        await logs(f"[DALL·E] User {chat_id} updated {setting_type} to {value}", type_e="info")

    except Exception as e:
        await logs(f"[DALL·E] Error in process_generation_callback for chat_id {chat_id}: {e}", type_e="error")
        raise

@callbacks_settings_router.callback_query(lambda call: call.data.startswith("lang:"))
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
        inline_menu = await get_language_inline(chat_id)
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

        await logs(f"Language changed for user {chat_id} to {chosen_lang}", type_e="info")
    except Exception as e:
        await logs(f"Error in process_lang_callback for user {chat_id}: {e}", type_e="error")
        raise

@callbacks_settings_router.message(PromptState.waiting_for_input)
async def handle_text_input(message: types.Message, state: FSMContext):
    await logs(f"[FSM] Prompt received from {message.chat.id}: {message.text}", type_e="debug")

    chat_id = message.chat.id if message.chat.type == ChatType.PRIVATE else message.from_user.id
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language") or DEFAULT_LANGUAGES
    message_id_for_deletion = user_data.get("message_id")
    if message_id_for_deletion:
        try:
            await message.bot.delete_message(chat_id, message_id_for_deletion)
        except TelegramBadRequest as e:
            if "message to delete not found" in str(e):
                await logs(f"Message to delete not found: {e}", type_e="warning")
            else:
                await logs(f"Error deleting message: {e}", type_e="error")
    custom_role = message.text.strip()
    await update_user_data(chat_id, "role", custom_role)
    await state.clear() 

    inline_role_kb = await get_role_inline(chat_id)
    await message.answer(MESSAGES[lang]['role_selection'], reply_markup=inline_role_kb)
