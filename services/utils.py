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
from config import WHITE_LIST
from services.db_utils import update_user_data
from bot import bot, info_bot
from config import LOGGING_SETTINGS_TO_SEND

async def send_info_msg(chat_id=LOGGING_SETTINGS_TO_SEND["chat_id"], text=None, message_thread_id=None):
    """
    Функция отправки сообщения в логирующий бот
    """
    try:
        if LOGGING_SETTINGS_TO_SEND["permission"] and LOGGING_SETTINGS_TO_SEND["message_thread_id"] not in [None, 0]:
            await info_bot.send_message(chat_id=chat_id, text=text, message_thread_id=LOGGING_SETTINGS_TO_SEND["message_thread_id"])
        else:
            await info_bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        await log_info(f"Ошибка отправки сообщения: {e}", type_e="error")

async def count_tokens_for_user_text(text: str, model: str = "o200k_base") -> int:
    """
    Функция подсчёта токенов в тексте пользователя
    :param text: Текст пользователя
    :param model: Модель токенизации
    :return: Количество токенов
    """
    try:
        # Выполняем блокирующую операцию подсчёта токенов в отдельном потоке
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
        await log_info(f"Ошибка подсчёта токенов: {e}", type_e="error")
        return 0
    
async def check_user_limits(user_data: list, chat_id: int) -> bool:
    """
    Функция проверки лимитов пользователя
    :param user_data: Данные пользователя
    :param chat_id: ID чата
    :return: Результат проверки
    """
    try:
        # Извлекаем количество токенов и запросов
        tokens, requests, last_date = user_data  # user_data[0][0] -> tokens, user_data[0][1] -> requests
        last_date = last_date.strftime("%Y-%m-%d")
        current_date = datetime.now().strftime("%Y-%m-%d")
        date_to_write_db = datetime.fromisoformat(current_date)

        # Если chat_id в белом списке, лимиты не применяются
        if chat_id in WHITE_LIST:
            return True

        # Если дата изменилась, сбрасываем счетчики и обновляем дату
        if current_date != last_date:
            await update_user_data(chat_id, "tokens", 0)
            await update_user_data(chat_id, "requests", 0)
            await update_user_data(chat_id, "date_requests", date_to_write_db)
            return True

        # Проверка лимитов: если токенов больше 1000 или запросов больше 10 – возвращаем False
        if tokens > 1000 or requests > 10:
            return False

        return True
    except Exception as e:
        await log_info(f"Ошибка при проверке лимитов пользователя: {e}", type_e="error")
        return False
    
