import requests
from config import TELEGRAM_TOKEN

def send_telegram_message(message, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")
