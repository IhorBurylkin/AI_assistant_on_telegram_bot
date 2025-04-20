import os
import logging
import sys
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from config import WEBAPP_URL, MESSAGES

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
    app.logger.info(
        "%s %s %s — Body: %s",
        request.method, request.path, request.remote_addr,
        request.get_data(as_text=True)
    )

    app.logger.info("Headers: Host=%s, User-Agent=%s", 
                request.headers.get('Host'),
                request.headers.get('User-Agent'))

# ——————————————————————————————————————————————————————————————
# Конфигурация приложения
# ——————————————————————————————————————————————————————————————
API_BASE_URL = os.getenv('API_BASE_URL', '')

@app.route('/')
async def index():
    app.logger.info("Rendering index page, API_BASE_URL=%s", API_BASE_URL)
    chat_id = request.args.get('chat_id', type=int)
    app.logger.info("Chat ID: %s", chat_id)
    fields = {
        'title': 'Трекер расходов',
        'date_label': 'Дата',
        'date_error': 'Выберите дату',
        'time_label': 'Время',
        'time_error': 'Укажите время',
        'store_label': 'Магазин',
        'store_error': 'Укажите название магазина',
        'product_label': 'Товары',
        'product_placeholder': 'Введите список покупок',
        'product_error': 'Укажите хотя бы один товар',
        'total_label': 'Сумма',
        'total_error': 'Укажите сумму',
        'currency_label': 'Валюта',
        'currency_select': 'Выберите валюту',
        'currency_error': 'Выберите валюту'
    }
    
    buttons = {
        'submit': 'Отправить'
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

# ——————————————————————————————————————————————————————————————
if __name__ == "__main__":
    app.logger.info("Starting Waitress on 127.0.0.1:5000")
