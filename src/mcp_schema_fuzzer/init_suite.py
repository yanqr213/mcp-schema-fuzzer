from __future__ import annotations

import json
from pathlib import Path

from .utils import ensure_parent


SUITE_TEMPLATE = {
    "name": "starter-suite",
    "description": "Starter suite for an MCP tool or resource wrapper.",
    "targets": [
        {
            "id": "sample.tool",
            "kind": "tool",
            "schema": "schemas/sample.tool.schema.json",
            "examples": "fixtures/sample.tool.examples.json",
            "transcripts": "fixtures/sample.tool.transcripts.json",
        }
    ],
}

SCHEMA_TEMPLATE = {
    "type": "object",
    "required": ["path", "limit"],
    "properties": {
        "path": {"type": "string", "minLength": 1, "maxLength": 256},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        "mode": {"type": "string", "enum": ["safe", "preview"]},
    },
}

EXAMPLES_TEMPLATE = {
    "examples": [
        {
            "name": "starter example",
            "payload": {
                "path": "docs/guide.md",
                "limit": 10,
                "mode": "safe",
            },
        }
    ]
}

TRANSCRIPTS_TEMPLATE = {
    "entries": [
        {
            "case_id": "sample.tool.missing-required.path",
            "target": "sample.tool",
            "request": {
                "limit": 10,
                "mode": "safe",
            },
            "response": {
                "ok": False,
                "error": {
                    "code": "INVALID_ARGUMENT",
                    "message": "path is required",
                },
            },
        }
    ]
}

README_TEMPLATE = """# Starter Suite

This directory was created by `mcp-schema-fuzzer init-suite`.

- Edit `suite.json` to describe your targets.
- Replace the schema, examples, and transcript fixtures with your own files.
- Run `mcp-schema-fuzzer validate-fixtures suite.json` before `fuzz`.
"""


def init_suite(path: str, force: bool = False) -> Path:
    root = Path(path).resolve()
    if root.exists() and any(root.iterdir()) and not force:
        raise FileExistsError(f"destination is not empty: {root}")

    files = {
        root / "suite.json": SUITE_TEMPLATE,
        root / "schemas" / "sample.tool.schema.json": SCHEMA_TEMPLATE,
        root / "fixtures" / "sample.tool.examples.json": EXAMPLES_TEMPLATE,
        root / "fixtures" / "sample.tool.transcripts.json": TRANSCRIPTS_TEMPLATE,
    }
    for file_path, content in files.items():
        ensure_parent(file_path)
        file_path.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    readme_path = root / "README.md"
    ensure_parent(readme_path)
    readme_path.write_text(README_TEMPLATE, encoding="utf-8", newline="\n")
    return root
