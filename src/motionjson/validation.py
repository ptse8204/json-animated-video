from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .schemas import SCHEMA_IDS, schema_path


class MotionJSONValidationError(ValueError):
    """Raised when a MotionJSON document cannot be validated."""


@dataclass(frozen=True)
class ValidationIssue:
    path: Path
    message: str
    json_path: str = "$"

    def format(self) -> str:
        return f"{self.path}: {self.json_path}: {self.message}"


@dataclass(frozen=True)
class ValidationResult:
    checked: tuple[Path, ...]
    skipped: tuple[Path, ...]
    issues: tuple[ValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


def load_schema(schema_id: str) -> dict[str, Any]:
    """Load a packaged JSON Schema by MotionJSON schema id."""
    path = schema_path(schema_id)
    return json.loads(path.read_text(encoding="utf-8"))


def infer_schema_id(document: dict[str, Any]) -> str:
    """Return the document schema id from the top-level schema field."""
    schema_id = document.get("schema")
    if not isinstance(schema_id, str) or not schema_id:
        raise MotionJSONValidationError("MotionJSON document is missing a top-level string 'schema' field")
    if schema_id not in SCHEMA_IDS:
        raise MotionJSONValidationError(f"Unsupported MotionJSON schema: {schema_id}")
    return schema_id


def _json_pointer(error: ValidationError) -> str:
    parts = []
    for part in error.absolute_path:
        if isinstance(part, int):
            parts.append(str(part))
        else:
            escaped = str(part).replace("~", "~0").replace("/", "~1")
            parts.append(escaped)
    return "$" if not parts else "$/" + "/".join(parts)


def validate_document(document: dict[str, Any], *, schema_id: str | None = None) -> list[ValidationError]:
    """Validate an in-memory MotionJSON document and return validation errors."""
    resolved_schema_id = schema_id or infer_schema_id(document)
    schema = load_schema(resolved_schema_id)
    validator = Draft202012Validator(schema)
    return sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MotionJSONValidationError(f"Invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise MotionJSONValidationError("MotionJSON document must be a JSON object")
    return data


def validate_file(path: str | Path) -> ValidationResult:
    """Validate one MotionJSON JSON file, inferring its schema from the document."""
    path = Path(path)
    try:
        document = _load_json_file(path)
        errors = validate_document(document)
    except MotionJSONValidationError as exc:
        return ValidationResult(checked=(path,), skipped=(), issues=(ValidationIssue(path=path, message=str(exc)),))

    issues = tuple(ValidationIssue(path=path, message=error.message, json_path=_json_pointer(error)) for error in errors)
    return ValidationResult(checked=(path,), skipped=(), issues=issues)


def _validate_candidate(candidate: Path) -> tuple[bool, tuple[ValidationIssue, ...]]:
    try:
        document = _load_json_file(candidate)
    except MotionJSONValidationError as exc:
        return True, (ValidationIssue(path=candidate, message=str(exc)),)

    schema_id = document.get("schema")
    if schema_id is None:
        return False, ()
    if schema_id not in SCHEMA_IDS:
        return True, (ValidationIssue(path=candidate, message=f"Unsupported MotionJSON schema: {schema_id}"),)

    issues = tuple(
        ValidationIssue(path=candidate, message=error.message, json_path=_json_pointer(error))
        for error in validate_document(document, schema_id=schema_id)
    )
    return True, issues


def validate_output_dir(path: str | Path, *, object_id: str = "object_0") -> ValidationResult:
    """Validate all recognized MotionJSON core JSON files under an output directory.

    Auxiliary JSON such as Lottie exports and benchmark reports do not use MotionJSON
    core schemas and are skipped unless they declare a known MotionJSON schema.
    """
    root = Path(path)
    checked: list[Path] = []
    skipped: list[Path] = []
    issues: list[ValidationIssue] = []

    required = {
        root / "scene_graph.json",
        root / "object_motion.json",
        root / "web_asset_manifest.json",
        root / "resource_profile.json",
        root / "objects" / object_id / "object_manifest.json",
    }
    for candidate in sorted(required):
        if not candidate.exists():
            checked.append(candidate)
            issues.append(ValidationIssue(path=candidate, message="Required MotionJSON artifact is missing"))
            continue
        checked_flag, candidate_issues = _validate_candidate(candidate)
        checked.append(candidate)
        issues.extend(candidate_issues)
        if not checked_flag:
            issues.append(ValidationIssue(path=candidate, message="Required MotionJSON artifact is missing a core schema"))

    for candidate in sorted(root.rglob("*.json")):
        if candidate in required:
            continue
        checked_flag, candidate_issues = _validate_candidate(candidate)
        if checked_flag:
            checked.append(candidate)
            issues.extend(candidate_issues)
        else:
            skipped.append(candidate)

    return ValidationResult(checked=tuple(checked), skipped=tuple(skipped), issues=tuple(issues))


def validate_path(path: str | Path, *, object_id: str = "object_0") -> ValidationResult:
    """Validate one MotionJSON file or an output directory."""
    path = Path(path)
    if path.is_dir():
        return validate_output_dir(path, object_id=object_id)
    return validate_file(path)
