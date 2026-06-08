from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from .models import Suite, Target, TranscriptEntry, ValidationResult
from .utils import load_json


def load_suite(suite_path: str) -> Suite:
    path = Path(suite_path).resolve()
    data = load_json(path)
    name = str(data.get("name", path.stem))
    description = str(data.get("description", ""))
    targets = []
    for raw_target in data.get("targets", []):
        targets.append(
            Target(
                id=str(raw_target["id"]),
                kind=str(raw_target.get("kind", "tool")),
                schema_path=(path.parent / raw_target["schema"]).resolve(),
                examples_path=((path.parent / raw_target["examples"]).resolve() if raw_target.get("examples") else None),
                transcripts_path=((path.parent / raw_target["transcripts"]).resolve() if raw_target.get("transcripts") else None),
            )
        )
    return Suite(name=name, description=description, root=path.parent, targets=targets)


def load_examples(path: Path) -> List[Dict[str, Any]]:
    data = load_json(path)
    return list(data.get("examples", []))


def load_transcripts(path: Path) -> List[TranscriptEntry]:
    data = load_json(path)
    entries = []
    for item in data.get("entries", []):
        entries.append(
            TranscriptEntry(
                case_id=str(item["case_id"]),
                target=str(item["target"]),
                request=item.get("request"),
                response=item.get("response", {}),
                source=str(path),
            )
        )
    return entries


def validate_suite(suite: Suite) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []
    summaries: List[Dict[str, Any]] = []

    if not suite.targets:
        errors.append("suite must define at least one target")

    target_ids = set()
    for target in suite.targets:
        target_errors = []
        target_warnings = []
        if target.id in target_ids:
            errors.append(f"duplicate target id: {target.id}")
        target_ids.add(target.id)
        if target.kind not in {"tool", "resource"}:
            target_errors.append(f"{target.id}: unsupported kind {target.kind!r}")
        if not target.schema_path.exists():
            target_errors.append(f"{target.id}: missing schema file {target.schema_path}")
        if target.examples_path and not target.examples_path.exists():
            target_errors.append(f"{target.id}: missing examples file {target.examples_path}")
        if target.transcripts_path and not target.transcripts_path.exists():
            target_errors.append(f"{target.id}: missing transcripts file {target.transcripts_path}")

        if target.examples_path and target.examples_path.exists():
            try:
                examples = load_examples(target.examples_path)
                if not examples:
                    target_warnings.append(f"{target.id}: examples file is empty")
                for example in examples:
                    if "payload" not in example:
                        target_errors.append(f"{target.id}: example missing payload field")
            except Exception as exc:
                target_errors.append(f"{target.id}: invalid examples file: {exc}")

        if target.transcripts_path and target.transcripts_path.exists():
            try:
                transcripts = load_transcripts(target.transcripts_path)
                seen_pairs = set()
                for entry in transcripts:
                    if not isinstance(entry.response, dict):
                        target_errors.append(f"{target.id}: transcript response must be an object")
                        continue
                    key = (entry.case_id, entry.target, str(entry.request))
                    if key in seen_pairs:
                        target_warnings.append(f"{target.id}: duplicate transcript entry for {entry.case_id}")
                    seen_pairs.add(key)
                    if entry.target != target.id:
                        target_errors.append(f"{target.id}: transcript target mismatch for {entry.case_id}")
                    if "ok" not in entry.response:
                        target_errors.append(f"{target.id}: transcript response missing ok for {entry.case_id}")
            except Exception as exc:
                target_errors.append(f"{target.id}: invalid transcripts file: {exc}")

        errors.extend(target_errors)
        warnings.extend(target_warnings)
        summaries.append(
            {
                "target": target.id,
                "errors": target_errors,
                "warnings": target_warnings,
            }
        )

    return ValidationResult(suite=suite, errors=errors, warnings=warnings, target_summaries=summaries)


def load_suite_and_validate(path: str) -> Tuple[Suite, ValidationResult]:
    suite = load_suite(path)
    return suite, validate_suite(suite)
