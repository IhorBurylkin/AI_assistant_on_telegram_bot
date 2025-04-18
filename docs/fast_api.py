from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from config import DEFAULT_LANGUAGES, MESSAGES
from services.db_utils import read_user_all_data
from logs import log_info

# Инициализация
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/form/{chat_id}", response_class=HTMLResponse)
async def form(request: Request, chat_id: int):
    try:
        user_data = await read_user_all_data(chat_id)
        lang = user_data.get("language") if user_data else DEFAULT_LANGUAGES
        
        return templates.TemplateResponse(
            "form.html",
            {
                "request": request,
                "fields": MESSAGES[lang]["check_struckture_data"],
                "buttons": MESSAGES[lang]["web_app_bt"],
            }
        )
    except Exception as e:
        await log_info(f"Error in webapp for chat_id {chat_id}: {e}", type_e="error")
        return HTMLResponse(f"<h1>Error</h1><p>{str(e)}</p>", status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
