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
    await log_info("PostgreSQL connection established", type_e="info")

async def close_connection():
    global conn
    await conn.close()
    await log_info("PostgreSQL connection closed", type_e="info")

async def init_db_tables():
    """
    Asynchronous function for checking and initializing tables in PostgreSQL.
    
    The function performs the following steps:
      1. Establishes an asynchronous connection to the database.
      2. For each table in TABLE_SCHEMAS:
         - Checks if the table exists.
         - If the table doesn't exist, creates it with the required columns.
         - If the table exists, checks for all necessary columns.
           If any column is missing, adds it using ALTER TABLE.
      3. Closes the connection.
    In case of errors, logging is done using log_info.
    """
    global conn
    try:
        # Iterate through each table in the schema
        for table_name, columns in TABLE_SCHEMAS.items():
            # Check if the table exists
            table_exists_query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = $1
                );
            """
            exists = await conn.fetchval(table_exists_query, table_name)
            
            if not exists:
                # If the table doesn't exist, create a CREATE TABLE query with required columns
                columns_def = ", ".join([f"{col} {col_type}" for col, col_type in columns.items()])
                create_query = f"CREATE TABLE {table_name} ({columns_def});"
                await conn.execute(create_query)
                await log_info(f"Table %s created with columns: %s, {table_name}, {columns_def}", type_e="info")
            else:
                # If the table exists, get a list of existing columns
                columns_query = """
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = $1;
                """
                existing_columns = await conn.fetch(columns_query, table_name)
                existing_columns = {record["column_name"] for record in existing_columns}
                
                # Check and add missing columns
                for col, col_type in columns.items():
                    if col not in existing_columns:
                        alter_query = f"ALTER TABLE {table_name} ADD COLUMN {col} {col_type};"
                        await conn.execute(alter_query)
                        await log_info(f"Column %s added to table %s, {col}, {table_name}", type_e="info")
    except Exception as e:
        await log_info(f"Error initializing tables: %s, {e}", type_e="error")
        raise

async def user_exists(user_id: int) -> bool:
    """
    Asynchronous function to check if user_id exists in the PostgreSQL database.
    
    Parameters:
      user_id: int - identifier of the user to find.
      
    Returns:
      True if the user is found, False if the user doesn't exist or an error occurred.
    """
    global conn
    try:
        # Execute a query to check if the user exists.
        # Here the table is called "chat_ids", and it's assumed to have a "user_id" column.
        query = "SELECT 1 FROM chat_ids WHERE user_id = $1 LIMIT 1;"
        result = await conn.fetchval(query, user_id)
        
        await log_info(f"Check for user_id %s in chat_ids table completed successfully, {user_id}", type_e="info")
        
        # If result is not None, the user was found.
        return True if result else False
    except Exception as e:
        await log_info(f"Error checking for user {user_id} %s: %s, {user_id}, {e}", type_e="error")
        return False

async def write_json(table_name: str, data):
    """
    Asynchronous writing of JSON data to a PostgreSQL table.
    
    Parameters:
      table_name: str - name of the table that stores JSON (a "data" column of JSON type is expected).
      data: dict - data to be saved as JSON.
    
    Returns:
      None. In case of an error, a message is logged.
    
    Note: if the table uses an UPSERT mechanism (e.g., by primary key),
         you can configure the query with ON CONFLICT to update an existing record.
    """
    global conn
    try:
        # Convert data to JSON-compatible format if needed (asyncpg can work with dict)
        # You can use json.dumps if you need to save as a string:
        # json_data = json.dumps(data, ensure_ascii=False, indent=4)
        # But asyncpg automatically converts dict to json type
        
        # Query example: insert data into the table.
        # If the table has a unique key (e.g., "id"), you can use ON CONFLICT for UPSERT.
        # Here's a simple INSERT example.
        query = f"INSERT INTO {table_name} (data) VALUES ($1);"
        await conn.execute(query, data)
        
        # Log successful write
        await log_info(f"Successfully wrote JSON data to table: %s, {table_name}", type_e="info")
    except asyncpg.exceptions.UndefinedTableError:
        # Table not found
        await log_info(f"Table not found: %s, {table_name}", type_e="error")
    except Exception as e:
        # Handle other errors
        await log_info(f"Error writing JSON to table %s: %s, {table_name}, {e}", type_e="error")
    return None

async def read_user_data(chat_id: int, key: str = None):
    """
    Asynchronously queries user data from the "chat_ids" table in the PostgreSQL database.
    
    Arguments:
      chat_id (int): User identifier to be searched in the user_id column.
      key (str, optional): If specified, the function returns the value of this key from the found row.
                          If key=None, the function returns the entire row (as a dictionary).
                             
    Returns:
      A dictionary with user data if the record is found and key=None,
      or the value for the specified key if key is set.
      If the record is not found or an error occurs, returns None.
    """
    global conn
    try:
        # Execute query: find row in chat_ids table by user_id value
        query = "SELECT * FROM chat_ids WHERE user_id = $1 LIMIT 1;"
        row = await conn.fetchrow(query, chat_id)
        await log_info(f"Query for chat_id: %s executed successfully, {chat_id}", type_e="info")
        
        if row is not None:
            # Convert result to dictionary for easy field access
            row_dict = dict(row)
            if key is None:
                return row_dict
            else:
                # If key is specified, return its value from the found row
                return row_dict.get(key)
        else:
            return None

    except asyncpg.exceptions.UndefinedTableError:
        await log_info("Table 'chat_ids' not found.", type_e="error")
    except Exception as e:
        await log_info(f"An unexpected error occurred when querying chat_id %s: %s, {chat_id}, {e}", type_e="error")
    return None

async def read_user_all_data(chat_id: int):
    """
    Asynchronously queries data from the "chat_ids" table in PostgreSQL for the specified chat_id.
    
    Arguments:
      chat_id (int): User identifier to be searched in the user_id column.
    
    Returns:
      A Record with user data if found, otherwise None.
    """
    global conn
    try:
        
        # Execute query to find record by user_id (chat_id)
        query = "SELECT * FROM chat_ids WHERE user_id = $1"
        row = await conn.fetchrow(query, chat_id)
        
        # Log successful query execution
        await log_info(f"Query for chat_id: %s executed successfully, {chat_id}", type_e="info")
        
        # If record is found, return it; otherwise return None
        return row
    except Exception as e:
        # Log error and return None
        await log_info(f"Error querying data for chat_id %s: %s, {chat_id}, {e}", type_e="error")
        return None
    
async def write_user_to_json(file_path: str, user_data: dict):
    """
    Asynchronous function for writing data to a PostgreSQL table.
    
    Arguments:
      file_path (str): Name of the table to which data will be written.
      user_data (dict): Data to write, where each key corresponds to a column name.
    
    The function creates a dynamic SQL INSERT query using column names and
    parameterized placeholders, executes the query, logs success or error, and closes the connection.
    """
    global conn
    try:
        # Get list of columns and values from dictionary
        columns = list(user_data.keys())
        values = list(user_data.values())
        
        # Form string with column names separated by commas
        columns_str = ", ".join(columns)
        
        # Form string of parameters as $1, $2, ..., $n
        placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])
        
        # Form INSERT query
        query = f"INSERT INTO {file_path} ({columns_str}) VALUES ({placeholders});"
        
        # Execute query with parameters
        await conn.execute(query, *values)
        await log_info(f"Data successfully written to table: %s, {file_path}", type_e="info")
    except Exception as e:
        await log_info(f"Error writing data to table %s: %s, {file_path}, {e}", type_e="error")
        return None   

async def update_user_data(chat_id: int, key: str, value):
    """
    Asynchronous function for updating user data in the "chat_ids" table in PostgreSQL.
    
    Arguments:
      chat_id (int): User identifier to be searched in the user_id column.
      key (str): Name of the column to update.
      value: New value for the specified column.
      
    If a record with user_id = chat_id is found, the function updates the value of column key to value.
    """
    global conn
    try:
        # Form SQL query for update. 
        # Note: column name (key) cannot be parameterized, so it's assumed
        # that the key value is safe and valid.
        query = f"UPDATE chat_ids SET {key} = $2 WHERE user_id = $1;"
        
        # Execute query. The execute method will return a string like "UPDATE <n>" on successful update.
        result = await conn.execute(query, chat_id, value)
        
        await log_info(f"Data updated for chat_id %s, key %s, new value: %s, {chat_id}, {key}, {value}", type_e="info")
    except Exception as e:
        await log_info(f"Error updating data for chat_id %s, key %s: %s, {chat_id}, {key}, {e}", type_e="error")

async def get_chat_history(chat_id: int):
    """
    Asynchronous function to retrieve the entire row from the "context" table in PostgreSQL,
    where the chat_id value is found in the user_id column.

    Arguments:
      chat_id (int): Chat identifier (user_id) to search for the record.

    Returns:
      A dictionary with row data if the record is found, or None if the record doesn't exist or an error occurred.
    """
    global conn
    try:
        # Execute query to find record by user_id in "context" table
        query = "SELECT context FROM context WHERE user_id = $1 LIMIT 1;"
        row = await conn.fetchrow(query, chat_id)

        if row is not None:
            # Extract value from context column; if value is None, use empty list
            context_list = row["context"]
            if isinstance(context_list, str):
                context_list = json.loads(context_list)
        else:
            # If record doesn't exist, start with empty list and create new record
            context_list = []
        
        # Log successful query execution
        await log_info(f"Chat history successfully retrieved for chat_id: %s, {chat_id}", type_e="info")
        
        # If record is found, return it as dictionary, otherwise None
        return context_list
    except Exception as e:
        # Log the error and return None
        await log_info(f"Error retrieving chat history for chat_id %s: %s, {chat_id}, {e}", type_e="error")
        return None 
    
async def update_chat_history(chat_id: int, new_message: dict):
    """
    Asynchronously updates the chat history for a given chat_id in the "context" table of PostgreSQL.
    
    The function performs the following steps:
      1. Establishes a connection to the database.
      2. Looks for a record in the "context" table where user_id equals chat_id.
      3. If a record is found, extracts the value of the context column, which should be a list.
         If the list is empty or the value is missing, sets it as [new_message].
         If the list is not empty, adds new_message to the end of the list.
      4. If after adding, the list length exceeds 4 elements, keeps only the last 4 messages.
      5. Updates the record in the database with the new list.
      6. Closes the connection and logs the result.
      
    Arguments:
      chat_id (int): User/chat identifier.
      new_message (dict): New message to add to the history (e.g., {"role": "user", "content": "Example text"}).
    """
    global conn
    try:
        # Query to get current chat history for the given chat_id
        query_select = "SELECT context FROM context WHERE user_id = $1 LIMIT 1;"
        row = await conn.fetchrow(query_select, chat_id)
        
        if row is not None:
            # Extract value from context column; if value is None, use empty list
            context_list = row["context"]
            if isinstance(context_list, str):
                context_list = json.loads(context_list)
            #     context_list = []
        else:
            # If record doesn't exist, start with empty list and create new record
            context_list = []
            query_insert = "INSERT INTO context (user_id, context) VALUES ($1, $2);"
            await conn.execute(query_insert, chat_id, json.dumps(context_list))
        
        # If list is empty, set it as [new_message]
        if not context_list:
            context_list = [new_message]
        else:
            # Otherwise add new message to end of list
            context_list.append(new_message)
            # If list length exceeds 4, keep only last 4 elements
            if len(context_list) > 4:
                context_list = context_list[-4:]
        
        # Update record in "context" table
        query_update = "UPDATE context SET context = $2 WHERE user_id = $1;"
        # Convert list to JSON string for storage in JSON or text type column
        await conn.execute(query_update, chat_id, json.dumps(context_list))
        
        await log_info(f"Chat history for chat_id %s updated successfully, {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Error updating chat history for chat_id %s: %s, {chat_id}, {e}", type_e="error")

async def clear_user_context(chat_id: int):
    """
    Asynchronous function for clearing a user's context in the "context" table of PostgreSQL.
    
    Arguments:
      chat_id (int): User identifier to be searched in the user_id column.
      
    If the record is found, the function updates the value of the context column, setting it to empty (e.g., an empty JSON array '[]'),
    while the value in the user_id column remains unchanged.
    """
    global conn
    try:
        # Form query to update context column for given user_id
        query = "UPDATE context SET context = $2 WHERE user_id = $1;"
        # Set empty context (empty JSON array)
        await conn.execute(query, chat_id, '[]')
        
        await log_info(f"Chat history for chat_id %s cleared successfully, {chat_id}", type_e="info")
    except Exception as e:
        await log_info(f"Error clearing chat history for chat_id %s: %s, {chat_id}, {e}", type_e="error")