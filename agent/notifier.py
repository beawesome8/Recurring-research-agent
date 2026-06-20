# agent/notifier.py
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    response = httpx.post(url, data=payload)
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    result = send_telegram_message("Test message from your research agent.")
    print(result)