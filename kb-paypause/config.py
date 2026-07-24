"""공통 설정 (전원 동의 없이 변경 금지) — 계약서 8절"""
API_PORT = 8000
STREAMLIT_PORT = 8501

# 경로는 반드시 상대경로 (절대경로 쓰면 배포에서 깨짐 — 계약서 7절)
BUSINESS_MODEL_PATH = "models/business_model.cbm"
BUSINESS_DATA_PATH = "data/processed/business.csv"
CONTRACT_RULES_PATH = "config/contract_rules.json"
REFUND_STANDARDS_PATH = "config/refund_standards.json"
REFERENCE_DIR = "data/reference/"
SAMPLES_DIR = "data/samples/contracts/"
