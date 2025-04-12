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
    Function for sending a message to the logging bot
    """
    try:
        if LOGGING_SETTINGS_TO_SEND["permission"] and LOGGING_SETTINGS_TO_SEND["message_thread_id"] not in [None, 0]:
            await info_bot.send_message(chat_id=chat_id, text=text, message_thread_id=LOGGING_SETTINGS_TO_SEND["message_thread_id"])
        else:
            await info_bot.send_message(chat_id=chat_id, text=text)
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

async def download_photo(photo: types.PhotoSize, file_path: str):
    """
    Function for downloading and processing a photo
    :param photo: Photo
    :param file_path: Path to save the file
    """
    try:
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

    # # 3. Perspective correction (alignment)
    # edged = cv2.Canny(equalized, 50, 150)
    # contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    # contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    # cv2.imwrite("step_edged.jpg", edged)

    # receipt_contour = None
    # for cnt in contours:
    #     peri = cv2.arcLength(cnt, True)
    #     approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
    #     if len(approx) == 4:  # look for contour with four vertices (receipt)
    #         receipt_contour = approx
    #         break

    # if receipt_contour is not None:
    #     pts = receipt_contour.reshape(4, 2)
    #     pts = order_points(pts)

    #     # Calculate dimensions of future image
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
    #     # If receipt contour not found, continue with pre-processed image
    #     warped = equalized

    # 4. Remove noise and smooth (median filter)
    # blurred = cv2.medianBlur(equalized, 5)
    # cv2.imwrite("step_blurred.jpg", blurred)

    # 5. Binarize image (Otsu method)
    # ret, thresh = cv2.threshold(equalized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # cv2.imwrite("step_thresh.jpg", thresh)

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
        await log_info(f"Error sending message: {e}", type_e="error")
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