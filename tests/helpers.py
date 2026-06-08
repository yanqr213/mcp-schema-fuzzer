from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def build_basic_suite(root: Path) -> Path:
    suite = {
        "name": "test-suite",
        "description": "test fixtures",
        "targets": [
            {
                "id": "demo.tool",
                "kind": "tool",
                "schema": "schemas/demo.tool.schema.json",
                "examples": "fixtures/demo.tool.examples.json",
                "transcripts": "fixtures/demo.tool.transcripts.json",
            }
        ],
    }
    schema = {
        "type": "object",
        "required": ["path", "count"],
        "properties": {
            "path": {"type": "string", "minLength": 1, "maxLength": 8},
            "count": {"type": "integer", "minimum": 1, "maximum": 3},
            "mode": {"type": "string", "enum": ["safe", "preview"]},
            "tags": {"type": "array", "minItems": 1, "maxItems": 2, "items": {"type": "string", "minLength": 2}},
        },
    }
    examples = {
        "examples": [
            {
                "name": "happy path",
                "payload": {"path": "docs.md", "count": 2, "mode": "safe", "tags": ["aa"]},
            }
        ]
    }
    transcripts = {
        "entries": [
            {
                "case_id": "demo.tool.missing-required.path",
                "target": "demo.tool",
                "request": {"count": 2, "mode": "safe", "tags": ["aa"]},
                "response": {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": "path is required"}},
            },
            {
                "case_id": "demo.tool.missing-required.count",
                "target": "demo.tool",
                "request": {"path": "docs.md", "mode": "safe", "tags": ["aa"]},
                "response": {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": "count is required"}},
            },
            {
                "case_id": "demo.tool.minimum.count",
                "target": "demo.tool",
                "request": {"path": "docs.md", "count": 0, "mode": "safe", "tags": ["aa"]},
                "response": {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": "count must be at least 1"}},
            },
            {
                "case_id": "demo.tool.maximum.count",
                "target": "demo.tool",
                "request": {"path": "docs.md", "count": 4, "mode": "safe", "tags": ["aa"]},
                "response": {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": "count must be at most 3"}},
            },
        ]
    }
    write_json(root / "suite.json", suite)
    write_json(root / "schemas" / "demo.tool.schema.json", schema)
    write_json(root / "fixtures" / "demo.tool.examples.json", examples)
    write_json(root / "fixtures" / "demo.tool.transcripts.json", transcripts)
    return root / "suite.json"
