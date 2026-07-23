"""
business_lookup.py

체력단련장업 인허가 데이터에서 업체명과 주소를 검색하고
사용자가 선택할 수 있는 후보 업체 목록을 반환한다.
"""

from __future__ import annotations
from business_model import predict

import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd



# ============================================================
# 1. 파일 경로와 기본 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

BUSINESS_DATA_PATH = (
    BASE_DIR
    / "data"
    / "processed"
    / "business.csv"
)

MAX_RESULTS = 10


# ============================================================
# 2. 데이터 컬럼 설정
# ============================================================

BUSINESS_ID_COL = "business_id"
BUSINESS_NAME_COL = "사업장명"
STATUS_COL = "영업상태명"
OPEN_DATE_COL = "인허가일자"
CLOSE_DATE_COL = "폐업일자"

ROAD_ADDRESS_COL = "도로명주소"
LOT_ADDRESS_COL = "지번주소"
ANALYSIS_ADDRESS_COL = "analysis_address"

SIDO_COL = "sido"
SIGUNGU_COL = "sigungu"


# ============================================================
# 3. 데이터 불러오기
# ============================================================

def _load_business_data() -> pd.DataFrame:
    if not BUSINESS_DATA_PATH.exists():
        raise FileNotFoundError(
            "업체 데이터 파일을 찾을 수 없습니다.\n"
            f"확인 경로: {BUSINESS_DATA_PATH}"
        )

    business_df = pd.read_csv(
        BUSINESS_DATA_PATH,
        encoding="utf-8-sig",
        low_memory=False,
    )

    required_cols = [
        BUSINESS_NAME_COL,
        STATUS_COL,
        OPEN_DATE_COL,
    ]

    missing_cols = [
        col
        for col in required_cols
        if col not in business_df.columns
    ]

    if missing_cols:
        raise ValueError(
            "business.csv에 필수 컬럼이 없습니다: "
            + ", ".join(missing_cols)
        )

    # business_id가 없으면 원본 행 기준으로 생성
    if BUSINESS_ID_COL not in business_df.columns:
        if "source_index" in business_df.columns:
            source_index = pd.to_numeric(
                business_df["source_index"],
                errors="coerce",
            ).fillna(business_df.index)

            business_df[BUSINESS_ID_COL] = (
                "gym-"
                + source_index
                .astype(int)
                .astype(str)
                .str.zfill(6)
            )

        else:
            business_df[BUSINESS_ID_COL] = [
                f"gym-{index:06d}"
                for index in range(len(business_df))
            ]

    # 날짜 변환
    for col in [OPEN_DATE_COL, CLOSE_DATE_COL]:
        if col in business_df.columns:
            business_df[col] = pd.to_datetime(
                business_df[col],
                errors="coerce",
            )

    # 대표 주소 생성
    if ANALYSIS_ADDRESS_COL not in business_df.columns:
        road_address = (
            business_df[ROAD_ADDRESS_COL]
            if ROAD_ADDRESS_COL in business_df.columns
            else pd.Series(
                pd.NA,
                index=business_df.index,
                dtype="string",
            )
        )

        lot_address = (
            business_df[LOT_ADDRESS_COL]
            if LOT_ADDRESS_COL in business_df.columns
            else pd.Series(
                pd.NA,
                index=business_df.index,
                dtype="string",
            )
        )

        business_df[ANALYSIS_ADDRESS_COL] = (
            road_address
            .fillna(lot_address)
            .astype("string")
            .str.strip()
        )
        # 시도·시군구가 없거나 비어 있으면 주소에서 추출
    address_text = (
        business_df[ANALYSIS_ADDRESS_COL]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    extracted_sido = address_text.str.split().str[0]
    extracted_sigungu = address_text.str.split().str[1]

    if SIDO_COL not in business_df.columns:
        business_df[SIDO_COL] = extracted_sido
    else:
        business_df[SIDO_COL] = (
            business_df[SIDO_COL]
            .replace("", pd.NA)
            .fillna(extracted_sido)
        )

    if SIGUNGU_COL not in business_df.columns:
        business_df[SIGUNGU_COL] = extracted_sigungu
    else:
        business_df[SIGUNGU_COL] = (
            business_df[SIGUNGU_COL]
            .replace("", pd.NA)
            .fillna(extracted_sigungu)
        )

    # 검색용 정규화 컬럼
    business_df["_normalized_name"] = (
        business_df[BUSINESS_NAME_COL]
        .fillna("")
        .astype(str)
        .map(_normalize_text)
    )

    business_df["_normalized_address"] = (
        business_df[ANALYSIS_ADDRESS_COL]
        .fillna("")
        .astype(str)
        .map(_normalize_text)
    )

    return business_df


# ============================================================
# 4. 문자열 정규화
# ============================================================

def _normalize_text(value: Any) -> str:
    """
    검색 비교를 위해 공백과 일부 특수문자를 제거한다.

    예:
    'ABC 피트니스(강남점)' → 'abc피트니스강남점'
    """

    if value is None or pd.isna(value):
        return ""

    text = str(value).strip().lower()

    # 한글·영문·숫자만 유지
    text = re.sub(
        r"[^0-9a-z가-힣]",
        "",
        text,
    )

    return text


def _split_address_tokens(address: str) -> list[str]:
    """
    주소를 공백 기준 토큰으로 나눈다.

    너무 짧은 토큰은 검색 정확도를 떨어뜨릴 수 있어 제외한다.
    """

    if not address:
        return []

    cleaned = re.sub(
        r"[,()\[\]]",
        " ",
        str(address),
    )

    tokens = [
        _normalize_text(token)
        for token in cleaned.split()
    ]

    return [
        token
        for token in tokens
        if len(token) >= 2
    ]


# ============================================================
# 5. 안전한 값 변환
# ============================================================

def _safe_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    # numpy 정수형 → 일반 Python int
    if isinstance(value, np.integer):
        return int(value)

    # numpy 실수형 → 일반 Python float
    if isinstance(value, np.floating):
        return round(float(value), 6)

    # numpy bool → 일반 Python bool
    if isinstance(value, np.bool_):
        return bool(value)

    # 일반 Python float
    if isinstance(value, float):
        if value.is_integer():
            return int(value)

        return round(value, 6)

    return value


def _get_value(
    row: pd.Series,
    column: str,
    default: Any = None,
) -> Any:
    if column not in row.index:
        return default

    value = _safe_value(row[column])

    if value is None:
        return default

    return value


# ============================================================
# 6. 영업상태 정리
# ============================================================

def _normalize_status(status: Any) -> str:
    if status is None or pd.isna(status):
        return "확인필요"

    status_text = str(status).strip()

    if status_text in {
        "영업/정상",
        "정상영업",
        "영업중",
    }:
        return "정상영업"

    if "폐업" in status_text:
        return "폐업"

    if "취소" in status_text:
        return "허가취소"

    if "정지" in status_text:
        return "영업정지"

    return status_text


# ============================================================
# 7. 검색 점수 계산
# ============================================================

def _calculate_match_score(
    row: pd.Series,
    normalized_name: str,
    address_tokens: list[str],
) -> float:
    candidate_name = row["_normalized_name"]
    candidate_address = row["_normalized_address"]

    score = 0.0

    # 업체명 정확 일치
    if candidate_name == normalized_name:
        score += 100

    # 검색어가 업체명에 포함
    elif normalized_name in candidate_name:
        score += 70

        # 이름 길이가 비슷할수록 우선
        length_difference = abs(
            len(candidate_name) - len(normalized_name)
        )

        score += max(
            0,
            20 - length_difference,
        )

    # 업체명이 검색어에 포함
    elif candidate_name in normalized_name:
        score += 55

    # 주소 토큰 일치
    if address_tokens:
        matched_tokens = sum(
            token in candidate_address
            for token in address_tokens
        )

        address_match_ratio = (
            matched_tokens / len(address_tokens)
        )

        score += address_match_ratio * 50

        # 모든 주소 토큰이 포함되면 가산점
        if matched_tokens == len(address_tokens):
            score += 20

    # 정상영업 업체를 동점일 때 조금 우선
    normalized_status = _normalize_status(
        row.get(STATUS_COL)
    )

    if normalized_status == "정상영업":
        score += 1

    return score


# ============================================================
# 8. 반환 결과 생성
# ============================================================

def _row_to_search_result(
    row: pd.Series,
    match_score: float,
) -> dict[str, Any]:
    return {
        "business_id": _get_value(
            row,
            BUSINESS_ID_COL,
        ),
        "business_name": _get_value(
            row,
            BUSINESS_NAME_COL,
            "",
        ),
        "status": _normalize_status(
            row.get(STATUS_COL)
        ),
        "open_date": _get_value(
            row,
            OPEN_DATE_COL,
        ),
        "close_date": _get_value(
            row,
            CLOSE_DATE_COL,
        ),
        "road_address": _get_value(
            row,
            ROAD_ADDRESS_COL,
        ),
        "lot_address": _get_value(
            row,
            LOT_ADDRESS_COL,
        ),
        "address": _get_value(
            row,
            ANALYSIS_ADDRESS_COL,
        ),
        "sido": _get_value(
            row,
            SIDO_COL,
        ),
        "sigungu": _get_value(
            row,
            SIGUNGU_COL,
        ),
        "match_score": round(
            float(match_score),
            2,
        ),
    }


# ============================================================
# 9. 공개 검색 함수
# ============================================================

def search(
    name: str,
    address: str | None = None,
) -> list[dict[str, Any]]:
    """
    업체명과 선택적 주소를 입력받아 검색 후보를 반환한다.

    Parameters
    ----------
    name:
        검색할 업체명

    address:
        선택적 주소 문자열.
        동명이업체가 있을 때 검색 정확도를 높인다.

    Returns
    -------
    list[dict]
        검색 점수가 높은 순서의 업체 후보 목록
    """

    if not isinstance(name, str):
        raise TypeError(
            "업체명은 문자열이어야 합니다."
        )

    normalized_name = _normalize_text(name)

    if len(normalized_name) < 2:
        return []

    business_df = _load_business_data()

    # 1차: 업체명 포함 검색
    name_mask = (
        business_df["_normalized_name"]
        .str.contains(
            normalized_name,
            regex=False,
            na=False,
        )
    )

    candidates = business_df[
        name_mask
    ].copy()

    # 검색어가 후보 이름보다 긴 경우를 고려한 역방향 검색
    if candidates.empty:
        reverse_mask = (
            business_df["_normalized_name"]
            .apply(
                lambda candidate_name: (
                    bool(candidate_name)
                    and candidate_name in normalized_name
                )
            )
        )

        candidates = business_df[
            reverse_mask
        ].copy()

    if candidates.empty:
        return []

    address_tokens = _split_address_tokens(
        address or ""
    )

    candidates["_match_score"] = candidates.apply(
        lambda row: _calculate_match_score(
            row=row,
            normalized_name=normalized_name,
            address_tokens=address_tokens,
        ),
        axis=1,
    )

    # 주소를 입력했는데 일치하는 후보가 있다면
    # 주소가 전혀 맞지 않는 후보는 후순위로 정렬됨
    candidates = candidates.sort_values(
        by=[
            "_match_score",
            OPEN_DATE_COL,
        ],
        ascending=[
            False,
            False,
        ],
        na_position="last",
    )

    results = [
        _row_to_search_result(
            row,
            row["_match_score"],
        )
        for _, row in candidates.head(
            MAX_RESULTS
        ).iterrows()
    ]

    return results


# ============================================================
# 10. business_id로 업체 한 건 조회
# ============================================================

def get_by_id(
    business_id: str,
) -> dict[str, Any] | None:
    """
    business_id에 해당하는 전체 업체 정보를 dict로 반환한다.

    이후 business_model.predict() 입력값을 만들 때 사용할 수 있다.
    """

    if not isinstance(business_id, str):
        raise TypeError(
            "business_id는 문자열이어야 합니다."
        )

    business_df = _load_business_data()

    matched = business_df[
        business_df[BUSINESS_ID_COL].astype(str)
        == business_id.strip()
    ]

    if matched.empty:
        return None

    row = matched.iloc[0]

    result: dict[str, Any] = {}

    for column in business_df.columns:
        if column.startswith("_"):
            continue

        result[column] = _safe_value(
            row[column]
        )

    return result
MODEL_FEATURE_DATA_PATH = (
    BASE_DIR
    / "data"
    / "processed"
    / "business_model_2y_features.csv"
)


def get_model_features(
    business_id: str,
) -> dict[str, Any] | None:
    """
    business_id에 해당하는 모델 입력 변수를 반환한다.
    """

    if not MODEL_FEATURE_DATA_PATH.exists():
        raise FileNotFoundError(
            "모델 입력 데이터 파일을 찾을 수 없습니다.\n"
            f"확인 경로: {MODEL_FEATURE_DATA_PATH}"
        )

    business = get_by_id(business_id)

    if business is None:
        return None

    feature_df = pd.read_csv(
        MODEL_FEATURE_DATA_PATH,
        encoding="utf-8-sig",
        low_memory=False,
    )

    # business_id가 모델 데이터에도 있으면 바로 검색
    if BUSINESS_ID_COL in feature_df.columns:
        matched = feature_df[
            feature_df[BUSINESS_ID_COL].astype(str)
            == business_id.strip()
        ]

    # 없으면 source_index로 연결
    elif (
        "source_index" in feature_df.columns
        and "source_index" in business
    ):
        matched = feature_df[
            pd.to_numeric(
                feature_df["source_index"],
                errors="coerce",
            )
            == int(business["source_index"])
        ]

    else:
        raise ValueError(
            "business_model_2y_features.csv에 "
            "business_id 또는 source_index가 없습니다."
        )

    if matched.empty:
        return None

    row = matched.iloc[0]

    result: dict[str, Any] = {}

    for column in feature_df.columns:
        result[column] = _safe_value(row[column])

    return result

# ============================================================
# 최종 A → C business_result 생성
# ============================================================

def _calculate_operation_months(
    open_date: Any,
    close_date: Any = None,
    data_as_of: str = "2026-07-20",
) -> int | None:
    """
    개업일부터 폐업일 또는 데이터 기준일까지의 영업 개월 수를 계산한다.
    """

    start = pd.to_datetime(
        open_date,
        errors="coerce",
    )

    if pd.isna(start):
        return None

    end = pd.to_datetime(
        close_date,
        errors="coerce",
    )

    if pd.isna(end):
        end = pd.to_datetime(
            data_as_of,
            errors="coerce",
        )

    if pd.isna(end) or end < start:
        return None

    months = (
        (end.year - start.year) * 12
        + (end.month - start.month)
    )

    # 해당 월의 개업일을 아직 지나지 않았다면 1개월 차감
    if end.day < start.day:
        months -= 1

    return max(int(months), 0)


def _get_current_region_statistics(
    sido: str | None,
    sigungu: str | None,
) -> dict[str, Any]:
    """
    현재 business.csv 기준 동일 시도·시군구의
    정상영업·폐업 업체 수와 과거 폐업기록 비율을 계산한다.
    """

    if not sido or not sigungu:
        return {
            "local_active_count": 0,
            "local_closed_count": 0,
            "historical_closure_ratio": 0.0,
        }

    business_df = _load_business_data()

    region_df = business_df[
        (business_df[SIDO_COL].astype(str) == str(sido))
        & (
            business_df[SIGUNGU_COL].astype(str)
            == str(sigungu)
        )
    ].copy()

    normalized_status = region_df[
        STATUS_COL
    ].map(_normalize_status)

    active_count = int(
        (normalized_status == "정상영업").sum()
    )

    closed_count = int(
        (normalized_status == "폐업").sum()
    )

    denominator = active_count + closed_count

    if denominator == 0:
        closure_ratio = 0.0
    else:
        closure_ratio = round(
            closed_count / denominator * 100,
            1,
        )

    return {
        "local_active_count": active_count,
        "local_closed_count": closed_count,
        "historical_closure_ratio": closure_ratio,
    }


def analyze_business(
    business_id: str,
) -> dict[str, Any] | None:
    """
    선택된 업체를 조회하고 모델 분석을 수행하여
    통합계약서의 business_result 형식으로 반환한다.

    최신 개업 업체처럼 모델 입력 데이터가 없는 경우에는
    위험점수를 임의 생성하지 않고 check_required로 반환한다.
    """

    business = get_by_id(
        business_id
    )

    if business is None:
        return None

    status = _normalize_status(
        business.get(STATUS_COL)
    )

    open_date = business.get(
        OPEN_DATE_COL
    )

    close_date = business.get(
        CLOSE_DATE_COL
    )

    sido = business.get(
        SIDO_COL
    )

    sigungu = business.get(
        SIGUNGU_COL
    )

    region_stats = (
        _get_current_region_statistics(
            sido=sido,
            sigungu=sigungu,
        )
    )

    operation_months = (
        _calculate_operation_months(
            open_date=open_date,
            close_date=close_date,
            data_as_of="2026-07-20",
        )
    )

    model_features = get_model_features(
        business_id
    )

    # 모델 분석 가능한 업체
    if model_features is not None:
        prediction = predict(
            model_features
        )

        relative_risk_percentile = (
            prediction[
                "relative_risk_percentile"
            ]
        )

        risk_level = prediction[
            "risk_level"
        ]

        risk_factors = prediction[
            "risk_factors"
        ]

        model_version = prediction[
            "model_version"
        ]

        data_as_of = prediction[
            "data_as_of"
        ]

        disclaimer = prediction[
            "disclaimer"
        ]

    # 관찰기간 또는 모델 변수가 부족한 업체
    else:
        relative_risk_percentile = None
        risk_level = "check_required"

        risk_factors = [
            "모델 분석에 필요한 관찰기간 또는 과거 지역정보가 부족합니다.",
            "현재 영업상태와 지역 비교통계를 중심으로 확인하세요.",
        ]

        model_version = "business-v2"
        data_as_of = "2026-07-20"

        disclaimer = (
            "모델 분석에 필요한 정보가 부족하여 "
            "개별 상대위험 백분위를 산출하지 않았습니다."
        )

    return {
        "business_id": str(
            business_id
        ),
        "status": status,
        "open_date": open_date,
        "operation_months": operation_months,
        "local_active_count": region_stats[
            "local_active_count"
        ],
        "local_closed_count": region_stats[
            "local_closed_count"
        ],
        "historical_closure_ratio": region_stats[
            "historical_closure_ratio"
        ],
        "same_address_history_count": int(
            model_features.get(
                "same_address_history_count",
                0,
            )
        )
        if model_features is not None
        else 0,
        "relative_risk_percentile": (
            relative_risk_percentile
        ),
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "model_version": model_version,
        "data_as_of": data_as_of,
        "disclaimer": disclaimer,
    }

# ============================================================
# 11. 직접 실행 테스트
# ============================================================

if __name__ == "__main__":
    import json

    test_name = input(
        "검색할 업체명을 입력하세요: "
    ).strip()

    test_address = input(
        "주소를 입력하세요(선택): "
    ).strip()

    results = search(
        name=test_name,
        address=test_address or None,
    )

    print(
        f"\n검색 결과: {len(results)}건"
    )

    print(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        )
    )

    if results:
        selected_id = results[0][
            "business_id"
        ]

        print(
            f"\n첫 번째 업체 분석: {selected_id}"
        )

        business_result = analyze_business(
            selected_id
        )

        print(
            json.dumps(
                business_result,
                ensure_ascii=False,
                indent=2,
            )
        )     
