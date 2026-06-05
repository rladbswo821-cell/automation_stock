"""
report.py — HTML 리포트 조립 모듈
Google Sheets 레코드와 환율을 받아 Telegram용 HTML 문자열을 반환.
섹션 구성: 4️⃣ 핵심 경제 지표 (지표값 + 뉴스 헤드라인)
"""
import unicodedata
from datetime import datetime

from data_fetch import get_macro_dwmy, get_macro_value_only, fetch_macro_news
from analysis import generate_macro_interpretation


# ── 포맷 유틸 ────────────────────────────────────────────────────────────────

def get_display_width(s) -> int:
    """한글/전각 문자는 폭 2, 그 외는 폭 1로 계산"""
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in str(s))


def pad_str(s, width: int, align: str = 'right') -> str:
    """한글 혼용 문자열을 고정폭으로 패딩"""
    s = str(s)
    padding = width - get_display_width(s)
    if padding <= 0:
        return s
    return (' ' * padding + s) if align == 'right' else (s + ' ' * padding)


# ── 거시경제 지표 목록 ────────────────────────────────────────────────────────

# (ticker, is_curr, emoji) 순서
_MACRO_TICKERS: list[tuple[str, bool, str]] = [
    ("KRW=X",    True,  "💵"),
    ("^GSPC",    False, "📈"),
    ("^KS11",    False, "🇰🇷"),
    ("^TNX",     False, "🏛️"),
    ("^TYX",     False, "🏛️"),
    ("^VIX",     False, "😨"),
    ("CL=F",     False, "🛢️"),
    ("DX-Y.NYB", False, "💰"),
]


# ── 리포트 조립 ───────────────────────────────────────────────────────────────

def build_report(records: list[dict], usd_krw: float) -> tuple[str, str]:
    """
    핵심 경제 지표 섹션만 포함한 HTML 리포트 반환.
    각 지표 아래 Google News RSS 헤드라인 2개 포함.
    """
    current_date = datetime.now().strftime("%m/%d")

    # 제목
    msg = f"📋 <b>[ {current_date} 자산관리 리포트 ]</b>\n\n"

    # 섹션 4: 핵심 경제 지표 + 규칙 기반 한줄평 + 뉴스 헤드라인
    msg += "<b>4️⃣ 핵심 경제 지표 (D/W/M/Y)</b>\n"
    for ticker, is_curr, emoji in _MACRO_TICKERS:
        # 지표값 + 등락률
        dwmy_str = get_macro_dwmy(ticker, is_curr)
        msg += f"{emoji} {dwmy_str}\n"

        # 규칙 기반 한줄평
        val = get_macro_value_only(ticker)
        if val is not None:
            interp = generate_macro_interpretation(ticker, val)
            msg += f"{interp}\n"

        # Google News RSS 헤드라인 최대 2개
        headlines = fetch_macro_news(ticker)
        for h in headlines:
            msg += f"      📰 {h}\n"

        msg += "\n"

    # insight_msg는 빈 문자열 반환 (종합 분석 섹션 제거)
    return msg, ""
