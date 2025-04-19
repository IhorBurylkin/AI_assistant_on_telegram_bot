from fastapi import FastAPI, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from config import DEFAULT_LANGUAGES, MESSAGES
from services.db_utils import read_user_all_data, save_form_data
from logs import log_info
from typing import Dict, Any

# Словарь с текстами для формы
DEFAULT_FORM_TEXT = {
    "title": "Форма данных",
    "date_label": "Дата",
    "date_error": "Пожалуйста, выберите дату.",
    "time_label": "Время",
    "time_error": "Пожалуйста, выберите время.",
    "store_label": "Магазин",
    "store_error": "Введите название магазина.",
    "product_label": "Наименование товара",
    "product_placeholder": "Введите текст...",
    "product_error": "Введите название товара.",
    "total_label": "Итого",
    "total_error": "Введите корректную сумму.",
    "currency_label": "Валюта",
    "currency_select": "Выберите валюту",
    "currency_error": "Выберите валюту."
}

DEFAULT_BUTTONS = {
    "submit": "Отправить"
}

# Словарь для тестирования, если структура MESSAGES не соответствует ожидаемой
DEFAULT_FORM_TEXT = {
    "title": "Форма данных",
    "date_label": "Дата",
    "date_error": "Пожалуйста, выберите дату.",
    "time_label": "Время",
    "time_error": "Пожалуйста, выберите время.",
    "store_label": "Магазин",
    "store_error": "Введите название магазина.",
    "product_label": "Наименование товара",
    "product_placeholder": "Введите текст...",
    "product_error": "Введите название товара.",
    "total_label": "Итого",
    "total_error": "Введите корректную сумму.",
    "currency_label": "Валюта",
    "currency_select": "Выберите валюту",
    "currency_error": "Выберите валюту."
}

DEFAULT_BUTTONS = {
    "submit": "Отправить"
}

# Инициализация
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/form/{chat_id}", response_class=HTMLResponse)
async def form(request: Request, chat_id: int):
    try:
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language") if user_data else DEFAULT_LANGUAGES
        
        # Используем тестовые данные, если структура MESSAGES не содержит нужных ключей
        try:
            fields = MESSAGES[lang]["check_struckture_data"]
            buttons = MESSAGES[lang]["web_app_bt"]
            
            # Проверяем наличие всех необходимых ключей
            if not all(key in fields for key in DEFAULT_FORM_TEXT.keys()):
                fields = DEFAULT_FORM_TEXT
                
            if "submit" not in buttons:
                buttons = DEFAULT_BUTTONS
                
        except (KeyError, TypeError):
            fields = DEFAULT_FORM_TEXT
            buttons = DEFAULT_BUTTONS
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "fields": fields,
                "buttons": buttons,
            }
        )
    except Exception as e:
        await log_info(f"Error in webapp for chat_id {chat_id}: {e}", type_e="error")
        return HTMLResponse(f"<h1>Error</h1><p>{str(e)}</p>", status_code=500)

@app.post("/submit")
async def submit_form(data: Dict[Any, Any] = Body(...)):
    try:
        # Сохраняем данные формы
        print(data)
        return JSONResponse({"status": "success"})
    except Exception as e:
        await log_info(f"Error saving form data: {e}", type_e="error")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fast_api:app", host="0.0.0.0", port=8000, reload=True)