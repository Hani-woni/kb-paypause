"""[C 소유] 최종 판정·융합"""

def fuse(business_result: dict | None,
         contract_result: dict,
         refund_result: dict,
         payment_result: dict) -> dict:
    """/api/analyze 응답 조립. business는 None 가능."""
    raise NotImplementedError  # TODO(C)

def level(policy_score: int) -> str:
    """payable / revise / hold 중 하나 반환."""
    raise NotImplementedError  # TODO(C)
