import json
import aiofiles
from logs import log_info

# Импорт ключей из файла конфигурации
with open("config/config.json", "r", encoding = "utf-8") as file:
    config = json.load(file)

with open("config/white_list.json", "r", encoding = "utf-8") as file:
    config_white_list = json.load(file)   

# Глобальные переменные
USERS_FILE_PATH = config.get("USERS_FILE_PATH")
CHAT_HISTORIES_FILE_PATH = config.get("CHAT_HISTORIES_FILE_PATH")

async def read_json(file_path: str):
    """Асинхронное чтение из файла с указанием пути"""
    try:
        async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
            content = await f.read()
            data = json.loads(content)
            await log_info("Успешно прочитан JSON-файл: %s", file_path, type_e="info")
            return data
    except FileNotFoundError:
        await log_info("Файл не найден: %s", file_path, type_e="error")
    except json.JSONDecodeError:
        await log_info("Ошибка декодирования JSON в файле: %s", file_path, type_e="error")
    except Exception as e:
        await log_info("Произошла непредвиденная ошибка: %s", e, type_e="error")
    return None

async def write_json(file_path: str, data):
    """Асинхронная запись в файл с указанием пути и данных"""
    try:
        json__str = json.dump(data, ensure_ascii=False, indent=4)
        async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
            await f.write(json__str)
            await log_info("Успешно записан JSON-файл: %s", file_path, type_e="info")
    except FileNotFoundError:
        await log_info("Файл не найден: %s", file_path, type_e="error")
    except Exception as e:
        await log_info("Ошибка записи JSON в файл %s: %s", e, file_path, type_e="error")
    return None

async def read_user_data(chat_id: int, key: str = None):
    """Асинхронное чтение данных с chat_ids.json и указанием chat_id и key"""
    try:
        async with aiofiles.open(USERS_FILE_PATH, mode="r", encoding="utf-8") as f:
            content = await f.read()
        data = json.loads(content)
        user_data = data.get(str(chat_id))
        return user_data.get(key) if user_data else None

    except FileNotFoundError:
        await log_info("Файл не найден!", type_e="error")
    except json.JSONDecodeError:
        await log_info("Ошибка декодирования JSON!", type_e="error")
    except Exception as e:
        await log_info("Произошла непредвиденная ошибка: %s", e, type_e="error")
    return None

async def user_exists(chat_id: int):
    """Асинхронная проверка наличия пользователя в chat_ids.json и указанием chat_id"""
    try:
        async with aiofiles.open(USERS_FILE_PATH, mode="r", encoding="utf-8") as f:
            content = await f.read()
        data = json.loads(content)
        user_data = data.get(str(chat_id))
        return True if user_data else False

    except FileNotFoundError:
        await log_info("Файл не найден!", type_e="error")
    except json.JSONDecodeError:
        await log_info("Ошибка декодирования JSON!", type_e="error")
    except Exception as e:
        await log_info("Произошла непредвиденная ошибка: %s", e, type_e="error")
    return None

async def read_user_all_data(chat_id: int):
    """Асинхронное чтение данных с chat_ids.json и указанием chat_id"""
    try:
        async with aiofiles.open(USERS_FILE_PATH, mode="r", encoding="utf-8") as f:
            content = await f.read()
        data = json.loads(content)
        user_data = data.get(str(chat_id))
        return user_data if user_data else None

    except FileNotFoundError:
        await log_info("Файл не найден!", type_e="error")
    except json.JSONDecodeError:
        await log_info("Ошибка декодирования JSON!", type_e="error")
    except Exception as e:
        await log_info("Произошла непредвиденная ошибка: %s", e, type_e="error")
    return None

async def write_user_to_json(file_path: str, user_data: dict):
    """Асинхронная запись в файл с указанием file_path и user_data"""
    try:
        async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
            content = await f.read()
        try:
            existing_data = json.loads(content)
        except json.JSONDecodeError:
            existing_data = {}
            await log_info(f"Ошибка декодирования JSON в файле {file_path}. Будет использован пустой словарь.", type_e="warning")
    except FileNotFoundError:
        existing_data = {}
        await log_info(f"Файл {file_path} не найден. Будет создан новый.", type_e="warning")
    except Exception as e:
        await log_info(f"Ошибка чтения файла {file_path}: {e}", type_e="error")
        existing_data = {}

    # Извлекаем user_id и приводим его к строке
    user_id = str(user_data.get("user_id"))
    
    # Если пользователь отсутствует в данных, добавляем его
    if user_id not in existing_data:
        existing_data[user_id] = user_data
        try:
            async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
                await f.write(json.dumps(existing_data, ensure_ascii=False, indent=4))
            await log_info(f"Пользователь {user_id} успешно добавлен в {file_path}.", type_e="info")
        except Exception as e:
            await log_info(f"Ошибка записи в файл {file_path}: {e}", type_e="error")

async def update_user_data(chat_id: int, key: str, value):
    """Асинхронное обновление данных в chat_ids.json и указанием chat_id, key, value"""
    try:
        async with aiofiles.open(USERS_FILE_PATH, mode="r", encoding="utf-8") as f:
            content = await f.read()
        data = json.loads(content)
    except FileNotFoundError:
        await log_info(f"Файл {USERS_FILE_PATH} не найден!", type_e="error")
        return
    except json.JSONDecodeError:
        await log_info(f"Ошибка декодирования JSON в {USERS_FILE_PATH}!", type_e="error")
        return
    except Exception as e:
        await log_info("Произошла непредвиденная ошибка: %s", e, type_e="error")
        return

    if str(chat_id) not in data:
        data[str(chat_id)] = {}

    data[str(chat_id)][key] = value

    try:
        async with aiofiles.open(USERS_FILE_PATH, mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=4))
    except Exception as e:
        await log_info(f"Ошибка записи в {USERS_FILE_PATH}: {e}", type_e="error")
        return

