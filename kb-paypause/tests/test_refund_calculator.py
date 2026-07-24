import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from refund_calculator import calculate


def test_golden_path():
    contract_data = {
        "contract_type": "period",
        "contract_price": 1200000,
        "normal_price": 2400000,
        "contract_months": 12,
        "refund_base": "normal_price",
    }
    usage = {"used_months": 1}
    result = calculate(contract_data, usage)

    assert result["reference_refund"] == 980000
    assert result["contract_refund"] < result["reference_refund"]
    assert result["expected_disadvantage"] == result["reference_refund"] - result["contract_refund"]
    print("PASS:", result)


test_golden_path()
