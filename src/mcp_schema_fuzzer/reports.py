from __future__ import annotations

import datetime as _dt
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List

from .utils import dump_json, ensure_parent, severity_rank


def write_report_bundle(report: Dict[str, Any], output_base: Path) -> Dict[str, str]:
    json_path = output_base.with_suffix(".json")
    md_path = output_base.with_suffix(".md")
    xml_path = output_base.with_suffix(".xml")
    dump_json(report, json_path)
    ensure_parent(md_path)
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    ensure_parent(xml_path)
    xml_path.write_text(render_junit(report), encoding="utf-8", newline="\n")
    return {"json": str(json_path), "markdown": str(md_path), "junit": str(xml_path)}


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
