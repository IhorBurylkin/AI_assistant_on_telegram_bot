import asyncio
import os
import re
from typing import Any, Dict, List, Union
from datetime import datetime, timedelta, timezone, time
from aiogram import types
from PIL import Image
from config.config import WHITE_LIST, MESSAGES
from services.db_utils import update_user_data
from logs.log import logs

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
        await logs(f"Module: utils. Error checking user limits: {e}", type_e="error")
        return False

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
        await logs(f"Image successfully resized: {image_path}", type_e="info")
    except Exception as e:
        await logs(f"Module: utils. Error resizing image {image_path}: {e}", type_e="error")

async def convert_audio(ogg_file: str, wav_file: str):
    """
    Function for converting audio from OGG to WAV format
    :param ogg_file: Path to OGG file
    :param wav_file: Path to WAV file
    """
    try:
        if os.path.exists(wav_file):
            os.remove(wav_file)
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", ogg_file, "-ar", "16000", "-ac", "1", wav_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            error_message = stderr.decode().strip()
            await logs(f"ffmpeg error: {error_message}", type_e="error")
            raise Exception(f"ffmpeg error: {error_message}")
        
        await logs(f"Audio successfully converted: {ogg_file} -> {wav_file}", type_e="info")
    except Exception as e:
        await logs(f"Module: utils. Error converting audio: {e}", type_e="error")

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
        await logs(f"Time until midnight (UTC): {remaining}", type_e="info")
        return remaining
    except Exception as e:
        await logs(f"Error calculating time until midnight (UTC): {e}", type_e="error")
        raise

async def dict_to_str(message_dict: dict) -> str:
    """
    Converts a dictionary to a string.
    :param message_dict: Input dictionary
    :return: String representation of the dictionary
    """
    try:
        def _serialize(obj, indent: int = 0) -> list[str]:
            lines: list[str] = []
            prefix = " " * indent

            if isinstance(obj, dict):
                for key, val in obj.items():
                    if isinstance(val, dict):
                        lines.append(f"{prefix}{key}:")
                        lines.extend(_serialize(val, indent + 2))
                    elif isinstance(val, list):
                        lines.append(f"{prefix}{key}:")
                        for item in val:
                            if isinstance(item, dict):
                                lines.extend(_serialize(item, indent + 2))
                            else:
                                lines.append(f"{prefix}  {item}")
                    else:
                        lines.append(f"{prefix}{key}: {val}")
            else:
                lines.append(f"{prefix}{obj}")

            return lines

        result_lines = _serialize(message_dict)
        result = "\n".join(result_lines)

        await logs(f"Converted dict to string:\n{result}", type_e="info")
        return result

    except Exception as e:
        await logs(f"Error converting dict to string: {e}", type_e="error")
        return ""
    
async def dict_to_str_for_webapp(message_dict: dict) -> str:
    lines = []
    for key, items in message_dict.items():
        lines.append(f"{key}:")
        for item in items:
            lines.append(f"    {item}")
    return "\n".join(lines)

async def map_keys(
    input_data: Union[Dict[str, Any], List[Dict[str, Any]]],
    user_id: int,
    lang: str
) -> List[Dict[str, Any]]:
    """
    Преобразует словарь (или список словарей) с чеками в плоский список записей для БД
    с полями: date, time, store, check_id, category, product, quantity, price, total, currency.
    При этом 'total' каждой записи берётся из ключа 'Итого' всего чека.
    """
    # Порядок полей в БД
    db_fields = ["date", "time", "store", "check_id",
                 "category", "product", "quantity", "price", "total", "currency"]
    # Соответствующие ключи во входном словаре (локаль):
    # ["Дата", "Время", "Магазин", "№ чека", "Категория", "Наименование товара", "Количество", "Цена", "Итого", "Валюта"]
    lang_keys = MESSAGES[lang]["check_struckture_data_for_db"]
    # Сделаем словарь сопоставления базовых полей
    base_mapping = dict(zip(lang_keys, db_fields))

    async def _parse_item(item_str: str) -> Dict[str, Any]:
        """
        Разбирает строку вида "<Название> x <qty> - <price> - <line_total>"
        Возвращает {product, quantity, price}, игнорируя line_total.
        """
        m = re.match(r"^(.*?) x (\d+) - ([\d.]+) - [\d.]+$", item_str)
        if not m:
            return {}
        return {
            "product":  m.group(1),
            "quantity": int(m.group(2)),
            "price":    float(m.group(3)),
        }

    async def _process_one(check: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Собираем неизменяемые поля
        base: Dict[str, Any] = {"user_id": user_id}
        for src_key, dest in base_mapping.items():
            if dest in ("category", "product", "quantity", "price", "total"):
                continue
            base[dest] = check.get(src_key, "")

        # Итоговая сумма всего чека
        total_sum = check.get(lang_keys[8], "")  # ключ "Итого"
        total_value = float(total_sum) if total_sum else 0.0

        records: List[Dict[str, Any]] = []
        goods_block = check.get(lang_keys[5], {})  # ключ "Наименование товара"
        currency    = check.get(lang_keys[9], "")  # ключ "Валюта"

        # goods_block: категория → list[str]
        for category, items in goods_block.items():
            for item_str in items:
                parsed = await _parse_item(item_str)
                if not parsed:
                    continue
                record = {
                    **base,
                    "category": category,
                    **parsed,
                    "total":   total_value,
                    "currency":currency
                }
                records.append(record)

        # Если товаров нет, создаём одну «пустую» запись с общим total
        if not records:
            records.append({
                **base,
                "category": "",
                "product":  "",
                "quantity": 0,
                "price":    0.0,
                "total":    total_value,
                "currency":currency
            })

        return records

    try:
        all_records: List[Dict[str, Any]] = []
        checks = input_data if isinstance(input_data, list) else [input_data]
        for chk in checks:
            all_records.extend(await _process_one(chk))

        await logs(f"Mapped {len(all_records)} records for user {user_id}", type_e="info")
        return all_records

    except Exception as e:
        await logs(f"Error in map_keys: {e}", type_e="error")
        return []