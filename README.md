<div align="center">

# ⏸️ KB PayPause

### 장기 선결제 전에 계약위험과 예상손실을 확인하는 금융 안전 서비스

계약서 분석 · 업체 영업지속 상대위험 · 환급액 계산 · 결제수단 비교

</div>
<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white)
![CatBoost](https://img.shields.io/badge/Model-CatBoost-F2C94C)
![License](https://img.shields.io/badge/License-Competition%20Project-lightgrey)

</div>
## 💡 서비스 소개

**KB PayPause**는 헬스장·PT 등 장기 선결제 계약 전에  
계약조건, 업체 영업지속 상대위험, 예상 환급액, 결제수단별 보호수준을 함께 분석하여  
소비자가 충분히 검토한 뒤 계약과 결제방식을 선택하도록 돕는 사전예방 서비스입니다.

## 🚨 문제 정의

장기 선결제 계약에서는 다음 위험을 소비자가 결제 전에 파악하기 어렵습니다.

- **불리한 계약조건**: 환불불가, 과도한 위약금, 정상가 기준 차감
- **업체 영업중단 위험**: 휴업·폐업 시 잔여 이용금액 회수 어려움
- **결제수단별 보호 차이**: 현금·일시불·할부에 따라 소비자 보호수단이 달라짐

기존 서비스는 계약서 검토, 환불 계산, 업체 정보, 카드 혜택을 각각 제공하지만  
이를 결제 전 하나의 판단 과정으로 연결하는 데 한계가 있습니다.

## 🏗️ 전체 시스템 구조

```text
계약서 PDF·이미지 및 업체정보 입력
                ↓
        OCR 및 계약정보 구조화
                ↓
 ┌──────────────────────────────────┐
 │ 업체 영업지속 상대위험 분석        │
 │ 규칙기반 계약서 위험조항 분석      │
 │ 환급액·결제수단 위험 비교          │
 └──────────────────────────────────┘
                ↓
          최종 통합 판단
                ↓
 계약 진행 / 조건 수정 / 결제 보류
                ↓
       Streamlit 결과 화면

## 🛠️ 기술 스택

| 구분 | 기술 |
|---|---|
| Frontend | Streamlit |
| Language | Python 3.10 |
| PDF 처리 | PyMuPDF |
| OCR | EasyOCR |
| 계약서 분석 | 정규표현식·키워드 기반 규칙 엔진 |
| 업체 위험 분석 | CatBoost |
| 데이터 처리 | Pandas, NumPy |
| 평가 | PR-AUC, ROC-AUC |
| 테스트 | Pytest |
