import requests
from config import BOT_TOKEN, CHAT_ID


def send_alert(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"[Telegram] Đã gửi: {message[:60]}...")
    except Exception as e:
        print(f"[Telegram] Lỗi gửi tin: {e}")
