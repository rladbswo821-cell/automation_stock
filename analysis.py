"""
analysis.py — 복합 투자 등급 판정 + AI 종합 분석 모듈
data_fetch.get_advanced_technicals() 결과를 입력으로 매수/매도 등급 계산.
"""
import math
from google import genai
from config import GEMINI_API_KEY, RSI_BUY, RSI_SELL, MFI_BUY, MFI_SELL, UNIT_BUDGET


def grade_signal(tech: dict) -> dict:
    """
    기술지표 딕셔너리로 복합 매수/매도 등급 계산.

    매수 신호 (각 1점):
      - RSI ≤ RSI_BUY (과매도)
      - MFI ≤ MFI_BUY (자금 유출 과다)
      - 볼린저밴드 하단 이탈 (투매 구간)
      - 이동평균 정배열 / 골든크로스

    매도 신호 (각 -1점):
      - RSI ≥ RSI_SELL (과매수)
      - MFI ≥ MFI_SELL (자금 과열)
      - 볼린저밴드 상단 돌파 (과열 구간)
      - 이동평균 역배열 / 데드크로스

    반환:
      score        : 정수 (양수=매수 우세, 음수=매도 우세)
      buy_reasons  : 충족된 매수 조건 목록
      sell_reasons : 충족된 매도 조건 목록
      grade        : 등급 레이블 문자열
      badge        : ★★★ / ★★ / ★ / "" / ▼ / ▼▼
      color        : 🟢 / 🟡 / ⚪ / 🔴
    """
    buy_reasons:  list[str] = []
    sell_reasons: list[str] = []

    # 매수 신호 조건 체크
    if tech["rsi"] <= RSI_BUY:
        buy_reasons.append(f"RSI {tech['rsi']}")
    if tech["mfi"] <= MFI_BUY:
        buy_reasons.append(f"MFI {tech['mfi']}")
    if tech["bb"] == "하단이탈(투매)":
        buy_reasons.append("BB하단이탈")
    if tech.get("ma_align") == "golden":
        buy_reasons.append("골든크로스")

    # 매도 신호 조건 체크
    if tech["rsi"] >= RSI_SELL:
        sell_reasons.append(f"RSI {tech['rsi']}")
    if tech["mfi"] >= MFI_SELL:
        sell_reasons.append(f"MFI {tech['mfi']}")
    if tech["bb"] == "상단돌파(과열)":
        sell_reasons.append("BB상단돌파")
    if tech.get("ma_align") == "dead":
        sell_reasons.append("데드크로스")

    score = len(buy_reasons) - len(sell_reasons)

    # 점수 → 등급 결정 (Python 3.10 match-case)
    match score:
        case s if s >= 3:
            grade, badge, color = "강력 매수 권장", "★★★", "🟢"
        case 2:
            grade, badge, color = "매수 권장", "★★", "🟢"
        case 1:
            grade, badge, color = "매수 관심", "★", "🟡"
        case 0 if not buy_reasons and not sell_reasons:
            grade, badge, color = "중립", "", "⚪"
        case 0:
            # 매수·매도 신호가 동시에 존재해 상쇄된 경우
            grade, badge, color = "혼재", "~", "🟡"
        case -1:
            grade, badge, color = "매도 주의", "▼", "🔴"
        case _:
            grade, badge, color = "매도 권장", "▼▼", "🔴"

    return {
        "score":        score,
        "buy_reasons":  buy_reasons,
        "sell_reasons": sell_reasons,
        "grade":        grade,
        "badge":        badge,
        "color":        color,
    }


