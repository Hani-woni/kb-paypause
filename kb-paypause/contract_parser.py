"""[B 소유] contract_parser.py

OCR로 추출한 계약서 원문을 공통 contract_data 구조로 변환한다.

작성 원칙
---------
1. 계약서 원문에서 직접 확인되는 값만 추출한다.
2. 확인되지 않는 값은 0이나 False로 추정하지 않고 None으로 둔다.
3. 금액은 원 단위 정수, 비율은 퍼센트 숫자로 저장한다.
   예: 1,200,000원 -> 1200000
       위약금 10% -> 10.0
4. 계약 유형은 contract_type.detect()를 통해 판정한다.
"""

from __future__ import annotations

import re
from typing import Optional

from contract_type import detect


# ---------------------------------------------------------------------
# 공통 문자열 처리
# ---------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """OCR 원문의 공백과 줄바꿈을 정리한다."""
    if not isinstance(text, str):
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _compact_text(text: str) -> str:
    """탐지용으로 모든 공백을 한 칸으로 정리한다."""
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------
# 숫자 변환
# ---------------------------------------------------------------------

def _to_int(value: str | None) -> Optional[int]:
    """쉼표가 포함된 숫자 문자열을 정수로 변환한다."""
    if value is None:
        return None

    digits = re.sub(r"[^\d]", "", value)

    if not digits:
        return None

    try:
        return int(digits)
    except ValueError:
        return None


def _to_float(value: str | None) -> Optional[float]:
    """숫자 문자열을 실수로 변환한다."""
    if value is None:
        return None

    cleaned = value.replace(",", "").strip()

    try:
        return float(cleaned)
    except ValueError:
        return None


# ---------------------------------------------------------------------
# 정규식 추출 도우미
# ---------------------------------------------------------------------

def _extract_first_group(
    text: str,
    patterns: list[str],
    flags: int = re.IGNORECASE,
) -> Optional[str]:
    """여러 정규식 중 처음 발견된 첫 번째 그룹을 반환한다."""
    for pattern in patterns:
        match = re.search(pattern, text, flags)

        if match:
            value = match.group(1).strip()

            if value:
                return value

    return None


def _extract_money(text: str, labels: list[str]) -> Optional[int]:
    """지정된 항목명 뒤의 금액을 추출한다."""
    label_pattern = "|".join(re.escape(label) for label in labels)

    patterns = [
        rf"(?:{label_pattern})\s*[:：]?\s*([\d,]+)\s*원",
        rf"(?:{label_pattern})\s*[:：]?\s*금?\s*([\d,]+)",
    ]

    value = _extract_first_group(text, patterns)
    return _to_int(value)


# ---------------------------------------------------------------------
# 기본 계약 정보
# ---------------------------------------------------------------------

def _extract_business_name(text: str) -> Optional[str]:
    """업체명 또는 사업자명을 추출한다."""
    patterns = [
        r"(?:업체명|상호명|상호|사업자명|체육시설명|센터명)\s*[:：]\s*([^\n]+)",
    ]

    return _extract_first_group(text, patterns)


def _extract_business_address(text: str) -> Optional[str]:
    """업체 주소를 추출한다."""
    patterns = [
        r"(?:사업장\s*주소|업체\s*주소|소재지|주소)\s*[:：]\s*([^\n]+)",
    ]

    return _extract_first_group(text, patterns)


def _extract_contract_months(text: str) -> Optional[int]:
    """계약기간을 개월 단위로 추출한다."""
    patterns = [
        r"(?:계약\s*기간|이용\s*기간|회원권\s*기간)\s*[:：]?\s*(\d+)\s*개?월",
        r"(\d+)\s*개?월\s*(?:이용권|회원권|계약)",
    ]

    value = _extract_first_group(text, patterns)
    return _to_int(value)


