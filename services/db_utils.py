import asyncio
import asyncpg
import json
from datetime import datetime, date
from logs.log import logs
from config.config import DB_DSN

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
        "message_id": "bigint"
    },
    "context": {
        "user_id": "bigint",
        "context": "json"
    },
    "checks_analytics": {
        "user_id": "bigint",
        "date": "date",
        "time": "time",
        "store": "text",
        "check_id": "text",
        "category": "text",
        "product": "text",
        "quantity": "bigint",
        "price": "double precision",
        "total": "double precision",
        "currency": "text"
    }
}

_pool = None
conn = None

async def create_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DB_DSN, min_size=2, max_size=10)
        await logs("PostgreSQL connection pool established", type_e="info")
    return _pool

async def create_connection():
    """Creates a connection and initializes the global conn variable"""
    global conn
    conn = await get_connection()
    await logs("PostgreSQL connection established", type_e="info")

async def get_connection():
    """Get a connection from the pool or create a direct connection if no pool exists"""
    global _pool, conn
    if _pool is not None:
        return await _pool.acquire()
    if conn is None:
        conn = await asyncpg.connect(DB_DSN)
    return conn

async def release_connection(connection):
    """Release a connection back to the pool if using a pool"""
    global _pool
    if _pool is not None and connection is not _pool:
        await _pool.release(connection)

async def close_connection():
    global conn
    if conn:
        await conn.close()
        conn = None
        await logs("PostgreSQL connection closed", type_e="info")

async def close_pool():
    global _pool
    if _pool is None:
        return

    try:
        await asyncio.wait_for(_pool.close(), timeout=10)
        await logs("PostgreSQL connection pool closed gracefully", type_e="info")
    except asyncio.TimeoutError:
        await logs("Module: db_utils. Timeout on Pool.close(); forcing termination", type_e="warning")
        try:
            _pool.terminate()
            await logs("PostgreSQL pool terminated", type_e="info")
        except Exception as e:
            await logs(f"Module: db_utils. Error during pool.terminate(): {e}", type_e="error")
    except Exception as e:
        await logs(f"Module: db_utils. Unexpected error on pool.close(): {e}", type_e="error")
    finally:
        _pool = None

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
    In case of errors, logging is done using logs.
    """
    connection = None
    try:
        connection = await get_connection()
        # Iterate through each table in the schema
        for table_name, columns in TABLE_SCHEMAS.items():
            # Check if the table exists
            table_exists_query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = $1
                );
            """
            exists = await connection.fetchval(table_exists_query, table_name)
            
            if not exists:
                # If the table doesn't exist, create a CREATE TABLE query with required columns
                columns_def = ", ".join([f"{col} {col_type}" for col, col_type in columns.items()])
                create_query = f"CREATE TABLE {table_name} ({columns_def});"
                await connection.execute(create_query)
                await logs(f"Table {table_name} created with columns: {columns_def}", type_e="info")
            else:
                # If the table exists, get a list of existing columns
                columns_query = """
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = $1;
                """
                existing_columns = await connection.fetch(columns_query, table_name)
                existing_columns = {record["column_name"] for record in existing_columns}
                
                # Check and add missing columns
                for col, col_type in columns.items():
                    if col not in existing_columns:
                        alter_query = f"ALTER TABLE {table_name} ADD COLUMN {col} {col_type};"
                        await connection.execute(alter_query)
                        await logs(f"Column {col} added to table {table_name}", type_e="info")
    except Exception as e:
        await logs(f"Module: db_utils. Error initializing tables: {e}", type_e="error")
        raise
    finally:
        if connection:
            await release_connection(connection)

