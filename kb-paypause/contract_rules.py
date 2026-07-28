"""[B 소유] contract_rules.py

contract_data와 config/contract_rules.json을 바탕으로
계약서 위험조항 및 확인 필요사항을 탐지한다.
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
    if not isinstance(value, str):
        return ""

    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\u00a0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)

    return value.strip()


def _split_clauses(text: str) -> list[str]:
    """PDF 줄바꿈으로 문장이 중간에 잘리지 않도록 문장 단위로 분리한다."""
    if not text:
        return []

    merged = re.sub(r"\s*\n\s*", " ", text)
    parts = re.split(
        r"(?<=[.!?。])\s+|(?=\s*제\s*\d+\s*조)",
        merged,
    )

    clauses = []

    for part in parts:
        clause = re.sub(r"\s+", " ", part).strip(" -ㆍ·")

        if clause:
            clauses.append(clause)

    return clauses


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized_text = re.sub(r"\s+", "", text).lower()
    normalized_keyword = re.sub(r"\s+", "", keyword).lower()

    return normalized_keyword in normalized_text


def _find_keyword_evidence(
    clauses: list[str],
    keywords: list[str],
    required_context: Optional[list[str]] = None,
) -> tuple[Optional[str], Optional[str]]:
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
    return {
        "code": rule.get("code"),
        "title": rule.get("title"),
        "severity": rule.get("severity"),
        "rule_type": rule.get("rule_type"),
        "description": rule.get("description"),
        "evidence": evidence,
        "evidence_source": evidence_source,
        "matched_keyword": matched_keyword,
        "reference_documents": rule.get("reference_documents", []),
        "reference_summary": rule.get("reference_summary"),
        "output_limit": rule.get("output_limit"),
    }


def _analyze_normal_price_deduction(
    rule: dict,
    contract_data: dict,
    clauses: list[str],
) -> Optional[dict]:
    evidence, keyword = _find_keyword_evidence(
        clauses,
        rule.get("keywords", []),
        required_context=[
            "환불",
            "환급",
            "해지",
            "공제",
            "이용대금",
            "사용기간",
        ],
    )

    if evidence:
        return _make_result(rule, evidence, keyword)

    if (
        contract_data.get("refund_base") == "normal_price"
        and contract_data.get("raw_text")
    ):
        evidence, keyword = _find_keyword_evidence(
            clauses,
            [
                "정상가",
                "정상가격",
                "정가",
                "할인 전 가격",
                "할인 전 정상가",
            ],
            required_context=[
                "환불",
                "환급",
                "해지",
                "공제",
                "사용기간",
                "이용한 횟수",
            ],
        )

        if evidence:
            return _make_result(rule, evidence, keyword)

    return None


def _analyze_penalty_excess(
    rule: dict,
    contract_data: dict,
    clauses: list[str],
) -> Optional[dict]:
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
    keywords = rule.get("keywords", [])

    if not keywords:
        return None

    evidence, keyword = _find_keyword_evidence(
        clauses,
        keywords,
        required_context=rule.get("required_context"),
    )

    if evidence is None:
        return None

    return _make_result(rule, evidence, keyword)


def _analyze_multiple_deduction(
    rule: dict,
    clauses: list[str],
) -> Optional[dict]:
    deduction_groups = rule.get("deduction_groups", {})
    minimum_groups = int(rule.get("minimum_groups", 2))

    for clause in clauses:
        has_refund_context = any(
            _contains_keyword(clause, keyword)
            for keyword in ["환불", "환급", "공제"]
        )

        if not has_refund_context:
            continue

        matched_groups = []

        for group_name, keywords in deduction_groups.items():
            if any(
                _contains_keyword(clause, keyword)
                for keyword in keywords
            ):
                matched_groups.append(group_name)

        if len(matched_groups) >= minimum_groups:
            return _make_result(
                rule,
                evidence=clause,
                matched_keyword=", ".join(matched_groups),
            )

    return None


def _analyze_closure_refund_restriction(
    rule: dict,
    contract_data: dict,
    clauses: list[str],
) -> Optional[dict]:
    evidence, keyword = _find_keyword_evidence(
        clauses,
        rule.get("keywords", []),
        required_context=[
            "폐업",
            "휴업",
            "영업 중단",
            "지점 이전",
        ],
    )

    if evidence:
        return _make_result(rule, evidence, keyword)

    if contract_data.get("closure_refund_clause") is False:
        evidence, keyword = _find_keyword_evidence(
            clauses,
            [
                "현금 환불",
                "환불을 요구할 수 없다",
                "환급을 요구할 수 없다",
                "환불 불가",
                "환급 불가",
            ],
            required_context=[
                "폐업",
                "휴업",
                "영업 중단",
                "지점 이전",
            ],
        )

        if evidence:
            return _make_result(rule, evidence, keyword)

    return None


def _analyze_guarantee_insurance_disclosure(
    rule: dict,
    clauses: list[str],
) -> Optional[dict]:
    evidence, matched_keyword = _find_keyword_evidence(
        clauses,
        rule.get("keywords", []),
    )

    if evidence is None:
        return None

    full_text = " ".join(clauses)
    has_detail = any(
        _contains_keyword(full_text, detail)
        for detail in rule.get("detail_keywords", [])
    )

    if has_detail:
        return None

    return _make_result(rule, evidence, matched_keyword)


KEYWORD_RULE_CODES = {
    "NON_REFUNDABLE",
    "PT_NORMAL_PRICE_DEDUCTION",
    "REFUND_DEFICIT_ADDITIONAL_PAYMENT",
    "REFUND_APPLICATION_RESTRICTION",
    "SUSPENSION_REASON_RESTRICTION",
    "TRAINER_CHANGE_NO_REFUND",
    "BUSINESS_LIABILITY_EXEMPTION",
    "UNILATERAL_TERMINATION_NO_REFUND",
    "EXCLUSIVE_JURISDICTION",
    "CONTRACT_TERMS_NOT_PROVIDED",
    "SESSION_DEDUCTION_CHECK",
}


def analyze(contract_data: dict) -> list[dict]:
    if not isinstance(contract_data, dict):
        return []

    raw_text = _normalize_text(contract_data.get("raw_text"))
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

        elif code == "MULTIPLE_DEDUCTION":
            result = _analyze_multiple_deduction(
                rule,
                clauses,
            )

        elif code == "CLOSURE_CASH_REFUND_RESTRICTION":
            result = _analyze_closure_refund_restriction(
                rule,
                contract_data,
                clauses,
            )

        elif code in KEYWORD_RULE_CODES:
            result = _analyze_keyword_rule(
                rule,
                clauses,
            )

        elif code == "GUARANTEE_INSURANCE_NOT_DISCLOSED":
            result = _analyze_guarantee_insurance_disclosure(
                rule,
                clauses,
            )

        if result is not None:
            results.append(result)

    return results