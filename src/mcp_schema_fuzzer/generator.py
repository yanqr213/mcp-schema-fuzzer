from __future__ import annotations

from typing import Any, Dict, List

from .models import FuzzCase
from .schema import (
    above_maximum,
    below_minimum,
    collect_nodes,
    dangerous_path_candidates,
    longer_array,
    longer_text,
    overlong_text,
    schema_type,
    shorter_array,
    shorter_text,
    synthesize_valid_value,
    wrong_type_value,
)
from .utils import delete_in_path, get_in_path, looks_path_like, normalize_json, set_in_path, slugify


def _source_name(example: Dict[str, Any], index: int) -> str:
    return str(example.get("name", f"example-{index + 1}"))


def _base_payload(example: Dict[str, Any], schema: Dict[str, Any]) -> Any:
    if "payload" in example:
        return example["payload"]
    return synthesize_valid_value(schema)


def _build_case_id(target_id: str, category: str, path: str, variant: str = "") -> str:
    if path == "$":
        base = f"{target_id}.{category}"
    else:
        base = f"{target_id}.{category}.{slugify(path)}"
    if variant:
        return f"{base}.{slugify(variant)}"
    return base


def _append_case(
    cases: List[FuzzCase],
    seen: set,
    target_id: str,
    category: str,
    severity: str,
    path: str,
    variant: str,
    payload: Any,
    rationale: str,
    source_example: str,
    tags: List[str],
) -> None:
    signature = (target_id, category, path, variant, normalize_json(payload))
    if signature in seen:
        return
    seen.add(signature)
    cases.append(
        FuzzCase(
            id=_build_case_id(target_id, category, path, variant),
            target=target_id,
            category=category,
            severity=severity,
            path=path,
            variant=variant,
            payload=payload,
            rationale=rationale,
            source_example=source_example,
            tags=tags,
        )
    )


def generate_cases(target_id: str, schema: Dict[str, Any], examples: List[Dict[str, Any]]) -> List[FuzzCase]:
    if not examples:
        examples = [{"name": "synthetic-valid", "payload": synthesize_valid_value(schema)}]

    nodes = collect_nodes(schema)
    cases: List[FuzzCase] = []
    seen = set()

    for index, example in enumerate(examples):
        source_example = _source_name(example, index)
        payload = _base_payload(example, schema)
        for node in nodes:
            kind = node.kind
            if node.required and node.path != "$":
                _append_case(
                    cases,
                    seen,
                    target_id,
                    "missing-required",
                    "error",
                    node.path,
                    "",
                    delete_in_path(payload, node.path),
                    f"Required field `{node.path}` is removed from the request.",
                    source_example,
                    ["required"],
                )
            if node.path != "$":
                _append_case(
                    cases,
                    seen,
                    target_id,
                    "wrong-type",
                    "error",
                    node.path,
                    "",
                    set_in_path(payload, node.path, wrong_type_value(kind)),
                    f"Field `{node.path}` is replaced with a value of the wrong type for `{kind}`.",
                    source_example,
                    ["type"],
                )

            if "enum" in node.schema and node.path != "$":
                _append_case(
                    cases,
                    seen,
                    target_id,
                    "invalid-enum",
                    "error",
                    node.path,
                    "",
                    set_in_path(payload, node.path, "__invalid_enum__"),
                    f"Field `{node.path}` receives a value outside the declared enum set.",
                    source_example,
                    ["enum"],
                )

            if kind == "string" and node.path != "$":
                min_length = node.schema.get("minLength")
                if min_length is not None:
                    candidate = shorter_text(int(min_length))
                    if candidate is not None:
                        _append_case(
                            cases,
                            seen,
                            target_id,
                            "min-length",
                            "error",
                            node.path,
                            "",
                            set_in_path(payload, node.path, candidate),
                            f"String field `{node.path}` is shorter than `minLength={min_length}`.",
                            source_example,
                            ["bounds", "string"],
                        )
                max_length = node.schema.get("maxLength")
                if max_length is not None:
                    _append_case(
                        cases,
                        seen,
                        target_id,
                        "max-length",
                        "error",
                        node.path,
                        "",
                        set_in_path(payload, node.path, longer_text(int(max_length))),
                        f"String field `{node.path}` exceeds `maxLength={max_length}`.",
                        source_example,
                        ["bounds", "string"],
                    )
                _append_case(
                    cases,
                    seen,
                    target_id,
                    "overlong-text",
                    "warning",
                    node.path,
                    "",
                    set_in_path(payload, node.path, overlong_text(node.schema)),
                    f"String field `{node.path}` is replaced with a very long payload to probe truncation and error handling.",
                    source_example,
                    ["long-text"],
                )
                if looks_path_like(node.path):
                    for label, candidate in dangerous_path_candidates():
                        _append_case(
                            cases,
                            seen,
                            target_id,
                            "dangerous-path",
                            "error",
                            node.path,
                            label,
                            set_in_path(payload, node.path, candidate),
                            "A path-like field receives a traversal or sensitive-path string. The string is generated only for validation and is never executed.",
                            source_example,
                            ["path", "dangerous"],
                        )

            if kind in {"integer", "number"} and node.path != "$":
                if "minimum" in node.schema:
                    _append_case(
                        cases,
                        seen,
                        target_id,
                        "minimum",
                        "error",
                        node.path,
                        "",
                        set_in_path(payload, node.path, below_minimum(node.schema)),
                        f"Numeric field `{node.path}` is set below `minimum={node.schema['minimum']}`.",
                        source_example,
                        ["bounds", "number"],
                    )
                if "maximum" in node.schema:
                    _append_case(
                        cases,
                        seen,
                        target_id,
                        "maximum",
                        "error",
                        node.path,
                        "",
                        set_in_path(payload, node.path, above_maximum(node.schema)),
                        f"Numeric field `{node.path}` is set above `maximum={node.schema['maximum']}`.",
                        source_example,
                        ["bounds", "number"],
                    )

            if kind == "array" and node.path != "$":
                item_schema = node.schema.get("items", {})
                if "minItems" in node.schema:
                    candidate = shorter_array(int(node.schema["minItems"]), item_schema)
                    if candidate is not None:
                        _append_case(
                            cases,
                            seen,
                            target_id,
                            "min-items",
                            "error",
                            node.path,
                            "",
                            set_in_path(payload, node.path, candidate),
                            f"Array field `{node.path}` is shortened below `minItems={node.schema['minItems']}`.",
                            source_example,
                            ["bounds", "array"],
                        )
                if "maxItems" in node.schema:
                    _append_case(
                        cases,
                        seen,
                        target_id,
                        "max-items",
                        "error",
                        node.path,
                        "",
                        set_in_path(payload, node.path, longer_array(int(node.schema["maxItems"]), item_schema)),
                        f"Array field `{node.path}` is extended beyond `maxItems={node.schema['maxItems']}`.",
                        source_example,
                        ["bounds", "array"],
                    )

    return cases


def find_case(cases: List[FuzzCase], case_id: str) -> FuzzCase:
    for case in cases:
        if case.id == case_id:
            return case
    raise KeyError(case_id)


def generate_seed_payload(schema: Dict[str, Any]) -> Any:
    return synthesize_valid_value(schema)


def case_paths(cases: List[FuzzCase]) -> List[str]:
    return [case.path for case in cases]
