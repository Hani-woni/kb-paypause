import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import final_fusion
import payment_compare
import refund_calculator


def test_golden_path():
    contract_data = {
        "contract_type": "period",
        "business_name": "KB 피트니스 강남점",
        "contract_price": 1200000,
        "cash_price": 1080000,
        "normal_price": 2400000,
        "monthly_price": 120000,
        "contract_months": 12,
        "refund_base": "normal_price",
        "closure_refund_clause": False,
        "installment_months": None,
    }
    contract_result = {
        "contract_data": contract_data,
        "risks": [{
            "code": "NON_REFUNDABLE", "severity": "high", "title": "환불불가 조항",
            "description": "이벤트 상품의 환불을 제한합니다.",
            "evidence": "이벤트 등록 상품은 환불이 불가합니다.",
        }],
        "extraction_warnings": [], "confidence": 0.92,
    }
    business_result = {
        "status": "정상영업", "operation_months": 28,
        "historical_closure_ratio": 18.2, "relative_risk_percentile": 72.4,
        "risk_level": "caution", "data_as_of": "2026-07-22",
    }
    usage = {"used_months": 1}

    refund_result = refund_calculator.calculate(contract_data, usage)
    payment_result = payment_compare.compare(contract_data)
    fused = final_fusion.fuse(business_result, contract_result, refund_result, payment_result)

    assert fused["level"] == "hold"
    assert fused["level_label"] == "결제 보류 권고"
    assert fused["summary"]["contract_price"] == 1200000
    assert fused["summary"]["cash_discount"] == 120000
    assert any(o["method"] == "monthly" for o in fused["payment_options"])
    assert "폐업 시 미사용 이용금액은 어떻게 처리되는지 확인 부탁드립니다." in fused["questions"]
    print("PASS:", fused)


test_golden_path()
