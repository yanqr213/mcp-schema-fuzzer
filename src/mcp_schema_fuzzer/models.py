from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Target:
    id: str
    kind: str
    schema_path: Path
    examples_path: Optional[Path] = None
    transcripts_path: Optional[Path] = None


@dataclass
class Suite:
    name: str
    description: str
    root: Path
    targets: List[Target]


@dataclass
class FuzzCase:
    id: str
    target: str
    category: str
    severity: str
    path: str
    variant: str
    payload: Any
    rationale: str
    source_example: str
    tags: List[str] = field(default_factory=list)


@dataclass
class TranscriptEntry:
    case_id: str
    target: str
    request: Any
    response: Dict[str, Any]
    source: str


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    target: str
    case_id: Optional[str] = None
    category: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    suite: Suite
    errors: List[str]
    warnings: List[str]
    target_summaries: List[Dict[str, Any]]
