import asyncio
import asyncpg
import json
from logs import log_info
from config import DB_DSN

TABLE_SCHEMAS = {
    "chat_ids": {
        "user_id": "bigint",
        "username": "text",
        "first_name": "text",
        "last_name": "text",
        "language": "text",
        "context_enabled": "boolean",
        "web_enabled": "boolean",
        "set_answer": "text",
        "set_answer_temp": "double precision",
        "set_answer_top_p": "double precision",
        "model": "text",
        "tokens": "bigint",
        "requests": "bigint",
        "date_requests": "date",
        "role": "text",
        "have_tokens": "bigint",
        "in_limit_list": "text",
        "resolution": "text",
        "quality": "text",
    },
    "context": {
        "user_id": "bigint",
        "context": "json"
    }
}

conn = None

async def create_connection():
    global conn
    conn = await asyncpg.connect(DB_DSN)
    await log_info("Соединение с PostgreSQL установлено", type_e="info")

async def close_connection():
    global conn
    await conn.close()
    await log_info("Соединение с PostgreSQL закрыто", type_e="info")

async def init_db_tables():
    """
    Асинхронная функция для проверки и инициализации таблиц в PostgreSQL.
    
    Функция выполняет следующие шаги:
      1. Устанавливает асинхронное соединение с базой данных.
      2. Для каждой таблицы из TABLE_SCHEMAS:
         - Проверяет, существует ли таблица.
         - Если таблица отсутствует, создаёт её с требуемыми колонками.
         - Если таблица существует, проверяет наличие всех необходимых колонок.
           Если какая-то колонка отсутствует, добавляет её через ALTER TABLE.
      3. Закрывает соединение.
    В случае ошибок логирование производится с помощью log_info.
    """
    global conn
    try:
        # Перебираем каждую таблицу из схемы
        for table_name, columns in TABLE_SCHEMAS.items():
            # Проверяем, существует ли таблица
            table_exists_query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = $1
                );
            """
            exists = await conn.fetchval(table_exists_query, table_name)
            
            if not exists:
                # Если таблица отсутствует, формируем запрос CREATE TABLE с требуемыми колонками
                columns_def = ", ".join([f"{col} {col_type}" for col, col_type in columns.items()])
                create_query = f"CREATE TABLE {table_name} ({columns_def});"
                await conn.execute(create_query)
                await log_info(f"Таблица %s создана с колонками: %s, {table_name}, {columns_def}", type_e="info")
            else:
                # Если таблица существует, получаем список существующих колонок
                columns_query = """
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = $1;
                """
                existing_columns = await conn.fetch(columns_query, table_name)
                existing_columns = {record["column_name"] for record in existing_columns}
                
                # Проверяем и добавляем недостающие колонки
                for col, col_type in columns.items():
                    if col not in existing_columns:
                        alter_query = f"ALTER TABLE {table_name} ADD COLUMN {col} {col_type};"
                        await conn.execute(alter_query)
                        await log_info(f"Колонка %s добавлена в таблицу %s, {col}, {table_name}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка при инициализации таблиц: %s, {e}", type_e="error")
        raise

async def user_exists(user_id: int) -> bool:
    """
    Асинхронная функция для проверки наличия user_id в базе данных PostgreSQL.
    
    Параметры:
      user_id: int - идентификатор пользователя, который нужно найти.
      
    Возвращает:
      True, если пользователь найден, False, если пользователь не существует или произошла ошибка.
    """
    global conn
    try:
        # Выполняем запрос для проверки наличия пользователя.
        # Здесь таблица называется "chat_ids", и предполагается, что в ней есть колонка "user_id".
        query = "SELECT 1 FROM chat_ids WHERE user_id = $1 LIMIT 1;"
        result = await conn.fetchval(query, user_id)
        
        await log_info(f"Проверка наличия user_id %s в таблице chat_ids выполнена успешно, {user_id}", type_e="info")
        
        # Если result не None, значит пользователь найден.
        return True if result else False
    except Exception as e:
        await log_info(f"Ошибка при проверке наличия {user_id} %s: %s, {user_id}, {e}", type_e="error")
        return False

async def write_json(table_name: str, data):
    """
    Асинхронная запись JSON-данных в таблицу PostgreSQL.
    
    Параметры:
      table_name: str - имя таблицы, в которой хранится JSON (ожидается наличие столбца "data" типа JSON).
      data: dict - данные, которые будут сохранены в виде JSON.
    
    Возвращает:
      None. В случае ошибки логируется сообщение.
    
    Примечание: если в таблице используется механизм UPSERT (например, по первичному ключу),
               можно настроить запрос с ON CONFLICT, чтобы обновлять существующую запись.
    """
    global conn
    try:
        # Преобразуем данные в JSON-совместимый формат, если необходимо (asyncpg умеет работать с dict)
        # Здесь можно использовать json.dumps, если требуется сохранить как строку:
        # json_data = json.dumps(data, ensure_ascii=False, indent=4)
        # Но asyncpg автоматически преобразует dict в тип json
        
        # Пример запроса: вставляем данные в таблицу.
        # Если в таблице есть уникальный ключ (например, "id"), можно использовать ON CONFLICT для UPSERT.
        # Здесь приведён простой пример INSERT.
        query = f"INSERT INTO {table_name} (data) VALUES ($1);"
        await conn.execute(query, data)
        
        # Логируем успешную запись
        await log_info(f"Успешно записаны JSON-данные в таблицу: %s, {table_name}", type_e="info")
    except asyncpg.exceptions.UndefinedTableError:
        # Таблица не найдена
        await log_info(f"Таблица не найдена: %s, {table_name}", type_e="error")
    except Exception as e:
        # Обработка других ошибок
        await log_info(f"Ошибка записи JSON в таблицу %s: %s, {table_name}, {e}", type_e="error")
    return None

async def read_user_data(chat_id: int, key: str = None):
    """
    Асинхронно запрашивает данные пользователя из таблицы "chat_ids" в базе PostgreSQL.
    
    Аргументы:
      chat_id (int): Идентификатор пользователя, который ищется в колонке user_id.
      key (str, опционально): Если указан, функция вернет значение этого ключа из найденной строки.
                             Если key=None, функция вернет всю строку (в виде словаря).
                             
    Возвращает:
      Словарь с данными пользователя, если запись найдена и key=None,
      или значение по указанному ключу, если key задан.
      Если запись не найдена или произошла ошибка, возвращает None.
    """
    global conn
    try:
        # Выполняем запрос: ищем строку в таблице chat_ids по значению user_id
        query = "SELECT * FROM chat_ids WHERE user_id = $1 LIMIT 1;"
        row = await conn.fetchrow(query, chat_id)
        await log_info(f"Успешно выполнен запрос для chat_id: %s, {chat_id}", type_e="info")
        
        if row is not None:
            # Преобразуем результат в словарь для удобного доступа к полям
            row_dict = dict(row)
            if key is None:
                return row_dict
            else:
                # Если ключ указан, возвращаем его значение из найденной строки
                return row_dict.get(key)
        else:
            return None

    except asyncpg.exceptions.UndefinedTableError:
        await log_info("Таблица 'chat_ids' не найдена.", type_e="error")
    except Exception as e:
        await log_info(f"Произошла непредвиденная ошибка при запросе chat_id %s: %s, {chat_id}, {e}", type_e="error")
    return None

async def read_user_all_data(chat_id: int):
    """
    Асинхронно запрашивает данные из таблицы "chat_ids" в PostgreSQL для указанного chat_id.
    
    Аргументы:
      chat_id (int): Идентификатор пользователя, который ищется в колонке user_id.
    
    Возвращает:
      Запись (Record) с данными пользователя, если найдена, иначе None.
    """
    global conn
    try:
        
        # Выполняем запрос для поиска записи по user_id (chat_id)
        query = "SELECT * FROM chat_ids WHERE user_id = $1"
        row = await conn.fetchrow(query, chat_id)
        
        # Логируем успешное выполнение запроса
        await log_info(f"Успешно выполнен запрос для chat_id: %s, {chat_id}", type_e="info")
        
        # Если запись найдена, возвращаем её; иначе возвращаем None
        return row
    except Exception as e:
        # Логируем ошибку и возвращаем None
        await log_info(f"Ошибка при запросе данных для chat_id %s: %s, {chat_id}, {e}", type_e="error")
        return None
    
async def write_user_to_json(file_path: str, user_data: dict):
    """
    Асинхронная функция для записи данных в таблицу PostgreSQL.
    
    Аргументы:
      file_path (str): Имя таблицы, в которую будут записаны данные.
      user_data (dict): Данные для записи, где каждый ключ соответствует названию колонки.
    
    Функция формирует динамический SQL-запрос на вставку с использованием имен колонок и
    параметризованных плейсхолдеров, выполняет запрос, логирует успех или ошибку и закрывает соединение.
    """
    global conn
    try:
        # Получаем список колонок и значений из словаря
        columns = list(user_data.keys())
        values = list(user_data.values())
        
        # Формируем строку с названиями колонок, разделёнными запятыми
        columns_str = ", ".join(columns)
        
        # Формируем строку параметров в виде $1, $2, ..., $n
        placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])
        
        # Формируем запрос INSERT
        query = f"INSERT INTO {file_path} ({columns_str}) VALUES ({placeholders});"
        
        # Выполняем запрос с параметрами
        await conn.execute(query, *values)
        await log_info(f"Успешно записаны данные в таблицу: %s, {file_path}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка записи данных в таблицу %s: %s, {file_path}, {e}", type_e="error")
        return None   

async def update_user_data(chat_id: int, key: str, value):
    """
    Асинхронная функция обновления данных пользователя в таблице "chat_ids" PostgreSQL.
    
    Аргументы:
      chat_id (int): Идентификатор пользователя, который ищется в колонке user_id.
      key (str): Имя колонки, которую необходимо обновить.
      value: Новое значение для указанной колонки.
      
    Если запись с user_id = chat_id найдена, функция обновляет значение колонки key на value.
    """
    global conn
    try:
        # Формируем SQL-запрос для обновления. 
        # Внимание: имя колонки (key) нельзя параметризовать, поэтому предполагается, 
        # что значение key безопасно и валидно.
        query = f"UPDATE chat_ids SET {key} = $2 WHERE user_id = $1;"
        
        # Выполняем запрос. Метод execute вернёт строку вида "UPDATE <n>" при успешном обновлении.
        result = await conn.execute(query, chat_id, value)
        
        await log_info(f"Данные обновлены для chat_id %s, ключ %s, новое значение: %s, {chat_id}, {key}, {value}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка обновления данных для chat_id %s, ключ %s: %s, {chat_id}, {key}, {e}", type_e="error")

async def get_chat_history(chat_id: int):
    """
    Асинхронная функция для получения всей строки из таблицы "context" в PostgreSQL,
    где значение chat_id найдено в колонке user_id.

    Аргументы:
      chat_id (int): Идентификатор чата (user_id) для поиска записи.

    Возвращает:
      Словарь с данными строки, если запись найдена, или None, если записи нет или произошла ошибка.
    """
    global conn
    try:
        # Выполняем запрос для поиска записи по user_id в таблице "context"
        query = "SELECT context FROM context WHERE user_id = $1 LIMIT 1;"
        row = await conn.fetchrow(query, chat_id)

        if row is not None:
            # Извлекаем значение из колонки context; если значение None, используем пустой список
            context_list = row["context"]
            if isinstance(context_list, str):
                context_list = json.loads(context_list)
        else:
            # Если записи не существует, начинаем с пустого списка и создаём новую запись
            context_list = []
        
        # Логируем успешное выполнение запроса
        await log_info(f"Успешно получена история чата для chat_id: %s, {chat_id}", type_e="info")
        
        # Если запись найдена, возвращаем её в виде словаря, иначе None
        return context_list
    except Exception as e:
        # Логируем возникшую ошибку и возвращаем None
        await log_info(f"Ошибка получения истории чата для chat_id %s: %s, {chat_id}, {e}", type_e="error")
        return None 
    
async def update_chat_history(chat_id: int, new_message: dict):
    """
    Асинхронно обновляет историю чата для заданного chat_id в таблице "context" PostgreSQL.
    
    Функция выполняет следующие шаги:
      1. Устанавливает соединение с базой данных.
      2. Ищет запись в таблице "context", где user_id равен chat_id.
      3. Если запись найдена, извлекает значение колонки context, которое должно быть списком.
         Если список пуст или значение отсутствует, устанавливает его как [new_message].
         Если список не пуст, добавляет new_message в конец списка.
      4. Если после добавления длина списка превышает 4 элементов, оставляет только последние 4 сообщения.
      5. Обновляет запись в базе данными нового списка.
      6. Закрывает соединение и логирует результат.
      
    Аргументы:
      chat_id (int): Идентификатор пользователя/чата.
      new_message (dict): Новое сообщение для добавления в историю (например, {"role": "user", "content": "Пример текста"}).
    """
    global conn
    try:
        # Запрос на получение текущей истории чата для заданного chat_id
        query_select = "SELECT context FROM context WHERE user_id = $1 LIMIT 1;"
        row = await conn.fetchrow(query_select, chat_id)
        
        if row is not None:
            # Извлекаем значение из колонки context; если значение None, используем пустой список
            context_list = row["context"]
            if isinstance(context_list, str):
                context_list = json.loads(context_list)
            #     context_list = []
        else:
            # Если записи не существует, начинаем с пустого списка и создаём новую запись
            context_list = []
            query_insert = "INSERT INTO context (user_id, context) VALUES ($1, $2);"
            await conn.execute(query_insert, chat_id, json.dumps(context_list))
        
        # Если список пуст, устанавливаем его как [new_message]
        if not context_list:
            context_list = [new_message]
        else:
            # Иначе добавляем новое сообщение в конец списка
            context_list.append(new_message)
            # Если длина списка превышает 4, оставляем только последние 4 элемента
            if len(context_list) > 4:
                context_list = context_list[-4:]
        
        # Обновляем запись в таблице "context"
        query_update = "UPDATE context SET context = $2 WHERE user_id = $1;"
        # Преобразуем список в JSON-строку для хранения в колонке типа JSON или text
        await conn.execute(query_update, chat_id, json.dumps(context_list))
        
        await log_info(f"История чата для chat_id %s обновлена успешно, {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка обновления истории чата для chat_id %s: %s, {chat_id}, {e}", type_e="error")

async def clear_user_context(chat_id: int):
    """
    Асинхронная функция для очистки контекста пользователя в таблице "context" PostgreSQL.
    
    Аргументы:
      chat_id (int): Идентификатор пользователя, который ищется в колонке user_id.
      
    Если запись найдена, функция обновляет значение столбца context, устанавливая его пустым (например, пустой JSON-массив '[]'),
    при этом значение в колонке user_id остается неизменным.
    """
    global conn
    try:
        # Формируем запрос для обновления столбца context для заданного user_id
        query = "UPDATE context SET context = $2 WHERE user_id = $1;"
        # Устанавливаем пустой контекст (пустой JSON-массив)
        await conn.execute(query, chat_id, '[]')
        
        await log_info(f"История чата для chat_id %s успешно очищена, {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка очистки истории чата для chat_id %s: %s, {chat_id}, {e}", type_e="error")