from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Set

from .utils import dump_json, slugify, write_text


def import_recorder_snapshot(
    snapshot: Mapping[str, Any],
    destination: str,
    suite_name: str = "",
    description: str = "",
    force: bool = False,
    include_empty_examples: bool = False,
) -> Dict[str, str]:
    root = Path(destination).resolve()
    if root.exists() and any(root.iterdir()) and not force:
        raise FileExistsError(f"destination is not empty: {root}")

    tools = _snapshot_tools(snapshot)
    if not tools:
        raise ValueError("recorder snapshot does not contain any tools")
    used_slugs: Set[str] = set()
    targets: List[Dict[str, Any]] = []
    written: Dict[str, str] = {}

    for tool in tools:
        name = str(tool.get("name", "tool"))
        slug = _unique_slug(slugify(name), used_slugs)
        schema_rel = f"schemas/{slug}.schema.json"
        examples_rel = f"fixtures/{slug}.examples.json"
        schema_path = root / schema_rel
        examples_path = root / examples_rel

        dump_json(_schema_document(tool), schema_path)
        examples_document = _examples_document(tool, include_empty=include_empty_examples)

        target = {
            "id": name,
            "kind": "tool",
            "schema": schema_rel,
            "metadata": _target_metadata(tool),
        }
        if examples_document["examples"]:
            dump_json(examples_document, examples_path)
            target["examples"] = examples_rel
            written[f"examples:{name}"] = str(examples_path)
        targets.append(target)
        written[f"schema:{name}"] = str(schema_path)

    suite = {
        "name": suite_name or _suite_name(snapshot),
        "description": description or "Generated from an mcp-contract-recorder snapshot. Record invalid-input transcripts after fuzz cases are generated.",
        "metadata": _suite_metadata(snapshot),
        "targets": targets,
    }
    suite_path = root / "suite.json"
    dump_json(suite, suite_path)
    readme_path = root / "README.md"
    write_text(readme_path, _readme(suite["name"], len(targets)))
    written["suite"] = str(suite_path)
    written["readme"] = str(readme_path)
    return written


def _snapshot_tools(snapshot: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    raw_tools = snapshot.get("tools", {})
    tools: List[Mapping[str, Any]] = []
    if isinstance(raw_tools, Mapping):
        for key, raw_tool in sorted(raw_tools.items(), key=lambda item: str(item[0])):
            if not isinstance(raw_tool, Mapping):
                continue
            tool = dict(raw_tool)
            tool.setdefault("name", str(key))
            tools.append(tool)
    elif isinstance(raw_tools, list):
        for raw_tool in raw_tools:
            if isinstance(raw_tool, Mapping):
                tools.append(raw_tool)
    return tools


def _schema_document(tool: Mapping[str, Any]) -> Dict[str, Any]:
    schema = dict(tool.get("inputSchema") or tool.get("input_schema") or {"type": "object"})
    if not schema:
        schema = {"type": "object"}
    if "type" not in schema and "properties" in schema:
        schema["type"] = "object"
    return schema


def _examples_document(tool: Mapping[str, Any], include_empty: bool = False) -> Dict[str, Any]:
    examples = []
    for index, example in enumerate(tool.get("examples", []) or [], start=1):
        if not isinstance(example, Mapping) or "input" not in example:
            continue
        item: Dict[str, Any] = {
            "name": f"{tool.get('name', 'tool')} observed input {index}",
            "payload": example["input"],
        }
        if example.get("source"):
            item["source"] = example["source"]
        if "output" in example:
            item["observed_output"] = example["output"]
        if "error" in example:
            item["observed_error"] = example["error"]
        examples.append(item)
    if not examples and include_empty:
        examples.append({"name": "synthetic-valid", "payload": {}})
    return {"examples": examples}


def _suite_metadata(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    metadata = {
        "importedFrom": "mcp-contract-recorder",
        "snapshotFormat": str(snapshot.get("format", "")),
        "recorderVersion": str(snapshot.get("recorderVersion", "")),
        "createdAt": str(snapshot.get("createdAt", "")),
    }
    source_metadata = snapshot.get("metadata")
    if isinstance(source_metadata, Mapping):
        metadata["sourceMetadata"] = dict(source_metadata)
    return {key: value for key, value in metadata.items() if _present(value)}


def _target_metadata(tool: Mapping[str, Any]) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "sourceToolName": tool.get("name"),
        "observedErrorCodes": _error_codes(tool),
    }
    stats = tool.get("stats")
    compatibility = tool.get("compatibility")
    if isinstance(stats, Mapping):
        metadata["stats"] = dict(stats)
    if isinstance(compatibility, Mapping):
        metadata["compatibility"] = dict(compatibility)
    return {key: value for key, value in metadata.items() if _present(value)}


def _error_codes(tool: Mapping[str, Any]) -> List[str]:
    codes = []
    for error in tool.get("errors", []) or []:
        if isinstance(error, Mapping) and error.get("code") is not None:
            codes.append(str(error["code"]))
    return sorted(set(codes))


def _suite_name(snapshot: Mapping[str, Any]) -> str:
    metadata = snapshot.get("metadata")
    if isinstance(metadata, Mapping) and metadata.get("recorder"):
        return f"{metadata['recorder']}-fuzzer-suite"
    return "mcp-contract-fuzzer-suite"


def _unique_slug(candidate: str, used: Set[str]) -> str:
    if candidate not in used:
        used.add(candidate)
        return candidate
    index = 2
    while f"{candidate}-{index}" in used:
        index += 1
    slug = f"{candidate}-{index}"
    used.add(slug)
    return slug


def _readme(name: str, target_count: int) -> str:
    return f"""# {name}

This suite was generated by `mcp-schema-fuzzer import-recorder-snapshot`.

- Targets: {target_count}
- Run `mcp-schema-fuzzer validate-fixtures suite.json` before fuzzing.
- Run `mcp-schema-fuzzer fuzz suite.json --output outputs/report` to generate cases and reports.
- Record invalid-input transcripts separately after inspecting generated case IDs.

The importer copies recorded input schemas and redacted observed inputs from the snapshot. It does not invent rejection transcripts.
"""


def _present(value: Any) -> bool:
    return value not in ("", None) and value != []
