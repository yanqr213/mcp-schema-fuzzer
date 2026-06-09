import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from mcp_schema_fuzzer.cli import build_parser, main
from mcp_schema_fuzzer.init_suite import init_suite
from tests.helpers import build_basic_suite


class CliTests(unittest.TestCase):
    def test_build_parser_knows_commands(self):
        parser = build_parser()
        parsed = parser.parse_args(["check", "report.json", "--check", "warning"])
        self.assertEqual(parsed.command, "check")

    def test_build_parser_knows_import_recorder_snapshot(self):
        parser = build_parser()
        parsed = parser.parse_args(["import-recorder-snapshot", "snapshot.json", "--out-dir", "suite"])
        self.assertEqual(parsed.command, "import-recorder-snapshot")

    def test_init_suite_creates_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_suite(str(Path(tmp) / "starter"))
            self.assertTrue((root / "suite.json").exists())

    def test_import_recorder_snapshot_command_creates_valid_suite(self):
        snapshot = {
            "format": "mcp-contract-recorder.snapshot/v1",
            "recorderVersion": "0.3.0",
            "createdAt": "2026-06-09T00:00:00Z",
            "tools": {
                "echo": {
                    "name": "echo",
                    "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                    "examples": [{"input": {"text": "hi"}, "output": {"text": "hi"}}],
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot_path = root / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["import-recorder-snapshot", str(snapshot_path), "--out-dir", str(root / "suite"), "--name", "echo-suite"])
            with contextlib.redirect_stdout(io.StringIO()):
                validate_code = main(["validate-fixtures", str(root / "suite" / "suite.json")])

        self.assertEqual(exit_code, 0)
        self.assertEqual(validate_code, 0)
        self.assertIn("Imported recorder snapshot", stdout.getvalue())

    def test_import_recorder_snapshot_command_reports_bad_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot_path = root / "empty.json"
            snapshot_path.write_text(json.dumps({"tools": {}}), encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = main(["import-recorder-snapshot", str(snapshot_path), "--out-dir", str(root / "suite")])

        self.assertEqual(exit_code, 1)
        self.assertIn("does not contain any tools", stderr.getvalue())

    def test_validate_fixtures_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path = build_basic_suite(Path(tmp))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["validate-fixtures", str(suite_path)])
            self.assertEqual(exit_code, 0)
            self.assertIn("fixtures are valid", stdout.getvalue())

    def test_validate_fixtures_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path = Path(tmp) / "suite.json"
            suite_path.write_text('{"name":"broken","targets":[]}', encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["validate-fixtures", str(suite_path)])
            self.assertEqual(exit_code, 1)

    def test_fuzz_writes_report_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path = build_basic_suite(Path(tmp))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["fuzz", str(suite_path), "--output", str(Path(tmp) / "out" / "report")])
            self.assertEqual(exit_code, 0)
            self.assertTrue((Path(tmp) / "out" / "report.json").exists())
            self.assertTrue((Path(tmp) / "out" / "report.sarif").exists())
            self.assertIn("SARIF:", stdout.getvalue())

    def test_check_command_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            report.write_text(json.dumps({"suite": "demo", "counts": {"cases": 0, "findings": 0, "errors": 0, "warnings": 0}, "findings": []}), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["check", str(report), "--check", "error"])
            self.assertEqual(exit_code, 0)
            self.assertIn("Gate passed", stdout.getvalue())

    def test_check_command_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            report.write_text(json.dumps({"suite": "demo", "counts": {"cases": 0, "findings": 1, "errors": 1, "warnings": 0}, "findings": [{"severity": "error", "code": "X", "message": "bad", "target": "demo"}]}), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                exit_code = main(["check", str(report), "--check", "error"])
            self.assertEqual(exit_code, 2)

    def test_explain_command_prints_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_path = build_basic_suite(Path(tmp))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["explain", str(suite_path), "demo.tool.minimum.count"])
            self.assertEqual(exit_code, 0)
            self.assertIn("Case: demo.tool.minimum.count", stdout.getvalue())
