"""[C 소유] 결제수단별 선불 노출액 비교"""

METHOD_LABELS = {
    "cash": "현금·계좌이체",
    "bank_transfer": "현금·계좌이체",
    "card_lump_sum": "카드 일시불",
    "card_installment": "카드 할부",
    "monthly": "월 단위 결제",
}


def compare(contract_data: dict) -> dict:
    """결제수단별 선불 노출액을 비교해 payment_result를 반환한다.

    - cash_price 기준으로 현금 선불 노출액을 계산한다.
    - monthly_price가 있으면 월결제 옵션의 위험 감소액을 계산한다.
    - 미확인 금액(None)은 0으로 치환하지 않고 계산에서 제외한다 (계약서 7절).
    """
    contract_price = contract_data.get("contract_price")
    cash_price = contract_data.get("cash_price")
    monthly_price = contract_data.get("monthly_price")
    installment_months = contract_data.get("installment_months")

    cash_discount = None
    if contract_price is not None and cash_price is not None:
        cash_discount = contract_price - cash_price

    exposures = {}
    if cash_price is not None:
        exposures["cash"] = cash_price
    if contract_price is not None:
        exposures["card_lump_sum"] = contract_price  # 카드 일시불은 현금할인 없이 계약금액 그대로 노출
    if monthly_price is not None:
        exposures["monthly"] = monthly_price
    if contract_price is not None and installment_months:
        exposures["card_installment"] = round(contract_price / installment_months)

    max_prepaid_exposure = max(exposures.values()) if exposures else None
    cash_exposure = exposures.get("cash")

    options = []
    for method, exposure in exposures.items():
        if method == "cash":
            continue
        risk_reduction = None
        if cash_exposure is not None:
            risk_reduction = cash_exposure - exposure
        options.append({
            "method": method,
            "label": METHOD_LABELS.get(method, method),
            "prepaid_exposure": exposure,
            "risk_reduction_vs_cash": risk_reduction,
            "note": _note_for(method),
        })

    safest_method = None
    if options:
        valid = [o for o in options if o["risk_reduction_vs_cash"] is not None]
        if valid:
            safest_method = max(valid, key=lambda o: o["risk_reduction_vs_cash"])["method"]

    return {
        "cash_discount": cash_discount,
        "max_prepaid_exposure": max_prepaid_exposure,
        "safest_method": safest_method,
        "options": options,
    }


def _note_for(method: str) -> str:
    notes = {
        "monthly": "장기 선납 위험을 줄입니다.",
        "card_installment": "할부항변권 적용 여부를 별도 확인하세요.",
        "card_lump_sum": "카드 일시불은 선불 노출액이 큽니다.",
    }
    return notes.get(method, "")