async def convert_audio(ogg_file: str, wav_file: str):
    """
    Функция конвертации аудио из формата OGG в WAV
    :param ogg_file: Путь к файлу OGG
    :param wav_file: Путь к файлу WAV
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
        
        await log_info(f"Успешно конвертирован аудио: {ogg_file} -> {wav_file}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка конвертации аудио: {e}", type_e="error")
        raise

async def resize_image(image_path: str, max_size: tuple = (512, 512)):
    """
    Функция изменения размера изображения
    :param image_path: Путь к изображению
    :param max_size: Максимальный размер
    """
    try:
        def _resize():
            with Image.open(image_path) as img:
                img.thumbnail(max_size)
                img.save(image_path)
        await asyncio.to_thread(_resize)
        await log_info(f"Изображение успешно изменено: {image_path}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка при изменении размера изображения {image_path}: {e}", type_e="error")
        raise

async def download_photo(photo: types.PhotoSize, file_path: str):
    """
    Функция загрузки и обработки фотографии
    :param photo: Фотография
    :param file_path: Путь для сохранения файла
    """
    try:
        file_info = await bot.get_file(photo.file_id)
        await bot.download_file(file_info.file_path, destination=file_path)
        await resize_image(file_path)
        await log_info(f"Фото успешно загружено и обработано: {file_path}", type_e="info")
    except Exception as e:
        await log_info(f"Ошибка при загрузке фотографии: {e}", type_e="error")
        raise

async def time_until_midnight_utc() -> timedelta:
    """
    Функция вычисления времени до полуночи (UTC)
    :return: Время до полуночи
    """
    try:
        now = datetime.now(timezone.utc)
        tomorrow = now.date() + timedelta(days=1)
        midnight = datetime.combine(tomorrow, time.min).replace(tzinfo=timezone.utc)
        remaining = midnight - now
        await log_info(f"Время до полуночи (UTC): {remaining}", type_e="info")
        return remaining
    except Exception as e:
        await log_info(f"Ошибка при вычислении времени до полуночи (UTC): {e}", type_e="error")
        raise

def order_points(pts):
    """
    Сортирует точки в порядке:
    верхний левый, верхний правый, нижний правый, нижний левый.
    """
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # минимальная сумма – верхний левый
    rect[2] = pts[np.argmax(s)]  # максимальная сумма – нижний правый

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # минимальная разница – верхний правый
    rect[3] = pts[np.argmax(diff)]  # максимальная разница – нижний левый
    return rect

def process_receipt(image_path):
    """
    Обрабатывает изображение чека:
      1. Перевод в оттенки серого.
      2. Повышение контрастности (гистограммное выравнивание).
      3. Коррекция перспективы.
      4. Удаление шума и сглаживание.
      5. Бинаризация с помощью метода Оцу.
      6. Обрезка до границ чека.
      
    Возвращает обработанное изображение (numpy-массив).
    """
    # Загрузка изображения
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Ошибка: не удалось загрузить изображение.")
        
    # 1. Перевод в оттенки серого
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cv2.imwrite("step_gray.jpg", gray)

    # 2. Повышение контрастности (гистограммное выравнивание)
    #equalized = cv2.equalizeHist(gray)
    # Альтернативно можно использовать CLAHE:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    equalized = clahe.apply(gray)
    cv2.imwrite("step_equalized.jpg", equalized)

    # # 3. Коррекция перспективы (выравнивание)
    # edged = cv2.Canny(equalized, 50, 150)
    # contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    # contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    # cv2.imwrite("step_edged.jpg", edged)

    # receipt_contour = None
    # for cnt in contours:
    #     peri = cv2.arcLength(cnt, True)
    #     approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
    #     if len(approx) == 4:  # ищем контур с четырьмя вершинами (чек)
    #         receipt_contour = approx
    #         break

    # if receipt_contour is not None:
    #     pts = receipt_contour.reshape(4, 2)
    #     pts = order_points(pts)

    #     # Вычисляем размеры будущего изображения
    #     (tl, tr, br, bl) = pts
    #     widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    #     widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    #     maxWidth = max(int(widthA), int(widthB))

    #     heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    #     heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    #     maxHeight = max(int(heightA), int(heightB))

    #     dst = np.array([
    #         [0, 0],
    #         [maxWidth - 1, 0],
    #         [maxWidth - 1, maxHeight - 1],
    #         [0, maxHeight - 1]], dtype="float32")
            
    #     M = cv2.getPerspectiveTransform(pts, dst)
    #     warped = cv2.warpPerspective(equalized, M, (maxWidth, maxHeight))
    # else:
    #     # Если контур чека не найден, продолжаем с предварительно обработанным изображением
    #     warped = equalized

    # 4. Удаление шума и сглаживание (медианный фильтр)
    # blurred = cv2.medianBlur(equalized, 5)
    # cv2.imwrite("step_blurred.jpg", blurred)

    # 5. Бинаризация изображения (метод Оцу)
    # ret, thresh = cv2.threshold(equalized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # cv2.imwrite("step_thresh.jpg", thresh)

    # 6. Финальная обрезка до границ чека
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
    Асинхронная обёртка для process_receipt,
    выполняющая её в пуле потоков.
    Возвращает обработанное изображение (numpy-массив).
    """
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(pool, process_receipt, image_path)
    return result

async def process_and_save_receipt(image_path, output_path=None):
    """
    Асинхронно обрабатывает изображение чека, сохраняет результат и возвращает путь к сохранённому файлу.
    
    :param image_path: Путь к исходному изображению.
    :param output_path: Опционально, путь для сохранения обработанного изображения.
                        Если не указан, формируется имя файла вида: "originalname_processed.ext"
    :return: Путь к сохранённому обработанному изображению.
    """
    try:
        processed_image = await async_process_receipt(image_path)
        
        # Если путь для сохранения не указан, генерируем его на основе исходного имени
        if output_path is None:
            dirname, filename = os.path.split(image_path)
            name, ext = os.path.splitext(filename)
            output_path = os.path.join(dirname, f"{name}_processed{ext}")

        success = cv2.imwrite(output_path, processed_image)
        if not success:
            raise IOError("Ошибка сохранения обработанного изображения.")
            
        return output_path
    except Exception as e:
        await log_info(f"Ошибка отправки сообщения: {e}", type_e="error")
        raise

async def open_cv_image_processing(image_path):
    # Укажите путь к вашему изображению (чеком)
    try:
        image_processed_path = await process_and_save_receipt(image_path)
        print("Обработанное изображение сохранено по пути:", image_processed_path)
        return image_processed_path
    except Exception as e:
        await log_info(f"Ошибка обработки изображения: {e}", type_e="error")
        return image_path
