"""
report.py — HTML 리포트 조립 모듈
Google Sheets 레코드와 환율을 받아 Telegram용 HTML 문자열을 반환.
"""
import unicodedata
from datetime import datetime

from data_fetch import (
    map_ticker, get_advanced_technicals,
    get_macro_dwmy, get_macro_value_only,
)
from analysis import (
    grade_signal, calc_order, format_quant_line,
    generate_macro_interpretation,
    generate_summary_insight,
)


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


def safe_float(val) -> float:
    """콤마·퍼센트 제거 후 float 변환, 실패 시 0.0 반환"""
    try:
        s = str(val).replace(',', '').replace('%', '').strip()
        return float(s) if s else 0.0
    except:
        return 0.0


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
    Google Sheets 레코드 + 환율 → 전체 HTML 리포트 문자열 반환.
    섹션 구성: 1구분별자산 / 3매수매도종목 / 4거시경제+한줄평 / 6종합의견
    """
    current_date = datetime.now().strftime("%m/%d")
    total_val    = sum(safe_float(r.get('평가금액', 0)) for r in records)
    acc_map: dict[str, float] = {}
    quant_lines: list[str]    = []

    for r in records:
        name = str(r.get('종목명', '')).strip()
        # '구분'(A열) 우선 사용, 없으면 '계좌', 그것도 없으면 '기타'
        acc  = str(r.get('구분', r.get('계좌', '기타'))).strip()
        val  = safe_float(r.get('평가금액', 0))
        if not name or val == 0:
            continue
        acc_map[acc] = acc_map.get(acc, 0) + val
        if not any(k in name for k in ['현금', '예금', '대기자금']):
            buy         = safe_float(r.get('매입가', r.get('평균단가', 0)))
            cur         = safe_float(r.get('현재가', 0))
            current_qty = int(safe_float(r.get('수량', 0)))
            # 기술지표 → 복합 등급 + 매수/매도 주문 계산
            # score >= 2(매수권장 이상) 또는 score <= -1(매도주의 이상)만 포함
            tk   = map_ticker(name)
            tech = get_advanced_technicals(tk)
            if tech:
                sig   = grade_signal(tech)
                order = calc_order(tech, sig, usd_krw, current_qty)
                if sig["score"] >= 2 or sig["score"] <= -1:
                    quant_lines.append(format_quant_line(name, tech, sig, order))

    # 제목
    msg = f"📋 <b>[ {current_date} 자산관리 리포트 ]</b>\n\n"

    # 섹션 1: 구분별 자산 ('구분' 열 기준)
    msg += f"<b>1️⃣ 구분별 자산 [{total_val/1000000:,.1f}백만원] (점유율)</b>\n<pre>"
    for a, v in sorted(acc_map.items(), key=lambda x: x[1], reverse=True):
        msg += (
            f"🏦 {pad_str(a[:6], 10, 'left')}"
            f" {pad_str(f'{v/1000000:.1f}', 7)}백만원"
            f" ({(v/total_val)*100:.1f}%)\n"
        )
    msg += "</pre>\n"

    # 섹션 3: 매수/매도 필요 종목
    if quant_lines:
        msg += "<b>3️⃣ 매수/매도 필요 종목</b>\n" + "\n".join(quant_lines) + "\n"
    else:
        msg += "<b>3️⃣ 매수/매도 필요 종목</b>\n• 특이사항 없음\n"
    msg += (
        "\n<i>💡 [지표 가이드]</i>\n"
        "- RSI (심리/ 30↓:매수★, 70↑:매도▼)\n"
        "- MFI (자금흐름/ 30↓:매수★, 80↑:매도▼)\n"
        "- 볼린저 (이탈폭/ 하단이탈:매수★, 상단돌파:매도▼)\n"
        "- 이평선 (골든크로스:매수★, 데드크로스:매도▼)\n"
        "- 등급: ★★★강력매수 / ★★매수 / ★관심 / ▼주의(50%) / ▼▼매도(전량)\n"
        "- 🛒 매수가이드: 예산100만원 기준 / 💰 매도가이드: 보유수량 기준\n"
    )

    # 섹션 4: 거시경제 지표 + 규칙 기반 한줄평
    msg += "\n<b>4️⃣ 핵심 경제 지표 (D/W/M/Y)</b>\n"
    macro_summaries: list[str] = []
    for ticker, is_curr, emoji in _MACRO_TICKERS:
        dwmy_str = get_macro_dwmy(ticker, is_curr)
        msg += f"{emoji} {dwmy_str}\n"
        val = get_macro_value_only(ticker)
        if val is not None:
            interp = generate_macro_interpretation(ticker, val)
            msg += f"{interp}\n"
            macro_summaries.append(interp.strip())
        msg += "\n"

    # 섹션 6: 단일 Gemini 호출 종합 의견
    portfolio_summary = (
        f"총자산 {total_val/1000000:,.1f}백만원 | "
        + " / ".join(
            f"{a} {v/total_val*100:.0f}%"
            for a, v in sorted(acc_map.items(), key=lambda x: x[1], reverse=True)
        )
    )
    signal_summary = "\n".join(quant_lines) if quant_lines else "매수/매도 신호 없음"
    macro_summary  = " | ".join(macro_summaries[:5])

    insight_msg = (
        f"<b>6️⃣ 종합 분석 및 제안</b>\n"
        + generate_summary_insight(portfolio_summary, signal_summary, macro_summary)
    )
    return msg, insight_msg
