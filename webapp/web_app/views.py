from django.shortcuts import render
from config.config import MESSAGES, DEFAULT_LANGUAGES
from logs.log import logs
from services.db_utils import read_user_all_data
import json
from django.http import JsonResponse, HttpResponseNotAllowed, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from services.db_utils import get_connection, release_connection
from handlers.callbacks_options import process_user_input_list

async def check_form(request):
    chat_id = int(request.GET.get('chat_id'))
    date = request.GET.get('date')
    time = request.GET.get('time')
    store = request.GET.get('store')
    check_id = request.GET.get('check_id')
    product = request.GET.get('product')
    total = request.GET.get('total')
    currency = request.GET.get('currency')
    lang = request.GET.get('lang')

    if chat_id:
        await logs(f"[Django] Received request from chat_id = {chat_id}", type_e="info")
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
            'check_id_label': MESSAGES[lang]["web_app_bt"]["fields"]["check_id_label"],
            'check_id_error': MESSAGES[lang]["web_app_bt"]["fields"]["check_id_error"],
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
            'check_id': check_id or '',
            'product': product or '',
            'total': total or '',
            'currency': currency or '',
            'chat_id': chat_id or '',
        }
        context = {
            'fields': fields,
            'buttons': buttons,
            'values': values,
        }

    return render(request, 'web_app/check_form.html', context)

@csrf_exempt
async def api_submit(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    keys = ['date', 'time', 'store', 'check_id', 'product', 'total', 'currency', 'chat_id']
    values = [payload.get(k) for k in keys]
    date, time, store, check_id, product, total, currency, chat_id = values

    await logs("[Django] "
        f"Received expense submission - "
        f"Date: {date}, Time: {time}, Store: {store}, "
        f"Check_id: {check_id}, Product: {product}, "
        f"Total: {total} Currency: {currency}, Chat ID: {chat_id}",
        type_e="info"
    )

    conn = await get_connection()
    try:
        await process_user_input_list(user_text_input=values)
        await logs(f"[Django] Data processed successfully for chat_id {chat_id}", type_e="info")
    finally:
        await release_connection(conn)

    return JsonResponse({
        'success': True,
        'message': 'Successfully received data'
    }, status=200)