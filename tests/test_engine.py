import tempfile
import unittest
from pathlib import Path

from mcp_schema_fuzzer.engine import analyze_target, run_fuzz, summarize_report_counts
from mcp_schema_fuzzer.generator import generate_cases
from mcp_schema_fuzzer.suite import load_suite, load_transcripts
from tests.helpers import build_basic_suite, write_json


class EngineTests(unittest.TestCase):
    def test_analyze_target_reports_missing_transcripts(self):
        schema = {
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"type": "integer", "minimum": 1}},
        }
        cases = generate_cases("demo.tool", schema, [{"payload": {"value": 1}}])
        findings = analyze_target("demo.tool", cases, [])
        self.assertTrue(any(item.code == "missing_transcript" for item in findings))

    def test_analyze_target_reports_accepted_invalid_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path = build_basic_suite(Path(tmp))
            suite = load_suite(str(suite_path))
            write_json(
                suite.targets[0].transcripts_path,
                {
                    "entries": [
                        {
                            "case_id": "demo.tool.minimum.count",
                            "target": "demo.tool",
                            "request": {"path": "docs.md", "count": 0, "mode": "safe", "tags": ["aa"]},
                            "response": {"ok": True},
                        }
                    ]
                },
            )
            cases = generate_cases("demo.tool", {"type": "object", "required": ["count"], "properties": {"count": {"type": "integer", "minimum": 1}}}, [{"payload": {"count": 1}}])
            findings = analyze_target("demo.tool", cases, load_transcripts(suite.targets[0].transcripts_path))
            self.assertTrue(any(item.code == "invalid_input_accepted" for item in findings))

    def test_analyze_target_reports_request_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path = build_basic_suite(Path(tmp))
            suite = load_suite(str(suite_path))
            transcripts = [
                type("Entry", (), {"case_id": "demo.tool.minimum.count", "target": "demo.tool", "request": {"count": 9}, "response": {"ok": False, "error": {"code": "X", "message": "bad"}}, "source": "test"})
            ]
            cases = generate_cases("demo.tool", {"type": "object", "required": ["count"], "properties": {"count": {"type": "integer", "minimum": 1}}}, [{"payload": {"count": 1}}])
            findings = analyze_target("demo.tool", cases, transcripts)
            self.assertTrue(any(item.code == "request_mismatch" for item in findings))

    def test_analyze_target_reports_unstable_case(self):
        schema = {"type": "object", "required": ["count"], "properties": {"count": {"type": "integer", "minimum": 1}}}
        cases = generate_cases("demo.tool", schema, [{"payload": {"count": 1}}])
        transcripts = [
            type("Entry", (), {"case_id": "demo.tool.minimum.count", "target": "demo.tool", "request": {"count": 0}, "response": {"ok": False, "error": {"code": "A", "message": "count bad"}}, "source": "a"}),
            type("Entry", (), {"case_id": "demo.tool.minimum.count", "target": "demo.tool", "request": {"count": 0}, "response": {"ok": False, "error": {"code": "B", "message": "count bad"}}, "source": "b"}),
        ]
        findings = analyze_target("demo.tool", cases, transcripts)
        self.assertTrue(any(item.code == "unstable_case_response" for item in findings))

    def test_run_fuzz_produces_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path = build_basic_suite(Path(tmp))
            suite = load_suite(str(suite_path))
            report = run_fuzz(suite)
            self.assertEqual(report["suite"], "test-suite")
            self.assertIn("counts", report)
            self.assertGreater(report["counts"]["cases"], 0)

    def test_summarize_report_counts_tracks_severity(self):
        counts = summarize_report_counts([], [])
        self.assertEqual(counts["highest_severity"], "none")
