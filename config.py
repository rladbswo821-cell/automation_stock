"""
config.py — 환경변수(.env)와 운영 설정(config.json) 전역 로드
모든 모듈은 이 파일에서 상수를 import해서 사용한다.
"""
import os
import json
from dotenv import load_dotenv

# .env 파일에서 API 키 로드
load_dotenv()
GEMINI_API_KEY   = os.environ["GEMINI_API_KEY"]
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# 운영 설정 로드
with open("config.json", encoding="utf-8") as _f:
    CFG = json.load(_f)

SHEET_NAME  = CFG["sheet_name"]    # 구글 시트 이름
WORKSHEET   = CFG["worksheet"]    # 워크시트 탭 이름
UNIT_BUDGET = CFG["unit_budget"]  # 1회 매수 표준 예산 (KRW)
RSI_BUY  = CFG["signal"]["rsi_buy"]   # RSI 매수 임계값 (기본 30)
RSI_SELL = CFG["signal"]["rsi_sell"]  # RSI 매도 임계값 (기본 70)
MFI_BUY  = CFG["signal"]["mfi_buy"]   # MFI 매수 임계값 (기본 30)
MFI_SELL = CFG["signal"]["mfi_sell"]  # MFI 매도 임계값 (기본 80)
MA_SHORT = CFG["signal"]["ma_short"]  # 단기 이동평균 기간 (기본 5)
MA_MID   = CFG["signal"]["ma_mid"]    # 중기 이동평균 기간 (기본 20)
MA_LONG  = CFG["signal"]["ma_long"]   # 장기 이동평균 기간 (기본 60)
