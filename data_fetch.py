"""
data_fetch.py — 외부 데이터 수집 모듈
yfinance 시세/기술지표, Google Sheets 자산 데이터, News RSS 수집
"""
import time
import yfinance as yf
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import gspread
from google.oauth2.credentials import Credentials
from google.auth import exceptions as auth_exc
from google.auth.transport.requests import Request
from config import SHEET_NAME, WORKSHEET, MA_SHORT, MA_MID, MA_LONG

# Drawing/Stock 두 프로젝트가 동일 클라이언트 ID를 사용하므로 토큰 공유 — 중복 발급 방지
SHARED_TOKEN = r'C:\Users\hankook\Desktop\google_shared_token.json'


class TokenExpiredError(Exception):
    """Google OAuth 토큰 만료 시 발생 — 메인 봇에서 Telegram 알림 처리"""


def _call_with_retry(fn, delays: tuple[int, ...] = (5, 15, 45)):
    """최대 len(delays)+1번 시도, 실패마다 delays[i]초 대기 후 재시도"""
    exc = None
    for i in range(len(delays) + 1):
        try:
            return fn()
        except Exception as e:
            exc = e
            if i < len(delays):
                time.sleep(delays[i])
    raise exc  # type: ignore[misc]


def map_ticker(name: str) -> str | None:
    """종목 한글명 → yfinance 티커 변환"""
    n = name.upper()
    if 'APPLE' in n or '애플' in n:    return 'AAPL'
    if 'NVIDI' in n or '엔비디아' in n: return 'NVDA'
    if '마이크로' in n:                 return 'MSFT'
    if '브로드컴' in n:                 return 'AVGO'
    if 'S&P500' in n or 'KODEX' in n or 'TIGER' in n: return 'SPY'
    if '다우존스' in n or '배당' in n:  return 'SCHD'
    if '국채' in n:                     return 'TLT'
    return None


def get_advanced_technicals(ticker: str) -> dict | None:
    """yfinance 1년 데이터로 RSI, MACD, MFI, 볼린저밴드, 추세 계산 (1회 재시도)"""
    if not ticker:
        return None
    try:
        # 네트워크 오류 시 1회 재시도 (5초 대기)
        hist = _call_with_retry(
            lambda: yf.Ticker(ticker).history(period="1y"),
            delays=(5,),
        )
        if len(hist) < 100:
            return None
        close = hist['Close']
        # RSI 계산 (EWM 방식)
        delta = close.diff()
        gain  = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss  = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rsi   = 100 - (100 / (1 + (gain / loss).iloc[-1]))
        # MACD (EMA 12 - EMA 26)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd  = ema12.iloc[-1] - ema26.iloc[-1]
        # MFI (자금흐름지수)
        high, low, vol = hist['High'], hist['Low'], hist['Volume']
        tp       = (high + low + close) / 3
        rmf      = tp * vol
        pos_flow = (rmf.where(tp.diff() > 0, 0)).rolling(14).sum()
        neg_flow = (rmf.where(tp.diff() < 0, 0)).rolling(14).sum()
        mfi      = 100 - (100 / (1 + (pos_flow / neg_flow).iloc[-1]))
        # 이동평균 추세 (50일 vs 200일)
        ma50, ma200 = close.rolling(50).mean().iloc[-1], close.rolling(200).mean().iloc[-1]
        # 볼린저밴드 (20일, ±2σ) — MA_MID 기간 재사용
        ma_mid_val, std_mid = close.rolling(MA_MID).mean().iloc[-1], close.rolling(MA_MID).std().iloc[-1]
        # 볼린저밴드 상/하단 가격 계산 (지정가 주문에 활용)
        bb_upper = round(ma_mid_val + (std_mid * 2), 4)
        bb_lower = round(ma_mid_val - (std_mid * 2), 4)
        bb = "안정"
        if   close.iloc[-1] > bb_upper: bb = "상단돌파(과열)"
        elif close.iloc[-1] < bb_lower: bb = "하단이탈(투매)"
        # 단/중/장기 이동평균 정배열·역배열 판정 (config.json: 5/20/60일)
        ma_s = close.rolling(MA_SHORT).mean().iloc[-1]
        ma_m = ma_mid_val
        ma_l = close.rolling(MA_LONG).mean().iloc[-1]
        if   ma_s > ma_m > ma_l: ma_align = "golden"   # 정배열 (골든크로스)
        elif ma_s < ma_m < ma_l: ma_align = "dead"     # 역배열 (데드크로스)
        else:                    ma_align = "neutral"
        return {
            "rsi":         round(rsi, 1),
            "macd":        round(macd, 2),
            "mfi":         round(mfi, 1),
            "trend":       "상승" if ma50 > ma200 else "하락",
            "bb":          bb,
            "bb_upper":    bb_upper,       # 볼린저 상단 가격 (USD)
            "bb_lower":    bb_lower,       # 볼린저 하단 가격 (USD)
            "close_price": round(float(close.iloc[-1]), 4),  # 현재가 (USD)
            "ma_align":    ma_align,
        }
    except:
        return None


