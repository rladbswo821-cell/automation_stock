"""텔레그램 연결 테스트"""
import sys
import os
sys.path.insert(0, r'C:\Users\hankook\Desktop\Automation_Stock')
os.chdir(r'C:\Users\hankook\Desktop\Automation_Stock')

from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
import requests

print(f"TOKEN: {TELEGRAM_TOKEN[:15]}...")
print(f"CHAT_ID: {TELEGRAM_CHAT_ID}")

r = requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
    data={"chat_id": TELEGRAM_CHAT_ID, "text": "✅ 텔레그램 연결 테스트"}
)
print(f"응답: {r.status_code}")
print(r.text[:300])
