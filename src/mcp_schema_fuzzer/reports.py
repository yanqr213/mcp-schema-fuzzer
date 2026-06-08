from __future__ import annotations

import datetime as _dt
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List

from . import __version__
from .utils import dump_json, normalize_json, severity_rank, write_text


def write_report_bundle(report: Dict[str, Any], output_base: Path) -> Dict[str, str]:
    json_path = output_base.with_suffix(".json")
    md_path = output_base.with_suffix(".md")
    xml_path = output_base.with_suffix(".xml")
    sarif_path = output_base.with_suffix(".sarif")
    dump_json(report, json_path)
    write_text(md_path, render_markdown(report))
    write_text(xml_path, render_junit(report))
    write_text(sarif_path, render_sarif(report))
    return {"json": str(json_path), "markdown": str(md_path), "junit": str(xml_path), "sarif": str(sarif_path)}


def render_markdown(report: Dict[str, Any]) -> str:
    counts = report["counts"]
    lines = [
        f"# Fuzz Report: {report['suite']}",
        "",
        f"- Generated cases: {counts['cases']}",
        f"- Findings: {counts['findings']}",
        f"- Errors: {counts['errors']}",
        f"- Warnings: {counts['warnings']}",
        f"- Highest severity: {counts['highest_severity']}",
        "",
        "## Targets",
        "",
    ]
    for target in report["targets"]:
        lines.append(f"- `{target['id']}` ({target['kind']}): {target['case_count']} cases, {target['finding_count']} findings")
    lines.extend(["", "## Findings", ""])
    findings = sorted(report["findings"], key=lambda item: (-severity_rank(item["severity"]), item["target"], item.get("case_id") or ""))
    if not findings:
        lines.append("- No findings. All generated cases have matching rejecting transcripts.")
    for finding in findings:
        case_text = f" case `{finding['case_id']}`" if finding.get("case_id") else ""
        lines.append(f"- [{finding['severity']}] `{finding['code']}` on `{finding['target']}`{case_text}: {finding['message']}")
    generated_at = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    lines.extend(["", "## Generated At", "", generated_at, ""])
    return "\n".join(lines)


def render_junit(report: Dict[str, Any]) -> str:
    suite_el = ET.Element(
        "testsuite",
        name=report["suite"],
        tests=str(len(report["cases"])),
        failures=str(sum(1 for finding in report["findings"] if finding["severity"] == "error")),
    )
    findings_by_case = {}
    for finding in report["findings"]:
        findings_by_case.setdefault(finding.get("case_id"), []).append(finding)
    for case in report["cases"]:
        case_el = ET.SubElement(suite_el, "testcase", classname=case["target"], name=case["id"])
        findings = findings_by_case.get(case["id"], [])
        for finding in findings:
            if finding["severity"] == "error":
                failure = ET.SubElement(case_el, "failure", message=finding["code"])
                failure.text = finding["message"]
            else:
                system_out = ET.SubElement(case_el, "system-out")
                system_out.text = f"[warning] {finding['code']}: {finding['message']}"
    return ET.tostring(suite_el, encoding="unicode")


