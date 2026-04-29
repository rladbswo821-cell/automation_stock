"""
report.py — HTML 리포트 조립 모듈
Google Sheets 레코드와 환율을 받아 Telegram용 HTML 문자열을 반환.
"""
import unicodedata
from datetime import datetime

from data_fetch import (
    map_ticker, get_advanced_technicals,
    get_macro_dwmy, fetch_news_raw,
)
from analysis import (
    grade_signal, calc_order, format_quant_line,
    generate_ai_news_summary, generate_ai_insight,
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


# ── 리포트 조립 ───────────────────────────────────────────────────────────────

def build_report(records: list[dict], usd_krw: float) -> tuple[str, str]:
    """
    Google Sheets 레코드 + 환율 → 전체 HTML 리포트 문자열 반환.
    섹션 구성: 주목종목 / 1계좌 / 2종목 / 3분석 / 4거시 / 5뉴스 / 6AI제안
    """
    current_date = datetime.now().strftime("%m/%d")
    total_val    = sum(safe_float(r.get('평가금액', 0)) for r in records)
    acc_map, stock_data, quant_lines, watch_lines, holdings_news = {}, [], [], [], []

    for r in records:
        name = str(r.get('종목명', '')).strip()
        acc  = str(r.get('계좌', '일반')).strip()
        val  = safe_float(r.get('평가금액', 0))
        if not name or val == 0:
            continue
        acc_map[acc] = acc_map.get(acc, 0) + val
        if not any(k in name for k in ['현금', '예금', '대기자금']):
            buy         = safe_float(r.get('매입가', r.get('평균단가', 0)))
            cur         = safe_float(r.get('현재가', 0))
            y_rate      = ((cur / buy) - 1) * 100 if buy > 0 else 0
            current_qty = int(safe_float(r.get('수량', 0)))
            stock_data.append({'name': name, 'val_m': val / 1000000, 'yield': y_rate})
            if any(k in acc for k in ['해외주식', '국내주식', '연금저축', 'IRP']):
                holdings_news.append(name)
            # 기술지표 → 복합 등급 + 매수/매도 주문 계산
            tk   = map_ticker(name)
            tech = get_advanced_technicals(tk)
            if tech:
                sig   = grade_signal(tech)
                order = calc_order(tech, sig, usd_krw, current_qty)
                if sig["grade"] != "중립":
                    quant_lines.append(format_quant_line(name, tech, sig, order))
                    badge_str = f" {sig['badge']}" if sig["badge"] else ""
                    watch_lines.append(
                        f"{sig['color']} <b>{name[:10]}</b>  {sig['grade']}{badge_str}"
                    )

    # 제목 + 주목 종목 요약
    msg = f"📋 <b>[ {current_date} 자산관리 리포트 ]</b>\n\n"
    if watch_lines:
        msg += "📌 <b>주목 종목</b>\n" + "\n".join(watch_lines) + "\n\n"

    # 섹션 1: 계좌별 자산
    msg += f"<b>1️⃣ 계좌별 자산 [{total_val/1000000:,.1f}백만원] (점유율)</b>\n<pre>"
    for a, v in sorted(acc_map.items(), key=lambda x: x[1], reverse=True):
        msg += (
            f"🏦 {pad_str(a[:6], 10, 'left')}"
            f" {pad_str(f'{v/1000000:.1f}', 7)}백만원"
            f" ({(v/total_val)*100:.1f}%)\n"
        )
    msg += "</pre>\n"

    # 섹션 2: 종목 수익률
    stock_val_sum = sum(s['val_m'] for s in stock_data)
    total_y = (
        sum(s['yield'] * s['val_m'] for s in stock_data) / stock_val_sum
        if stock_val_sum > 0 else 0
    )
    msg += f"<b>2️⃣ 주식 종목 현황 [{stock_val_sum:,.1f}백만원] ({total_y:+.1f}%)</b>\n<pre>"
    for s in sorted(stock_data, key=lambda x: x['yield'], reverse=True):
        val_m_str = f"{s['val_m']:.1f}"
        msg += (
            f"🏦 {pad_str(s['name'][:12], 12, 'left')}"
            f" {pad_str(val_m_str, 7)}백만원"
            f" ({s['yield']:+.1f}%)\n"
        )
    msg += "</pre>\n"

    # 섹션 3: 복합 투자 등급
    if quant_lines:
        msg += "<b>3️⃣ 종목분석</b>\n" + "\n".join(quant_lines) + "\n"
    else:
        msg += "<b>3️⃣ 종목분석</b>\n• 특이사항 없음\n"
    msg += (
        "\n<i>💡 [지표 가이드]</i>\n"
        "- RSI (심리/ 30↓:매수★, 70↑:매도▼)\n"
        "- MFI (자금흐름/ 30↓:매수★, 80↑:매도▼)\n"
        "- 볼린저 (이탈폭/ 하단이탈:매수★, 상단돌파:매도▼)\n"
        "- 이평선 (골든크로스:매수★, 데드크로스:매도▼)\n"
        "- 등급: ★★★강력매수 / ★★매수 / ★관심 / ▼주의(50%) / ▼▼매도(전량)\n"
        "- 🛒 매수가이드: 예산100만원 기준 / 💰 매도가이드: 보유수량 기준\n"
    )

    # 섹션 4: 거시경제 지표
    msg += "\n<b>4️⃣ 핵심 경제 지표 (D/W/M/Y)</b>\n"
    msg += (
        f"💵 환율: {get_macro_dwmy('KRW=X', True)}\n"
        f"📈 S&P500: {get_macro_dwmy('^GSPC')}\n"
        f"🇰🇷 KOSPI: {get_macro_dwmy('^KS11')}\n"
        f"🏛️ 미10년물: {get_macro_dwmy('^TNX')}\n"
        f"🏛️ 미30년물: {get_macro_dwmy('^TYX')}\n"
        f"😨 VIX공포: {get_macro_dwmy('^VIX')}\n"
        f"🛢️ 유가(WTI): {get_macro_dwmy('CL=F')}\n"
        f"💰 달러인덱스: {get_macro_dwmy('DX-Y.NYB')}\n"
    )

    # 섹션 5: 종목 뉴스 (RSS → Gemini 요약)
    raw_news = fetch_news_raw(list(set(holdings_news)))
    msg += "\n<b>5️⃣ 종목별 소식</b>\n" + generate_ai_news_summary(raw_news) + "\n"

    # 섹션 6: AI 종합 분석 (별도 메시지로 분리)
    insight_msg = (
        "\n<b>6️⃣ 종합 분석 및 제안</b>\n"
        + generate_ai_insight(
            str(stock_data),
            msg.split('4️⃣')[1].split('5️⃣')[0],
            str(quant_lines),
        )
    )
    return msg, insight_msg
