from pathlib import Path

from ocr_parser import extract


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "헬스장_PT_이용계약서_불공정조항_테스트용.pdf"
)


def test_extract_realistic_contract_pdf():
    ocr_text, contract_data = extract(str(FIXTURE_PATH))

    assert ocr_text
    assert contract_data["contract_type"] == "bundle"
    assert contract_data["business_name"] == "핏맥스짐 성수점"
    assert contract_data["contract_price"] == 1200000
    assert contract_data["normal_price"] == 3200000
    assert contract_data["contract_months"] == 12
    assert contract_data["total_sessions"] == 20
    assert contract_data["penalty_rate"] == 10.0
    assert contract_data["refund_base"] == "normal_price"
    assert contract_data["non_refundable"] is True
    assert contract_data["closure_refund_clause"] is False
    assert contract_data["payment_method"] == "card_installment"
    assert contract_data["installment_months"] == 12