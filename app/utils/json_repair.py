from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JsonRepairResult:
    data: dict[str, Any]
    json_text: str
    repaired: bool


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^```\s*", "", text).strip()
    return re.sub(r"\s*```$", "", text).strip()


def extract_json_object_text(raw_text: str) -> str:
    text = _strip_code_fence(raw_text or "")
    if not text:
        raise ValueError("empty_llm_response")
    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    if start < 0:
        raise ValueError("json_object_start_not_found")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\" and in_string:
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1].strip()

    raise ValueError("json_object_end_not_found")


def _repair_json_text(json_text: str) -> str:
    repaired = json_text.strip()
    for bad_quote in ("“", "”", "„", "‟"):
        repaired = repaired.replace(bad_quote, '"')
    for bad_quote in ("‘", "’"):
        repaired = repaired.replace(bad_quote, "'")
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    return repaired


def _loads_dict(json_text: str) -> dict[str, Any]:
    data = json.loads(json_text)
    if not isinstance(data, dict):
        raise ValueError("json_root_not_object")
    return data


def loads_json_object_with_repair(raw_text: str) -> JsonRepairResult:
    json_text = extract_json_object_text(raw_text)
    try:
        return JsonRepairResult(data=_loads_dict(json_text), json_text=json_text, repaired=False)
    except json.JSONDecodeError:
        repaired_text = _repair_json_text(json_text)
        if repaired_text != json_text:
            try:
                return JsonRepairResult(
                    data=_loads_dict(repaired_text),
                    json_text=repaired_text,
                    repaired=True,
                )
            except json.JSONDecodeError:
                pass

        literal = ast.literal_eval(json_text)
        if not isinstance(literal, dict):
            raise ValueError("json_root_not_object")
        return JsonRepairResult(data=literal, json_text=json_text, repaired=True)
