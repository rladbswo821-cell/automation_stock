# todo.md — Automation_Stock 개선 로드맵

> 현재 버전: Ver 16.6 (`asset_master_bot.pyw`, 단일 파일 198줄)
> 코딩 시작 전 이 파일을 컨펌받은 후 진행.

---

## 1. 코드 구조 개선

### 1-1. 의존성 명세
- [ ] `requirements.txt` 작성
  ```
  schedule, requests, gspread, yfinance, pandas
  google-genai, google-auth, google-auth-oauthlib
  python-dotenv
  ```

### 1-2. 설정 외부화
- [ ] `.env` 파일 생성 — 민감 정보 분리
  ```env
  GEMINI_API_KEY=...
  TELEGRAM_TOKEN=...
  TELEGRAM_CHAT_ID=...
  ```
- [ ] `config.json` 생성 — 운영 설정 분리
  ```json
  {
    "schedule_times": ["08:00", "16:00"],
    "sheet_name": "자산관리DB",
    "signal": {
      "rsi_buy": 30,
      "rsi_sell": 70,
      "ma_short": 5,
      "ma_mid": 20,
      "ma_long": 60
    }
  }
  ```

### 1-3. 모듈 분리 (단일 파일 → 5개)

| 파일 | 담당 역할 |
|------|----------|
| `config.py` | `.env`·`config.json` 로드, 전역 상수 제공 |
| `data_fetch.py` | yfinance 시세, Google News RSS, 거시지표 수집 |
| `analysis.py` | 기술지표 계산 + 매수/매도 신호 판정 |
| `report.py` | HTML 리포트 문자열 생성 |
| `bot.py` | `schedule` 루프 + Telegram 전송 (진입점 `.pyw`) |

---

## 2. 에러 복구 강화

- [ ] **Google Sheets API 재시도**
  - 503 에러 발생 시 3회 재시도: 대기 5s → 15s → 45s (exponential backoff)
- [ ] **yfinance 타임아웃 처리**
  - `download()` 호출 시 timeout=10s 설정, 실패 시 1회 재시도
- [ ] **Telegram 에러 알림**
  - 현재: 로그 파일에만 기록
  - 개선: 실패 시 Telegram으로 에러 요약 메시지 전송
    - 형식: `⚠️ [MM/DD HH:MM] 리포트 생성 실패\n사유: {error}`
- [ ] **OAuth 토큰 만료 감지**
  - `google.auth.exceptions.TransportError` 캐치
  - 만료 시 Telegram 알림: `🔑 Google 토큰 만료. renew_token.py 실행 필요`
- [ ] **프로세스 안정성**
  - 최상위 `try-except`로 예외 감싸기 → 프로세스 종료 방지
  - 예외 발생 후 다음 스케줄에서 자동 재시도

---

## 3. 분석 기능 확장 — 매수/매도 신호

### 3-1. 지표별 신호 조건

| 지표 | 매수 신호 | 매도 신호 |
|------|----------|----------|
| **RSI** | ≤ 30 (과매도) | ≥ 70 (과매수) |
| **볼린저밴드** | 종가 ≤ 하단밴드 | 종가 ≥ 상단밴드 |
| **이동평균 정배열** | MA5 > MA20 > MA60 | — |
| **이동평균 역배열** | — | MA5 < MA20 < MA60 |

> 기존 임계값(RSI ≤35/≥65) → 신규 임계값(RSI ≤30/≥70)으로 변경

### 3-2. 복합 신호 등급 (`analysis.py` 구현)

```
매수 신호 3개 모두 충족  →  🟢 강력 매수 권장 ★★★
매수 신호 2개 충족       →  🟢 매수 권장     ★★
매수 신호 1개 충족       →  🟡 매수 관심     ★
신호 없음                →  ⚪ 중립
매도 신호 1개 충족       →  🔴 매도 주의     ▼
매도 신호 2개 이상 충족  →  🔴 매도 권장     ▼▼
```

매수 신호 3개:
1. RSI ≤ 30
2. 종가 ≤ 볼린저밴드 하단
3. MA5 > MA20 > MA60 (정배열)

매도 신호 2개:
1. RSI ≥ 70
2. 종가 ≥ 볼린저밴드 상단 OR MA5 < MA20 < MA60 (역배열)

### 3-3. 리포트 표시 (`report.py` 구현)

**종목별 섹션에 배지 추가:**
```
🟢 강력 매수 권장 ★★★  (RSI 27 | BB 하단 이탈 | 정배열)
🔴 매도 주의 ▼          (RSI 72)
⚪ 중립
```

**리포트 최상단 "주목 종목" 요약 섹션 추가:**
```
📌 주목 종목
━━━━━━━━━━━━━━
🟢 AAPL  강력 매수 권장 ★★★
🔴 NVDA  매도 주의 ▼
```
- 신호 없는 종목(중립)은 이 섹션에서 제외

---

## 진행 상태

| 영역 | 상태 |
|------|------|
| 1. 코드 구조 개선 | ✅ 완료 (Ver 16.7) |
| 2. 에러 복구 강화 | ✅ 완료 (Ver 16.7) |
| 3. 분석 기능 확장 | ✅ 완료 (Ver 16.8) |
| 4. 매도 주문 설계 | ✅ 완료 (Ver 17.0) |
| 5. 모듈 분리 완성 + 평일 스케줄 | ✅ 완료 (Ver 17.1) |
| 6. 안정성/운영 (토큰 자동갱신 + 스케줄러) | ✅ 완료 (Ver 17.1) |