async def get_chat_history(chat_id: int):
    """Асинхронное чтение истории с файла context.json и указанием chat_id"""
    try:
        async with aiofiles.open(CHAT_HISTORIES_FILE_PATH, mode="r", encoding="utf-8") as f:
            content = await f.read()
        context_data = json.loads(content)
    except FileNotFoundError:
        await log_info(f"Файл {CHAT_HISTORIES_FILE_PATH} не найден!", type_e="error")
        return []
    except json.JSONDecodeError:
        await log_info(f"Ошибка декодирования JSON в {CHAT_HISTORIES_FILE_PATH}!", type_e="error")
        return []
    
    return context_data.get(str(chat_id), [])

async def update_chat_history(chat_id: int, new_message: dict):
    """Асинхронное обновление истории с файла context.json и указанием chat_id, new_message"""
    try:
        async with aiofiles.open(CHAT_HISTORIES_FILE_PATH, mode="r", encoding="utf-8") as f:
            content = await f.read()
        context_data = json.loads(content)
    except FileNotFoundError:
        await log_info(f"Файл {CHAT_HISTORIES_FILE_PATH} не найден! Создаю новый файл.", type_e="warning")
        context_data = {}
    except json.JSONDecodeError:
        await log_info(f"Ошибка декодирования JSON в {CHAT_HISTORIES_FILE_PATH}!", type_e="error")
        context_data = {}

    chat_id_str = str(chat_id)
    if chat_id_str in context_data:
        context_data[chat_id_str].append(new_message)
    else:
        context_data[chat_id_str] = [new_message]

    if len(context_data[chat_id_str]) > 4:
        context_data[chat_id_str] = context_data[chat_id_str][-4:]

    try:
        async with aiofiles.open(CHAT_HISTORIES_FILE_PATH, mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(context_data, ensure_ascii=False, indent=4))
    except Exception as e:
        await log_info(f"Ошибка записи в файл {CHAT_HISTORIES_FILE_PATH}: {e}", type_e="error")

async def clear_user_context(chat_id: int):
    """Асинхронная очистка истории в файле context.json и указанием chat_id"""
    try:
        async with aiofiles.open(CHAT_HISTORIES_FILE_PATH, mode="r", encoding="utf-8") as f:
            content = await f.read()
        data = json.loads(content)
    except FileNotFoundError:
        await log_info(f"Файл {CHAT_HISTORIES_FILE_PATH} не найден!", type_e="error")
        return
    except json.JSONDecodeError:
        await log_info(f"Ошибка декодирования JSON в {CHAT_HISTORIES_FILE_PATH}!", type_e="error")
        return

    if str(chat_id) in data:
        del data[str(chat_id)]

    try:
        async with aiofiles.open(CHAT_HISTORIES_FILE_PATH, mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=4))
    except Exception as e:
        await log_info(f"Ошибка записи в файл {CHAT_HISTORIES_FILE_PATH}: {e}", type_e="error")

async def read_or_write_in_any_files(operation: str, file_path: str, key_f=None, key_s: str = None, value=None):
    """Асинхронная универсальная функция чтения, записи, перезаписи с указанием 
    operation (read/write/rewrite), file_path, key_f, key_s, value"""
    # Чтение данных из файла
    try:
        async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
            content = await f.read()
        data = json.loads(content)
    except FileNotFoundError:
        await log_info(f"Файл {file_path} не найден!", type_e="error")
        data = {}
    except json.JSONDecodeError:
        await log_info(f"Ошибка декодирования JSON в {file_path}!", type_e="error")
        data = {}

    # Если операция "read", возвращаем нужное значение
    if operation == "read":
        if key_f is None and key_s is None and value is None:
            return data     
        elif key_s is None and value is None:
            return data.get(str(key_f))
        elif value is None:
            return data.get(str(key_f), {}).get(key_s)
    
    # Если операция "rewrite" или "write" – обновляем данные
    else:
        chat_id_str = str(key_f) if key_f is not None else "default"
        if operation == "rewrite":
            # Режим перезаписи: просто устанавливаем новое значение
            if key_s is not None:
                if chat_id_str not in data or not isinstance(data.get(chat_id_str), (str, int, list, dict)):
                    data[chat_id_str] = {}
                data[chat_id_str][key_s] = value
            else:
                data[chat_id_str] = value
        else:  # operation == "write"
            # Режим добавления: объединяем новое значение с уже существующим
            if key_s is not None:
                if chat_id_str not in data or not isinstance(data.get(chat_id_str), (str, int, list, dict)):
                    data[chat_id_str] = {}
                if key_s in data[chat_id_str]:
                    current = data[chat_id_str][key_s]
                    if isinstance(current, list):
                        current.append(value)
                    else:
                        data[chat_id_str][key_s] = [current, value]
                else:
                    data[chat_id_str][key_s] = value
            else:
                if chat_id_str in data:
                    current = data[chat_id_str]
                    if isinstance(current, list):
                        current.append(value)
                    else:
                        if isinstance(current, dict) and isinstance(value, dict):
                            current.update(value)
                            data[chat_id_str] = current
                        else:
                            data[chat_id_str] = [current, value]
                else:
                    data[chat_id_str] = value
        # Запись обновлённых данных в файл
        try:
            async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            await log_info(f"Ошибка записи в файл {file_path}: {e}", type_e="error")
            return False
        return True