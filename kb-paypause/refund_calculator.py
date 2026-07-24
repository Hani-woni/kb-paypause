"""[C 소유] 환급액 계산
근거: 계속거래 등의 해지·해제에 따른 위약금 및 대금의 환급에 관한 산정기준
      (공정거래위원회고시 제2019-9호, 방문판매법 제32조④)
"""
import json
import os

DEFAULT_PENALTY_CAP = 0.10  # 헬스·피트니스업종 위약금 상한 (제4조)
STANDARDS_PATH = "config/refund_standards.json"


def _load_standards() -> dict:
    """B가 관리하는 config/refund_standards.json 로드. 없거나 비면 법정 기본값 사용."""
    if os.path.exists(STANDARDS_PATH):
        try:
            with open(STANDARDS_PATH, encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"penalty_cap_by_category": {"default": DEFAULT_PENALTY_CAP}}


def calculate(contract_data: dict, usage: dict, category: str = "default") -> dict:
    """refund_result 반환.

    - 위약금은 항상 '실제 지급한 계약대금'(contract_price)의 penalty_cap 상한으로 계산한다 (제4조).
    - 사용료 공제 기준액은 refund_base에 따라 달라진다: 계약서가 정상가(normal_price)를
      공제 기준으로 못박아뒀으면 그 기준으로, 아니면 실제 지급액 기준으로 계산한다.
    - 공식(법정) 기준은 사용료 공제도 반드시 실제 지급액 기준이어야 하므로(제5조 취지),
      계약서가 정상가 기준을 쓰면 공식기준보다 소비자에게 불리한 결과가 나올 수 있다.
    """
    contract_price = contract_data.get("contract_price")
    contract_months = contract_data.get("contract_months")
    refund_base = contract_data.get("refund_base", "unknown")
    normal_price = contract_data.get("normal_price")
    used_months = usage.get("used_months")

    if contract_data.get("contract_type") == "bundle" and contract_price is None:
        return {"error": "MISSING_BUNDLE_PRICE",
                "message": "결합형 상품의 항목별 가격이 없어 계산할 수 없습니다."}
    if None in (contract_price, contract_months, used_months):
        return {"error": "MISSING_FIELDS",
                "message": "환급 계산에 필요한 값이 부족합니다."}

    standards = _load_standards()
    penalty_cap = standards.get("penalty_cap_by_category", {}).get(
        category, standards.get("penalty_cap_by_category", {}).get("default", DEFAULT_PENALTY_CAP)
    )
    penalty = contract_price * penalty_cap

    def refund_with_usage_basis(usage_basis: float) -> int:
        usage_deduction = usage_basis * (used_months / contract_months)
        return round(contract_price - usage_deduction - penalty)

    # 공식 기준 (법정, 사용료 공제도 항상 실제 지급액 기준 — 제5조)
    reference_refund = refund_with_usage_basis(contract_price)

    # 계약서 기준: refund_base가 정상가면 그 기준으로 사용료를 더 많이 공제당함 (소비자 불리)
    if refund_base == "normal_price" and normal_price is not None:
        contract_refund = refund_with_usage_basis(normal_price)
    else:
        contract_refund = reference_refund

    expected_disadvantage = reference_refund - contract_refund

    return {
        "contract_refund": contract_refund,
        "reference_refund": reference_refund,
        "expected_disadvantage": expected_disadvantage,
        "assumptions": [
            f"사용기간 {used_months}개월",
            f"위약금 상한 {int(penalty_cap * 100)}% (공정위고시 제2019-9호 제4조)",
        ],
        "legal_basis": "공정거래위원회고시 제2019-9호 (방문판매법 제32조④)",
    }
