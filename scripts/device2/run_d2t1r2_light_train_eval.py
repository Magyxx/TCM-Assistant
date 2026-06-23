from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from datasets import Dataset
from peft import PeftModel, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

try:
    import yaml
except Exception:  # noqa: BLE001
    yaml = None


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.prompts.sft_prompt import build_sft_user_message  # noqa: E402


DEFAULT_BASE_ADAPTER = Path(
    "/mnt/e/ai_artifacts/tcm_assistant_device2/d2t1/d2t1_20260623_formal/adapter/final_adapter"
)
DEFAULT_MODEL_PATH = Path("/mnt/e/models/Qwen2.5-1.5B-Instruct")
DEFAULT_CONFIG = ROOT / "configs" / "device2" / "lora_risk_repair.yaml"
DEFAULT_EVAL_CONFIG = ROOT / "configs" / "device2" / "eval_risk_repair.yaml"
DEFAULT_TRAIN = ROOT / "data" / "sft" / "processed" / "train_sft_risk_repair.jsonl"
DEFAULT_VALID = ROOT / "data" / "sft" / "processed" / "valid_sft_risk_repair.jsonl"
DEFAULT_TRAIN_MESSAGES = ROOT / "data" / "sft" / "processed" / "train_sft_risk_repair_messages.jsonl"
DEFAULT_VALID_MESSAGES = ROOT / "data" / "sft" / "processed" / "valid_sft_risk_repair_messages.jsonl"
DEFAULT_ORIGINAL_EXTRACT = ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_val.jsonl"
DEFAULT_RISK_REPAIR = ROOT / "data" / "sft" / "eval" / "eval_risk_repair.jsonl"
DEFAULT_NEGATION_REPAIR = ROOT / "data" / "sft" / "eval" / "eval_negation_repair.jsonl"
DEFAULT_D2T1_METRICS = ROOT / "artifacts" / "device2" / "d2t1_metrics.json"
DEFAULT_REPO_METRICS = ROOT / "artifacts" / "device2" / "metrics"
DEFAULT_REPO_MANIFESTS = ROOT / "artifacts" / "device2" / "manifests"
DEFAULT_REPO_PREDICTIONS = ROOT / "artifacts" / "device2" / "predictions"
DEFAULT_REPORT_DIR = ROOT / "reports" / "device2"

CORE_FIELDS = ("chief_complaint", "duration", "symptoms_status", "risk_flags_status")
NEGATION_TAGS = {"negation_detection", "parallel_negation", "risk_none", "fever_not_high_risk"}
TRI_STATES = {"unknown", "none", "present"}
OUTPUT_KEYS = {
    "chief_complaint",
    "duration",
    "symptoms",
    "symptoms_status",
    "sleep",
    "appetite",
    "stool_urine",
    "risk_flags",
    "risk_flags_status",
    "next_question",
    "summary",
}
BADCASE_CATEGORIES = [
    "invalid_json",
    "schema_failed",
    "risk_false_negative",
    "risk_false_positive",
    "negation_false_positive",
    "negation_false_negative",
    "risk_keyword_extracted_but_status_wrong",
    "status_correct_but_evidence_missing",
    "hallucinated_symptom",
    "diagnosis_or_prescription_violation",
    "core_field_regression",
]
VIOLATION_MARKERS = [
    "diagnosis",
    "diagnose",
    "prescription",
    "treatment_plan",
    "诊断",
    "处方",
    "方剂",
    "开药",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def ensure_pad_token(tokenizer: Any) -> None:
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token


def load_tokenizer(model_path: Path, allow_download: bool) -> Any:
    from transformers import AutoTokenizer

    loaded = AutoTokenizer.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        local_files_only=not allow_download,
    )
    ensure_pad_token(loaded)
    return loaded


def format_messages(tokenizer: Any, messages: list[dict[str, str]], add_generation_prompt: bool) -> str:
    if getattr(tokenizer, "chat_template", None):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=add_generation_prompt,
        )
    parts = []
    for message in messages:
        parts.append(f"[{message['role'].upper()}]\n{message['content']}")
    if add_generation_prompt:
        parts.append("[ASSISTANT]\n")
    return "\n\n".join(parts)


def build_train_dataset(path: Path, tokenizer: Any, max_length: int) -> Dataset:
    rows = read_jsonl(path)
    texts = [format_messages(tokenizer, row["messages"], add_generation_prompt=False) for row in rows]
    dataset = Dataset.from_dict({"text": texts})

    def tokenize(batch: dict[str, list[str]]) -> dict[str, Any]:
        return tokenizer(batch["text"], truncation=True, max_length=max_length)

    return dataset.map(tokenize, batched=True, remove_columns=["text"])


def load_base_model(model_path: Path, allow_download: bool, dtype: str) -> Any:
    torch_dtype = torch.bfloat16 if dtype == "bf16" else torch.float16
    return AutoModelForCausalLM.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        local_files_only=not allow_download,
        torch_dtype=torch_dtype,
        device_map="auto",
    )


