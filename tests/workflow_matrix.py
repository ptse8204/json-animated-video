from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MATRIX_SCHEMA = "motionjson.local_ui_workflow_matrix.v0.1"
MATRIX_PATH = Path(__file__).resolve().parent / "fixtures" / "local_ui_workflow_matrix.v0.1.json"


def load_workflow_matrix() -> dict[str, Any]:
    with MATRIX_PATH.open("r", encoding="utf-8") as handle:
        matrix = json.load(handle)
    assert matrix["schema"] == MATRIX_SCHEMA
    assert isinstance(matrix.get("cases"), list)
    return matrix


def workflow_cases() -> list[dict[str, Any]]:
    return load_workflow_matrix()["cases"]


def workflow_case(case_id: str) -> dict[str, Any]:
    for case in workflow_cases():
        if case["id"] == case_id:
            return case
    raise KeyError(case_id)


def get_path(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if part == "length":
            return len(current)
        if isinstance(current, list):
            current = current[int(part)]
        else:
            current = current[part]
    return current
