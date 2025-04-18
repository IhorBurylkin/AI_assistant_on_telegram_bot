import tiktoken
import asyncio
import datetime
from PIL import Image
from aiogram import types
from datetime import datetime, timedelta, timezone, time
import cv2
import os
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from logs import log_info
from config import WHITE_LIST, LOGGING_SETTINGS_TO_SEND, PRODUCT_KEYS, PRODUCT_KEYS_FOR_PARSE, MESSAGES
from services.db_utils import update_user_data

async def send_info_msg(text=None, message_thread_id=None, info_bot=None, chat_id=None):
    """
    Function for sending a message to the logging bot
    """
    if chat_id is None:
        chat_id = LOGGING_SETTINGS_TO_SEND["chat_id"]
        
    try:
        # Only proceed if we have a bot instance
        if info_bot is not None:
            if LOGGING_SETTINGS_TO_SEND["permission"] and LOGGING_SETTINGS_TO_SEND["message_thread_id"] not in [None, 0]:
                await info_bot.send_message(chat_id=chat_id, text=text, message_thread_id=LOGGING_SETTINGS_TO_SEND["message_thread_id"])
            else:
                await info_bot.send_message(chat_id=chat_id, text=text)
        else:
            # Log that we couldn't send the message due to missing bot instance
            print(f"Warning: Could not send info message - info_bot instance not provided")
    except Exception as e:
        await log_info(f"Error sending message: {e}", type_e="error")

async def count_tokens_for_user_text(text: str, model: str = "o200k_base") -> int:
    """
    Function for counting tokens in user text
    :param text: User text
    :param model: Tokenization model
    :return: Number of tokens
    """
    try:
        # Perform blocking token counting operation in a separate thread
        def count(model):
            if model not in ["gpt-4o-mini", "gpt-4o"]:
                model = "o200k_base"
                encoding = tiktoken.get_encoding(model)
            else:
                encoding = tiktoken.encoding_for_model(model)
            tokens = encoding.encode(text)
            return len(tokens)
        
        token_count = await asyncio.to_thread(count, model)
        return token_count
    except Exception as e:
        await log_info(f"Error counting tokens: {e}", type_e="error")
        return 0
    
async def check_user_limits(user_data: list, chat_id: int) -> bool:
    """
    Function for checking user limits
    :param user_data: User data
    :param chat_id: Chat ID
    :return: Check result
    """
    try:
        # Extract token and request counts
        tokens, requests, last_date = user_data  # user_data[0][0] -> tokens, user_data[0][1] -> requests
        last_date = last_date.strftime("%Y-%m-%d")
        current_date = datetime.now().strftime("%Y-%m-%d")
        date_to_write_db = datetime.fromisoformat(current_date)

        # If chat_id is in white list, limits don't apply
        if chat_id in WHITE_LIST:
            return True

        # If date changed, reset counters and update date
        if current_date != last_date:
            await update_user_data(chat_id, "tokens", 0)
            await update_user_data(chat_id, "requests", 0)
            await update_user_data(chat_id, "date_requests", date_to_write_db)
            return True

        # Check limits: if tokens > 1000 or requests > 10 - return False
        if tokens > 1000 or requests > 10:
            return False

        return True
    except Exception as e:
        await log_info(f"Error checking user limits: {e}", type_e="error")
        return False
    