def validate_identifier(name):
    """Validate SQL identifier (table/column name)"""
    if not name or not isinstance(name, str) or not all(c.isalnum() or c == '_' for c in name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    
#_____________________________________________________________
#_______________________READ_FUNCTIONS________________________
#_____________________________________________________________
async def user_exists(user_id: int) -> bool:
    """
    Asynchronous function to check if user_id exists in the PostgreSQL database.
    
    Parameters:
      user_id: int - identifier of the user to find.
      
    Returns:
      True if the user is found, False if the user doesn't exist or an error occurred.
    """
    connection = None
    try:
        connection = await get_connection()
        # Execute a query to check if the user exists.
        # Here the table is called "chat_ids", and it's assumed to have a "user_id" column.
        query = "SELECT 1 FROM chat_ids WHERE user_id = $1 LIMIT 1;"
        result = await connection.fetchval(query, user_id)
        
        await logs(f"Check for user_id {user_id} in chat_ids table completed successfully", type_e="info")
        
        # If result is not None, the user was found.
        return True if result else False
    except Exception as e:
        await logs(f"Error checking for user {user_id}: {e}", type_e="error")
        return False
    finally:
        if connection:
            await release_connection(connection)

async def read_user_all_data(chat_id: int):
    """
    Asynchronously queries data from the "chat_ids" table in PostgreSQL for the specified chat_id.
    
    Arguments:
      chat_id (int): User identifier to be searched in the user_id column.
    
    Returns:
      A Record with user data if found, otherwise None.
    """
    connection = None
    try:
        connection = await get_connection()
        # Execute query to find record by user_id (chat_id)
        query = "SELECT * FROM chat_ids WHERE user_id = $1"
        row = await connection.fetchrow(query, chat_id)
        
        # Log successful query execution
        await logs(f"Query for chat_id: {chat_id} executed successfully", type_e="info")
        
        # If record is found, return it; otherwise return None
        return row
    except Exception as e:
        # Log error and return None
        await logs(f"Module: db_utils. Error querying data for chat_id {chat_id}: {e}", type_e="error")
        return None
    finally:
        if connection:
            await release_connection(connection)

async def read_chat_history(chat_id: int):
    """
    Asynchronous function to retrieve the entire row from the "context" table in PostgreSQL,
    where the chat_id value is found in the user_id column.

    Arguments:
      chat_id (int): Chat identifier (user_id) to search for the record.

    Returns:
      A dictionary with row data if the record is found, or None if the record doesn't exist or an error occurred.
    """
    connection = None
    try:
        connection = await get_connection()
        # Execute query to find record by user_id in "context" table
        query = "SELECT context FROM context WHERE user_id = $1 LIMIT 1;"
        row = await connection.fetchrow(query, chat_id)

        if row is not None:
            # Extract value from context column; if value is None, use empty list
            context_list = row["context"]
            if isinstance(context_list, str):
                context_list = json.loads(context_list)
        else:
            # If record doesn't exist, start with empty list and create new record
            context_list = []
        
        # Log successful query execution
        await logs(f"Chat history successfully retrieved for chat_id: {chat_id}", type_e="info")
        
        # If record is found, return it as dictionary, otherwise None
        return context_list
    except Exception as e:
        # Log the error and return None
        await logs(f"Error retrieving chat history for chat_id {chat_id}: {e}", type_e="error")
        return None 
    finally:
        if connection:
            await release_connection(connection)

async def read_with_period(chat_id: int, start_date: str, end_date: str):
    """
    Asynchronously reads data from the 'checks_analytics' table in PostgreSQL for a given chat_id
    within a specified date range.

    Arguments:
      chat_id (int): User identifier to be searched in the user_id column.
      start_date (str): Start date for the query in 'YYYY-MM-DD' format.
      end_date (str): End date for the query in 'YYYY-MM-DD' format.

    Returns:
      A list of dictionaries with row data if records are found, or None if no records exist or an error occurred.
    """
    connection = None
    try:
        async def format_date(user_date: str) -> date:
            return date.fromisoformat(user_date) if isinstance(user_date, str) else user_date

        connection = await get_connection()
        
        start_date = await format_date(start_date)
        end_date = await format_date(end_date)

        # SQL query to select records within the specified date range
        query = f"""
            SELECT date, time, store, check_id, category, product, quantity, price, total, currency
            FROM checks_analytics
            WHERE user_id = $1
              AND date   >= $2
              AND date   <= $3
        """
        rows = await connection.fetch(query, chat_id, start_date, end_date)
        
        # Log successful query execution
        await logs(f"Query executed successfully for chat_id: {chat_id}", type_e="info")
        
        # If records are found, return them as a list of dictionaries
        if rows:
            return [dict(row) for row in rows]
        else:
            return None
    except Exception as e:
        # Log error and return None
        await logs(f"Error reading data for chat_id {chat_id}: {e}", type_e="error")
        return None 
    finally:
        if connection:
            await release_connection(connection)

#_____________________________________________________________
#______________________WRITE_FUNCTIONS________________________
#_____________________________________________________________
async def clear_user_context(chat_id: int):
    """
    Asynchronous function for clearing a user's context in the "context" table of PostgreSQL.
    
    Arguments:
      chat_id (int): User identifier to be searched in the user_id column.
      
    If the record is found, the function updates the value of the context column, setting it to empty (e.g., an empty JSON array '[]'),
    while the value in the user_id column remains unchanged.
    """
    connection = None
    try:
        connection = await get_connection()
        # Form query to update context column for given user_id
        query = "UPDATE context SET context = $2 WHERE user_id = $1;"
        # Set empty context (empty JSON array)
        await connection.execute(query, chat_id, '[]')
        
        await logs(f"Chat history for chat_id {chat_id} cleared successfully", type_e="info")
    except Exception as e:
        await logs(f"Error clearing chat history for chat_id {chat_id}: {e}", type_e="error")
    finally:
        if connection:
            await release_connection(connection)

async def write_user_to_json(file_path: str, user_data: dict):
    """
    Asynchronous function for writing data to a PostgreSQL table.
    
    Arguments:
      file_path (str): Name of the table to which data will be written.
      user_data (dict): Data to write, where each key corresponds to a column name.
    
    The function creates a dynamic SQL INSERT query using column names and
    parameterized placeholders, executes the query, logs success or error, and closes the connection.
    """
    connection = None
    try:
        connection = await get_connection()
        if "date" in user_data:
            try:
                date_str = user_data.get("date", "")
                for fmt in ("%Y-%m-%d", "%d.%m.%y", "%d.%m.%Y"):
                    try:
                        user_data["date"] = datetime.strptime(date_str, fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    await logs(f"Error converting date: unsupported format '{date_str}'", type_e="error")
            except Exception as ex:
                await logs(f"Error converting date: {ex}", type_e="error")
        if "time" in user_data:
            try:
                user_data["time"] = user_data["time"].strip()
                if user_data["time"].count(":") == 1:
                    raw_time_full = f"{user_data["time"]}:00"
                else:
                    raw_time_full = user_data["time"]
                user_data["time"] = datetime.strptime(raw_time_full, "%H:%M:%S").time()
            except Exception as ex:
                await logs(f"Error converting time: {ex}", type_e="error")
        if "check_id" in user_data:
            try:
                if isinstance(user_data["check_id"], int):
                    user_data["check_id"] = str(user_data["check_id"])
            except Exception as e:
                await logs(f"Error converting check_id: {e}", type_e="error")
        if "product" in user_data:
            try:
                if isinstance(user_data["product"], dict):
                    user_data["product"] = json.dumps(user_data["product"], ensure_ascii=False)
                elif not isinstance(user_data["product"], str):
                    user_data["product"] = str(user_data["product"])
            except Exception as e:
                await logs(f"Error converting product_name: {e}", type_e="error")
        if "price" in user_data:
            try:
                if isinstance(user_data["price"], str):
                    user_data["price"] = float(user_data["price"].replace(",", "."))
            except Exception as ex:
                await logs(f"Error converting price: {ex}", type_e="error")
        if "total" in user_data:
            try:
                if isinstance(user_data["total"], str):
                    user_data["total"] = float(user_data["total"].replace(",", "."))
            except Exception as ex:
                await logs(f"Error converting total: {ex}", type_e="error")
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
        await connection.execute(query, *values)
        await logs(f"Data successfully written to table: {file_path}", type_e="info")
        return True
    except Exception as e:
        await logs(f"Error writing data to table {file_path}: {e}", type_e="error")
        return None   
    finally:
        if connection:
            await release_connection(connection)

async def update_user_data(chat_id: int, key: str, value):
    """
    Asynchronous function for updating user data in the "chat_ids" table in PostgreSQL.
    
    Arguments:
      chat_id (int): User identifier to be searched in the user_id column.
      key (str): Name of the column to update.
      value: New value for the specified column.
      
    If a record with user_id = chat_id is found, the function updates the value of column key to value.
    """
    connection = None
    try:
        connection = await get_connection()
        # Form SQL query for update. 
        # Note: column name (key) cannot be parameterized, so it's assumed
        # that the key value is safe and valid.
        validate_identifier(key)
        query = f"UPDATE chat_ids SET {key} = $2 WHERE user_id = $1;"
        
        # Execute query. The execute method will return a string like "UPDATE <n>" on successful update.
        result = await connection.execute(query, chat_id, value)
        
        await logs(f"Data updated for chat_id {chat_id}, key {key}, new value: {value}", type_e="info")
    except Exception as e:
        await logs(f"Module: db_utils. Error updating data for chat_id {chat_id}, key {key}: {e}", type_e="error")
    finally:
        if connection:
            await release_connection(connection)

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
    connection = None
    try:
        connection = await get_connection()
        # Query to get current chat history for the given chat_id
        query_select = "SELECT context FROM context WHERE user_id = $1 LIMIT 1;"
        row = await connection.fetchrow(query_select, chat_id)
        
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
            await connection.execute(query_insert, chat_id, json.dumps(context_list))
        
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
        await connection.execute(query_update, chat_id, json.dumps(context_list))
        
        await logs(f"Chat history for chat_id {chat_id} updated successfully", type_e="info")
    except Exception as e:
        await logs(f"Error updating chat history for chat_id {chat_id}: {e}", type_e="error")
    finally:
        if connection:
            await release_connection(connection)