def cleanup_model(model: Any | None = None) -> None:
    if model is not None:
        del model
    import gc

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def strip_assistant(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    return [message for message in messages if message.get("role") != "assistant"]


def extract_json_object_text(text: str) -> str | None:
    text = text.strip()
    import re

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        return fenced.group(1).strip()
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
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
    return None


def parse_json_output(text: str) -> dict[str, Any] | None:
    json_text = extract_json_object_text(text)
    if not json_text:
        return None
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            value = item.get("name") or item.get("value") or item.get("text") or item.get("symptom")
        else:
            value = item
        text = normalize_text(value)
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return output


def normalize_tri_state(value: Any, fallback: str = "unknown") -> str:
    value_text = normalize_text(value)
    if value_text is None:
        return fallback
    value_text = value_text.lower()
    value_text = {"confirmed": "present", "new": "present", "yes": "present", "no": "none", "absent": "none"}.get(
        value_text,
        value_text,
    )
    return value_text if value_text in TRI_STATES else fallback


RISK_KEYWORD_FLAGS: list[tuple[str, list[str]]] = []
NEGATION_MARKERS: list[str] = []


def keyword_negated(text: str, keyword: str, window: int = 12) -> bool:
    compact = "".join(str(text or "").split())
    idx = compact.find(keyword)
    if idx < 0:
        return False
    prefix = compact[max(0, idx - window) : idx].replace("涓嶉€€", "")
    return any(marker in prefix for marker in NEGATION_MARKERS)


def project_risk(user_input: str | None, extracted_flags: list[str], previous_status: str, previous_flags: list[str]) -> tuple[str, list[str]]:
    text = str(user_input or "")
    if previous_status == "present":
        return "present", list(dict.fromkeys(previous_flags + extracted_flags))
    flags = list(dict.fromkeys(extracted_flags))
    negated_match = False
    for flag, keywords in RISK_KEYWORD_FLAGS:
        for keyword in keywords:
            if keyword not in text:
                continue
            if keyword_negated(text, keyword):
                negated_match = True
                continue
            flags.append(flag)
    flags = list(dict.fromkeys(flags))
    if flags:
        return "present", flags
    if negated_match:
        return "none", []
    return "unknown", []


def postprocess_output(parsed: dict[str, Any], state_json: dict[str, Any], user_input: str) -> dict[str, Any]:
    obj = {key: parsed.get(key) for key in OUTPUT_KEYS} if isinstance(parsed, dict) else {}
    chief = normalize_text(obj.get("chief_complaint"))
    duration = normalize_text(obj.get("duration"))
    symptoms = normalize_list(obj.get("symptoms"))
    risk_flags = normalize_list(obj.get("risk_flags"))
    symptoms_status = normalize_tri_state(obj.get("symptoms_status"), fallback="unknown")
    risk_status = normalize_tri_state(obj.get("risk_flags_status"), fallback="unknown")

    if symptoms:
        symptoms_status = "present"
    if risk_status == "none":
        risk_flags = []
    if risk_flags:
        risk_status = "present"
    projected_status, projected_flags = project_risk(
        user_input=user_input,
        extracted_flags=risk_flags,
        previous_status=normalize_tri_state(state_json.get("risk_flags_status"), fallback="unknown"),
        previous_flags=normalize_list(state_json.get("risk_flags")),
    )
    if projected_status == "present":
        risk_status = "present"
        risk_flags = projected_flags
    elif projected_status == "none" and risk_status != "present":
        risk_status = "none"
        risk_flags = []

    return {
        "chief_complaint": chief,
        "duration": duration,
        "symptoms": symptoms,
        "symptoms_status": symptoms_status,
        "sleep": normalize_text(obj.get("sleep")),
        "appetite": normalize_text(obj.get("appetite")),
        "stool_urine": normalize_text(obj.get("stool_urine")),
        "risk_flags": risk_flags,
        "risk_flags_status": risk_status,
        "next_question": normalize_text(obj.get("next_question")),
        "summary": normalize_text(obj.get("summary")) or "",
    }


def validate_output_schema(output: Any) -> str | None:
    if not isinstance(output, dict):
        return "output must be an object"
    extra = set(output) - OUTPUT_KEYS
    if extra:
        return f"unexpected output keys: {sorted(extra)}"
    if not isinstance(output.get("symptoms", []), list):
        return "symptoms must be a list"
    if not isinstance(output.get("risk_flags", []), list):
        return "risk_flags must be a list"
    if output.get("symptoms_status", "unknown") not in TRI_STATES:
        return "symptoms_status must be unknown, none, or present"
    if output.get("risk_flags_status", "unknown") not in TRI_STATES:
        return "risk_flags_status must be unknown, none, or present"
    if not isinstance(output.get("summary", ""), str):
        return "summary must be a string"
    return None


def model_device(model: Any) -> torch.device:
    device = getattr(model, "device", None)
    if device is not None:
        return torch.device(device)
    return next(model.parameters()).device


def generate_predictions(
    *,
    backend: str,
    model: Any,
    tokenizer: Any,
    gold_rows: list[dict[str, Any]],
    message_rows: dict[str, dict[str, Any]],
    out_path: Path,
    max_new_tokens: int,
    limit: int | None,
) -> list[dict[str, Any]]:
    model.eval()
    rows = gold_rows[:limit] if limit else gold_rows
    predictions: list[dict[str, Any]] = []
    device = model_device(model)
    started = time.time()

    for index, gold in enumerate(rows, start=1):
        sample_id = gold["id"]
        message_row = message_rows[sample_id]
        input_messages = strip_assistant(message_row["messages"])
        prompt = format_messages(tokenizer, input_messages, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt")
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        input_len = inputs["input_ids"].shape[1]
        raw_output = tokenizer.decode(output_ids[0][input_len:], skip_special_tokens=True).strip()
        parsed = parse_json_output(raw_output) or {}
        postprocessed = postprocess_output(
            parsed,
            state_json=(gold.get("input") or {}).get("state_json") or {},
            user_input=str((gold.get("input") or {}).get("user_input") or ""),
        )
        schema_error = validate_output_schema(postprocessed)
        predictions.append(
            {
                "id": sample_id,
                "backend": backend,
                "output": postprocessed,
                "parsed_output": parsed,
                "raw_output": raw_output,
                "schema_ok": schema_error is None,
                "schema_error": schema_error,
                "meta": gold.get("meta", {}),
            }
        )
        if index % 2 == 0 and torch.cuda.is_available():
            torch.cuda.empty_cache()

    write_jsonl(out_path, predictions)
    elapsed = round(time.time() - started, 3)
    return [{**row, "generation_elapsed_seconds_total": elapsed} for row in predictions]


def normalize_value(value: Any) -> Any:
    if isinstance(value, list):
        return sorted(str(item).strip() for item in value)
    if isinstance(value, str):
        return value.strip()
    return value


def field_results(expected: dict[str, Any], predicted: dict[str, Any]) -> dict[str, bool]:
    return {field: normalize_value(expected.get(field)) == normalize_value(predicted.get(field)) for field in CORE_FIELDS}


def is_negation_case(row: dict[str, Any]) -> bool:
    row_tags = set((row.get("meta") or {}).get("tags") or [])
    return bool(row_tags & NEGATION_TAGS) or any("negation" in str(tag) for tag in row_tags)


def is_risk_case(row: dict[str, Any]) -> bool:
    row_tags = set((row.get("meta") or {}).get("tags") or [])
    expected = row.get("output") or {}
    return any("risk" in str(tag) for tag in row_tags) or expected.get("risk_flags_status") != "unknown"


def rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def evaluate_predictions(gold_rows: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    pred_by_id = {row["id"]: row for row in predictions}
    total = 0
    exact = 0
    schema_pass = 0
    field_pass = {field: 0 for field in CORE_FIELDS}
    neg_total = 0
    neg_risk_status_pass = 0
    risk_total = 0
    risk_status_pass = 0
    coherent_risk_total = 0
    coherent_risk_status_pass = 0
    badcases: list[dict[str, Any]] = []

    for gold in gold_rows:
        pred = pred_by_id.get(gold["id"])
        if pred is None:
            badcases.append({"id": gold["id"], "reason": "missing prediction"})
            continue
        total += 1
        expected = gold.get("output") or {}
        predicted = pred.get("output") or {}
        if pred.get("schema_ok"):
            schema_pass += 1
        fields = field_results(expected, predicted)
        for field, ok in fields.items():
            if ok:
                field_pass[field] += 1
        if all(fields.values()):
            exact += 1
        else:
            badcases.append(
                {
                    "id": gold["id"],
                    "tags": (gold.get("meta") or {}).get("tags") or [],
                    "failed_fields": [field for field, ok in fields.items() if not ok],
                    "expected_core": {field: expected.get(field) for field in CORE_FIELDS},
                    "predicted_core": {field: predicted.get(field) for field in CORE_FIELDS},
                    "raw_output_preview": str(pred.get("raw_output", ""))[:500],
                }
            )
        if is_negation_case(gold):
            neg_total += 1
            if normalize_value(expected.get("risk_flags_status")) == normalize_value(predicted.get("risk_flags_status")):
                neg_risk_status_pass += 1
        if is_risk_case(gold):
            risk_total += 1
            if normalize_value(expected.get("risk_flags_status")) == normalize_value(predicted.get("risk_flags_status")):
                risk_status_pass += 1
            coherent_risk_total += 1
            if normalize_value(expected.get("risk_flags_status")) == normalize_value(predicted.get("risk_flags_status")):
                coherent_risk_status_pass += 1

    return {
        "total": total,
        "exact_core_pass": exact,
        "exact_core_rate": rate(exact, total),
        "schema_pass": schema_pass,
        "schema_pass_rate": rate(schema_pass, total),
        "field_pass": field_pass,
        "field_rates": {field: rate(count, total) for field, count in field_pass.items()},
        "negation_total": neg_total,
        "negation_risk_status_pass": neg_risk_status_pass,
        "negation_risk_status_rate": rate(neg_risk_status_pass, neg_total),
        "risk_total": risk_total,
        "risk_status_pass": risk_status_pass,
        "risk_status_rate": rate(risk_status_pass, risk_total),
        "coherent_risk_total": coherent_risk_total,
        "coherent_risk_status_pass": coherent_risk_status_pass,
        "coherent_risk_status_rate": rate(coherent_risk_status_pass, coherent_risk_total),
        "badcases": badcases,
    }


def line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def file_summary(path: Path) -> dict[str, Any]:
    return {
        "path": rel(path),
        "sha256": sha256_file(path),
        "line_count": line_count(path),
        "bytes": path.stat().st_size,
    }


def config_summary(path: Path) -> dict[str, Any]:
    return {
        "path": rel(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists() or yaml is None:
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def git_command(args: list[str]) -> str:
    safe_dir = str(ROOT).replace("\\", "/")
    proc = subprocess.run(
        ["git", "-c", f"safe.directory={safe_dir}", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        return f"<git failed: {proc.stderr.strip() or proc.stdout.strip()}>"
    return proc.stdout.strip()


def git_info() -> dict[str, Any]:
    return {
        "branch": git_command(["branch", "--show-current"]),
        "head": git_command(["rev-parse", "--short", "HEAD"]),
        "head_full": git_command(["rev-parse", "HEAD"]),
        "status_short": git_command(["status", "--short"]),
        "recent_commits": git_command(["log", "--oneline", "--decorate", "-8"]).splitlines(),
    }


def module_versions(names: list[str]) -> dict[str, dict[str, Any]]:
    versions: dict[str, dict[str, Any]] = {}
    for name in names:
        try:
            module = importlib.import_module(name)
            versions[name] = {"ok": True, "version": getattr(module, "__version__", "unknown")}
        except Exception as exc:  # noqa: BLE001
            versions[name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return versions


def training_env_summary() -> dict[str, Any]:
    cuda_available = torch.cuda.is_available()
    return {
        "python": sys.executable,
        "prefix": sys.prefix,
        "packages": module_versions(
            ["torch", "transformers", "datasets", "accelerate", "peft", "trl", "bitsandbytes", "safetensors", "yaml"]
        ),
        "torch": {
            "version": getattr(torch, "__version__", "unknown"),
            "cuda_version": getattr(torch.version, "cuda", None),
            "cuda_available": cuda_available,
            "device_count": torch.cuda.device_count() if cuda_available else 0,
            "device_name": torch.cuda.get_device_name(0) if cuda_available else None,
        },
        "env": {
            key: os.environ.get(key)
            for key in ["HF_HOME", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE", "PIP_CACHE_DIR", "TMPDIR", "TCM_DEVICE2_ARTIFACTS"]
        },
        "vllm_importable": importlib.util.find_spec("vllm") is not None,
    }


def raw_to_message_row(row: dict[str, Any]) -> dict[str, Any]:
    input_payload = row.get("input") or {}
    output_payload = row.get("output") or {}
    return {
        "id": row["id"],
        "task": row.get("task", "report_turn_extraction"),
        "messages": [
            {"role": "system", "content": str(row.get("system_prompt") or "")},
            {
                "role": "user",
                "content": build_sft_user_message(
                    state_json=input_payload.get("state_json") or {},
                    user_input=str(input_payload.get("user_input") or ""),
                ),
            },
            {"role": "assistant", "content": json.dumps(output_payload, ensure_ascii=False)},
        ],
        "meta": row.get("meta") or {},
    }


def build_eval_sets(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    original_rows = read_jsonl(args.original_extract_file)
    original_negation = [row for row in original_rows if is_negation_case(row)]
    original_risk = [row for row in original_rows if is_risk_case(row)]
    risk_repair_rows = read_jsonl(args.eval_risk_repair_file)
    negation_repair_rows = read_jsonl(args.eval_negation_repair_file)

    return {
        "eval_extract": {
            "label": "original_extract",
            "rows": original_rows,
            "source_path": rel(args.original_extract_file),
            "source_kind": "file",
        },
        "eval_negation": {
            "label": "original_negation",
            "rows": original_negation,
            "source_path": rel(args.original_extract_file),
            "source_kind": "derived_from_original_extract",
            "standalone_file_exists": False,
        },
        "eval_risk": {
            "label": "original_risk",
            "rows": original_risk,
            "source_path": rel(args.original_extract_file),
            "source_kind": "derived_from_original_extract",
            "standalone_file_exists": False,
        },
        "eval_risk_repair": {
            "label": "risk_repair",
            "rows": risk_repair_rows,
            "source_path": rel(args.eval_risk_repair_file),
            "source_kind": "file",
        },
        "eval_negation_repair": {
            "label": "negation_repair",
            "rows": negation_repair_rows,
            "source_path": rel(args.eval_negation_repair_file),
            "source_kind": "file",
        },
    }


def load_trainable_adapter_model(model_path: Path, adapter_path: Path, allow_download: bool, compute_dtype: str) -> Any:
    torch_dtype = torch.bfloat16 if compute_dtype == "bf16" else torch.float16
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch_dtype,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        local_files_only=not allow_download,
        quantization_config=quantization_config,
        device_map="auto",
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)
    return PeftModel.from_pretrained(model, str(adapter_path), is_trainable=True, local_files_only=True)


def latest_log_value(logs: list[dict[str, Any]], key: str) -> float | None:
    for item in reversed(logs):
        value = item.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return round(float(value), 6)
    return None


def run_training(args: argparse.Namespace, run_paths: dict[str, Path], tokenizer: Any) -> dict[str, Any]:
    train_dataset = build_train_dataset(args.train_messages_file, tokenizer, args.max_length)
    valid_dataset = build_train_dataset(args.valid_messages_file, tokenizer, args.max_length)
    trainer_output_dir = run_paths["trainer_output_dir"]
    adapter_dir = run_paths["adapter_dir"]

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    model = load_trainable_adapter_model(
        args.model_path,
        args.resume_adapter,
        allow_download=args.allow_download,
        compute_dtype=args.compute_dtype,
    )

    training_args = TrainingArguments(
        output_dir=str(trainer_output_dir),
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_train_epochs,
        max_steps=args.max_steps if args.max_steps > 0 else -1,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        bf16=args.compute_dtype == "bf16",
        fp16=args.compute_dtype == "fp16",
        report_to="none",
        remove_unused_columns=False,
        eval_strategy="epoch",
        save_strategy="epoch",
        gradient_checkpointing=args.gradient_checkpointing,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=valid_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )

    started = time.time()
    started_at = utc_now()
    train_output = trainer.train()
    eval_metrics = trainer.evaluate()
    ended_at = utc_now()
    duration = round(time.time() - started, 3)

    trainer.save_model(str(adapter_dir))
    trainer.save_state()
    tokenizer.save_pretrained(str(adapter_dir))
    peak_memory = None
    if torch.cuda.is_available():
        peak_memory = round(torch.cuda.max_memory_allocated() / (1024**3), 4)
    logs = list(trainer.state.log_history)
    cleanup_model(model)

    return {
        "status": "ok",
        "start_time": started_at,
        "end_time": ended_at,
        "duration_seconds": duration,
        "base_model_path": str(args.model_path),
        "resume_adapter_path": str(args.resume_adapter),
        "output_adapter_path": str(adapter_dir),
        "train_loss": round(float(train_output.training_loss), 6) if train_output.training_loss is not None else latest_log_value(logs, "loss"),
        "eval_loss": round(float(eval_metrics["eval_loss"]), 6) if "eval_loss" in eval_metrics else latest_log_value(logs, "eval_loss"),
        "train_steps": int(getattr(trainer.state, "global_step", 0)),
        "num_train_epochs": args.num_train_epochs,
        "peak_gpu_memory_gib": peak_memory,
        "oom_or_downgrade_events": [],
        "log_history": logs,
        "train_args": {
            "qlora": True,
            "continued_from_adapter": True,
            "num_train_epochs": args.num_train_epochs,
            "max_steps_effective": args.max_steps if args.max_steps > 0 else None,
            "learning_rate": args.learning_rate,
            "max_length": args.max_length,
            "per_device_train_batch_size": args.per_device_train_batch_size,
            "gradient_accumulation_steps": args.gradient_accumulation_steps,
            "compute_dtype": args.compute_dtype,
            "gradient_checkpointing": args.gradient_checkpointing,
        },
    }


def adapter_check(adapter_dir: Path, trainer_output_dir: Path) -> dict[str, Any]:
    expected = {
        "adapter_config": adapter_dir / "adapter_config.json",
        "adapter_model": adapter_dir / "adapter_model.safetensors",
        "tokenizer_json": adapter_dir / "tokenizer.json",
        "tokenizer_config": adapter_dir / "tokenizer_config.json",
        "training_args": adapter_dir / "training_args.bin",
        "trainer_state": trainer_output_dir / "trainer_state.json",
    }
    files = {name: {"path": str(path), "exists": path.exists(), "bytes": path.stat().st_size if path.exists() else 0} for name, path in expected.items()}
    required_ok = all(files[name]["exists"] for name in ["adapter_config", "adapter_model", "tokenizer_config"])
    return {
        "generated_at": utc_now(),
        "adapter_path": str(adapter_dir),
        "trainer_output_dir": str(trainer_output_dir),
        "status": "ok" if required_ok else "failed",
        "files": files,
        "git_policy": {
            "adapter_model_safetensors_external_only": str(adapter_dir).startswith("/mnt/e/"),
            "do_not_commit_weight_files": True,
        },
    }


def text_blob(row: dict[str, Any]) -> str:
    input_payload = row.get("input") or {}
    state = input_payload.get("state_json") or {}
    output = row.get("output") or {}
    pieces = [
        str(input_payload.get("user_input") or ""),
        str(state.get("summary") or ""),
        " ".join(str(item) for item in state.get("symptoms") or []),
        " ".join(str(item) for item in state.get("risk_flags") or []),
        " ".join(str(item) for item in output.get("symptoms") or []),
        " ".join(str(item) for item in output.get("risk_flags") or []),
        str(output.get("summary") or ""),
    ]
    return " ".join(pieces)


def list_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def expected_status(row: dict[str, Any]) -> str:
    return str((row.get("output") or {}).get("risk_flags_status") or "unknown")


def predicted_status(pred: dict[str, Any] | None) -> str:
    if pred is None:
        return "<missing>"
    return str((pred.get("output") or {}).get("risk_flags_status") or "<missing>")


def has_violation(pred: dict[str, Any] | None) -> bool:
    if pred is None:
        return False
    raw = str(pred.get("raw_output") or "")
    parsed = pred.get("parsed_output") if isinstance(pred.get("parsed_output"), dict) else {}
    parsed_keys = " ".join(str(key) for key in parsed)
    parsed_values = " ".join(str(value) for value in parsed.values())
    combined = f"{raw} {parsed_keys} {parsed_values}".lower()
    return any(marker.lower() in combined for marker in VIOLATION_MARKERS)


def has_hallucinated_symptom(row: dict[str, Any], pred: dict[str, Any] | None) -> bool:
    if pred is None:
        return False
    predicted = pred.get("output") or {}
    expected = row.get("output") or {}
    source = text_blob(row)
    expected_items = set(list_items(expected.get("symptoms")) + list_items(expected.get("risk_flags")))
    for item in list_items(predicted.get("symptoms")) + list_items(predicted.get("risk_flags")):
        if item in expected_items:
            continue
        if item and item in source:
            continue
        return True
    return False


def enrich_metrics(gold_rows: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = evaluate_predictions(gold_rows, predictions)
    pred_by_id = {row["id"]: row for row in predictions}
    json_valid = 0
    false_negative = 0
    false_positive = 0
    negation_false_positive = 0
    negation_false_negative = 0
    hallucinated = 0
    violations = 0
    status_correct_but_evidence_missing = 0
    risk_keyword_extracted_but_status_wrong = 0

    for gold in gold_rows:
        pred = pred_by_id.get(gold["id"])
        if pred and parse_json_output(str(pred.get("raw_output") or "")) is not None:
            json_valid += 1
        expected = expected_status(gold)
        predicted = predicted_status(pred)
        predicted_flags = list_items((pred.get("output") or {}).get("risk_flags") if pred else [])
        if expected == "present" and predicted != "present":
            false_negative += 1
        if expected != "present" and predicted == "present":
            false_positive += 1
        if is_negation_case(gold) and expected != "present" and predicted == "present":
            negation_false_positive += 1
        if is_negation_case(gold) and expected == "present" and predicted != "present":
            negation_false_negative += 1
        if predicted_flags and expected != predicted:
            risk_keyword_extracted_but_status_wrong += 1
        if predicted == "present" and not predicted_flags:
            status_correct_but_evidence_missing += 1
        if has_hallucinated_symptom(gold, pred):
            hallucinated += 1
        if has_violation(pred):
            violations += 1

    total = metrics["total"]
    metrics.update(
        {
            "json_valid": json_valid,
            "json_valid_rate": rate(json_valid, total),
            "risk_false_negative_count": false_negative,
            "risk_false_positive_count": false_positive,
            "negation_accuracy": metrics["negation_risk_status_rate"],
            "negation_false_positive_count": negation_false_positive,
            "negation_false_negative_count": negation_false_negative,
            "hallucinated_symptom_count": hallucinated,
            "hallucination_rate": rate(hallucinated, total),
            "diagnosis_or_prescription_violation_count": violations,
            "risk_keyword_extracted_but_status_wrong_count": risk_keyword_extracted_but_status_wrong,
            "status_correct_but_evidence_missing_count": status_correct_but_evidence_missing,
        }
    )
    return metrics


def classify_badcases(eval_name: str, gold_rows: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pred_by_id = {row["id"]: row for row in predictions}
    cases: list[dict[str, Any]] = []
    for gold in gold_rows:
        pred = pred_by_id.get(gold["id"])
        expected = expected_status(gold)
        predicted = predicted_status(pred)
        predicted_output = pred.get("output") if pred else {}
        expected_output = gold.get("output") or {}
        categories: list[str] = []

        if pred is None or parse_json_output(str(pred.get("raw_output") or "")) is None:
            categories.append("invalid_json")
        if pred is None or not pred.get("schema_ok"):
            categories.append("schema_failed")
        if expected == "present" and predicted != "present":
            categories.append("risk_false_negative")
        if expected != "present" and predicted == "present":
            categories.append("risk_false_positive")
        if is_negation_case(gold) and expected != "present" and predicted == "present":
            categories.append("negation_false_positive")
        if is_negation_case(gold) and expected == "present" and predicted != "present":
            categories.append("negation_false_negative")
        if list_items((predicted_output or {}).get("risk_flags")) and expected != predicted:
            categories.append("risk_keyword_extracted_but_status_wrong")
        if predicted == "present" and not list_items((predicted_output or {}).get("risk_flags")):
            categories.append("status_correct_but_evidence_missing")
        if has_hallucinated_symptom(gold, pred):
            categories.append("hallucinated_symptom")
        if has_violation(pred):
            categories.append("diagnosis_or_prescription_violation")
        field_ok = field_results(expected_output, predicted_output or {}) if pred else {field: False for field in CORE_FIELDS}
        if not all(field_ok.values()):
            categories.append("core_field_regression")

        if categories:
            cases.append(
                {
                    "eval_set": eval_name,
                    "id": gold["id"],
                    "categories": categories,
                    "tags": (gold.get("meta") or {}).get("tags") or [],
                    "expected_core": {field: expected_output.get(field) for field in CORE_FIELDS},
                    "predicted_core": {field: (predicted_output or {}).get(field) for field in CORE_FIELDS},
                    "raw_output_preview": str((pred or {}).get("raw_output", ""))[:500],
                }
            )
    return cases


def summarize_badcases(all_cases: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {category: 0 for category in BADCASE_CATEGORIES}
    severity = {category: index for index, category in enumerate(BADCASE_CATEGORIES)}
    for case in all_cases:
        for category in case["categories"]:
            counts[category] = counts.get(category, 0) + 1
    top_cases = sorted(
        all_cases,
        key=lambda item: min(severity.get(category, 99) for category in item["categories"]),
    )[:10]
    return {
        "generated_at": utc_now(),
        "category_counts": counts,
        "total_badcases": len(all_cases),
        "top_10_badcases": top_cases,
        "all_badcases": all_cases,
    }


def evaluate_adapter(
    *,
    backend: str,
    adapter_path: Path,
    args: argparse.Namespace,
    tokenizer: Any,
    eval_sets: dict[str, dict[str, Any]],
    run_paths: dict[str, Path],
    write_requested_metrics: bool,
) -> dict[str, Any]:
    model_base = load_base_model(args.model_path, allow_download=args.allow_download, dtype=args.compute_dtype)
    model = PeftModel.from_pretrained(model_base, str(adapter_path), local_files_only=True)
    model.eval()

    results: dict[str, Any] = {}
    for eval_name, item in eval_sets.items():
        rows = item["rows"]
        message_rows = {row["id"]: raw_to_message_row(row) for row in rows}
        pred_path = run_paths["prediction_dir"] / f"{backend}_{eval_name}_predictions.jsonl"
        predictions = generate_predictions(
            backend=backend,
            model=model,
            tokenizer=tokenizer,
            gold_rows=rows,
            message_rows=message_rows,
            out_path=pred_path,
            max_new_tokens=args.max_new_tokens,
            limit=None,
        )
        sample_path = DEFAULT_REPO_PREDICTIONS / f"d2t1r2_{backend}_{eval_name}_sample.jsonl"
        write_jsonl(sample_path, predictions[: min(3, len(predictions))])
        metrics = enrich_metrics(rows, predictions)
        payload = {
            "generated_at": utc_now(),
            "stage": "D2-T1R2",
            "backend": backend,
            "adapter_path": str(adapter_path),
            "eval_set": eval_name,
            "eval_label": item["label"],
            "source_path": item["source_path"],
            "source_kind": item["source_kind"],
            "standalone_file_exists": item.get("standalone_file_exists", True),
            "prediction_path_external": str(pred_path),
            "prediction_sample_repo": rel(sample_path),
            "metrics": metrics,
        }
        if write_requested_metrics:
            write_json(DEFAULT_REPO_METRICS / f"d2t1r2_{eval_name}_metrics.json", payload)
        results[eval_name] = payload
    cleanup_model(model)
    return results


def compare_value(baseline: float | int | None, candidate: float | int | None, higher_is_better: bool = True) -> str:
    if baseline is None or candidate is None:
        return "not_comparable"
    if candidate == baseline:
        return "unchanged"
    improved = candidate > baseline if higher_is_better else candidate < baseline
    return "improved" if improved else "regressed"


def build_comparison(
    baseline_file_metrics: dict[str, Any],
    d2t1_eval: dict[str, Any],
    d2t1r2_eval: dict[str, Any],
) -> dict[str, Any]:
    baseline_lora = baseline_file_metrics.get("lora_metrics") or {}
    original = d2t1r2_eval["eval_extract"]["metrics"]
    original_risk = d2t1r2_eval["eval_risk"]["metrics"]
    original_negation = d2t1r2_eval["eval_negation"]["metrics"]
    d2t1_original = d2t1_eval["eval_extract"]["metrics"]
    d2t1_risk_repair = d2t1_eval["eval_risk_repair"]["metrics"]
    r2_risk_repair = d2t1r2_eval["eval_risk_repair"]["metrics"]
    d2t1_negation_repair = d2t1_eval["eval_negation_repair"]["metrics"]
    r2_negation_repair = d2t1r2_eval["eval_negation_repair"]["metrics"]

    metrics = {
        "exact_core_rate": {
            "d2t1": baseline_lora.get("exact_core_rate"),
            "d2t1r2": original.get("exact_core_rate"),
            "conclusion": compare_value(baseline_lora.get("exact_core_rate"), original.get("exact_core_rate")),
        },
        "schema_pass_rate": {
            "d2t1": baseline_lora.get("schema_pass_rate"),
            "d2t1r2": original.get("schema_pass_rate"),
            "conclusion": compare_value(baseline_lora.get("schema_pass_rate"), original.get("schema_pass_rate")),
        },
        "json_valid_rate": {
            "d2t1": d2t1_original.get("json_valid_rate"),
            "d2t1r2": original.get("json_valid_rate"),
            "conclusion": compare_value(d2t1_original.get("json_valid_rate"), original.get("json_valid_rate")),
        },
        "risk_status_rate": {
            "d2t1": baseline_lora.get("risk_status_rate"),
            "d2t1r2": original_risk.get("risk_status_rate"),
            "conclusion": compare_value(baseline_lora.get("risk_status_rate"), original_risk.get("risk_status_rate")),
        },
        "coherent_risk_status_rate": {
            "d2t1": d2t1_eval["eval_risk"].get("metrics", {}).get("coherent_risk_status_rate"),
            "d2t1r2": original_risk.get("coherent_risk_status_rate"),
            "conclusion": compare_value(
                d2t1_eval["eval_risk"].get("metrics", {}).get("coherent_risk_status_rate"),
                original_risk.get("coherent_risk_status_rate"),
            ),
        },
        "risk_false_negative_count": {
            "d2t1": d2t1_risk_repair.get("risk_false_negative_count"),
            "d2t1r2": r2_risk_repair.get("risk_false_negative_count"),
            "conclusion": compare_value(
                d2t1_risk_repair.get("risk_false_negative_count"),
                r2_risk_repair.get("risk_false_negative_count"),
                higher_is_better=False,
            ),
        },
        "risk_false_positive_count": {
            "d2t1": d2t1_risk_repair.get("risk_false_positive_count"),
            "d2t1r2": r2_risk_repair.get("risk_false_positive_count"),
            "conclusion": compare_value(
                d2t1_risk_repair.get("risk_false_positive_count"),
                r2_risk_repair.get("risk_false_positive_count"),
                higher_is_better=False,
            ),
        },
        "negation_accuracy": {
            "d2t1": d2t1_negation_repair.get("negation_accuracy"),
            "d2t1r2": r2_negation_repair.get("negation_accuracy"),
            "conclusion": compare_value(d2t1_negation_repair.get("negation_accuracy"), r2_negation_repair.get("negation_accuracy")),
        },
        "hallucination_rate": {
            "d2t1": d2t1_original.get("hallucination_rate"),
            "d2t1r2": original.get("hallucination_rate"),
            "conclusion": compare_value(d2t1_original.get("hallucination_rate"), original.get("hallucination_rate"), higher_is_better=False),
        },
        "diagnosis_or_prescription_violation_count": {
            "d2t1": d2t1_original.get("diagnosis_or_prescription_violation_count"),
            "d2t1r2": original.get("diagnosis_or_prescription_violation_count"),
            "conclusion": compare_value(
                d2t1_original.get("diagnosis_or_prescription_violation_count"),
                original.get("diagnosis_or_prescription_violation_count"),
                higher_is_better=False,
            ),
        },
    }
    return {
        "generated_at": utc_now(),
        "stage": "D2-T1R2",
        "baseline_note": "D2-T1 file metrics are from artifacts/device2/d2t1_metrics.json; repair-set baseline is freshly evaluated with the D2-T1 adapter.",
        "original_eval_note": "original eval_risk/eval_negation are derived subsets of sft_report_turn_extract_val.jsonl because standalone files are absent.",
        "metrics": metrics,
    }


def decide_status(comparison: dict[str, Any], d2t1r2_eval: dict[str, Any], adapter_payload: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    metrics = comparison["metrics"]
    risk_repair = d2t1r2_eval["eval_risk_repair"]["metrics"]
    negation_repair = d2t1r2_eval["eval_negation_repair"]["metrics"]
    original = d2t1r2_eval["eval_extract"]["metrics"]
    original_risk = d2t1r2_eval["eval_risk"]["metrics"]

    if adapter_payload["status"] != "ok":
        return "failed", ["adapter check failed"]
    if original.get("schema_pass_rate", 0.0) < (metrics["schema_pass_rate"].get("d2t1") or 0.0):
        reasons.append("schema_pass_rate regressed below D2-T1")
    if original.get("exact_core_rate", 0.0) < 0.5:
        reasons.append("exact_core_rate is below D2-T1 threshold 0.5")
    if original_risk.get("risk_status_rate", 0.0) <= 0.3333:
        reasons.append("risk_status_rate is not clearly above D2-T1 baseline 0.3333")
    if risk_repair.get("risk_false_negative_count", 0) != 0:
        reasons.append("eval_risk_repair still has risk false negatives")
    if negation_repair.get("negation_accuracy", 0.0) < (metrics["negation_accuracy"].get("d2t1") or 0.0):
        reasons.append("negation accuracy regressed on negation repair set")
    if metrics["hallucination_rate"]["conclusion"] == "regressed":
        reasons.append("hallucination_rate increased on original extract set")
    if original.get("diagnosis_or_prescription_violation_count", 0) != 0:
        reasons.append("diagnosis/prescription boundary violation found")
    return ("caution" if reasons else "ok"), reasons


def markdown_table(rows: list[tuple[str, Any]]) -> str:
    lines = ["| Metric | Value |", "| --- | ---: |"]
    for key, value in rows:
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines)


def write_manifest_reports(manifest: dict[str, Any]) -> None:
    write_json(DEFAULT_REPO_MANIFESTS / "d2t1r2_run_manifest.json", manifest)
    lines = [
        "# D2-T1R2 Run Manifest",
        "",
        f"Generated at: `{manifest['generated_at']}`",
        "",
        "## Git",
        "",
        f"* branch: `{manifest['git']['branch']}`",
        f"* head: `{manifest['git']['head']}`",
        f"* status at freeze: `{manifest['git']['status_short'] or 'clean'}`",
        "",
        "## Inputs",
        "",
        f"* base adapter: `{manifest['base_d2t1_adapter_path']}`",
        f"* train repair data: `{manifest['files']['train_repair']['path']}` ({manifest['files']['train_repair']['line_count']} lines)",
        f"* valid repair data: `{manifest['files']['valid_repair']['path']}` ({manifest['files']['valid_repair']['line_count']} lines)",
        f"* eval risk repair: `{manifest['files']['eval_risk_repair']['path']}` ({manifest['files']['eval_risk_repair']['line_count']} lines)",
        f"* eval negation repair: `{manifest['files']['eval_negation_repair']['path']}` ({manifest['files']['eval_negation_repair']['line_count']} lines)",
        f"* config: `{manifest['files']['config']['path']}`",
        "",
        "## Outputs",
        "",
        f"* output adapter target: `{manifest['output_adapter_target_path']}`",
        f"* vLLM touched: `{manifest['vllm_touched']}`",
    ]
    write_text(DEFAULT_REPORT_DIR / "d2t1r2_run_manifest.md", "\n".join(lines) + "\n")


def write_training_report(training: dict[str, Any]) -> None:
    write_json(DEFAULT_REPO_METRICS / "d2t1r2_training_metrics.json", training)
    rows = [
        ("status", training["status"]),
        ("continued_from_adapter", training["train_args"]["continued_from_adapter"]),
        ("epochs", training["num_train_epochs"]),
        ("steps", training["train_steps"]),
        ("train_loss", training["train_loss"]),
        ("eval_loss", training["eval_loss"]),
        ("duration_seconds", training["duration_seconds"]),
        ("peak_gpu_memory_gib", training["peak_gpu_memory_gib"]),
    ]
    lines = [
        "# D2-T1R2 Training Report",
        "",
        f"Generated at: `{utc_now()}`",
        "",
        "## Summary",
        "",
        markdown_table(rows),
        "",
        "## Paths",
        "",
        f"* base model: `{training['base_model_path']}`",
        f"* resume adapter: `{training['resume_adapter_path']}`",
        f"* output adapter: `{training['output_adapter_path']}`",
        "",
        "Adapters, checkpoints, and model weights are external to the Git repository.",
    ]
    write_text(DEFAULT_REPORT_DIR / "d2t1r2_training_report.md", "\n".join(lines) + "\n")


def write_evaluation_report(d2t1_eval: dict[str, Any], d2t1r2_eval: dict[str, Any]) -> None:
    lines = ["# D2-T1R2 Evaluation Report", "", f"Generated at: `{utc_now()}`", ""]
    for eval_name, payload in d2t1r2_eval.items():
        metrics = payload["metrics"]
        lines.extend(
            [
                f"## {eval_name}",
                "",
                f"* source: `{payload['source_path']}`",
                f"* source kind: `{payload['source_kind']}`",
                f"* D2-T1 sample prediction: `{d2t1_eval[eval_name]['prediction_sample_repo']}`",
                f"* D2-T1R2 sample prediction: `{payload['prediction_sample_repo']}`",
                "",
                markdown_table(
                    [
                        ("total", metrics["total"]),
                        ("exact_core_rate", metrics["exact_core_rate"]),
                        ("schema_pass_rate", metrics["schema_pass_rate"]),
                        ("json_valid_rate", metrics["json_valid_rate"]),
                        ("risk_status_rate", metrics["risk_status_rate"]),
                        ("coherent_risk_status_rate", metrics["coherent_risk_status_rate"]),
                        ("risk_false_negative_count", metrics["risk_false_negative_count"]),
                        ("risk_false_positive_count", metrics["risk_false_positive_count"]),
                        ("negation_accuracy", metrics["negation_accuracy"]),
                        ("hallucination_rate", metrics["hallucination_rate"]),
                        ("diagnosis_or_prescription_violation_count", metrics["diagnosis_or_prescription_violation_count"]),
                    ]
                ),
                "",
            ]
        )
    write_text(DEFAULT_REPORT_DIR / "d2t1r2_evaluation_report.md", "\n".join(lines) + "\n")


def write_comparison_report(comparison: dict[str, Any], status: str, reasons: list[str]) -> None:
    write_json(DEFAULT_REPO_METRICS / "d2t1r2_compare_to_d2t1.json", comparison)
    lines = [
        "# D2-T1R2 Compare To D2-T1",
        "",
        f"Generated at: `{comparison['generated_at']}`",
        "",
        f"Acceptance status: `{status}`",
        "",
    ]
    if reasons:
        lines.extend(["## Cautions", ""])
        lines.extend(f"* {reason}" for reason in reasons)
        lines.append("")
    lines.extend(["## Metrics", "", "| Metric | D2-T1 | D2-T1R2 | Conclusion |", "| --- | ---: | ---: | --- |"])
    for name, item in comparison["metrics"].items():
        lines.append(f"| {name} | {item.get('d2t1')} | {item.get('d2t1r2')} | {item.get('conclusion')} |")
    lines.extend(["", "## Notes", "", f"* {comparison['baseline_note']}", f"* {comparison['original_eval_note']}"])
    write_text(DEFAULT_REPORT_DIR / "d2t1r2_compare_to_d2t1.md", "\n".join(lines) + "\n")


def write_badcase_report(badcases: dict[str, Any]) -> None:
    write_json(DEFAULT_REPO_METRICS / "d2t1r2_badcases.json", badcases)
    lines = [
        "# D2-T1R2 Badcase Analysis",
        "",
        f"Generated at: `{badcases['generated_at']}`",
        "",
        "## Category Counts",
        "",
        "| Category | Count |",
        "| --- | ---: |",
    ]
    for category in BADCASE_CATEGORIES:
        lines.append(f"| {category} | {badcases['category_counts'].get(category, 0)} |")
    lines.extend(["", "## Top 10 Badcases", ""])
    if not badcases["top_10_badcases"]:
        lines.append("No remaining badcases in the D2-T1R2 evaluation outputs.")
    else:
        for case in badcases["top_10_badcases"]:
            lines.append(f"* `{case['eval_set']}` / `{case['id']}`: {', '.join(case['categories'])}")
    write_text(DEFAULT_REPORT_DIR / "d2t1r2_badcase_analysis.md", "\n".join(lines) + "\n")


def build_manifest(args: argparse.Namespace, run_paths: dict[str, Path]) -> dict[str, Any]:
    return {
        "generated_at": utc_now(),
        "stage": "D2-T1R2: Risk Repair Light Training",
        "git": git_info(),
        "base_d2t1_adapter_path": str(args.resume_adapter),
        "files": {
            "train_repair": file_summary(args.train_file),
            "valid_repair": file_summary(args.valid_file),
            "eval_risk_repair": file_summary(args.eval_risk_repair_file),
            "eval_negation_repair": file_summary(args.eval_negation_repair_file),
            "config": config_summary(args.config),
            "eval_config": config_summary(args.eval_config),
        },
        "output_adapter_target_path": str(run_paths["adapter_dir"]),
        "external_run_dir": str(run_paths["external_run_dir"]),
        "training_env_summary": training_env_summary(),
        "vllm_touched": False,
        "policy": {
            "do_not_modify_serving_venv": True,
            "do_not_overwrite_d2t1_adapter": True,
            "do_not_commit_model_weights": True,
            "final_risk_decision_remains_rule_engine_backed": True,
        },
    }


def required_input_check(args: argparse.Namespace) -> list[str]:
    required = [
        args.model_path,
        args.resume_adapter,
        args.config,
        args.eval_config,
        args.train_file,
        args.valid_file,
        args.train_messages_file,
        args.valid_messages_file,
        args.original_extract_file,
        args.eval_risk_repair_file,
        args.eval_negation_repair_file,
        args.d2t1_metrics_file,
    ]
    return [str(path) for path in required if not path.exists()]


def parse_args() -> argparse.Namespace:
    config = load_yaml_config(DEFAULT_CONFIG)
    training = config.get("training") or {}
    parser = argparse.ArgumentParser(description="Run D2-T1R2 risk repair light training and evaluation.")
    parser.add_argument("--model-path", type=Path, default=Path(config.get("base_model") or DEFAULT_MODEL_PATH))
    parser.add_argument("--resume-adapter", type=Path, default=Path(config.get("starting_adapter") or DEFAULT_BASE_ADAPTER))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--eval-config", type=Path, default=DEFAULT_EVAL_CONFIG)
    parser.add_argument("--train-file", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--valid-file", type=Path, default=DEFAULT_VALID)
    parser.add_argument("--train-messages-file", type=Path, default=DEFAULT_TRAIN_MESSAGES)
    parser.add_argument("--valid-messages-file", type=Path, default=DEFAULT_VALID_MESSAGES)
    parser.add_argument("--original-extract-file", type=Path, default=DEFAULT_ORIGINAL_EXTRACT)
    parser.add_argument("--eval-risk-repair-file", type=Path, default=DEFAULT_RISK_REPAIR)
    parser.add_argument("--eval-negation-repair-file", type=Path, default=DEFAULT_NEGATION_REPAIR)
    parser.add_argument("--d2t1-metrics-file", type=Path, default=DEFAULT_D2T1_METRICS)
    parser.add_argument("--external-root", type=Path, default=Path(config.get("external_output_root") or "/mnt/e/ai_artifacts/tcm_assistant_device2/d2t1r2"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--num-train-epochs", type=float, default=float(training.get("num_train_epochs", 4)))
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--max-length", type=int, default=int(training.get("max_length", 1024)))
    parser.add_argument("--learning-rate", type=float, default=float(training.get("learning_rate", 1e-4)))
    parser.add_argument("--per-device-train-batch-size", type=int, default=int(training.get("per_device_train_batch_size", 1)))
    parser.add_argument("--gradient-accumulation-steps", type=int, default=int(training.get("gradient_accumulation_steps", 4)))
    parser.add_argument("--logging-steps", type=int, default=2)
    parser.add_argument("--save-steps", type=int, default=10)
    parser.add_argument("--save-total-limit", type=int, default=int(training.get("save_total_limit", 2)))
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--compute-dtype", choices=("bf16", "fp16"), default=str(training.get("compute_dtype", "bf16")))
    parser.add_argument("--gradient-checkpointing", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_id = args.run_id or "risk_repair_" + utc_stamp()
    external_run_dir = args.external_root / run_id
    run_paths = {
        "external_run_dir": external_run_dir,
        "adapter_dir": external_run_dir / "adapter" / "final_adapter",
        "trainer_output_dir": external_run_dir / "trainer",
        "prediction_dir": external_run_dir / "predictions",
    }
    for path in [DEFAULT_REPO_METRICS, DEFAULT_REPO_MANIFESTS, DEFAULT_REPO_PREDICTIONS, DEFAULT_REPORT_DIR, *run_paths.values()]:
        path.mkdir(parents=True, exist_ok=True)

    missing = required_input_check(args)
    manifest = build_manifest(args, run_paths)
    if missing:
        manifest["status"] = "failed"
        manifest["missing_inputs"] = missing
        write_manifest_reports(manifest)
        failure = {
            "generated_at": utc_now(),
            "stage": "D2-T1R2",
            "status": "failed",
            "failure_reason": "missing required inputs",
            "missing_inputs": missing,
            "vllm_touched": False,
        }
        write_json(DEFAULT_REPO_METRICS / "d2t1r2_training_metrics.json", failure)
        write_text(DEFAULT_REPORT_DIR / "d2t1r2_training_report.md", "# D2-T1R2 Training Report\n\nStatus: `failed`\n\nMissing required inputs.\n")
        raise SystemExit(1)

    manifest["status"] = "frozen"
    write_manifest_reports(manifest)

    try:
        tokenizer = load_tokenizer(args.model_path, allow_download=args.allow_download)
        training = run_training(args, run_paths, tokenizer)
        write_training_report(training)
        adapter_payload = adapter_check(run_paths["adapter_dir"], run_paths["trainer_output_dir"])
        write_json(DEFAULT_REPO_METRICS / "d2t1r2_adapter_check.json", adapter_payload)

        eval_sets = build_eval_sets(args)
        d2t1_eval = evaluate_adapter(
            backend="d2t1",
            adapter_path=args.resume_adapter,
            args=args,
            tokenizer=tokenizer,
            eval_sets=eval_sets,
            run_paths=run_paths,
            write_requested_metrics=False,
        )
        d2t1r2_eval = evaluate_adapter(
            backend="d2t1r2",
            adapter_path=run_paths["adapter_dir"],
            args=args,
            tokenizer=tokenizer,
            eval_sets=eval_sets,
            run_paths=run_paths,
            write_requested_metrics=True,
        )

        comparison = build_comparison(read_json(args.d2t1_metrics_file), d2t1_eval, {name: payload for name, payload in d2t1r2_eval.items()})
        status, status_reasons = decide_status(comparison, {name: payload for name, payload in d2t1r2_eval.items()}, adapter_payload)
        comparison["acceptance_status"] = status
        comparison["acceptance_reasons"] = status_reasons
        write_evaluation_report(d2t1_eval, d2t1r2_eval)
        write_comparison_report(comparison, status, status_reasons)

        all_badcases: list[dict[str, Any]] = []
        for eval_name, item in eval_sets.items():
            predictions = read_jsonl(Path(d2t1r2_eval[eval_name]["prediction_path_external"]))
            all_badcases.extend(classify_badcases(eval_name, item["rows"], predictions))
        badcases = summarize_badcases(all_badcases)
        write_badcase_report(badcases)

        final_payload = {
            "status": status,
            "adapter": str(run_paths["adapter_dir"]),
            "training_metrics": rel(DEFAULT_REPO_METRICS / "d2t1r2_training_metrics.json"),
            "compare_metrics": rel(DEFAULT_REPO_METRICS / "d2t1r2_compare_to_d2t1.json"),
            "vllm_touched": False,
        }
        print(json.dumps(final_payload, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        failure = {
            "generated_at": utc_now(),
            "stage": "D2-T1R2",
            "status": "failed",
            "failure_reason": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "adapter": str(run_paths["adapter_dir"]),
            "vllm_touched": False,
        }
        write_json(DEFAULT_REPO_METRICS / "d2t1r2_training_metrics.json", failure)
        write_text(
            DEFAULT_REPORT_DIR / "d2t1r2_training_report.md",
            "\n".join(
                [
                    "# D2-T1R2 Training Report",
                    "",
                    "Status: `failed`",
                    "",
                    f"Failure: `{failure['failure_reason']}`",
                    "",
                    "vLLM touched: `false`",
                ]
            )
            + "\n",
        )
        print(json.dumps({"status": "failed", "failure_reason": failure["failure_reason"]}, ensure_ascii=False))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
