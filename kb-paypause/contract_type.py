"""[B 소유] contract_type.py

계약서에서 추출된 구조화 데이터를 바탕으로
계약 유형을 period/session/bundle/unknown 중 하나로 판정한다.
"""

from typing import Any


VALID_CONTRACT_TYPES = {
    "period",
    "session",
    "bundle",
    "unknown",
}


def _has_positive_number(value: Any) -> bool:
    """값이 0보다 큰 숫자인지 안전하게 확인한다."""
    if value is None or isinstance(value, bool):
        return False

    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def detect(contract_data: dict) -> str:
    """계약 유형을 판정한다.

    판정 기준
    ----------
    bundle
        계약기간과 총 이용횟수가 모두 존재하는 결합형 계약

    session
        총 이용횟수는 존재하지만 계약기간은 없는 횟수형 계약

    period
        계약기간은 존재하지만 총 이용횟수는 없는 기간형 계약

    unknown
        판정에 필요한 정보가 없거나 입력 형식이 잘못된 경우
    """
    if not isinstance(contract_data, dict):
        return "unknown"

    # 이미 parser나 사용자가 유효한 계약 유형을 명시했다면 우선 사용
    explicit_type = contract_data.get("contract_type")

    if explicit_type in VALID_CONTRACT_TYPES - {"unknown"}:
        return explicit_type

    has_period = _has_positive_number(
        contract_data.get("contract_months")
    )

    has_sessions = _has_positive_number(
        contract_data.get("total_sessions")
    )

    if has_period and has_sessions:
        return "bundle"

    if has_sessions:
        return "session"

    if has_period:
        return "period"

    return "unknown"