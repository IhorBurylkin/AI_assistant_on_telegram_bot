from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.db_utils import read_user_all_data
from config import DEFAULT_LANGUAGES, MESSAGES, MODELS, MODELS_FOR_MENU, LIMITS, WHITE_LIST
from logs import log_info
from services.utils import time_until_midnight_utc

async def get_settings_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Получаем язык пользователя; если не найден, используем значение по умолчанию
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES
    
    # Получаем состояние контекста и определяем иконку
    context_enabled = user_data.get("context_enabled")
    context_icon = "✅" if context_enabled else "❌"
    # Получаем состояние web_enabled
    web_enabled = user_data.get("web_enabled")
    web_icon = "✅" if web_enabled else "❌"
    
    # Формируем inline-меню настроек
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_set_model'], callback_data="settings:set_model")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_context'].format(context_icon), callback_data="settings:toggle_context")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_web_search'].format(web_icon), callback_data="settings:web_enabled")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_answer'], callback_data="settings:set_answer")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_role'], callback_data="settings:role")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_generation'], callback_data="settings:generation")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_interface_language'], callback_data="settings:interface_language")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_close'], callback_data="settings:close")]
    ])
    await log_info(f"Inline-меню настроек успешно сформировано для пользователя {chat_id}", type_e="info")
    return kb

async def get_options_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Получаем язык пользователя; если не найден, используем значение по умолчанию
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    # Формируем inline-меню опций
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['clear_context'], callback_data="options:clear_context")],
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['generate_image'], callback_data="options:generate_image")],
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['add_check'], callback_data="options:add_check")],
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['close'], callback_data="settings:close")]
    ])
    await log_info(f"Inline меню опций успешно сформировано для пользователя {chat_id}", type_e="info")
    return kb

async def get_profile_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Получаем язык пользователя; если не найден, используем значение по умолчанию
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    # Формируем inline-меню профиля
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['profile']['limits'], callback_data="profile:usage_limit")],
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['profile']['close'], callback_data="settings:close")]
    ])
    await log_info(f"Inline меню профиля успешно сформировано для пользователя {chat_id}", type_e="info")
    return kb

async def get_model_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Получаем язык пользователя; если не найден, используем значение по умолчанию
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    # Получаем текущую модель и статус web_enabled
    set_model = user_data.get("model")
    web_enabled = user_data.get("web_enabled")

    buttons = []

    # Корректируем модель, если включён web_enabled
    if web_enabled:
        if set_model == "gpt-4o-mini-search-preview":
            set_model = "gpt-4o-mini"
        elif set_model == "gpt-4o-search-preview":
            set_model = "gpt-4o"

    # Создаем кнопки для выбора модели
    for i, option in enumerate(MODELS):
        icon = "✅" if set_model == option else ""
        buttons.append([InlineKeyboardButton(
            text=f"{MODELS_FOR_MENU[i]} {icon}",
            callback_data=f"model:{option}"
        )])

    # Добавляем кнопку "Назад"
    buttons.append([InlineKeyboardButton(
        text=MESSAGES[lang]['settings_back'], callback_data="settings:back"
    )])

    await log_info(f"Inline-меню выбора модели успешно сформировано для пользователя {chat_id}", type_e="info")
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_answer_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Получаем язык пользователя; если не найден, используем значение по умолчанию
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    # Получаем установленное значение ответа
    set_answer = user_data.get("set_answer")
    
    # Определяем варианты ответа и формируем кнопки
    options = ["minimal", "moderate", "increased", "maximum"]
    buttons = []
    for i, option in enumerate(options):
        icon = "✅" if set_answer == option else ""
        buttons.append([InlineKeyboardButton(
            text=f"{MESSAGES[lang]['set_answer'][i]} {icon}",
            callback_data=f"answer:{option}"
        )])
    
    # Добавляем кнопку "Назад"
    buttons.append([InlineKeyboardButton(
        text=MESSAGES[lang]['settings_back'],
        callback_data="settings:back"
    )])
    
    await log_info(f"Inline меню 'answer' успешно сформировано для пользователя {chat_id}", type_e="info")
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_role_inline(chat_id: int) -> InlineKeyboardMarkup:

    # Получаем язык пользователя; если не найден, используем значение по умолчанию
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    # Получаем роль пользователя и списки ролей из сообщений
    role_from_db = user_data.get("role")
    roles_list = MESSAGES[lang]['set_role']
    roles_system_list = MESSAGES[lang]['set_role_system']

    # Асинхронная функция для получения индекса текущей роли
    async def get_current_role(text: str) -> int:
        try:
            return roles_system_list.index(text)
        except ValueError:
            return 4  # значение по умолчанию

    current_role_index = await get_current_role(role_from_db)
    current_role = roles_list[current_role_index]

    # Формируем inline-кнопки для каждой роли
    buttons = []
    for role_name in roles_list:
        icon = "✅" if role_name == current_role else ""
        buttons.append([InlineKeyboardButton(
            text=f"{role_name} {icon}",
            callback_data=f"role:{role_name}"
        )])

    # Добавляем кнопку "Назад"
    buttons.append([InlineKeyboardButton(
        text=MESSAGES[lang]['settings_back'],
        callback_data="settings:back"
    )])

    await log_info(f"Inline меню ролей успешно сформировано для пользователя {chat_id}", type_e="info")
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_generation_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Получаем язык пользователя; если не найден, используем значение по умолчанию
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    resolutions = MESSAGES[lang]["set_resolution"]
    qualities = MESSAGES[lang]["set_quality"]

    # Получаем текущее значение генерации
    current_resolution = user_data.get("resolution", resolutions[0])
    quality_code = user_data.get("quality", "standard")  # значение в БД: "standard" или "hd"

    # Маппинг для отображения пользователю
    quality_map = {
        "standard": qualities[0],  # "Обычная"
        "hd": qualities[1]         # "Высокая"
    }
    current_quality = quality_map.get(quality_code, qualities[0])

    # Вспомогательная функция для добавления чеков
    def with_checkmark(value, current):
        return f"{value} ✅" if value.lower() == current.lower() else value
    # Формируем inline-кнопки для каждого варианта генерации

    # Кнопки разрешения
    res_buttons = [
        InlineKeyboardButton(
            text=with_checkmark(val, current_resolution),
            callback_data=f"generation:resolution:{val}"
        )
        for val in resolutions
    ]

    # Кнопки качества
    qual_buttons = [
        InlineKeyboardButton(
            text=with_checkmark(val, current_quality),
            callback_data=f"generation:quality:{val.lower()}"
        )
        for val in qualities
    ]

    # Добавляем кнопку "Назад"
    back_button = [
        InlineKeyboardButton(
            text=MESSAGES[lang]['settings_back'],
            callback_data="settings:back"
        )
    ]
    # Формируем inline-клавиатуру
    inline_keyboard = [
        res_buttons,
        qual_buttons,
        back_button
    ]

    await log_info(f"Inline меню 'generation' успешно сформировано для пользователя {chat_id}", type_e="info")
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

