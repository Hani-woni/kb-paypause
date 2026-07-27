"""[C 소유] 최종 판정·융합"""

LEVEL_LABELS = {
    "payable": "결제 가능",
    "revise": "조건 수정 후 결제",
    "hold": "결제 보류 권고",
}


def fuse(business_result: dict | None,
         contract_result: dict,
         refund_result: dict,
         payment_result: dict) -> dict:
    """A·B·C 결과를 합쳐 /api/analyze 최종 응답을 조립한다."""
    contract_data = contract_result.get("contract_data", {})
    risks = contract_result.get("risks", [])
    high_risks = [r for r in risks if r.get("severity") == "high"]

    business_risk_level = business_result.get("risk_level") if business_result else None
    policy_score = _score(len(high_risks), business_risk_level, refund_result)
    final_level = level(policy_score)

    summary = {
        "contract_price": contract_data.get("contract_price"),
        "cash_discount": payment_result.get("cash_discount"),
        "expected_disadvantage": refund_result.get("expected_disadvantage"),
        "max_prepaid_exposure": payment_result.get("max_prepaid_exposure"),
    }

    payment_options = [
        {
            "method": o["method"],
            "label": o["label"],
            "prepaid_exposure": o["prepaid_exposure"],
            "risk_reduction_vs_cash": o["risk_reduction_vs_cash"],
        }
        for o in payment_result.get("options", [])
    ]

    suggestions = [f"{r['title']}의 수정을 요청하세요." for r in high_risks]

    questions = []
    if contract_data.get("closure_refund_clause") is False:
        questions.append("폐업 시 미사용 이용금액은 어떻게 처리되는지 확인 부탁드립니다.")

    return {
        "level": final_level,
        "level_label": LEVEL_LABELS[final_level],
        "policy_score": policy_score,
        "summary": summary,
        "contract_risks": risks,
        "refund": refund_result,
        "business": business_result,
        "payment_options": payment_options,
        "suggestions": suggestions,
        "questions": questions,
        "disclaimer": "법률적 확정 판단이 아닌 공식기준 참고 결과입니다.",
    }


def _score(high_risk_count: int, business_risk_level: str | None,
           refund_result: dict) -> int:
    """점수가 낮을수록 위험 (0~100). TODO: A·B 실 데이터 연결 후 가중치 조정."""
    score = 100
    score -= high_risk_count * 30
    if business_risk_level in ("caution", "check_required"):
        score -= 20
    disadvantage = refund_result.get("expected_disadvantage") or 0
    if disadvantage > 0:
        score -= 15
    return max(0, min(100, score))


def level(policy_score: int) -> str:
    """payable / revise / hold 중 하나 반환."""
    if policy_score >= 70:
        return "payable"
    elif policy_score >= 40:
        return "revise"
    return "hold"
