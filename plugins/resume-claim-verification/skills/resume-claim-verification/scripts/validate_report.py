#!/usr/bin/env python3
"""Validate and normalize resume claim verification report JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


ASSESSMENTS = {
    "Supported",
    "Plausible but unverified",
    "Needs clarification",
    "Material inconsistency",
    "Not assessable",
}
CONFIDENCE_LEVELS = {"High", "Medium", "Low"}
OVERALL_CONCLUSIONS = {
    "No material issues found",
    "Clarification recommended",
    "Human review recommended",
    "Insufficient evidence",
}

TOP_LEVEL_FIELDS = {
    "report_version",
    "candidate_label",
    "review_date",
    "reviewed_inputs",
    "overall_conclusion",
    "summary",
    "claims",
    "sources",
    "limitations",
}
CLAIM_FIELDS = {
    "id",
    "category",
    "claim",
    "assessment",
    "confidence",
    "observations",
    "inference",
    "evidence",
    "alternative_explanations",
    "follow_up_questions",
    "next_step",
}
EVIDENCE_FIELDS = {"source", "finding", "url"}
SOURCE_FIELDS = {"label", "url", "accessed"}

PROHIBITED_KEY_PARTS = {
    "fake",
    "fraud",
    "score",
    "hire",
    "ranking",
    "race",
    "ethnicity",
    "religion",
    "gender",
    "sex",
    "disability",
    "pregnancy",
    "national_origin",
    "marital_status",
    "sexual_orientation",
}
PROHIBITED_CONCLUSION_PATTERNS = (
    re.compile(r"\b(?:resume|candidate|experience|project)\s+is\s+fake\b", re.I),
    re.compile(r"\b(?:candidate|person|applicant)\s+(?:lied|is\s+(?:a\s+)?liar)\b", re.I),
    re.compile(r"\bcommitted\s+fraud\b", re.I),
    re.compile(r"\b(?:do\s+not|don't)\s+hire\b", re.I),
    re.compile(r"\b(?:hire|reject)\s+(?:the\s+)?candidate\b", re.I),
)

STANDARD_LIMITATIONS = [
    "Finding nothing online does not mean the claim is false.",
    "Private or confidential work may be impossible to confirm from public sources.",
    "A matching name or profile may belong to someone else.",
    "This report does not prove that anyone lied or committed fraud. A person must make every hiring decision.",
]


class ReportValidationError(ValueError):
    """Raised when a report violates the schema or safety contract."""


def _require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportValidationError(f"{path} must be an object")
    return value


def _reject_unknown_fields(obj: dict[str, Any], allowed: set[str], path: str) -> None:
    unknown = set(obj) - allowed
    if unknown:
        raise ReportValidationError(f"{path} contains unknown fields: {sorted(unknown)}")


def _reject_prohibited_keys(value: Any, path: str = "report") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower().replace("-", "_")
            if any(part in normalized for part in PROHIBITED_KEY_PARTS):
                raise ReportValidationError(f"{path}.{key} is a prohibited decision or sensitive field")
            _reject_prohibited_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_prohibited_keys(item, f"{path}[{index}]")


def _required_text(obj: dict[str, Any], key: str, path: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReportValidationError(f"{path}.{key} must be a non-empty string")
    return value.strip()


def _string_list(obj: dict[str, Any], key: str, path: str, *, allow_empty: bool = True) -> list[str]:
    value = obj.get(key)
    if not isinstance(value, list) or (not allow_empty and not value):
        qualifier = "a non-empty list" if not allow_empty else "a list"
        raise ReportValidationError(f"{path}.{key} must be {qualifier} of strings")
    cleaned: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ReportValidationError(f"{path}.{key}[{index}] must be a non-empty string")
        cleaned.append(item.strip())
    return cleaned


def _check_prohibited_conclusion(text: str, path: str) -> None:
    for pattern in PROHIBITED_CONCLUSION_PATTERNS:
        if pattern.search(text):
            raise ReportValidationError(f"{path} contains a prohibited hiring or fraud determination")


def _validate_evidence(raw: Any, path: str) -> dict[str, str]:
    item = _require_object(raw, path)
    _reject_unknown_fields(item, EVIDENCE_FIELDS, path)
    result = {
        "source": _required_text(item, "source", path),
        "finding": _required_text(item, "finding", path),
    }
    if "url" in item:
        result["url"] = _required_text(item, "url", path)
    return result


def _validate_source(raw: Any, path: str) -> dict[str, str]:
    item = _require_object(raw, path)
    _reject_unknown_fields(item, SOURCE_FIELDS, path)
    result = {"label": _required_text(item, "label", path)}
    for key in ("url", "accessed"):
        if key in item:
            result[key] = _required_text(item, key, path)
    return result


def validate_and_normalize_report(raw: Any) -> dict[str, Any]:
    report = _require_object(raw, "report")
    _reject_prohibited_keys(report)
    _reject_unknown_fields(report, TOP_LEVEL_FIELDS, "report")

    result: dict[str, Any] = {
        "report_version": _required_text(report, "report_version", "report"),
        "candidate_label": _required_text(report, "candidate_label", "report"),
        "review_date": _required_text(report, "review_date", "report"),
        "reviewed_inputs": _string_list(report, "reviewed_inputs", "report", allow_empty=False),
        "overall_conclusion": _required_text(report, "overall_conclusion", "report"),
        "summary": _required_text(report, "summary", "report"),
    }
    if result["report_version"] != "1.0":
        raise ReportValidationError("report.report_version must be '1.0'")
    try:
        date.fromisoformat(result["review_date"])
    except ValueError as exc:
        raise ReportValidationError("report.review_date must use YYYY-MM-DD") from exc
    if result["overall_conclusion"] not in OVERALL_CONCLUSIONS:
        raise ReportValidationError(
            f"report.overall_conclusion must be one of {sorted(OVERALL_CONCLUSIONS)}"
        )
    _check_prohibited_conclusion(result["summary"], "report.summary")

    raw_claims = report.get("claims")
    if not isinstance(raw_claims, list) or not raw_claims:
        raise ReportValidationError("report.claims must be a non-empty list")
    claims: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_claim in enumerate(raw_claims):
        path = f"report.claims[{index}]"
        claim = _require_object(raw_claim, path)
        _reject_unknown_fields(claim, CLAIM_FIELDS, path)
        normalized = {
            "id": _required_text(claim, "id", path),
            "category": _required_text(claim, "category", path),
            "claim": _required_text(claim, "claim", path),
            "assessment": _required_text(claim, "assessment", path),
            "confidence": _required_text(claim, "confidence", path),
            "observations": _string_list(claim, "observations", path),
            "inference": _required_text(claim, "inference", path),
            "alternative_explanations": _string_list(claim, "alternative_explanations", path),
            "follow_up_questions": _string_list(claim, "follow_up_questions", path),
            "next_step": _required_text(claim, "next_step", path),
        }
        if normalized["id"] in seen_ids:
            raise ReportValidationError(f"duplicate claim id: {normalized['id']}")
        seen_ids.add(normalized["id"])
        if normalized["assessment"] not in ASSESSMENTS:
            raise ReportValidationError(f"{path}.assessment must be one of {sorted(ASSESSMENTS)}")
        if normalized["confidence"] not in CONFIDENCE_LEVELS:
            raise ReportValidationError(
                f"{path}.confidence must be one of {sorted(CONFIDENCE_LEVELS)}"
            )
        _check_prohibited_conclusion(normalized["inference"], f"{path}.inference")
        raw_evidence = claim.get("evidence")
        if not isinstance(raw_evidence, list):
            raise ReportValidationError(f"{path}.evidence must be a list")
        normalized["evidence"] = [
            _validate_evidence(item, f"{path}.evidence[{evidence_index}]")
            for evidence_index, item in enumerate(raw_evidence)
        ]
        if normalized["assessment"] == "Supported" and not normalized["evidence"]:
            raise ReportValidationError(f"{path}: Supported claims require evidence")
        if normalized["assessment"] in {"Needs clarification", "Material inconsistency"}:
            if not normalized["follow_up_questions"]:
                raise ReportValidationError(f"{path}: flagged claims require follow-up questions")
            if not normalized["alternative_explanations"]:
                raise ReportValidationError(f"{path}: flagged claims require alternative explanations")
        claims.append(normalized)
    result["claims"] = claims

    raw_sources = report.get("sources")
    if not isinstance(raw_sources, list):
        raise ReportValidationError("report.sources must be a list")
    result["sources"] = [
        _validate_source(item, f"report.sources[{index}]") for index, item in enumerate(raw_sources)
    ]
    result["limitations"] = _string_list(report, "limitations", "report")
    for limitation in STANDARD_LIMITATIONS:
        if limitation not in result["limitations"]:
            result["limitations"].append(limitation)

    counts = Counter(claim["assessment"] for claim in claims)
    result["counts"] = {assessment: counts.get(assessment, 0) for assessment in sorted(ASSESSMENTS)}
    total = len(claims)
    ordered_assessments = sorted(ASSESSMENTS)
    raw_percentages = {
        assessment: 100 * counts.get(assessment, 0) / total
        for assessment in ordered_assessments
    }
    percentages = {assessment: int(raw_percentages[assessment]) for assessment in ordered_assessments}
    remaining_points = 100 - sum(percentages.values())
    remainder_order = sorted(
        ordered_assessments,
        key=lambda assessment: (raw_percentages[assessment] - percentages[assessment], assessment),
        reverse=True,
    )
    for assessment in remainder_order[:remaining_points]:
        percentages[assessment] += 1
    result["percentages"] = percentages
    return result


def load_and_validate(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        return validate_and_normalize_report(json.load(stream))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to the report JSON")
    parser.add_argument("--normalized-json", help="Optional path for normalized JSON output")
    args = parser.parse_args()
    try:
        report = load_and_validate(args.input)
    except (OSError, json.JSONDecodeError, ReportValidationError) as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1
    if args.normalized_json:
        output = Path(args.normalized_json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Valid report: {len(report['claims'])} claims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
