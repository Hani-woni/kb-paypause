# KB PayPause

계약서 PDF·이미지를 분석해 계약위험, 예상 환급액, 결제수단별 선불 노출액, 업체 영업지속 상대위험을 제공하는 금융소비자 보호 서비스입니다.

최종 결과는 다음 3단계로 제공합니다.

- `payable`: 결제 가능
- `revise`: 조건 수정 후 결제
- `hold`: 결제 보류 권고

## 역할 분담

| 담당 | 역할 | 주요 파일 |
|---|---|---|
| 김지연 | 업체 데이터·상대위험 모델 | `business_lookup.py`, `business_model.py` |
| 김서연 | OCR·계약정보 추출·위험조항 분석 | `ocr_parser.py`, `contract_parser.py`, `contract_rules.py` |
| 한예원 | 환급액·결제수단 비교·최종판정·웹 통합 | `refund_calculator.py`, `payment_compare.py`, `final_fusion.py`, `app.py` |
| **공통** | 스키마·환경설정 관리 | `schemas.py`, `config.py` |

## 실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

접속 주소:

```text
http://localhost:8501
```

## 테스트

```bash
pytest -q
```

## 협업 규칙

- 공통 필드명과 함수 시그니처는 담당자 협의 없이 변경하지 않습니다.
- 금액은 원 단위 정수, 비율과 백분위는 `0~100`으로 관리합니다.
- 확인되지 않은 값은 `0`이 아닌 `None` 또는 `null`로 유지합니다.
- 최종 상태값은 `payable`, `revise`, `hold`로 고정합니다.
- `.env`, 개인정보, 실계약서 원본은 GitHub에 업로드하지 않습니다.

자세한 모듈 규격과 연동 기준은 저장소의 통합계약서 문서를 참고합니다.