async def convert_audio(ogg_file: str, wav_file: str):
    """
    Function for converting audio from OGG to WAV format
    :param ogg_file: Path to OGG file
    :param wav_file: Path to WAV file
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", ogg_file, "-ar", "16000", "-ac", "1", wav_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            error_message = stderr.decode().strip()
            await log_info(f"ffmpeg error: {error_message}", type_e="error")
            raise Exception(f"ffmpeg error: {error_message}")
        
        await log_info(f"Audio successfully converted: {ogg_file} -> {wav_file}", type_e="info")
    except Exception as e:
        await log_info(f"Error converting audio: {e}", type_e="error")
        raise

async def resize_image(image_path: str, max_size: tuple = (512, 512)):
    """
    Function for resizing an image
    :param image_path: Path to the image
    :param max_size: Maximum size
    """
    try:
        def _resize():
            with Image.open(image_path) as img:
                img.thumbnail(max_size)
                img.save(image_path)
        await asyncio.to_thread(_resize)
        await log_info(f"Image successfully resized: {image_path}", type_e="info")
    except Exception as e:
        await log_info(f"Error resizing image {image_path}: {e}", type_e="error")
        raise

async def download_photo(photo: types.PhotoSize, file_path: str, bot=None):
    """
    Function for downloading and processing a photo
    :param photo: Photo
    :param file_path: Path to save the file
    :param bot: Bot instance to use for downloading
    """
    try:
        if bot is None:
            await log_info("Error: Bot instance not provided to download_photo", type_e="error")
            raise ValueError("Bot instance required for download_photo")
            
        file_info = await bot.get_file(photo.file_id)
        await bot.download_file(file_info.file_path, destination=file_path)
        await resize_image(file_path)
        await log_info(f"Photo successfully downloaded and processed: {file_path}", type_e="info")
    except Exception as e:
        await log_info(f"Error downloading photo: {e}", type_e="error")
        raise

async def time_until_midnight_utc() -> timedelta:
    """
    Function for calculating time until midnight (UTC)
    :return: Time until midnight
    """
    try:
        now = datetime.now(timezone.utc)
        tomorrow = now.date() + timedelta(days=1)
        midnight = datetime.combine(tomorrow, time.min).replace(tzinfo=timezone.utc)
        remaining = midnight - now
        await log_info(f"Time until midnight (UTC): {remaining}", type_e="info")
        return remaining
    except Exception as e:
        await log_info(f"Error calculating time until midnight (UTC): {e}", type_e="error")
        raise

async def get_current_datetime():
    """
    Asynchronously returns the current date and time.

    The function simulates an asynchronous operation by awaiting asyncio.sleep(0),
    then returns the current datetime using datetime.datetime.now().
    """
    await asyncio.sleep(0)  # This makes the function awaitable in an async context
    return datetime.now(timezone.utc)

def order_points(pts):
    """
    Sorts points in the order:
    top-left, top-right, bottom-right, bottom-left.
    """
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # minimum sum - top left
    rect[2] = pts[np.argmax(s)]  # maximum sum - bottom right

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # minimum difference - top right
    rect[3] = pts[np.argmax(diff)]  # maximum difference - bottom left
    return rect

def process_receipt(image_path):
    """
    Processes a receipt image:
      1. Conversion to grayscale.
      2. Contrast enhancement (histogram equalization).
      3. Perspective correction.
      4. Noise removal and smoothing.
      5. Binarization using the Otsu method.
      6. Cropping to receipt boundaries.
      
    Returns the processed image (numpy array).
    """
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Error: failed to load image.")
        
    # 1. Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cv2.imwrite("step_gray.jpg", gray)

    # 2. Enhance contrast (histogram equalization)
    #equalized = cv2.equalizeHist(gray)
    # Alternatively, use CLAHE:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    equalized = clahe.apply(gray)
    cv2.imwrite("step_equalized.jpg", equalized)

    # 6. Final cropping to receipt boundaries
    contours, _ = cv2.findContours(equalized.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        c = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(c)
        final = equalized[y:y+h, x:x+w]
    else:
        final = equalized

    return final

async def async_process_receipt(image_path):
    """
    Asynchronous wrapper for process_receipt,
    executing it in a thread pool.
    Returns the processed image (numpy array).
    """
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(pool, process_receipt, image_path)
    return result

async def process_and_save_receipt(image_path, output_path=None):
    """
    Asynchronously processes a receipt image, saves the result, and returns the path to the saved file.
    
    :param image_path: Path to the original image.
    :param output_path: Optional, path to save the processed image.
                        If not specified, a filename in the format "originalname_processed.ext" is generated.
    :return: Path to the saved processed image.
    """
    try:
        processed_image = await async_process_receipt(image_path)
        
        # If save path not specified, generate it based on original name
        if output_path is None:
            dirname, filename = os.path.split(image_path)
            name, ext = os.path.splitext(filename)
            output_path = os.path.join(dirname, f"{name}_processed{ext}")

        success = cv2.imwrite(output_path, processed_image)
        if not success:
            raise IOError("Error saving processed image.")
            
        return output_path
    except Exception as e:
        await log_info(f"Error processing image: {e}", type_e="error")
        raise

async def open_cv_image_processing(image_path):
    # Specify path to your image (receipt)
    try:
        image_processed_path = await process_and_save_receipt(image_path)
        print("Processed image saved at path:", image_processed_path)
        return image_processed_path
    except Exception as e:
        await log_info(f"Error processing image: {e}", type_e="error")
        return image_path
    
async def split_str_to_dict(text: str, split_only_line: bool = False):
    """
    Splits a string into a dictionary.
    :param text: Input string
    :return: Dictionary
    """
    try:
        lines = text.splitlines()
        message_to_db = {}
        i = 0
        if split_only_line:
            while i < len(lines):
                line = lines[i].strip()
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    if not value:
                        additional_lines = []
                        i += 1
                        while i < len(lines) and (":" not in lines[i]):
                            additional_lines.append(lines[i].strip())
                            i += 1
                        value = "\n".join(additional_lines)
                        message_to_db[key] = value
                        continue 
                    else:
                        message_to_db[key] = value
                i += 1
            return message_to_db
        else:
            while i < len(lines):
                line = lines[i].strip()
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    # Если после двоеточия значение отсутствует
                    if not value:
                        # Если ключ соответствует одному из вариантов для товаров
                        if key in PRODUCT_KEYS:
                            product_dict = {}
                            i += 1
                            # Собираем строки, пока не встретим новую строку с двоеточием
                            while i < len(lines) and (":" not in lines[i]):
                                curr_line = lines[i].strip()
                                # Если строка соответствует формату "Название - Цена"
                                if " - " in curr_line:
                                    prod_key, prod_val = curr_line.split(" - ", 1)
                                    product_dict[prod_key.strip()] = prod_val.strip()
                                i += 1
                            message_to_db[key] = product_dict
                            continue  # переход к следующей итерации цикла (i уже обновлён)
                        else:
                            val_list = []
                            i += 1
                            while i < len(lines) and (":" not in lines[i]):
                                val_list.append(lines[i].strip())
                                i += 1
                            message_to_db[key] = "\n".join(val_list)
                            continue
                    else:
                        message_to_db[key] = value
                i += 1
            return message_to_db
    except Exception as e:
        await log_info(f"Error splitting string to dict: {e}", type_e="error")
        return {}
    
async def dict_to_str(message_dict: dict) -> str:
    """
    Converts a dictionary to a string.
    :param message_dict: Input dictionary
    :return: String representation of the dictionary
    """
    try:
        result = []
        for key, value in message_dict.items():
            if isinstance(value, dict):
                sub_result = dict_to_str(value)
                result.append(f"{key}:\n{sub_result}")
            else:
                result.append(f"{key}: {value}")
        return "\n".join(result)
    except Exception as e:
        await log_info(f"Error converting dict to string: {e}", type_e="error")
        return ""
    
async def map_keys(input_data, user_id: int, lang: str) -> dict:
    """
    Maps keys in the input dictionary to new keys based on the mapping dictionary.
    :param input_dict: Input dictionary
    :param mapping_dict: Mapping dictionary
    :return: New dictionary with mapped keys
    """
    async def mapping_func(single_dict: dict, mapping: dict, user_id: int) -> dict:
        output = {"user_id": user_id}
        for key, value in single_dict.items():
            if key in mapping:
                output[mapping[key]] = value
            else:
                output[key] = value
        return output

    try:
        db_fields = ["date", "time", "store", "category", "product", "quantity", "price", "total", "currency"]
        mapping = dict(zip(MESSAGES[lang]["check_struckture_category_for_db"], db_fields))
        if isinstance(input_data, list):
            result_list = []
            for item in input_data:
                mapped_item = await mapping_func(item, mapping, user_id)
                result_list.append(mapped_item)
            return result_list
        elif isinstance(input_data, dict):
            return await mapping_func(input_data, mapping, user_id)
        else:
            raise TypeError("Input data must be a dict or a list of dicts")
    except Exception as e:
        await log_info(f"Error mapping keys: {e}", type_e="error")
        return {}
    
async def parse_ai_result_response(data: dict, lang: str) -> list:
    """
    Parses the AI result response and converts it into a list of dictionaries.
    :param data: Input dictionary
    :return: List of dictionaries
    """
    result = []
    header_keys = MESSAGES[lang]["check_struckture_data_for_parse"]
    header = {key: data.get(key, "") for key in header_keys}
    
    current_category = ""
    
    product_name = MESSAGES[lang]["check_struckture_data_for_product_name"]
    product_block = data.get(product_name, "")
    lines = [line.strip() for line in product_block.splitlines() if line.strip()]

    PRODUCT_KEYS = MESSAGES[lang]["check_struckture_data_for_db"]
    
    for line in lines:
        if line.endswith(":"):
            current_category = line.rstrip(":").strip()
            continue
        parts = line.split(" - ")
        if len(parts) < 2:
            continue
        price_str = parts[1].strip()
        try:
            price = float(price_str.replace(" ", "").replace(",", "."))
        except ValueError:
            price = 0.0

        left_part = parts[0].strip()
        found_delim = None
        for delim in [" x ", " X ", "x", "X", "*"]:
            if delim in left_part:
                found_delim = delim
                break

        if found_delim:
            name_qty = left_part.split(found_delim, 1)
            product_name = name_qty[0].strip()
            qty_str = name_qty[1].strip()
            try:
                quantity = int(qty_str)
            except ValueError:
                quantity = 1
        else:
            product_name = left_part
            quantity = 1
        
        item = {
            PRODUCT_KEYS_FOR_PARSE[0]: header.get(PRODUCT_KEYS[0], ""),
            PRODUCT_KEYS_FOR_PARSE[1]: header.get(PRODUCT_KEYS[1], ""),
            PRODUCT_KEYS_FOR_PARSE[2]: header.get(PRODUCT_KEYS[2], ""),
            PRODUCT_KEYS_FOR_PARSE[3]: current_category,
            PRODUCT_KEYS_FOR_PARSE[4]: product_name,
            PRODUCT_KEYS_FOR_PARSE[5]: quantity,
            PRODUCT_KEYS_FOR_PARSE[6]: price,
            PRODUCT_KEYS_FOR_PARSE[7]: header.get(PRODUCT_KEYS[7], ""),
            PRODUCT_KEYS_FOR_PARSE[8]: header.get(PRODUCT_KEYS[8], "")
        }
        result.append(item)
    
    return result