import os
import logging
import sys
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from config import WEBAPP_URL, MESSAGES, DEFAULT_LANGUAGES
from services.db_utils import read_user_all_data
from services.db_utils import get_connection, release_connection

app = Flask(__name__)
CORS(app)

CORS(app, resources={r"/api/*": {"origins": WEBAPP_URL}})
# ——————————————————————————————————————————————————————————————
# Логирование
# ——————————————————————————————————————————————————————————————
# создаём форматтер
text_handler = logging.StreamHandler(sys.stdout)
text_handler.setLevel(logging.INFO)
text_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s %(message)s'
))

# вращающийся файл-логгер: max 10MB, хранить 5 ротаций
file_handler = RotatingFileHandler(
    "app.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
)

app.logger.propagate = False

app.logger.handlers = [text_handler]
app.logger.setLevel(logging.INFO)
# подключаем к логгеру Flask
app.logger.addHandler(file_handler)

# логируем все входящие запросы
@app.before_request
async def log_request_info():
    raw_body = request.get_data(as_text=True)
    # Один вызов, полный лог
    app.logger.info(
        "%s %s %s — Body: %s — Host=%s — UA=%s",
        request.method,
        request.path,
        request.remote_addr,
        raw_body,
        request.headers.get('Host'),
        request.headers.get('User-Agent')
    )

# ——————————————————————————————————————————————————————————————
# Конфигурация приложения
# ——————————————————————————————————————————————————————————————
API_BASE_URL = os.getenv('API_BASE_URL', '')

@app.route('/')
async def index():
    chat_id = request.args.get('chat_id', type=int)
    print(f"chat_id = {chat_id}", type(chat_id))
    app.logger.info("Received request from chat_id = %s", chat_id)
    user_data = await read_user_all_data(chat_id)
    lang = user_data.get("language")
    if not lang:
        lang = DEFAULT_LANGUAGES
    fields = {
        'title': MESSAGES[lang]["web_app_bt"]["fields"]["title"],
        'date_label': MESSAGES[lang]["web_app_bt"]["fields"]["date_label"],
        'date_error': MESSAGES[lang]["web_app_bt"]["fields"]["date_error"], 
        'time_label': MESSAGES[lang]["web_app_bt"]["fields"]["time_label"],
        'time_error': MESSAGES[lang]["web_app_bt"]["fields"]["time_error"],
        'store_label': MESSAGES[lang]["web_app_bt"]["fields"]["store_label"],
        'store_error': MESSAGES[lang]["web_app_bt"]["fields"]["store_error"],
        'product_label': MESSAGES[lang]["web_app_bt"]["fields"]["product_label"],
        'product_placeholder': MESSAGES[lang]["web_app_bt"]["fields"]["product_placeholder"],
        'product_error': MESSAGES[lang]["web_app_bt"]["fields"]["product_error"],
        'total_label': MESSAGES[lang]["web_app_bt"]["fields"]["total_label"],
        'total_error': MESSAGES[lang]["web_app_bt"]["fields"]["total_error"],
        'currency_label': MESSAGES[lang]["web_app_bt"]["fields"]["currency_label"],
        'currency_select': MESSAGES[lang]["web_app_bt"]["fields"]["currency_select"],
        'currency_error': MESSAGES[lang]["web_app_bt"]["fields"]["currency_error"]
    }
    
    buttons = {
        'submit': MESSAGES[lang]["web_app_bt"]["buttons"]["submit"]
    }
    
    return render_template('index.html', 
                          fields=fields, 
                          buttons=buttons, 
                          api_base_url=API_BASE_URL)

@app.route('/api/submit', methods=['POST'])
async def api_submit():
    # Extract data from JSON body
    data = request.get_json(silent=True) or {}
    date = data.get('date')
    time = data.get('time')
    store = data.get('store')
    product = data.get('product')
    total = data.get('total')
    currency = data.get('currency')
    chat_id = data.get('chat_id')
    # Log received data
    app.logger.info(
        "Received expense submission - Date: %s, Time: %s, Store: %s, "
        "Product: %s, Total: %s %s, Chat ID: %s",
        date, time, store, product, total, currency, chat_id
    )
    conn = await get_connection()
    try:
        pass
    finally:
        await release_connection(conn)
    # Return success response
    return jsonify({
        'success': True,
        'message': 'Данные успешно получены'
    }), 200

@app.route('/api/hello', methods=['POST'])
async def api_hello():
    data = request.get_json(silent=True) or {}
    name = data.get('name', 'World')
    app.logger.info("Received hello request, name=%s", name)
    resp = {'message': f'Hello, {name}!'}
    app.logger.info("Responding: %s", resp)
    return jsonify(resp), 200
