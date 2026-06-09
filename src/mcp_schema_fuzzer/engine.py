from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .generator import generate_cases
from .models import Finding, FuzzCase, Suite
from .suite import load_examples, load_transcripts
from .utils import get_in_path, max_severity, set_in_path, stable_signature


def _finding(
    severity: str,
    code: str,
    message: str,
    target: str,
    case: Optional[FuzzCase] = None,
    **details: Any,
) -> Finding:
    return Finding(
        severity=severity,
        code=code,
        message=message,
        target=target,
        case_id=case.id if case else None,
        category=case.category if case else None,
        details=details,
    )


def _request_matches_case(case: FuzzCase, request: Any) -> bool:
    if request == case.payload:
        return True
    if case.category != "overlong-text":
        return False
    try:
        expected_text = get_in_path(case.payload, case.path)
        actual_text = get_in_path(request, case.path)
    except Exception:
        return False
    if not isinstance(expected_text, str) or not isinstance(actual_text, str):
        return False
    expected_shape = set_in_path(case.payload, case.path, "__TEXT__")
    actual_shape = set_in_path(request, case.path, "__TEXT__")
    if expected_shape != actual_shape:
        return False
    return len(actual_text) >= len(expected_text)


def run_fuzz(suite: Suite) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "suite": suite.name,
        "description": suite.description,
        "metadata": suite.metadata,
        "targets": [],
        "cases": [],
        "findings": [],
        "counts": {},
    }

    all_findings: List[Finding] = []
    all_cases: List[FuzzCase] = []

    for target in suite.targets:
        schema = _load_schema(target.schema_path)
        examples = load_examples(target.examples_path) if target.examples_path else []
        cases = generate_cases(target.id, schema, examples)
        transcripts = load_transcripts(target.transcripts_path) if target.transcripts_path else []
        findings = analyze_target(target.id, cases, transcripts)
        all_cases.extend(cases)
        all_findings.extend(findings)
        report["targets"].append(
            {
                "id": target.id,
                "kind": target.kind,
                "schema_uri": _path_uri(target.schema_path, suite.root),
                "examples_uri": _path_uri(target.examples_path, suite.root) if target.examples_path else None,
                "transcripts_uri": _path_uri(target.transcripts_path, suite.root) if target.transcripts_path else None,
                "metadata": target.metadata,
                "case_count": len(cases),
                "finding_count": len(findings),
            }
        )

    report["cases"] = [serialize_case(case) for case in all_cases]
    report["findings"] = [serialize_finding(finding) for finding in all_findings]
    report["counts"] = summarize_report_counts(all_cases, all_findings)
    return report


def _load_schema(path):
    from .utils import load_json

    return load_json(path)


def _path_uri(path: Path, fallback_base: Path) -> str:
    resolved = path.resolve()
    for base in (Path.cwd().resolve(), fallback_base.resolve()):
        try:
            return resolved.relative_to(base).as_posix()
        except ValueError:
            continue
    return resolved.as_posix()


def analyze_target(target_id: str, cases: List[FuzzCase], transcripts) -> List[Finding]:
    findings: List[Finding] = []
    transcripts_by_case = defaultdict(list)
    for entry in transcripts:
        transcripts_by_case[entry.case_id].append(entry)

    case_family_signatures = defaultdict(set)

    for case in cases:
        entries = transcripts_by_case.get(case.id, [])
        if not entries:
            findings.append(
                _finding(
                    "warning",
                    "missing_transcript",
                    f"No transcript entry recorded for generated case `{case.id}`.",
                    target_id,
                    case,
                )
            )
            continue

        signatures = set()
        matched_request = False
        for entry in entries:
            if _request_matches_case(case, entry.request):
                matched_request = True
            signature = stable_signature(entry.response)
            signatures.add(signature)
            case_family_signatures[(case.category, case.path)].add(signature)
            if entry.response.get("ok") is True:
                findings.append(
                    _finding(
                        "error",
                        "invalid_input_accepted",
                        "Transcript shows the target accepted an invalid fuzz case.",
                        target_id,
                        case,
                        transcript_source=entry.source,
                    )
                )
            elif not isinstance(entry.response.get("error"), dict):
                findings.append(
                    _finding(
                        "warning",
                        "error_shape_missing",
                        "Transcript rejected the case but did not provide a structured error object.",
                        target_id,
                        case,
                    )
                )

        if not matched_request:
            findings.append(
                _finding(
                    "warning",
                    "request_mismatch",
                    "Transcript request payload does not match the generated fuzz case payload.",
                    target_id,
                    case,
                )
            )

        if len(signatures) > 1:
            findings.append(
                _finding(
                    "error",
                    "unstable_case_response",
                    "Repeated transcript entries for the same case do not share a stable response signature.",
                    target_id,
                    case,
                    signatures=sorted(signatures),
                )
            )

    for (category, path), signatures in case_family_signatures.items():
        error_signatures = {signature for signature in signatures if signature != "ok"}
        if len(error_signatures) > 1:
            findings.append(
                Finding(
                    severity="warning",
                    code="unstable_case_family_signature",
                    message=f"Case family `{category}` at path `{path}` produces multiple error signatures for target `{target_id}`.",
                    target=target_id,
                    category=category,
                    details={"path": path, "signatures": sorted(error_signatures)},
                )
            )

    return findings


def serialize_case(case: FuzzCase) -> Dict[str, Any]:
    return {
        "id": case.id,
        "target": case.target,
        "category": case.category,
        "severity": case.severity,
        "path": case.path,
        "variant": case.variant,
        "payload": case.payload,
        "rationale": case.rationale,
        "source_example": case.source_example,
        "tags": case.tags,
    }


def serialize_finding(finding: Finding) -> Dict[str, Any]:
    return {
        "severity": finding.severity,
        "code": finding.code,
        "message": finding.message,
        "target": finding.target,
        "case_id": finding.case_id,
        "category": finding.category,
        "details": finding.details,
    }


def summarize_report_counts(cases: List[FuzzCase], findings: List[Finding]) -> Dict[str, Any]:
    warning_count = sum(1 for finding in findings if finding.severity == "warning")
    error_count = sum(1 for finding in findings if finding.severity == "error")
    categories = sorted({case.category for case in cases})
    highest = max_severity([finding.severity for finding in findings], default="warning" if findings else "none")
    return {
        "cases": len(cases),
        "findings": len(findings),
        "warnings": warning_count,
        "errors": error_count,
        "categories": categories,
        "highest_severity": highest,
    }