async def get_language_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Получаем язык пользователя; если не найден, используем значение по умолчанию
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en")],
        [InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="lang:de"),
            InlineKeyboardButton(text="🇪🇸 Español", callback_data="lang:es")],
        [InlineKeyboardButton(text=MESSAGES[lang]['settings_back'], callback_data="settings:back")]
    ])
    await log_info(f"Inline меню языков успешно сформировано для пользователя {chat_id}", type_e="info")
    return kb

async def get_generate_image_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Получаем язык пользователя; если не найден, используем значение по умолчанию
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['back'], callback_data="options:back")]
    ])
    await log_info(f"Inline меню генерации изображений успешно сформировано для пользователя {chat_id}", type_e="info")
    return kb

async def get_add_check_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Получаем язык пользователя; если не найден, используем значение по умолчанию
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MESSAGES[lang]['inline_kb']['options']['back'], callback_data="options:back")]
    ])
    await log_info(f"Inline меню добавления чеков успешно сформировано для пользователя {chat_id}", type_e="info")
    return kb

async def get_add_check_accept_inline(chat_id: int) -> InlineKeyboardMarkup:
    # Получаем язык пользователя; если не найден, используем значение по умолчанию
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data="options:accept"),
        InlineKeyboardButton(text="❌", callback_data="options:cancel")],
    ])
    await log_info(f"Inline меню подтверждения чеков успешно сформировано для пользователя {chat_id}", type_e="info")
    return kb

async def get_limits_inline(chat_id: int) -> InlineKeyboardMarkup:
    try:
        # Вычисляем время до полуночи
        remaining_time = await time_until_midnight_utc()
        total_seconds = int(remaining_time.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        formatted_time = f"{hours:02d}:{minutes:02d}"

        # Определяем chat_id и получаем язык пользователя
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language")
        if not lang:
            lang = DEFAULT_LANGUAGES

        # Получаем количество запросов и токенов, список лимитов и категорию
        tokens = user_data.get("tokens")
        requests = user_data.get("requests")
        which_list = user_data.get("in_limit_list")

        lost_req = LIMITS[which_list][0] - requests
        lost_tokens = LIMITS[which_list][1] - tokens

        # Формируем сообщение с лимитами
        if chat_id in WHITE_LIST:
            message_to_send = (
                f"{MESSAGES[lang]['limits'].format(lost_req, lost_tokens, formatted_time)}\n\n"
                f"{MESSAGES[lang]['white_list']}"
            )
        else:
            message_to_send = MESSAGES[lang]['limits'].format(lost_req, lost_tokens, formatted_time)

        # Формируем inline-меню с лимитами
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=MESSAGES[lang]['settings_back'], callback_data="profile:back")]
        ])

        await log_info(f"Inline limits успешно выполнена для chat_id {chat_id}", type_e="info")
        return kb, message_to_send
    except Exception as e:
        await log_info(f"Ошибка в command_limits: {e}", type_e="error")
        raise
