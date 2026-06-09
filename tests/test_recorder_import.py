import tempfile
import unittest
from pathlib import Path

from mcp_schema_fuzzer.recorder_import import import_recorder_snapshot
from mcp_schema_fuzzer.suite import load_examples, load_suite_and_validate
from mcp_schema_fuzzer.utils import load_json


def _snapshot():
    return {
        "format": "mcp-contract-recorder.snapshot/v1",
        "recorderVersion": "0.3.0",
        "createdAt": "2026-06-09T00:00:00Z",
        "metadata": {"recorder": "mcp-contract-recorder", "callCount": 2},
        "tools": {
            "search.docs": {
                "name": "search.docs",
                "inputSchema": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
                },
                "errors": [{"code": "VALIDATION_ERROR", "count": 1}],
                "examples": [
                    {
                        "input": {"query": "mcp", "limit": 3},
                        "output": {"items": []},
                        "source": "transcript.jsonl",
                    }
                ],
                "stats": {"callCount": 2},
                "compatibility": {"inputSchemaHash": "abc", "observedErrorCodes": ["VALIDATION_ERROR"]},
            }
        },
    }


class RecorderImportTests(unittest.TestCase):
    def test_import_recorder_snapshot_writes_valid_suite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "suite"
            paths = import_recorder_snapshot(_snapshot(), str(out_dir), suite_name="contracts")
            suite_json = load_json(Path(paths["suite"]))
            schema_json = load_json(out_dir / "schemas" / "search.docs.schema.json")
            examples = load_examples(out_dir / "fixtures" / "search.docs.examples.json")
            suite, validation = load_suite_and_validate(str(out_dir / "suite.json"))

        self.assertEqual(validation.errors, [])
        self.assertEqual(suite.name, "contracts")
        self.assertEqual(suite.metadata["importedFrom"], "mcp-contract-recorder")
        self.assertEqual(suite_json["targets"][0]["metadata"]["observedErrorCodes"], ["VALIDATION_ERROR"])
        self.assertEqual(schema_json["properties"]["query"]["type"], "string")
        self.assertEqual(examples[0]["payload"]["query"], "mcp")
        self.assertEqual(examples[0]["observed_output"], {"items": []})

    def test_import_recorder_snapshot_rejects_non_empty_destination_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "suite"
            out_dir.mkdir()
            (out_dir / "existing.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                import_recorder_snapshot(_snapshot(), str(out_dir))

    def test_import_recorder_snapshot_can_force_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "suite"
            out_dir.mkdir()
            (out_dir / "existing.txt").write_text("keep", encoding="utf-8")
            paths = import_recorder_snapshot(_snapshot(), str(out_dir), force=True)
            self.assertTrue(Path(paths["suite"]).exists())

    def test_import_recorder_snapshot_omits_empty_examples_by_default(self):
        snapshot = _snapshot()
        snapshot["tools"]["search.docs"]["examples"] = []
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "suite"
            import_recorder_snapshot(snapshot, str(out_dir))
            suite_json = load_json(out_dir / "suite.json")
            suite, validation = load_suite_and_validate(str(out_dir / "suite.json"))

        self.assertEqual(validation.errors, [])
        self.assertEqual(validation.warnings, [])
        self.assertIsNone(suite.targets[0].examples_path)
        self.assertNotIn("examples", suite_json["targets"][0])

    def test_import_recorder_snapshot_rejects_empty_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                import_recorder_snapshot({"tools": {}}, str(Path(tmp) / "suite"))


if __name__ == "__main__":
    unittest.main()