def render_sarif(report: Dict[str, Any]) -> str:
    findings = sorted(report["findings"], key=lambda item: (-severity_rank(item["severity"]), item["target"], item.get("case_id") or ""))
    rules = _sarif_rules(findings)
    results = [_sarif_result(report, finding) for finding in findings]
    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "mcp-schema-fuzzer",
                        "semanticVersion": __version__,
                        "informationUri": "https://github.com/yanqr213/mcp-schema-fuzzer",
                        "rules": rules,
                    }
                },
                "automationDetails": {"id": report["suite"]},
                "results": results,
                "properties": {
                    "description": report.get("description", ""),
                    "counts": report.get("counts", {}),
                    "reportFormat": "mcp-schema-fuzzer.sarif",
                },
            }
        ],
    }
    return json.dumps(sarif, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _sarif_rules(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    highest_by_code: Dict[str, str] = {}
    message_by_code: Dict[str, str] = {}
    for finding in findings:
        code = str(finding["code"])
        severity = str(finding["severity"])
        if severity_rank(severity) > severity_rank(highest_by_code.get(code, "none")):
            highest_by_code[code] = severity
        message_by_code.setdefault(code, str(finding["message"]))

    rules = []
    for code in sorted(highest_by_code):
        rules.append(
            {
                "id": code,
                "name": code.replace("_", " ").title(),
                "shortDescription": {"text": message_by_code[code]},
                "fullDescription": {"text": _rule_help(code)},
                "defaultConfiguration": {"level": _sarif_level(highest_by_code[code])},
                "help": {"text": _rule_help(code), "markdown": _rule_help(code)},
                "properties": {
                    "precision": "medium",
                    "tags": ["mcp", "agent-tools", "schema-fuzzing", "contract-testing"],
                },
            }
        )
    return rules


def _sarif_result(report: Dict[str, Any], finding: Dict[str, Any]) -> Dict[str, Any]:
    target = str(finding["target"])
    case_id = finding.get("case_id")
    category = finding.get("category")
    fingerprint_source = {
        "suite": report["suite"],
        "target": target,
        "case_id": case_id,
        "category": category,
        "code": finding["code"],
    }
    result = {
        "ruleId": finding["code"],
        "level": _sarif_level(finding["severity"]),
        "message": {"text": f"{target}: {finding['message']}"},
        "locations": [_sarif_location(report, finding)],
        "partialFingerprints": {
            "mcpSchemaFuzzer/v1": hashlib.sha256(normalize_json(fingerprint_source).encode("utf-8")).hexdigest()[:32]
        },
        "properties": {
            "severity": finding["severity"],
            "target": target,
            "case_id": case_id,
            "category": category,
            "details": finding.get("details", {}),
        },
    }
    return result


def _sarif_location(report: Dict[str, Any], finding: Dict[str, Any]) -> Dict[str, Any]:
    target_id = str(finding["target"])
    case_id = finding.get("case_id")
    category = finding.get("category")
    target = _find_target(report, target_id)
    location_uri = _target_location_uri(target)
    logical_name = str(case_id or category or target_id)
    return {
        "physicalLocation": {
            "artifactLocation": {"uri": location_uri},
            "region": {"startLine": 1},
        },
        "logicalLocations": [
            {
                "name": logical_name,
                "fullyQualifiedName": ".".join(part for part in [target_id, str(case_id or category or "")] if part),
                "kind": "function",
            }
        ],
    }


def _find_target(report: Dict[str, Any], target_id: str) -> Dict[str, Any]:
    for target in report.get("targets", []):
        if target.get("id") == target_id:
            return target
    return {"id": target_id}


def _target_location_uri(target: Dict[str, Any]) -> str:
    for key in ("transcripts_uri", "schema_uri", "examples_uri"):
        if target.get(key):
            return str(target[key]).replace("\\", "/")
    target_id = str(target.get("id", "target")).replace("\\", "/")
    return f"mcp-schema-fuzzer/{target_id}.contract.json"


def _sarif_level(severity: str) -> str:
    if severity == "error":
        return "error"
    if severity == "warning":
        return "warning"
    return "note"


def _rule_help(code: str) -> str:
    help_by_code = {
        "missing_transcript": "Record an offline transcript for this generated invalid input so the contract can prove it is rejected.",
        "invalid_input_accepted": "The transcript shows an invalid generated payload was accepted. Tighten schema validation or wrapper checks before the request reaches business logic.",
        "error_shape_missing": "Return a structured error object when rejecting invalid input so agents and callers can handle failures consistently.",
        "request_mismatch": "Refresh the transcript. The recorded request no longer matches the generated fuzz payload.",
        "unstable_case_response": "Repeated transcripts for the same invalid input produced different response signatures. Stabilize error codes and response shape.",
        "unstable_case_family_signature": "Related invalid inputs produced multiple error signatures. Prefer stable category-level error codes for predictable agent recovery.",
    }
    return help_by_code.get(code, "Review this MCP schema fuzzing finding and update the schema, wrapper validation, or recorded transcript.")


def gate_report(report: Dict[str, Any], threshold: str) -> bool:
    needed = severity_rank(threshold)
    if needed <= 0:
        return True
    for finding in report["findings"]:
        if severity_rank(finding["severity"]) >= needed:
            return False
    return True


def summarize_for_console(report: Dict[str, Any]) -> str:
    counts = report["counts"]
    return (
        f"{report['suite']}: {counts['cases']} cases, {counts['findings']} findings "
        f"({counts['errors']} error, {counts['warnings']} warning)"
    )


def top_findings(report: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    findings = sorted(report["findings"], key=lambda item: (-severity_rank(item["severity"]), item["target"], item.get("case_id") or ""))
    return findings[:limit]
