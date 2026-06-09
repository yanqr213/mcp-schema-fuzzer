from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List


PATHISH_TOKENS = {"path", "file", "filepath", "filename", "dir", "folder", "uri"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def dump_json(data: Any, path: Path) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def write_text(path: Path, content: str) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def normalize_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def slugify(text: str) -> str:
    lowered = text.lower().replace("_", "-").replace(" ", "-")
    lowered = re.sub(r"[^a-z0-9.\-]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-")
    return lowered or "item"


def path_to_label(parts: Iterable[str]) -> str:
    return ".".join(parts) if parts else "$"


def deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def iter_path_parts(path: str) -> Iterator[str]:
    for part in path.split("."):
        if part and part != "$":
            yield part


def looks_path_like(path: str) -> bool:
    tokens = {piece.lower() for piece in iter_path_parts(path)}
    return any(token in PATHISH_TOKENS for token in tokens)


def set_in_path(data: Any, path: str, value: Any) -> Any:
    updated = deep_copy(data)
    parts = list(iter_path_parts(path))
    if not parts:
        return value
    cursor = updated
    for part in parts[:-1]:
        if isinstance(cursor, list):
            cursor = cursor[int(part)]
        else:
            cursor = cursor[part]
    last = parts[-1]
    if isinstance(cursor, list):
        cursor[int(last)] = value
    else:
        cursor[last] = value
    return updated


def delete_in_path(data: Any, path: str) -> Any:
    updated = deep_copy(data)
    parts = list(iter_path_parts(path))
    if not parts:
        return updated
    cursor = updated
    for part in parts[:-1]:
        if isinstance(cursor, list):
            cursor = cursor[int(part)]
        else:
            cursor = cursor[part]
    last = parts[-1]
    if isinstance(cursor, list):
        cursor.pop(int(last))
    else:
        cursor.pop(last, None)
    return updated


def get_in_path(data: Any, path: str) -> Any:
    parts = list(iter_path_parts(path))
    cursor = data
    for part in parts:
        if isinstance(cursor, list):
            cursor = cursor[int(part)]
        else:
            cursor = cursor[part]
    return cursor


def severity_rank(severity: str) -> int:
    return {"warning": 1, "error": 2}.get(severity, 0)


def max_severity(values: Iterable[str], default: str = "warning") -> str:
    winner = default
    for severity in values:
        if severity_rank(severity) > severity_rank(winner):
            winner = severity
    return winner


def stable_signature(response: Dict[str, Any]) -> str:
    ok = bool(response.get("ok"))
    if ok:
        return "ok"
    error = response.get("error") or {}
    code = str(error.get("code", ""))
    message = str(error.get("message", ""))
    message = re.sub(r"\d+", "#", message)
    message = re.sub(r"['\"`].+?['\"`]", "<value>", message)
    return f"error:{code}:{message}"


def resolve_output_base(raw: str) -> Path:
    path = Path(raw)
    if path.suffix:
        return path.with_suffix("")
    return path


def pluralize(word: str, count: int) -> str:
    return word if count == 1 else f"{word}s"


def summarize_counts(values: List[Any], word: str) -> str:
    return f"{len(values)} {pluralize(word, len(values))}"
