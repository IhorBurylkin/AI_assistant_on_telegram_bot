from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from config import DEFAULT_LANGUAGES, MESSAGES
from services.db_utils import read_user_all_data

# Инициализация
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/form", response_class=HTMLResponse)
async def form(request: Request):
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES
    """
    Отдаёт страницу с формой.
    Динамически вставляются поля и кнопки из config.json.
    """
    return templates.TemplateResponse(
        "form.html",
        {
            "request":  request,
            "fields":   MESSAGES[lang]["check_struckture_data"],
            "buttons":  MESSAGES[lang]["web_app_bt"],
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
