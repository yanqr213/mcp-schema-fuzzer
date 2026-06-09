import tempfile
import unittest
from pathlib import Path

from mcp_schema_fuzzer.suite import load_examples, load_suite, load_suite_and_validate, load_transcripts, validate_suite
from mcp_schema_fuzzer.utils import load_json
from tests.helpers import build_basic_suite, write_json


class SuiteTests(unittest.TestCase):
    def test_load_suite_parses_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path = build_basic_suite(Path(tmp))
            suite = load_suite(str(suite_path))
            self.assertEqual(suite.name, "test-suite")
            self.assertEqual(suite.targets[0].id, "demo.tool")

    def test_load_json_accepts_utf8_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_text('\ufeff{"ok": true}', encoding="utf-8")
            self.assertEqual(load_json(path), {"ok": True})

    def test_load_examples_returns_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path = build_basic_suite(Path(tmp))
            suite = load_suite(str(suite_path))
            examples = load_examples(suite.targets[0].examples_path)
            self.assertEqual(examples[0]["name"], "happy path")

    def test_load_transcripts_returns_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path = build_basic_suite(Path(tmp))
            suite = load_suite(str(suite_path))
            entries = load_transcripts(suite.targets[0].transcripts_path)
            self.assertEqual(entries[0].target, "demo.tool")

    def test_validate_suite_accepts_valid_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path = build_basic_suite(Path(tmp))
            suite = load_suite(str(suite_path))
            result = validate_suite(suite)
            self.assertEqual(result.errors, [])

    def test_validate_suite_reports_missing_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            suite = {"name": "broken", "targets": [{"id": "demo.tool", "kind": "tool", "schema": "missing.json"}]}
            write_json(root / "suite.json", suite)
            loaded = load_suite(str(root / "suite.json"))
            result = validate_suite(loaded)
            self.assertTrue(any("missing schema file" in item for item in result.errors))

    def test_validate_suite_reports_duplicate_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            suite = {
                "name": "dup",
                "targets": [
                    {"id": "demo.tool", "kind": "tool", "schema": "a.json"},
                    {"id": "demo.tool", "kind": "tool", "schema": "b.json"},
                ],
            }
            write_json(root / "suite.json", suite)
            loaded = load_suite(str(root / "suite.json"))
            result = validate_suite(loaded)
            self.assertTrue(any("duplicate target id" in item for item in result.errors))

    def test_validate_suite_reports_bad_transcript_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path = build_basic_suite(Path(tmp))
            suite = load_suite(str(suite_path))
            write_json(
                suite.targets[0].transcripts_path,
                {
                    "entries": [
                        {
                            "case_id": "demo.tool.minimum.count",
                            "target": "other.tool",
                            "request": {},
                            "response": {"ok": False, "error": {"code": "X", "message": "bad"}},
                        }
                    ]
                },
            )
            result = validate_suite(suite)
            self.assertTrue(any("transcript target mismatch" in item for item in result.errors))

    def test_load_suite_and_validate_returns_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path = build_basic_suite(Path(tmp))
            suite, result = load_suite_and_validate(str(suite_path))
            self.assertEqual(suite.name, "test-suite")
            self.assertEqual(result.errors, [])
