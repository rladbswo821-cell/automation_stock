# CLAUDE.md — Automation_Stock

## 프로젝트 개요

매일 **08:00·16:00** 두 차례 자동 실행되어 보유 주식 포트폴리오를 분석하고
Telegram으로 HTML 리포트를 발송하는 자산관리 자동화 봇.

## 데이터 흐름

```
Google Sheets('자산관리DB')
    → yfinance (시세·기술지표)
    → Google News RSS (종목별 뉴스)
    → Gemini 2.5 Flash (뉴스 요약 + 종합 분석)
    → Telegram Bot (HTML 리포트 발송)
```

## 모듈 구조 (Ver 17.1)

| 파일 | 역할 |
|------|------|
| `asset_master_bot.pyw` | 진입점 — `bot.run()` 호출만 |
| `bot.py` | 스케줄 루프, Telegram 전송, 평일 가드, 로깅 |
| `report.py` | HTML 리포트 조립 (`build_report`) |
| `analysis.py` | 복합 등급 판정, 주문 계산, AI 분석·뉴스 요약 |
| `data_fetch.py` | yfinance, Google Sheets, News RSS, 환율 수집 |
| `config.py` | `.env` + `config.json` 전역 상수 로드 |

## 핵심 함수

| 함수 | 모듈 | 역할 |
|------|------|------|
| `build_report(records, usd_krw)` | `report.py` | 전체 HTML 리포트 생성 |
| `grade_signal(tech)` | `analysis.py` | 복합 매수/매도 등급 판정 |
| `calc_order(tech, sig, usd_krw, holdings)` | `analysis.py` | 매수·매도 주문 수량·가격 계산 |
| `get_advanced_technicals(ticker)` | `data_fetch.py` | RSI, MACD, MFI, BB, 이동평균선 |
| `get_macro_dwmy(ticker)` | `data_fetch.py` | 거시경제 지표 (D/W/M/Y) |
| `fetch_usd_krw()` | `data_fetch.py` | 실시간 USD/KRW 환율 |

## 설정값 위치

- `.env` — `GEMINI_API_KEY`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`
- `config.json` — 실행 시간, 시트명, RSI/MFI/MA 임계값, `unit_budget`

## 개발 규칙

- `.pyw` 확장자 유지 (콘솔 없는 백그라운드 실행)
- 기능 추가 시 기존 `schedule` 루프에 통합 (새 프로세스 금지)
- API 키·민감 정보는 코드에 직접 작성 금지 → `.env` 또는 `config.json` 참조

## 외부 의존성

```
schedule, requests, gspread, yfinance, pandas
google-genai (Gemini SDK)
google-auth, google-auth-oauthlib
python-dotenv (개선 후 추가 예정)
```

인증: 공유 토큰 `C:\Users\hankook\Desktop\google_shared_token.json` 사용 (Drawing과 공유)
토큰 만료 시 → `python renew_token.py` 실행 (Drawing 포함 동시 갱신)

## 실행 방법

```bat
# 백그라운드 봇 시작
Auto_start_stock.bat

# 직접 실행 (디버깅)
python asset_master_bot.pyw

# OAuth 토큰 갱신 (만료 시)
python renew_token.py
```

## 로그

- **파일**: `asset_master_log.txt`
- **형식**: `[YYYY-MM-DD HH:MM:SS] 🔄 메시지`
- 성공: `✅ 리포트 전송 성공`
- 실패: `❌ 오류: [traceback]`

## 매수/매도 신호 임계값 (개선 후 config.json 관리)

| 지표 | 매수 | 매도 |
|------|------|------|
| RSI | ≤ 30 | ≥ 70 |
| 볼린저밴드 | 종가 ≤ 하단밴드 | 종가 ≥ 상단밴드 |
| 이동평균 | MA5 > MA20 > MA60 (정배열) | MA5 < MA20 < MA60 (역배열) |