def _extract_total_sessions(text: str) -> Optional[int]:
    """PT 등의 총 계약 횟수를 추출한다."""
    patterns = [
        r"(?:총\s*횟수|계약\s*횟수|수강\s*횟수|PT\s*횟수|피티\s*횟수)\s*[:：]?\s*(\d+)\s*회",
        r"(?:PT|피티)\s*(\d+)\s*회",
        r"(\d+)\s*회\s*(?:PT|피티|수강권|이용권)",
    ]

    value = _extract_first_group(text, patterns)
    return _to_int(value)


def _extract_penalty_rate(text: str) -> Optional[float]:
    """위약금·해약금·중도해지 수수료의 퍼센트를 추출한다."""
    patterns = [
        r"(?:위약금|해약금|중도\s*해지\s*수수료|해지\s*수수료)"
        r"\s*[:：]?\s*(?:총\s*계약\s*대금의\s*)?(\d+(?:\.\d+)?)\s*%",
        r"(?:총\s*계약\s*대금|총\s*이용\s*금액)의\s*"
        r"(\d+(?:\.\d+)?)\s*%\s*(?:를\s*)?(?:위약금|해약금)",
    ]

    value = _extract_first_group(text, patterns)
    return _to_float(value)


def _extract_installment_months(text: str) -> Optional[int]:
    """카드 할부 개월 수를 추출한다."""
    patterns = [
        r"(?:카드\s*)?(\d+)\s*개?월\s*할부",
        r"할부\s*기간\s*[:：]?\s*(\d+)\s*개?월",
    ]

    value = _extract_first_group(text, patterns)
    return _to_int(value)


# ---------------------------------------------------------------------
# 조항·조건 탐지
# ---------------------------------------------------------------------

def _detect_refund_base(text: str) -> str:
    """환급 시 이용료 공제 기준을 판정한다."""
    normal_price_patterns = [
        r"정상가(?:격)?\s*(?:기준|으로)",
        r"정가\s*(?:기준|로)",
        r"할인\s*전\s*가격\s*(?:기준|으로)",
        r"(?:월|1회)\s*정상가",
    ]

    paid_price_patterns = [
        r"(?:실제\s*)?(?:결제|지급|납부|계약)\s*(?:금액|대금)\s*(?:기준|으로)",
        r"총\s*계약\s*대금\s*(?:기준|으로)",
    ]

    if any(re.search(pattern, text, re.IGNORECASE) for pattern in normal_price_patterns):
        return "normal_price"

    if any(re.search(pattern, text, re.IGNORECASE) for pattern in paid_price_patterns):
        return "paid_price"

    return "unknown"


def _detect_non_refundable(text: str) -> Optional[bool]:
    """환불 전면 제한 문구를 탐지한다."""
    risky_patterns = [
        r"환불\s*(?:은\s*)?불가",
        r"환급\s*(?:은\s*)?불가",
        r"중도\s*해지\s*(?:는\s*)?불가",
        r"어떠한\s*경우에도\s*환불(?:되지\s*않|하지\s*않)",
        r"(?:할인|이벤트|프로모션)\s*상품.*환불\s*불가",
    ]

    if any(re.search(pattern, text, re.IGNORECASE) for pattern in risky_patterns):
        return True

    # 명시적인 환불 가능 문구가 있는 경우에만 False
    refundable_patterns = [
        r"중도\s*해지\s*(?:가\s*)?가능",
        r"잔여\s*(?:이용료|대금).*환급",
        r"이용\s*일수.*공제.*환급",
        r"이용\s*횟수.*공제.*환급",
    ]

    if any(re.search(pattern, text, re.IGNORECASE) for pattern in refundable_patterns):
        return False

    return None


