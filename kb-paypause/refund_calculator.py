"""[C 소유] 환급액 계산 (계약기준 + 공식기준 참고)"""

def calculate(contract_data: dict, usage: dict) -> dict:
    """refund_result 반환.
    - normal_price 등 미확인값이 None이면 0으로 넘기지 말 것 (계약서 7절)
    - 결합형(bundle)에서 항목별 가격이 없으면 오류 상태 반환
    - 공식기준은 config/refund_standards.json (B 제공) 로드해 사용
    """
    raise NotImplementedError  # TODO(C)
