"""[B 소유] contract_rules.py

contract_data와 config/contract_rules.json을 바탕으로
계약서 위험조항 및 확인 필요사항을 탐지한다.

작성 원칙
---------
1. config에 등록된 구현 대상 규칙만 사용한다.
2. 계약서 원문에서 발견된 문장을 evidence로 반환한다.
3. 확인되지 않은 내용을 임의로 위험하다고 판단하지 않는다.
4. 법률적 확정 판단이 아니라 공식자료에 근거한 위험 신호를 제공한다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional


CONFIG_PATH = (
    Path(__file__).resolve().parent
    / "config"
    / "contract_rules.json"
)


def _load_rules() -> list[dict]:
    """config/contract_rules.json에서 구현 대상 규칙을 불러온다."""
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"계약 위험규칙 파일을 찾을 수 없습니다: {CONFIG_PATH}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"계약 위험규칙 JSON 형식이 잘못되었습니다: {exc}"
        ) from exc

    rules = config.get("rules", [])

    if not isinstance(rules, list):
        raise ValueError(
            "config/contract_rules.json의 rules는 리스트여야 합니다."
        )

    return rules


def _normalize_text(value: Any) -> str:
    """비교용으로 텍스트 공백을 정리한다."""
    if not isinstance(value, str):
        return ""

    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\u00a0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)

    return value.strip()


def _split_clauses(text: str) -> list[str]:
    """OCR 원문을 증거로 제시할 수 있는 문장·조항 단위로 나눈다."""
    if not text:
        return []

    parts = re.split(
        r"(?<=[.!?。])\s+|\n+|(?=\s*제\d+\s*조)",
        text,
    )

    clauses = []

    for part in parts:
        clause = re.sub(r"\s+", " ", part).strip(" -ㆍ·")

        if clause:
            clauses.append(clause)

    return clauses


def _contains_keyword(text: str, keyword: str) -> bool:
    """공백 차이를 일부 허용하여 키워드 포함 여부를 확인한다."""
    normalized_text = re.sub(r"\s+", "", text).lower()
    normalized_keyword = re.sub(r"\s+", "", keyword).lower()

    return normalized_keyword in normalized_text


def _find_keyword_evidence(
    clauses: list[str],
    keywords: list[str],
    required_context: Optional[list[str]] = None,
) -> tuple[Optional[str], Optional[str]]:
    """키워드가 들어 있는 실제 원문 조항과 키워드를 반환한다."""
    for clause in clauses:
        matched_keyword = next(
            (
                keyword
                for keyword in keywords
                if _contains_keyword(clause, keyword)
            ),
            None,
        )

        if matched_keyword is None:
            continue

        if required_context:
            has_context = any(
                _contains_keyword(clause, context)
                for context in required_context
            )

            if not has_context:
                continue

        return clause, matched_keyword

    return None, None


def _to_float(value: Any) -> Optional[float]:
    """bool을 제외하고 값을 안전하게 실수로 변환한다."""
    if value is None or isinstance(value, bool):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _make_result(
    rule: dict,
    evidence: str,
    matched_keyword: Optional[str] = None,
    evidence_source: str = "contract_text",
) -> dict:
    """공통 위험항목 반환 형식을 만든다."""
    return {
        "code": rule.get("code"),
        "title": rule.get("title"),
        "severity": rule.get("severity"),
        "rule_type": rule.get("rule_type"),
        "description": rule.get("description"),
        "evidence": evidence,
        "evidence_source": evidence_source,
        "matched_keyword": matched_keyword,
        "reference_documents": rule.get(
            "reference_documents",
            [],
        ),
        "reference_summary": rule.get(
            "reference_summary"
        ),
        "output_limit": rule.get("output_limit"),
    }


def _analyze_normal_price_deduction(
    rule: dict,
    contract_data: dict,
    clauses: list[str],
) -> Optional[dict]:
    """정상가가 중도해지 환급 공제 기준으로 사용되는지 확인한다."""
    keywords = rule.get("keywords", [])

    evidence, keyword = _find_keyword_evidence(
        clauses,
        keywords,
        required_context=[
            "환불",
            "환급",
            "해지",
            "공제",
            "이용대금",
        ],
    )

    if evidence:
        return _make_result(rule, evidence, keyword)

    # parser가 환급 공제 기준을 normal_price로 판정했지만
    # 금액 등이 중간에 있어 설정 키워드가 그대로 일치하지 않는 경우
    if (
        contract_data.get("refund_base") == "normal_price"
        and contract_data.get("raw_text")
    ):
        normal_price_keywords = [
            "정상가",
            "정상가격",
            "정가",
            "할인 전 가격",
        ]

        evidence, keyword = _find_keyword_evidence(
            clauses,
            normal_price_keywords,
        )

        if evidence:
            return _make_result(rule, evidence, keyword)

    return None


def _analyze_penalty_excess(
    rule: dict,
    contract_data: dict,
    clauses: list[str],
) -> Optional[dict]:
    """계약서에 기재된 위약금률이 기준을 초과하는지 확인한다."""
    threshold = rule.get("threshold", {})
    field = threshold.get("field")
    operator = threshold.get("operator")
    limit = _to_float(threshold.get("value"))
    value = _to_float(contract_data.get(field))

    if value is None or limit is None:
        return None

    if operator != "greater_than" or value <= limit:
        return None

    evidence, keyword = _find_keyword_evidence(
        clauses,
        rule.get("keywords", []),
    )

    if evidence:
        return _make_result(rule, evidence, keyword)

    # 원문 없이 사용자가 직접 구조화 값을 입력한 경우
    return _make_result(
        rule,
        evidence=f"입력된 위약금률: {value:g}%",
        matched_keyword=None,
        evidence_source="structured_input",
    )


def _analyze_keyword_rule(
    rule: dict,
    clauses: list[str],
) -> Optional[dict]:
    """일반 키워드 규칙을 실제 계약서 원문에서 탐지한다."""
    keywords = rule.get("keywords", [])

    if not keywords:
        return None

    evidence, keyword = _find_keyword_evidence(
        clauses,
        keywords,
    )

    if evidence is None:
        return None

    return _make_result(rule, evidence, keyword)


def analyze(contract_data: dict) -> list[dict]:
    """계약서 위험조항 및 확인 필요사항을 반환한다.

    Parameters
    ----------
    contract_data:
        contract_parser.parse()가 반환한 공통 계약 데이터.

    Returns
    -------
    list[dict]
        final_fusion.py에서 사용할 위험항목 목록.
    """
    if not isinstance(contract_data, dict):
        return []

    raw_text = _normalize_text(
        contract_data.get("raw_text")
    )
    clauses = _split_clauses(raw_text)
    results = []

    for rule in _load_rules():
        code = rule.get("code")
        result = None

        if code == "NORMAL_PRICE_DEDUCTION":
            result = _analyze_normal_price_deduction(
                rule,
                contract_data,
                clauses,
            )

        elif code == "PENALTY_EXCESS":
            result = _analyze_penalty_excess(
                rule,
                contract_data,
                clauses,
            )

        elif code in {
            "NON_REFUNDABLE",
            "BUSINESS_LIABILITY_EXEMPTION",
            "CONTRACT_TERMS_NOT_PROVIDED",
            "SESSION_DEDUCTION_CHECK",
        }:
            result = _analyze_keyword_rule(
                rule,
                clauses,
            )

        # config에 규칙이 추가되어도 코드가 지원하지 않으면
        # 임의 판단하지 않고 건너뛴다.
        if result is not None:
            results.append(result)

    return results