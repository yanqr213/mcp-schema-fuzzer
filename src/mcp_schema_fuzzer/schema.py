from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .utils import path_to_label


@dataclass
class NodeSpec:
    path: str
    schema: Dict[str, Any]
    kind: str
    required: bool = False


def schema_type(schema: Dict[str, Any]) -> str:
    if "type" in schema:
        value = schema["type"]
        if isinstance(value, list):
            return next((item for item in value if item != "null"), value[0])
        return str(value)
    if "properties" in schema:
        return "object"
    if "items" in schema:
        return "array"
    return "string"


def collect_nodes(schema: Dict[str, Any], path_parts: Optional[List[str]] = None, required: bool = False) -> List[NodeSpec]:
    path_parts = path_parts or []
    path = path_to_label(path_parts)
    kind = schema_type(schema)
    nodes = [NodeSpec(path=path, schema=schema, kind=kind, required=required)]
    if kind == "object":
        required_props = set(schema.get("required", []))
        for name, child in schema.get("properties", {}).items():
            nodes.extend(collect_nodes(child, path_parts + [name], name in required_props))
    elif kind == "array":
        item_schema = schema.get("items", {})
        nodes.extend(collect_nodes(item_schema, path_parts + ["0"], required=True))
    return nodes


def synthesize_valid_value(schema: Dict[str, Any]) -> Any:
    kind = schema_type(schema)
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if kind == "object":
        payload = {}
        required_props = set(schema.get("required", []))
        for name, child in schema.get("properties", {}).items():
            if name in required_props or "default" in child:
                payload[name] = child.get("default", synthesize_valid_value(child))
        return payload
    if kind == "array":
        min_items = schema.get("minItems", 1)
        length = max(min_items, 1)
        return [synthesize_valid_value(schema.get("items", {})) for _ in range(length)]
    if kind == "integer":
        minimum = schema.get("minimum")
        if minimum is not None:
            return int(minimum)
        return 0
    if kind == "number":
        minimum = schema.get("minimum")
        if minimum is not None:
            return float(minimum)
        return 0.0
    if kind == "boolean":
        return False
    if kind == "null":
        return None
    min_length = schema.get("minLength", 1)
    base = "sample"
    if min_length > len(base):
        base = "x" * min_length
    return base


def wrong_type_value(kind: str) -> Any:
    mapping = {
        "object": "not-an-object",
        "array": {"unexpected": True},
        "string": 42,
        "integer": "forty-two",
        "number": "3.14",
        "boolean": "true",
        "null": "null",
    }
    return mapping.get(kind, None)


def shorter_text(min_length: int) -> Optional[str]:
    if min_length <= 0:
        return None
    if min_length == 1:
        return ""
    return "x" * (min_length - 1)


def longer_text(max_length: int) -> str:
    return "x" * (max_length + 1)


def below_minimum(schema: Dict[str, Any]) -> Any:
    minimum = schema.get("minimum", 0)
    if schema_type(schema) == "integer":
        return int(minimum) - 1
    return float(minimum) - 1


def above_maximum(schema: Dict[str, Any]) -> Any:
    maximum = schema.get("maximum", 0)
    if schema_type(schema) == "integer":
        return int(maximum) + 1
    return float(maximum) + 1


def shorter_array(min_items: int, item_schema: Dict[str, Any]) -> Optional[List[Any]]:
    if min_items <= 0:
        return None
    return [synthesize_valid_value(item_schema) for _ in range(max(0, min_items - 1))]


def longer_array(max_items: int, item_schema: Dict[str, Any]) -> List[Any]:
    return [synthesize_valid_value(item_schema) for _ in range(max_items + 1)]


def overlong_text(schema: Dict[str, Any]) -> str:
    max_length = schema.get("maxLength")
    if max_length is not None:
        return longer_text(int(max_length))
    return "x" * 1025


def dangerous_path_candidates() -> List[Tuple[str, str]]:
    return [
        ("etc-passwd", "../../etc/passwd"),
        ("windows-hosts", "..\\..\\Windows\\System32\\drivers\\etc\\hosts"),
        ("root-ssh", "/var/log/../../root/.ssh/id_rsa"),
        ("system-sam", "C:\\Windows\\System32\\config\\SAM"),
        ("temp-secret", "\\\\?\\C:\\Temp\\..\\secret.txt"),
    ]


def supported_keywords(schema: Dict[str, Any]) -> Iterable[str]:
    allowed = {
        "type",
        "properties",
        "required",
        "items",
        "enum",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "default",
        "description",
        "title",
    }
    return [key for key in schema if key in allowed]