def get_macro_dwmy(ticker: str, is_curr: bool = False) -> str:
    """거시경제 지표 수집 — 당일/주간/월간/연간 수익률 반환 (1회 재시도)"""
    try:
        hist = _call_with_retry(
            lambda: yf.Ticker(ticker).history(period="2y"),
            delays=(5,),
        )
        if hist.empty:
            return "N/A"
        c = hist['Close']

        def calc(idx: int) -> str:
            if abs(idx) > len(c):
                return "0.0%"
            pct = ((c.iloc[-1] / c.iloc[idx]) - 1) * 100
            return f"{'+' if pct > 0 else ''}{pct:.1f}%"

        guides = {
            "KRW=X":    "1400 이상: 수입물가 상승 우려",
            "^GSPC":    "미국 시장 전반 투자 심리",
            "^KS11":    "국내 증시 외국인 수급",
            "^TNX":     "4.0% 이상: 기술주 하방 압력",
            "^TYX":     "장기 국채 ETF 방향성",
            "^VIX":     "20 이상: 변동성 주의, 30 이상: 패닉",
            "CL=F":     "80$ 이상: 인플레이션 재점화",
            "DX-Y.NYB": "105 이상: 글로벌 강달러 지속",
        }
        val = f"{c.iloc[-1]:,.2f}" if is_curr else f"{c.iloc[-1]:,.1f}"
        return (
            f"{val} ({calc(-2)}/{calc(-6)}/{calc(-22)}/{calc(-253)})\n"
            f"      [{guides.get(ticker, '')}]"
        )
    except:
        return "N/A"


def get_macro_value_only(ticker: str) -> float | None:
    """거시경제 지표 현재값(숫자)만 반환. 실패 시 None."""
    try:
        hist = _call_with_retry(
            lambda: yf.Ticker(ticker).history(period="5d"),
            delays=(5,),
        )
        if hist.empty:
            return None
        return float(hist['Close'].iloc[-1])
    except Exception:
        return None


def fetch_usd_krw() -> float:
    """실시간 USD/KRW 환율 반환 (yfinance KRW=X, 실패 시 1350.0 fallback)"""
    try:
        hist = yf.Ticker("KRW=X").history(period="5d")
        return float(hist['Close'].iloc[-1])
    except:
        return 1350.0  # 네트워크 오류 시 근사값 사용


def fetch_sheet_records() -> list[dict]:
    """
    Google Sheets '자산관리DB'에서 전체 레코드 반환 (exponential backoff 3회 재시도).
    액세스 토큰 만료 시 refresh_token으로 자동 갱신 후 token.json 재저장.
    refresh_token마저 무효일 경우 TokenExpiredError 발생 → Telegram 알림.
    """
    try:
        def _fetch():
            creds = Credentials.from_authorized_user_file(SHARED_TOKEN)
            # 액세스 토큰 만료 + 갱신 토큰 존재 → 자동 재발급
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(SHARED_TOKEN, 'w', encoding='utf-8') as f:
                    f.write(creds.to_json())
            gc    = gspread.authorize(creds)
            sheet = gc.open(SHEET_NAME).worksheet(WORKSHEET)
            return sheet.get_all_records()

        return _call_with_retry(_fetch, delays=(5, 15, 45))
    except auth_exc.RefreshError as e:
        # refresh_token까지 만료 → 수동 재인증 필요
        raise TokenExpiredError("Google OAuth 토큰 완전 만료 (renew_token.py 실행 필요)") from e


def fetch_news_raw(holdings_news: list[str]) -> str:
    """보유 종목 목록으로 Google News RSS 크롤링 → 원문 텍스트 반환"""
    raw = ""
    for name in holdings_news[:6]:
        try:
            url  = (
                f"https://news.google.com/rss/search?"
                f"q={urllib.parse.quote(name.split()[0])}&hl=ko&gl=KR&ceid=KR:ko"
            )
            req  = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            root = ET.fromstring(urllib.request.urlopen(req).read())
            for item in root.findall('./channel/item')[:3]:
                raw += f"[{name}] {item.find('title').text} / {item.find('description').text}\n"
        except:
            pass
    return raw
