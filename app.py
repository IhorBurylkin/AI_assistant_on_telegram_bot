import os
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from config.config import WEBAPP_URL, MESSAGES, DEFAULT_LANGUAGES
from services.db_utils import read_user_all_data
from services.db_utils import get_connection, release_connection
from logs.log import log_info
from handlers.callbacks import process_user_input_list

app = Flask(__name__)
CORS(app)

CORS(app, resources={r"/api/*": {"origins": WEBAPP_URL}})

@app.before_request
async def log_request_info():
    raw_body = request.get_data(as_text=True)
    await log_info(f"{request.method} {request.path} {request.remote_addr} — Body: {raw_body} — Host={request.headers.get('Host')} — UA={request.headers.get('User-Agent')}", 
                   type_e="info")

API_BASE_URL = os.getenv('API_BASE_URL', '')

@app.route('/')
async def index():
    return jsonify({
            'error': 'Bad request',
            'bot_url': 'https://t.me/ChatGPTX_2bot'
        }), 400

@app.route('/check_form/api')
async def check_form():
    date = request.args.get('date')             
    time = request.args.get('time')                     
    store = request.args.get('store')                  
    product = request.args.get('product')                  
    total = request.args.get('total', type=float)      
    currency = request.args.get('currency')                
    chat_id = request.args.get('chat_id', type=int)
    
    if chat_id:
        await log_info(f"Received request from chat_id = {chat_id}", type_e="info")
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
        values = {
            'date': date or '',
            'time': time or '',
            'store': store or '',
            'product': product or '',
            'total': total or '',
            'currency': currency or '',
            'chat_id': chat_id or '',
        }
        
        return render_template('check_form.html', 
                            fields=fields, 
                            buttons=buttons, 
                            values=values,
                            api_base_url=API_BASE_URL)

@app.route('/check_form/api/submit', methods=['POST'])
async def api_submit():
    keys = ['date', 'time', 'store', 'product', 'total', 'currency', 'chat_id']
    # Extract data from JSON body
    data = request.get_json(silent=True) or {}
    user_text_input = [data.get(k) for k in keys]
    date, time, store, product, total, currency, chat_id = user_text_input

    # Log received data
    await log_info(f"Received expense submission - Date: {date}, Time: {time}, Store: {store}, Product: {product}, Total: {total} {currency}, Chat ID: {chat_id}", 
                   type_e="info")
    conn = await get_connection()
    
    try:
        await process_user_input_list(user_text_input=user_text_input)
        await log_info(f"Data processed successfully for chat_id {chat_id}", type_e="info")
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
