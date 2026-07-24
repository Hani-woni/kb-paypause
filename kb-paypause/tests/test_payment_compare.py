import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from payment_compare import compare


def test_golden_path():
    contract_data = {
        "contract_price": 1200000,
        "cash_price": 1080000,
        "normal_price": 2400000,
        "monthly_price": 120000,
        "installment_months": 6,
    }
    result = compare(contract_data)
    assert result["cash_discount"] == 120000
    assert result["max_prepaid_exposure"] == 1200000  # 카드 일시불이 현금할인 없이 계약금액 그대로라 최대
    assert any(
        o["method"] == "monthly" and o["risk_reduction_vs_cash"] == 960000
        for o in result["options"]
    )
    assert any(
        o["method"] == "card_installment" and o["prepaid_exposure"] == 200000
        for o in result["options"]
    )
    assert any(
        o["method"] == "card_lump_sum" and o["risk_reduction_vs_cash"] == -120000
        for o in result["options"]
    )
    assert result["safest_method"] == "monthly"
    print("PASS:", result)


test_golden_path()