def _detect_closure_refund_clause(text: str) -> Optional[bool]:
    """폐업·휴업·영업중단 시 환급 보호조항을 탐지한다.

    문구가 없다는 이유만으로 False로 판단하지 않는다.
    """
    protective_patterns = [
        r"(?:폐업|휴업|영업\s*중단).*잔여.*환급",
        r"(?:폐업|휴업|영업\s*중단).*미사용.*환급",
        r"(?:폐업|휴업).*계약\s*해지",
        r"(?:폐업|휴업).*대체\s*시설",
    ]

    risky_patterns = [
        r"(?:폐업|휴업|영업\s*중단).*환불\s*불가",
        r"(?:폐업|휴업|영업\s*중단).*환급\s*불가",
        r"(?:폐업|휴업).*책임지지",
    ]

    if any(re.search(pattern, text, re.IGNORECASE) for pattern in protective_patterns):
        return True

    if any(re.search(pattern, text, re.IGNORECASE) for pattern in risky_patterns):
        return False

    return None


def _detect_auto_renewal(text: str) -> Optional[bool]:
    """자동연장 또는 자동갱신 문구 존재 여부를 확인한다."""
    renewal_patterns = [
        r"자동\s*연장",
        r"자동\s*갱신",
        r"별도\s*통보\s*없이.*연장",
        r"계약\s*기간.*자동으로\s*연장",
    ]

    if any(re.search(pattern, text, re.IGNORECASE) for pattern in renewal_patterns):
        return True

    no_renewal_patterns = [
        r"자동\s*연장되지\s*않",
        r"자동\s*갱신되지\s*않",
    ]

    if any(re.search(pattern, text, re.IGNORECASE) for pattern in no_renewal_patterns):
        return False

    return None


def _detect_payment_method(text: str) -> Optional[str]:
    """공통 PAYMENT_METHODS 값 중 하나로 결제수단을 판정한다."""
    patterns = [
        ("card_installment", [r"카드\s*\d+\s*개?월\s*할부", r"카드\s*할부"]),
        ("card_lump_sum", [r"카드\s*일시불"]),
        ("bank_transfer", [r"계좌\s*이체", r"무통장\s*입금", r"은행\s*이체"]),
        ("monthly", [r"월\s*납", r"월별\s*결제", r"매월\s*결제"]),
        ("cash", [r"현금\s*결제", r"현금\s*일시불"]),
    ]

    for method, method_patterns in patterns:
        if any(
            re.search(pattern, text, re.IGNORECASE)
            for pattern in method_patterns
        ):
            return method

    return None


# ---------------------------------------------------------------------
# 메인 함수
# ---------------------------------------------------------------------

def parse(ocr_text: str) -> dict:
    """OCR 원문을 공통 contract_data 형식으로 구조화한다."""
    normalized_text = _normalize_text(ocr_text)
    searchable_text = _compact_text(normalized_text)

    contract_data = {
        "contract_type": "unknown",
        "business_name": _extract_business_name(normalized_text),
        "business_address": _extract_business_address(normalized_text),
        "contract_price": _extract_money(
            searchable_text,
            [
                "총 계약대금",
                "총 계약금액",
                "계약대금",
                "계약금액",
                "총 이용금액",
                "이용대금",
            ],
        ),
        "cash_price": _extract_money(
            searchable_text,
            [
                "현금 할인가",
                "현금 할인금액",
                "현금 결제금액",
                "현금가",
            ],
        ),
        "normal_price": _extract_money(
            searchable_text,
            [
                "정상가",
                "정상가격",
                "정가",
                "할인 전 가격",
            ],
        ),
        "monthly_price": _extract_money(
            searchable_text,
            [
                "월 이용료",
                "월 납부금액",
                "월 결제금액",
                "월 회비",
            ],
        ),
        "contract_months": _extract_contract_months(searchable_text),
        "total_sessions": _extract_total_sessions(searchable_text),
        "penalty_rate": _extract_penalty_rate(searchable_text),
        "refund_base": _detect_refund_base(searchable_text),
        "non_refundable": _detect_non_refundable(searchable_text),
        "closure_refund_clause": _detect_closure_refund_clause(
            searchable_text
        ),
        "auto_renewal": _detect_auto_renewal(searchable_text),
        "payment_method": _detect_payment_method(searchable_text),
        "installment_months": _extract_installment_months(
            searchable_text
        ),
        "raw_text": normalized_text,
    }

    contract_data["contract_type"] = detect(contract_data)

    return contract_data