"""공통 스키마·상수 (전원 동의 없이 변경 금지) — 계약서 ⑦"""

CONTRACT_TYPES = ["period", "session", "bundle", "unknown"]
SEVERITY = ["low", "medium", "high"]                       # 숫자 1/2/3 금지
BUSINESS_RISK_LEVEL = ["low", "normal", "caution", "check_required"]
FINAL_LEVEL = ["payable", "revise", "hold"]                # 화면 문구와 분리
PAYMENT_METHODS = ["cash", "bank_transfer", "card_lump_sum",
                   "card_installment", "monthly"]
REFUND_BASE = ["paid_price", "normal_price", "unknown"]

LEVEL_LABELS = {                                            # 철자·띄어쓰기 고정
    "payable": "결제 가능",
    "revise": "조건 수정 후 결제",
    "hold": "결제 보류 권고",
}
