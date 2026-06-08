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

    def test_init_suite_creates_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_suite(str(Path(tmp) / "starter"))
            self.assertTrue((root / "suite.json").exists())

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
