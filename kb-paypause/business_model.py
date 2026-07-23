"""
business_model.py

업체 특성을 입력받아 다음 결과를 반환한다.

1. CatBoost 원시 위험점수
2. 학습 기준집단 내 상대위험 백분위
3. 위험등급
4. 주요 위험요인
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier


# ============================================================
# 1. 파일 경로
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = BASE_DIR / "models" / "business_model.cbm"
METADATA_PATH = BASE_DIR / "models" / "business_model_metadata.json"
REFERENCE_PATH = BASE_DIR / "models" / "business_risk_reference.csv"


# ============================================================
# 2. 서비스 설정
# ============================================================

MODEL_VERSION = "business-v2"

DISCLAIMER = (
    "공개 인허가 및 지역 영업이력을 바탕으로 산출한 "
    "상대위험 참고값이며, 개별 업체의 미래 폐업을 확정하지 않습니다."
)

# 팀 통합 규격에 맞는 위험등급
# 백분위가 높을수록 상대위험이 높은 업체
RISK_LEVEL_THRESHOLDS = {
    "low": 30.0,
    "normal": 70.0,
    "caution": 90.0,
}


# ============================================================
# 3. 모델 입력 변수
# ============================================================

# metadata에 feature_cols가 없을 때 사용하는 기본값
DEFAULT_FEATURE_COLS = [
    # 범주형 변수
    "sido",
    "sigungu",
    "공사립구분명",

    # 개업 시점 및 시설 변수
    "open_year",
    "open_month",
    "open_quarter",
    "소재지면적",
    "사무실면적",
    "지도자수",
    "탈의실면적",
    "휴게실면적",
    "same_address_history_count",

    # 개업 당시 지역 동적 변수
    "prior_1y_local_open_count",
    "prior_1y_local_close_count",
    "prior_3y_local_open_count",
    "prior_3y_local_close_count",
    "prior_3y_close_to_open_ratio",
    "prior_3y_closure_pressure",
    "local_active_at_open",
    "local_net_change_1y",

    # 로그 변환 변수
    "log_local_active_at_open",
    "log_prior_1y_open_count",
    "log_prior_1y_close_count",
    "log_prior_3y_open_count",
    "log_prior_3y_close_count",
]

DEFAULT_CATEGORICAL_COLS = [
    "sido",
    "sigungu",
    "공사립구분명",
]


# ============================================================
# 4. 모델 및 기준분포 불러오기
# ============================================================

def _load_metadata() -> dict[str, Any]:
    if not METADATA_PATH.exists():
        return {}

    with open(METADATA_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def _load_model() -> CatBoostClassifier:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"CatBoost 모델 파일을 찾을 수 없습니다: {MODEL_PATH}"
        )

    model = CatBoostClassifier()
    model.load_model(str(MODEL_PATH))

    return model


def _load_reference_scores() -> np.ndarray:
    if not REFERENCE_PATH.exists():
        raise FileNotFoundError(
            f"위험점수 기준분포 파일을 찾을 수 없습니다: {REFERENCE_PATH}"
        )

    reference_df = pd.read_csv(
        REFERENCE_PATH,
        encoding="utf-8-sig",
    )

    if "risk_score" not in reference_df.columns:
        raise ValueError(
            "business_risk_reference.csv에 "
            "'risk_score' 컬럼이 없습니다."
        )

    reference_scores = pd.to_numeric(
        reference_df["risk_score"],
        errors="coerce",
    ).dropna()

    if reference_scores.empty:
        raise ValueError(
            "business_risk_reference.csv에 "
            "사용 가능한 위험점수가 없습니다."
        )

    return np.sort(reference_scores.to_numpy(dtype=float))


METADATA = _load_metadata()
MODEL = _load_model()
REFERENCE_SCORES = _load_reference_scores()


# metadata에 저장된 값을 우선 사용
FEATURE_COLS = METADATA.get(
    "feature_cols",
    DEFAULT_FEATURE_COLS,
)

CATEGORICAL_COLS = METADATA.get(
    "categorical_cols",
    DEFAULT_CATEGORICAL_COLS,
)

DATA_AS_OF = METADATA.get(
    "data_as_of",
    "2026-07-20",
)

MODEL_VERSION = METADATA.get(
    "model_version",
    MODEL_VERSION,
)


# CatBoost 모델 내부에 변수명이 저장되어 있으면 최우선 사용
if getattr(MODEL, "feature_names_", None):
    model_feature_names = list(MODEL.feature_names_)

    if model_feature_names:
        FEATURE_COLS = model_feature_names


# ============================================================
# 5. 입력값 전처리
# ============================================================

def _prepare_features(features: dict[str, Any]) -> pd.DataFrame:
    """
    dict 형태의 업체 특성을 CatBoost 입력 DataFrame으로 변환한다.
    """

    if not isinstance(features, dict):
        raise TypeError(
            "features는 dict 형식이어야 합니다."
        )

    row: dict[str, Any] = {}

    for col in FEATURE_COLS:
        value = features.get(col)

        if col in CATEGORICAL_COLS:
            if value is None or pd.isna(value):
                row[col] = "unknown"
            else:
                row[col] = str(value)

        else:
            row[col] = pd.to_numeric(
                value,
                errors="coerce",
            )

    input_df = pd.DataFrame(
        [row],
        columns=FEATURE_COLS,
    )

    # 범주형 변수는 반드시 문자열로 통일
    for col in CATEGORICAL_COLS:
        if col in input_df.columns:
            input_df[col] = (
                input_df[col]
                .fillna("unknown")
                .astype(str)
            )

    return input_df


# ============================================================
# 6. 위험점수 → 백분위 변환
# ============================================================

def _score_to_percentile(risk_score: float) -> float:
    """
    기준집단 위험점수 중 현재 점수 이하의 비율을 계산한다.

    예:
    percentile 90 → 기준집단의 약 90%보다 위험점수가 높음
    """

    position = np.searchsorted(
        REFERENCE_SCORES,
        risk_score,
        side="right",
    )

    percentile = (
        position / len(REFERENCE_SCORES)
    ) * 100

    return round(
        float(np.clip(percentile, 0, 100)),
        1,
    )


# ============================================================
# 7. 위험등급 생성
# ============================================================

def _make_risk_level(
    percentile: float,
) -> str:
    if percentile < RISK_LEVEL_THRESHOLDS["low"]:
        return "low"

    if percentile < RISK_LEVEL_THRESHOLDS["normal"]:
        return "normal"

    if percentile < RISK_LEVEL_THRESHOLDS["caution"]:
        return "caution"

    return "check_required"


# ============================================================
# 8. 위험요인 문장 생성
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None or pd.isna(value):
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def _make_risk_factors(
    features: dict[str, Any],
    percentile: float,
) -> list[str]:
    factors: list[str] = []

    # 최종 상대위험이 낮으면 개별 위험조건을 과도하게 노출하지 않음
    if percentile < 30:
        return [
            "공개 인허가 및 지역 영업이력 기준 상대위험이 낮은 구간"
        ]

    same_address_count = _safe_float(
        features.get("same_address_history_count")
    )

    prior_3y_pressure = _safe_float(
        features.get("prior_3y_closure_pressure")
    )

    close_to_open_ratio = _safe_float(
        features.get("prior_3y_close_to_open_ratio")
    )

    prior_1y_close_count = _safe_float(
        features.get("prior_1y_local_close_count")
    )

    local_net_change = _safe_float(
        features.get("local_net_change_1y")
    )

    if same_address_count >= 1:
        factors.append(
            f"동일 주소의 과거 폐업 이력 {int(same_address_count)}건"
        )

    if prior_3y_pressure >= 0.30:
        factors.append(
            "개업 당시 지역의 최근 3년 폐업 압력이 높은 편"
        )

    if close_to_open_ratio >= 0.50:
        factors.append(
            "개업 당시 지역의 최근 3년 개업 대비 폐업 비율이 높은 편"
        )

    if prior_1y_close_count >= 5:
        factors.append(
            "개업 전 1년간 해당 지역의 폐업 업체 수가 많은 편"
        )

    if local_net_change < 0:
        factors.append(
            "개업 당시 지역의 최근 1년 업체 수가 감소세"
        )

    if percentile >= 90:
        factors.insert(
            0,
            "동일 업종 기준 상대위험 상위 10% 구간"
        )
    elif percentile >= 70:
        factors.insert(
            0,
            "동일 업종 기준 상대위험 상위 30% 구간"
        )
    else:
        factors.insert(
            0,
            "동일 업종 기준 상대위험이 중간 수준인 구간"
        )

    return factors[:4]


# ============================================================
# 9. 최종 예측 함수
# ============================================================

def predict(
    features: dict[str, Any],
) -> dict[str, Any]:
    """
    업체 특성 dict를 입력받아 상대위험 결과를 반환한다.

    Parameters
    ----------
    features:
        CatBoost 모델 입력 변수들이 포함된 dict

    Returns
    -------
    dict
        risk_score
        relative_risk_percentile
        risk_level
        risk_factors
        model_version
        data_as_of
        disclaimer
    """

    input_df = _prepare_features(features)

    probability = MODEL.predict_proba(
        input_df
    )[0, 1]

    risk_score = round(
        float(probability),
        6,
    )

    percentile = _score_to_percentile(
        risk_score
    )

    risk_level = _make_risk_level(
        percentile
    )

    risk_factors = _make_risk_factors(
        features=features,
        percentile=percentile,
    )

    return {
        "risk_score": risk_score,
        "relative_risk_percentile": percentile,
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "model_version": MODEL_VERSION,
        "data_as_of": DATA_AS_OF,
        "disclaimer": DISCLAIMER,
    }


# ============================================================
# 10. 직접 실행 테스트
# ============================================================

if __name__ == "__main__":
    sample_features = {
        "sido": "서울특별시",
        "sigungu": "강남구",
        "공사립구분명": "사립",

        "open_year": 2022,
        "open_month": 3,
        "open_quarter": 1,

        "소재지면적": 420.0,
        "사무실면적": 20.0,
        "지도자수": 3,
        "탈의실면적": 40.0,
        "휴게실면적": 10.0,

        "same_address_history_count": 1,

        "prior_1y_local_open_count": 10,
        "prior_1y_local_close_count": 5,
        "prior_3y_local_open_count": 30,
        "prior_3y_local_close_count": 15,

        "prior_3y_close_to_open_ratio": 0.5,
        "prior_3y_closure_pressure": 0.33,

        "local_active_at_open": 80,
        "local_net_change_1y": 5,

        "log_local_active_at_open": np.log1p(80),
        "log_prior_1y_open_count": np.log1p(10),
        "log_prior_1y_close_count": np.log1p(5),
        "log_prior_3y_open_count": np.log1p(30),
        "log_prior_3y_close_count": np.log1p(15),
    }

    result = predict(sample_features)

    print("\n예측 결과")
    print(json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    ))