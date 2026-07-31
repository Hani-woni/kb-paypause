"""[C 소유] 최종 판정·융합"""

LEVEL_LABELS = {
    "payable": "결제 가능",
    "revise": "조건 수정 후 결제",
    "hold": "결제 보류 권고",
}

# medium 위험조항은 아직 위반이 확정되지 않은 확인 필요 사항이라,
# 수정 요청이 아니라 업체에 물어볼 확인 질문으로 안내한다.
QUESTION_TEMPLATES = {
    "SESSION_DEDUCTION_CHECK": "PT 횟수 차감 기준(노쇼·당일취소 등)을 구체적으로 안내해 주실 수 있을까요?",
    "CONTRACT_TERMS_NOT_PROVIDED": "환급 규정이 명시된 계약서(서면)를 별도로 받을 수 있을까요?",
    "GUARANTEE_INSURANCE_NOT_DISCLOSED": "가입하신 보증보험의 보험사·보장 내용·보증기간을 알려주실 수 있을까요?",
}

def fuse(business_result: dict | None,
         contract_result: dict,
         refund_result: dict,
         payment_result: dict) -> dict:
    """A·B·C 결과를 합쳐 /api/analyze 최종 응답을 조립한다."""
    contract_data = contract_result.get("contract_data", {})
    risks = contract_result.get("risks", [])
    high_risks = [r for r in risks if r.get("severity") == "high"]
    medium_risks = [r for r in risks if r.get("severity") == "medium"]

    policy_score = _score(len(high_risks), len(medium_risks), business_result,
                          refund_result, contract_data.get("contract_price"))
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
            "note": o.get("note"),
        }
        for o in payment_result.get("options", [])
    ]

    suggestions = [f"「{r['title']}」 부분을 수정해 주실 수 있을까요?" for r in high_risks]

    questions = [
        QUESTION_TEMPLATES[r["code"]]
        for r in medium_risks
        if r["code"] in QUESTION_TEMPLATES
    ]
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


def _score(high_risk_count: int, medium_risk_count: int, business_result: dict | None,
           refund_result: dict, contract_price: int | None) -> int:
    """점수가 낮을수록 위험 (0~100).

    B(계약 위험조항)는 확정된 위반 개수를 세어 반영하고(3건 이상은 3건으로 캡),
    A(업체위험)·C(환급불리)는 각자 이미 계산해 둔 연속값(백분위·손해비율)에
    비례해 반영한다. 두 값을 못 구하는 경우에만 등급/유무 기반 고정값으로 대체한다.
    """
    score = 100
    score -= min(high_risk_count, 3) * 30
    score -= min(medium_risk_count, 3) * 10

    business_risk_level = business_result.get("risk_level") if business_result else None
    percentile = business_result.get("relative_risk_percentile") if business_result else None
    if percentile is not None:
        score -= (percentile / 100) * 20
    elif business_risk_level in ("caution", "check_required"):
        score -= 20  # 백분위를 못 구한 업체는 등급 기반 고정값으로 대체

    disadvantage = refund_result.get("expected_disadvantage") or 0
    if disadvantage > 0:
        if contract_price:
            score -= min(disadvantage / contract_price, 1) * 15
        else:
            score -= 15  # 계약금액을 모르면 비율을 못 구하므로 고정값으로 대체

    return max(0, min(100, round(score)))


def level(policy_score: int) -> str:
    """payable / revise / hold 중 하나 반환."""
    if policy_score >= 70:
        return "payable"
    elif policy_score >= 40:
        return "revise"
    return "hold"