def calc_order(
    tech: dict,
    sig: dict,
    usd_krw: float,
    current_holdings: int = 0,
) -> dict:
    """
    매수·매도 주문 수량·가격 계산.

    [매수] score > 0
      목표가: BB 하단 이탈 → bb_lower 지정가 / 그 외 → close_price 시장가
      수량  : floor(UNIT_BUDGET(KRW) / usd_krw / target_price)

    [매도] score < 0
      목표가: max(bb_upper, close_price × 1.02) 지정가
      수량  : 매도 권장(▼▼) → 보유 전량 / 매도 주의(▼) → ceil(보유 × 50%)

    반환 키:
      is_buy        : 매수 신호 여부
      target_price  : 매수 목표가 (USD)
      qty           : 매수 수량 (주)
      order_type    : "지정가" | "시장가"
      cost_krw      : 예상 매수 비용 (KRW)
      is_sell       : 매도 신호 여부
      sell_target   : 매도 목표가 (USD)
      sell_qty      : 매도 수량 (주)
      revenue_krw   : 예상 매도 대금 (KRW)
    """
    is_buy  = sig["score"] > 0
    is_sell = sig["score"] < 0
    close   = tech.get("close_price", 0.0)

    # ── 매수 계산 ──────────────────────────────────────────
    if is_buy and tech.get("bb") == "하단이탈(투매)":
        target_price = tech.get("bb_lower", close)
        order_type   = "지정가"
    else:
        target_price = close
        order_type   = "시장가"

    qty      = math.floor(UNIT_BUDGET / usd_krw / target_price) if target_price > 0 else 0
    cost_krw = round(qty * target_price * usd_krw)

    # ── 매도 계산 ──────────────────────────────────────────
    # 목표가: BB 상단가와 현재가+2% 중 높은 쪽을 지정가로 설정
    bb_upper     = tech.get("bb_upper", close)
    sell_target  = round(max(bb_upper, close * 1.02), 2)

    match sig["grade"]:
        case "매도 권장":    sell_qty = current_holdings                          # 전량
        case "매도 주의":    sell_qty = math.ceil(current_holdings * 0.5)         # 50%
        case _:              sell_qty = 0

    revenue_krw = round(sell_qty * sell_target * usd_krw)

    return {
        "is_buy":       is_buy,
        "target_price": round(target_price, 2),
        "qty":          qty,
        "order_type":   order_type,
        "cost_krw":     cost_krw,
        "is_sell":      is_sell,
        "sell_target":  sell_target,
        "sell_qty":     sell_qty,
        "revenue_krw":  revenue_krw,
    }


def format_quant_line(
    name: str,
    tech: dict,
    sig: dict,
    order: dict | None = None,
) -> str:
    """종목분석 섹션 상세 라인 포맷 — 등급 배지 + 지표 수치 + 근거 + 주문 정보"""
    reasons    = sig["buy_reasons"] or sig["sell_reasons"]
    reason_str = " | ".join(reasons) if reasons else "신호 없음"
    badge_str  = f" {sig['badge']}" if sig["badge"] else ""
    align_map  = {"golden": "정배열", "dead": "역배열", "neutral": "중립"}
    ma_label   = align_map.get(tech.get("ma_align", "neutral"), "")

    base = (
        f"📊 <b>{name[:12]}</b>  {sig['color']} {sig['grade']}{badge_str}\n"
        f"   RSI:{tech['rsi']} | MFI:{tech['mfi']} | MACD:{tech['macd']:.2f}"
        f" | {tech['bb']} | {ma_label}\n"
        f"   근거: {reason_str}"
    )

    # 매수 주문 라인
    if order and order["is_buy"] and order["qty"] > 0:
        base += (
            f"\n   🛒 매수 {order['order_type']} ${order['target_price']:,.2f}"
            f" × {order['qty']}주"
            f" ≈ {order['cost_krw']:,}원"
        )

    # 매도 주문 라인
    if order and order["is_sell"] and order["sell_qty"] > 0:
        base += (
            f"\n   💰 예약매도 지정가 ${order['sell_target']:,.2f}"
            f" × {order['sell_qty']}주"
            f" ≈ {order['revenue_krw']:,}원"
        )

    return base


