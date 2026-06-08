import unittest

from mcp_schema_fuzzer.generator import case_paths, find_case, generate_cases, generate_seed_payload


SCHEMA = {
    "type": "object",
    "required": ["path", "count"],
    "properties": {
        "path": {"type": "string", "minLength": 1, "maxLength": 8},
        "count": {"type": "integer", "minimum": 1, "maximum": 3},
        "mode": {"type": "string", "enum": ["safe", "preview"]},
        "tags": {"type": "array", "minItems": 1, "maxItems": 2, "items": {"type": "string", "minLength": 2}},
    },
}

EXAMPLES = [{"name": "happy", "payload": {"path": "docs.md", "count": 2, "mode": "safe", "tags": ["aa"]}}]


class GeneratorTests(unittest.TestCase):
    def test_generate_cases_includes_missing_required(self):
        cases = generate_cases("demo.tool", SCHEMA, EXAMPLES)
        ids = {case.id for case in cases}
        self.assertIn("demo.tool.missing-required.path", ids)
        self.assertIn("demo.tool.missing-required.count", ids)

    def test_generate_cases_includes_wrong_type(self):
        cases = generate_cases("demo.tool", SCHEMA, EXAMPLES)
        ids = {case.id for case in cases}
        self.assertIn("demo.tool.wrong-type.path", ids)
        self.assertIn("demo.tool.wrong-type.count", ids)

    def test_generate_cases_includes_enum_and_bounds(self):
        cases = generate_cases("demo.tool", SCHEMA, EXAMPLES)
        ids = {case.id for case in cases}
        self.assertIn("demo.tool.invalid-enum.mode", ids)
        self.assertIn("demo.tool.minimum.count", ids)
        self.assertIn("demo.tool.maximum.count", ids)

    def test_generate_cases_includes_path_cases(self):
        cases = generate_cases("demo.tool", SCHEMA, EXAMPLES)
        ids = {case.id for case in cases}
        self.assertTrue(any(case_id.startswith("demo.tool.dangerous-path.path.") for case_id in ids))
        self.assertIn("demo.tool.overlong-text.path", ids)

    def test_generate_cases_includes_array_bounds(self):
        cases = generate_cases("demo.tool", SCHEMA, EXAMPLES)
        ids = {case.id for case in cases}
        self.assertIn("demo.tool.min-items.tags", ids)
        self.assertIn("demo.tool.max-items.tags", ids)

    def test_generate_cases_deduplicates_same_payload(self):
        cases = generate_cases("demo.tool", SCHEMA, EXAMPLES + EXAMPLES)
        ids = [case.id for case in cases]
        self.assertEqual(len(ids), len(set(ids)))

    def test_find_case_returns_case(self):
        cases = generate_cases("demo.tool", SCHEMA, EXAMPLES)
        case = find_case(cases, "demo.tool.minimum.count")
        self.assertEqual(case.path, "count")

    def test_generate_seed_payload(self):
        payload = generate_seed_payload(SCHEMA)
        self.assertIn("path", payload)
        self.assertIn("count", payload)

    def test_case_paths_reports_paths(self):
        cases = generate_cases("demo.tool", SCHEMA, EXAMPLES)
        self.assertIn("path", case_paths(cases))
