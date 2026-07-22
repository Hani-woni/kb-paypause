# KB PayPause

계약서 이미지 → 위험 분석 → 환급/결제 시뮬레이션 → 결제 판정을 제공하는 3인 팀 프로젝트.

## 역할 분담 (통합계약서 기준)

| 담당 | 역할 | 소유 파일 |
|---|---|---|
| **A** | 데이터·모델 | `business_lookup.py`, `business_model.py`, 학습/평가 스크립트, 업체 데이터 |
| **B** | 계약·계산 | `ocr_parser.py`, `contract_parser.py`, `contract_type.py`, `contract_rules.py`, `rag_service.py`, 기준 문서 |
| **C** | 웹·통합 | `refund_calculator.py`, `payment_compare.py`, `final_fusion.py`, `app.py` |
| 공통 | 아무나 못 바꿈 | `schemas.py`, `config.py` |

> B = OCR·계약구조화·위험조항·RAG / C = 환급계산·결제비교·최종판정·웹통합

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env      # 키 값 채우기 (.env 는 커밋 금지)
streamlit run app.py      # http://localhost:8501
```

## 협업 규칙

- `schemas.py`·`config.py`·함수 시그니처 변경은 **관련 두 사람 이상 동의** 후, 단체방에 변경 전/후·이유·영향 파일 공유.
- 금액은 원 단위 정수, 비율은 0~100. 미확인값은 0이 아니라 `null`.
- `.env`, 실계약서, 개인정보, 대용량 모델은 커밋하지 않음 (`.gitignore` 참고).
- 최종 level 값은 `payable` / `revise` / `hold` 3종 고정.

## 통합 일정

1일차 인터페이스 확정 → 3일차 stub 관통 → 5일차 B 연결 → 7일차 A 연결 → 9일차 C 연결 → 10일차 골든패스 → 11~12일차 시나리오 테스트.

자세한 규약은 `통합계약서` 문서를 참고하세요.