# 우선순위 순 폴백 목록 — 2.5-flash 과부하 시 lite → 2.0-flash-lite 순으로 시도
_GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]


def _call_gemini(prompt: str) -> str | None:
    """
    Gemini API 호출 — 503 과부하 시 다음 모델로 자동 폴백.
    모든 모델 실패 시 None 반환.
    """
    client = genai.Client(api_key=GEMINI_API_KEY)
    for model in _GEMINI_MODELS:
        try:
            res = client.models.generate_content(model=model, contents=prompt)
            return res.text.strip()
        except Exception as e:
            print(f"  [Gemini] {model} 실패 → 다음 모델 시도: {e}")
    return None


def generate_ai_news_summary(raw_data: str) -> str:
    """Gemini로 뉴스 원문 요약 (인사말·서론 차단) — 모델 폴백 포함"""
    prompt = (
        "당신은 금융 에디터입니다. 아래 뉴스들에서 중복을 제거하고 종목별 핵심 사실을 요약하세요. "
        "수치(금액, %, 목표가 등)는 필수 포함하세요. 텔레그램 HTML(<b>)을 사용하세요.\n"
        "[경고] '안녕하세요', '에디터입니다' 같은 인사말이나 서론, 구분선(---)을 절대 쓰지 마세요. "
        "오직 본론(요약 내용)만 즉시 출력하세요.\n\n"
        f"{raw_data}"
    )
    return _call_gemini(prompt) or "• 뉴스 분석 실패"


def generate_ai_insight(portfolio_str: str, macro_str: str, quant_str: str) -> str:
    """
    멀티 에이전트 토론 방식 종합 분석.

    [흐름]
    1. 공격적 퀀트  — 수익률 극대화 관점 의견 (2문장)
    2. 보수적 배분가 — 리스크 관리 반론 (2문장)
    3. 중재자        — 토론 종합 → 실전 액션 플랜 3문장

    반환: Telegram HTML 포맷 3개 블록
    """
    # 공통 데이터 컨텍스트 (세 에이전트 모두 사용)
    context = (
        f"[포트폴리오 현황]\n{portfolio_str}\n\n"
        f"[거시경제 지표]\n{macro_str}\n\n"
        f"[기술분석 신호]\n{quant_str}"
    )

    # ── Agent 1: 공격적 퀀트 ──────────────────────────────────
    aggressive = _call_gemini(
        "당신은 공격적 퀀트 트레이더입니다. 수익률 극대화가 목표입니다.\n"
        "아래 포트폴리오 데이터를 보고, 공격적 매수·비중 확대 관점의 핵심 의견을 "
        "2문장 이내로 제시하세요. 종목명·수익률(%)·평가금액을 직접 인용하세요.\n"
        "[경고] 인사말·서론 없이 본론만 즉시 출력하세요.\n\n"
        f"{context}"
    ) or "데이터 부족으로 의견 생략"

    # ── Agent 2: 보수적 배분가 ────────────────────────────────
    conservative = _call_gemini(
        "당신은 보수적 자산 배분가입니다. 리스크 관리와 자본 보존이 목표입니다.\n"
        "아래 공격적 퀀트의 의견에 반론을 제기하고, "
        "리스크 헤지·비중 축소 관점의 대안을 2문장 이내로 제시하세요. "
        "거시지표 또는 기술신호 수치를 직접 인용하세요.\n"
        "[경고] 인사말·서론 없이 본론만 즉시 출력하세요.\n\n"
        f"[공격적 퀀트 의견]\n{aggressive}\n\n"
        f"{context}"
    ) or "데이터 부족으로 의견 생략"

    # ── Agent 3: 중재자 → 실전 액션 플랜 ────────────────────
    action_plan = _call_gemini(
        "당신은 투자 중재자입니다. 두 전문가의 토론을 종합해 "
        "'수익률을 높이기 위한 실전 액션 플랜'을 정확히 3문장으로 정리하세요.\n"
        "각 문장은 구체적 행동(매수/매도/비중 조정/관망 등)을 포함하고, "
        "종목명과 수치를 직접 인용하세요.\n"
        "[경고] 인사말·서론 없이 본론만 즉시 출력하세요.\n\n"
        f"[공격적 퀀트]\n{aggressive}\n\n"
        f"[보수적 배분가]\n{conservative}\n\n"
        f"{context}"
    ) or "액션 플랜 생성 실패"

    # ── Telegram HTML 포맷 조립 ───────────────────────────────
    return (
        f"⚔️ <b>공격적 퀀트</b>\n{aggressive}\n\n"
        f"🛡️ <b>보수적 배분가</b>\n{conservative}\n\n"
        f"⚖️ <b>실전 액션 플랜</b>\n{action_plan}"
    )


