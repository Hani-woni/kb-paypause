import os
import sys

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from contract_parser import parse
from contract_rules import analyze


def test_period_contract_and_core_risks():
    text = """
업체명: 테스트피트니스
총 계약금액: 1,200,000원
정상가: 2,400,000원
계약 기간: 12개월
위약금: 총 계약대금의 20%
중도해지 시 정상가 기준으로 이용대금을 공제합니다.
할인 상품은 환불 불가합니다.
"""

    contract_data = parse(text)
    risks = analyze(contract_data)
    risk_codes = [risk["code"] for risk in risks]

    assert contract_data["contract_type"] == "period"
    assert contract_data["contract_price"] == 1200000
    assert contract_data["normal_price"] == 2400000
    assert contract_data["contract_months"] == 12
    assert contract_data["penalty_rate"] == 20.0
    assert contract_data["refund_base"] == "normal_price"
    assert contract_data["non_refundable"] is True

    assert risk_codes == [
        "NORMAL_PRICE_DEDUCTION",
        "NON_REFUNDABLE",
        "PENALTY_EXCESS",
    ]

    for risk in risks:
        assert risk["severity"] in {"low", "medium", "high"}
        assert risk["title"]
        assert risk["evidence"]
        assert risk["reference_documents"]


def test_session_contract_and_check_rules():
    text = """
업체명: 안전체육센터
PT 횟수: 30회
계약서를 받지 못했고 환불 규정은 구두로만 설명받았습니다.
모든 사고는 회원 책임이며 사업자는 일절 책임지지 않습니다.
당일 취소 시 1회 차감합니다.
"""

    contract_data = parse(text)
    risks = analyze(contract_data)
    risk_codes = [risk["code"] for risk in risks]

    assert contract_data["contract_type"] == "session"
    assert contract_data["total_sessions"] == 30
    assert contract_data["contract_months"] is None

    assert risk_codes == [
        "BUSINESS_LIABILITY_EXEMPTION",
        "CONTRACT_TERMS_NOT_PROVIDED",
        "SESSION_DEDUCTION_CHECK",
    ]


def test_bundle_contract_type():
    text = """
업체명: 건강피트니스
총 계약금액: 2,750,000원
계약 기간: 6개월
PT 횟수: 50회
"""

    contract_data = parse(text)

    assert contract_data["contract_type"] == "bundle"
    assert contract_data["contract_months"] == 6
    assert contract_data["total_sessions"] == 50


def test_unknown_values_remain_none():
    text = """
업체명: 정보부족센터
총 계약금액: 500,000원
"""

    contract_data = parse(text)

    assert contract_data["contract_type"] == "unknown"
    assert contract_data["contract_months"] is None
    assert contract_data["total_sessions"] is None
    assert contract_data["penalty_rate"] is None
    assert contract_data["closure_refund_clause"] is None
    assert contract_data["auto_renewal"] is None
    assert contract_data["payment_method"] is None


def test_ten_percent_penalty_is_not_excessive():
    text = """
업체명: 정상센터
총 계약금액: 1,000,000원
계약 기간: 12개월
위약금: 총 계약대금의 10%
"""

    contract_data = parse(text)
    risks = analyze(contract_data)
    risk_codes = [risk["code"] for risk in risks]

    assert contract_data["penalty_rate"] == 10.0
    assert "PENALTY_EXCESS" not in risk_codes


def test_invalid_input_returns_safe_values():
    assert parse(None)["contract_type"] == "unknown"
    assert analyze(None) == []


if __name__ == "__main__":
    test_period_contract_and_core_risks()
    test_session_contract_and_check_rules()
    test_bundle_contract_type()
    test_unknown_values_remain_none()
    test_ten_percent_penalty_is_not_excessive()
    test_invalid_input_returns_safe_values()

    print("PASS: contract parser and rule tests")