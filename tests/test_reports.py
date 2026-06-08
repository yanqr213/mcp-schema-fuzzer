import json
import tempfile
import unittest
from pathlib import Path

from mcp_schema_fuzzer.reports import gate_report, render_junit, render_markdown, summarize_for_console, top_findings, write_report_bundle


REPORT = {
    "suite": "demo-suite",
    "description": "demo",
    "targets": [{"id": "demo.tool", "kind": "tool", "case_count": 2, "finding_count": 1}],
    "cases": [
        {"id": "demo.tool.minimum.count", "target": "demo.tool", "category": "minimum", "severity": "error", "path": "count", "variant": "", "payload": {"count": 0}, "rationale": "bad", "source_example": "happy", "tags": []},
        {"id": "demo.tool.wrong-type.path", "target": "demo.tool", "category": "wrong-type", "severity": "error", "path": "path", "variant": "", "payload": {"path": 42}, "rationale": "bad", "source_example": "happy", "tags": []},
    ],
    "findings": [
        {"severity": "warning", "code": "missing_transcript", "message": "No transcript", "target": "demo.tool", "case_id": "demo.tool.wrong-type.path", "category": "wrong-type", "details": {}}
    ],
    "counts": {"cases": 2, "findings": 1, "warnings": 1, "errors": 0, "categories": ["minimum"], "highest_severity": "warning"},
}


class ReportTests(unittest.TestCase):
    def test_render_markdown_contains_summary(self):
        output = render_markdown(REPORT)
        self.assertIn("# Fuzz Report: demo-suite", output)
        self.assertIn("Generated cases: 2", output)

    def test_render_junit_contains_testcase(self):
        output = render_junit(REPORT)
        self.assertIn("testcase", output)
        self.assertIn("demo.tool.minimum.count", output)

    def test_gate_report_warning_fails(self):
        self.assertFalse(gate_report(REPORT, "warning"))

    def test_gate_report_error_passes(self):
        self.assertTrue(gate_report(REPORT, "error"))

    def test_summarize_for_console(self):
        summary = summarize_for_console(REPORT)
        self.assertIn("2 cases", summary)

    def test_top_findings_limits_results(self):
        findings = top_findings(REPORT, limit=1)
        self.assertEqual(len(findings), 1)

    def test_write_report_bundle_writes_all_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_report_bundle(REPORT, Path(tmp) / "nested" / "report")
            for path in result.values():
                self.assertTrue(Path(path).exists())
            data = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
            self.assertEqual(data["suite"], "demo-suite")