# ── 거시경제 한줄평 ──────────────────────────────────────────────────────────

# 임계값 체크: 크거나 같은 첫 번째 threshold 의 comment 적용
_MACRO_RULES: dict[str, list[tuple[float, str]]] = {
    "KRW=X":     [(1400, "수입물가 상승 우려"), (1350, "평년 수준 유지"), (0, "수입물가 호조")],
    "^GSPC":     [(5500, "시장 과열 우려"),     (5000, "평년 수준"),     (0, "회피 심리 진행")],
    "^KS11":     [(2800, "외국인 수급 양호"),   (2600, "평년 수준"),     (0, "외국인 심한 매도")],
    "^TNX":      [(4.5,  "기술주 하방 압력 강화"), (4.0, "금리 부담 구간"), (0, "금리 안정")],
    "^TYX":      [(4.5,  "장기금리 상승"),      (4.0, "평년 수준"),      (0, "경기 약세 신호")],
    "^VIX":      [(30,   "시장 공포 심화"),     (20,  "변동성 증가 주의"), (0, "시장 안정")],
    "CL=F":      [(100,  "인플레이션 재점화"),  (80,  "평년 수준"),       (0, "경기 둔화 신호")],
    "DX-Y.NYB":  [(105,  "글로벌 강달러 지속"), (100, "평년 수준"),       (0, "달러 약세 진행")],
}

_MACRO_LABELS: dict[str, str] = {
    "KRW=X": "환율", "^GSPC": "S&P500", "^KS11": "KOSPI",
    "^TNX": "미10년물", "^TYX": "미30년물", "^VIX": "VIX",
    "CL=F": "유가", "DX-Y.NYB": "달러인덱스",
}


def generate_macro_interpretation(ticker: str, current_value: float) -> str:
    """규칙 기반 거시경제 지표 한줄평 반환"""
    label = _MACRO_LABELS.get(ticker, ticker)
    for threshold, comment in _MACRO_RULES.get(ticker, []):
        if current_value >= threshold:
            return f"  └ {label} {current_value:.1f} → {comment}"
    return f"  └ {label} {current_value:.1f} → 분석 불가"


def generate_summary_insight(
    portfolio_summary: str, signal_summary: str, macro_summary: str
) -> str:
    """섹션1·3·4 요약을 받아 단일 Gemini 호출로 3~5문장 종합 의견 생성"""
    prompt = (
        "당신은 금융 자산관리 전문가입니다. 아래 포트폴리오·기술신호·거시지표를 종합하여 "
        "3~5문장의 실전 조언을 제시하세요. 구체적 종목명과 수치를 인용하되 과장 없이 객관적으로.\n"
        "[경고] 인사말·서론·구분선 없이 본론만 즉시 출력하세요.\n\n"
        f"[포트폴리오]\n{portfolio_summary}\n\n"
        f"[기술신호]\n{signal_summary}\n\n"
        f"[거시경제]\n{macro_summary}"
    )
    return _call_gemini(prompt) or "• 분석 생성 실패"
