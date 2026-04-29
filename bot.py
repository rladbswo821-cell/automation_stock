"""
bot.py — 스케줄 루프 + Telegram 전송 모듈
평일(월~금)에만 실행되는 weekday 가드 포함.
"""
import time
import traceback
import schedule
import requests
from datetime import datetime

from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, CFG
from data_fetch import fetch_sheet_records, fetch_usd_krw, TokenExpiredError
from report import build_report


def log_msg(msg: str) -> None:
    """타임스탬프와 함께 콘솔 및 로그 파일에 기록"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")
    with open("asset_master_log.txt", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")


def send_telegram_msg(text: str) -> None:
    """HTML 포맷 텍스트를 Telegram으로 전송 (4000자 초과 시 절삭, HTML 에러 시 재전송)"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        if len(text) > 4000:
            text = text[:4000] + "\n\n⚠️ (내용이 길어 절삭되었습니다.)"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        res = requests.post(url, data=params)
        if res.status_code == 400:
            log_msg("⚠️ HTML 에러 재전송 시도..")
            params["parse_mode"] = ""
            params["text"] = (
                text.replace('<b>', '').replace('</b>', '')
                    .replace('<pre>', '').replace('</pre>', '')
            )
            res = requests.post(url, data=params)
        if res.status_code == 200:
            log_msg("✅ 리포트 전송 성공")
        else:
            log_msg(f"❌ 전송 실패: {res.text}")
    except Exception as e:
        log_msg(f"❌ 네트워크 오류: {e}")


def process_asset_db() -> None:
    """환율·시트 데이터 수집 → 리포트 생성 → Telegram 발송"""
    current_date = datetime.now().strftime("%m/%d")
    log_msg(f"🔄 [{current_date}] 리포트 분석 가동")
    try:
        usd_krw = fetch_usd_krw()
        records = fetch_sheet_records()
        main_msg, insight_msg = build_report(records, usd_krw)
        send_telegram_msg(main_msg)
        send_telegram_msg(insight_msg)

    except TokenExpiredError:
        alert = "🔑 <b>Google OAuth 토큰 만료</b>\nrenew_token.py 를 실행하여 재인증해주세요."
        log_msg("❌ Google 토큰 만료 — Telegram 알림 발송")
        send_telegram_msg(alert)

    except Exception:
        tb = traceback.format_exc()
        log_msg(f"❌ 오류: {tb}")
        send_telegram_msg(
            f"⚠️ <b>[{datetime.now().strftime('%m/%d %H:%M')}] 리포트 생성 실패</b>\n"
            f"<pre>{tb[-800:]}</pre>"
        )


def _weekday_job() -> None:
    """주말(토=5, 일=6) 제외, 평일에만 process_asset_db 실행"""
    if datetime.now().weekday() < 5:
        process_asset_db()


def run() -> None:
    """스케줄 등록 + 메인 루프 진입"""
    # config.json의 schedule_times로 평일 전용 스케줄 등록
    for t in CFG["schedule_times"]:
        schedule.every().day.at(t).do(_weekday_job)

    times_str = ", ".join(CFG["schedule_times"])
    send_telegram_msg(
        f"🚀 <b>마스터 봇(Ver 17.1) 가동 시작</b>\n"
        f"- 시간: {times_str} (평일 한정)"
    )
    # process_asset_db()  # 테스트용 즉시 실행

    while True:
        try:
            schedule.run_pending()
        except Exception:
            log_msg(f"❌ 스케줄러 오류: {traceback.format_exc()}")
        time.sleep(1)
