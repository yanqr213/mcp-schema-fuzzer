import unittest

from mcp_schema_fuzzer.schema import (
    above_maximum,
    below_minimum,
    collect_nodes,
    dangerous_path_candidates,
    schema_type,
    shorter_text,
    synthesize_valid_value,
    wrong_type_value,
)


class SchemaTests(unittest.TestCase):
    def test_schema_type_uses_explicit_type(self):
        self.assertEqual(schema_type({"type": "integer"}), "integer")

    def test_schema_type_infers_object(self):
        self.assertEqual(schema_type({"properties": {}}), "object")

    def test_collect_nodes_includes_nested_properties(self):
        schema = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}, "meta": {"type": "object", "properties": {"size": {"type": "integer"}}}}}
        paths = [node.path for node in collect_nodes(schema)]
        self.assertIn("name", paths)
        self.assertIn("meta.size", paths)

    def test_synthesize_valid_value_builds_required_object(self):
        schema = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string", "minLength": 2}, "count": {"type": "integer"}}}
        payload = synthesize_valid_value(schema)
        self.assertEqual(payload["name"], "sample")
        self.assertNotIn("count", payload)

    def test_wrong_type_value_for_string(self):
        self.assertEqual(wrong_type_value("string"), 42)

    def test_shorter_text_respects_minimum(self):
        self.assertEqual(shorter_text(3), "xx")
        self.assertEqual(shorter_text(1), "")

    def test_numeric_bounds_helpers(self):
        self.assertEqual(below_minimum({"type": "integer", "minimum": 1}), 0)
        self.assertEqual(above_maximum({"type": "integer", "maximum": 3}), 4)

    def test_dangerous_path_candidates_has_windows_and_unix_examples(self):
        values = dangerous_path_candidates()
        self.assertTrue(any(".." in item[1] for item in values))
        self.assertTrue(any("\\" in item[1] for item in values))
