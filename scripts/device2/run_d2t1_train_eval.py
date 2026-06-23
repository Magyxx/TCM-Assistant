from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import torch
from datasets import Dataset
from peft import LoraConfig, PeftModel, TaskType, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.utils.sft_postprocess import postprocess_turn_output
from app.rules.risk_rules import evaluate_risk_rules


DEFAULT_MODEL_PATH = Path("/mnt/e/models/Qwen2.5-1.5B-Instruct")
DEFAULT_TRAIN = ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_train.jsonl"
DEFAULT_VAL = ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_val.jsonl"
DEFAULT_TRAIN_MESSAGES = ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_train_messages.jsonl"
DEFAULT_VAL_MESSAGES = ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_val_messages.jsonl"
DEFAULT_REPO_ARTIFACT_DIR = ROOT / "artifacts" / "device2"
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_dataset_file(path: Path, schema: str) -> dict[str, Any]:
    rows = read_jsonl(path)
    validation_errors: list[str] = []
    sources: dict[str, int] = {}
    difficulties: dict[str, int] = {}
    tags: dict[str, int] = {}
    ids: list[str] = []

    for row in rows:
        ids.append(str(row.get("id", "")))
        error = validate_raw_row(row) if schema == "raw" else validate_messages_row(row)
        if error:
            validation_errors.append(f"{row.get('id', '<missing-id>')}: {error}")

        meta = row.get("meta") or {}
        source = str(meta.get("source", "unknown"))
        difficulty = str(meta.get("difficulty", "unknown"))
        sources[source] = sources.get(source, 0) + 1
        difficulties[difficulty] = difficulties.get(difficulty, 0) + 1
        for tag in meta.get("tags") or []:
            tag = str(tag)
            tags[tag] = tags.get(tag, 0) + 1

    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "rows": len(rows),
        "ids": ids,
        "sources": sources,
        "difficulties": difficulties,
        "tags": tags,
        "schema": schema,
        "schema_ok": not validation_errors,
        "schema_errors": validation_errors[:20],
    }


def validate_raw_row(row: dict[str, Any]) -> str | None:
    required = {"task", "id", "system_prompt", "input", "output", "meta"}
    missing = required - set(row)
    if missing:
        return f"missing keys: {sorted(missing)}"
    if row.get("task") != "report_turn_extraction":
        return "task must be report_turn_extraction"
    if not isinstance(row.get("input"), dict):
        return "input must be an object"
    if not isinstance(row["input"].get("state_json"), dict):
        return "input.state_json must be an object"
    if not isinstance(row["input"].get("user_input"), str) or not row["input"].get("user_input"):
        return "input.user_input must be a non-empty string"
    return validate_output_schema(row.get("output"))


def validate_messages_row(row: dict[str, Any]) -> str | None:
    required = {"id", "task", "messages", "meta"}
    missing = required - set(row)
    if missing:
        return f"missing keys: {sorted(missing)}"
    messages = row.get("messages")
    if not isinstance(messages, list) or len(messages) < 2:
        return "messages must contain at least system and user messages"
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            return f"message {index} must be an object"
        if message.get("role") not in {"system", "user", "assistant"}:
            return f"message {index} has invalid role"
        if not isinstance(message.get("content"), str):
            return f"message {index} content must be a string"
    return None


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


def freeze_datasets(paths: dict[str, tuple[Path, str]], out_path: Path) -> dict[str, Any]:
    payload = {
        "generated_at": utc_now(),
        "stage": "D2-T1 dataset freeze",
        "files": {name: summarize_dataset_file(path, schema) for name, (path, schema) in paths.items()},
    }
    payload["ok"] = all(item["schema_ok"] for item in payload["files"].values())
    write_json(out_path, payload)
    return payload


def ensure_pad_token(tokenizer: Any) -> None:
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token


def load_tokenizer(model_path: Path, allow_download: bool) -> Any:
    tokenizer = AutoTokenizer.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        local_files_only=not allow_download,
    )
    ensure_pad_token(tokenizer)
    return tokenizer


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


def guess_target_modules(model_path: Path) -> list[str]:
    lowered = str(model_path).lower()
    if "qwen" in lowered or "llama" in lowered or "mistral" in lowered:
        return ["q_proj", "k_proj", "v_proj", "o_proj", "up_proj", "down_proj", "gate_proj"]
    if "chatglm" in lowered:
        return ["query_key_value", "dense", "dense_h_to_4h", "dense_4h_to_h"]
    return ["q_proj", "v_proj"]


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


def load_qlora_model(model_path: Path, allow_download: bool, compute_dtype: str) -> Any:
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
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        inference_mode=False,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        target_modules=guess_target_modules(model_path),
    )
    return get_peft_model(model, peft_config)


def cleanup_model(model: Any | None = None) -> None:
    if model is not None:
        del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def strip_assistant(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    return [message for message in messages if message.get("role") != "assistant"]


def extract_json_object_text(text: str) -> str | None:
    text = text.strip()
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
        postprocessed = postprocess_turn_output(
            parsed_output=parsed,
            state_json=gold.get("input", {}).get("state_json", {}),
            user_input=gold.get("input", {}).get("user_input", ""),
        )
        schema_error = validate_output_schema(postprocessed)
        schema_ok = schema_error is None
        predictions.append(
            {
                "id": sample_id,
                "backend": backend,
                "output": postprocessed,
                "parsed_output": parsed,
                "raw_output": raw_output,
                "schema_ok": schema_ok,
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
    tags = set((row.get("meta") or {}).get("tags") or [])
    return bool(tags & NEGATION_TAGS) or any("negation" in str(tag) for tag in tags)


def is_risk_case(row: dict[str, Any]) -> bool:
    tags = set((row.get("meta") or {}).get("tags") or [])
    expected = row.get("output") or {}
    return any("risk" in str(tag) for tag in tags) or expected.get("risk_flags_status") != "unknown"


def risk_tag_gold_conflict(row: dict[str, Any]) -> bool:
    tags = set((row.get("meta") or {}).get("tags") or [])
    expected = row.get("output") or {}
    status = expected.get("risk_flags_status", "unknown")
    return ("risk_present" in tags and status != "present") or ("risk_none" in tags and status == "present")


def risk_label_context_mismatch(row: dict[str, Any]) -> bool:
    expected = row.get("output") or {}
    status = expected.get("risk_flags_status", "unknown")
    state_json = (row.get("input") or {}).get("state_json") or {}
    user_input = str((row.get("input") or {}).get("user_input") or "")
    if status == "present":
        if state_json.get("risk_flags_status") == "present" or state_json.get("risk_flags") or expected.get("risk_flags"):
            return False
        return evaluate_risk_rules(user_input, previous_status=state_json.get("risk_flags_status", "unknown")).risk_status != "present"
    if status == "none":
        if state_json.get("risk_flags_status") == "none":
            return False
        evaluation = evaluate_risk_rules(user_input, previous_status=state_json.get("risk_flags_status", "unknown"))
        if evaluation.risk_status == "none":
            return False
        return not any(marker in user_input for marker in ["没有", "未见", "无", "否认", "不"])
    return False


def is_coherent_risk_case(row: dict[str, Any]) -> bool:
    return is_risk_case(row) and not risk_tag_gold_conflict(row) and not risk_label_context_mismatch(row)


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
    risk_tag_gold_conflict_count = 0
    risk_label_context_mismatch_count = 0
    badcases: list[dict[str, Any]] = []

    for gold in gold_rows:
        sample_id = gold["id"]
        pred = pred_by_id.get(sample_id)
        if pred is None:
            badcases.append({"id": sample_id, "reason": "missing prediction"})
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
        all_ok = all(fields.values())
        if all_ok:
            exact += 1
        else:
            badcases.append(
                {
                    "id": sample_id,
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
        if risk_tag_gold_conflict(gold):
            risk_tag_gold_conflict_count += 1
        if risk_label_context_mismatch(gold):
            risk_label_context_mismatch_count += 1
        if is_coherent_risk_case(gold):
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
        "risk_tag_gold_conflict_count": risk_tag_gold_conflict_count,
        "risk_label_context_mismatch_count": risk_label_context_mismatch_count,
        "badcases": badcases,
    }


def compare_metrics(base: dict[str, Any], lora: dict[str, Any]) -> dict[str, Any]:
    return {
        "exact_core_rate_delta": round(lora["exact_core_rate"] - base["exact_core_rate"], 4),
        "schema_pass_rate_delta": round(lora["schema_pass_rate"] - base["schema_pass_rate"], 4),
        "risk_status_rate_delta": round(lora["risk_status_rate"] - base["risk_status_rate"], 4),
        "negation_risk_status_rate_delta": round(
            lora["negation_risk_status_rate"] - base["negation_risk_status_rate"], 4
        ),
    }


def vllm_preflight() -> dict[str, Any]:
    try:
        import vllm  # type: ignore

        return {"import_ok": True, "version": getattr(vllm, "__version__", "unknown"), "failure_reason": None}
    except Exception as exc:  # noqa: BLE001
        return {
            "import_ok": False,
            "version": None,
            "failure_reason": "vLLM import failed",
            "error": f"{type(exc).__name__}: {exc}",
        }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def report_table(metrics: dict[str, Any]) -> str:
    lines = [
        "| Metric | Value |",
        "| --- | ---: |",
        f"| total | {metrics['total']} |",
        f"| exact_core_rate | {metrics['exact_core_rate']} |",
        f"| schema_pass_rate | {metrics['schema_pass_rate']} |",
        f"| risk_status_rate | {metrics['risk_status_rate']} |",
        f"| coherent_risk_status_rate | {metrics.get('coherent_risk_status_rate', 0.0)} |",
        f"| risk_tag_gold_conflict_count | {metrics.get('risk_tag_gold_conflict_count', 0)} |",
        f"| risk_label_context_mismatch_count | {metrics.get('risk_label_context_mismatch_count', 0)} |",
        f"| negation_risk_status_rate | {metrics['negation_risk_status_rate']} |",
    ]
    for field, value in metrics["field_rates"].items():
        lines.append(f"| {field}_rate | {value} |")
    return "\n".join(lines)


def write_reports(
    *,
    report_dir: Path,
    run: dict[str, Any],
    freeze: dict[str, Any],
    base_metrics: dict[str, Any],
    lora_metrics: dict[str, Any],
    comparison: dict[str, Any],
    vllm: dict[str, Any],
) -> None:
    status = run["status"]
    adapter_path = run["adapter_path"]
    external_run_dir = run["external_run_dir"]
    command = run["repro_command"]

    write_text(
        report_dir / "d2t1_training_report.md",
        "\n".join(
            [
                "# D2-T1 Training Report",
                "",
                f"Generated at: `{run['generated_at']}`",
                "",
                f"Status: `{status}`",
                "",
                "## Runtime",
                "",
                f"* base model: `{run['model_path']}`",
                f"* training env: `{run['training_env']}`",
                f"* external run dir: `{external_run_dir}`",
                f"* adapter path: `{adapter_path}`",
                f"* train epochs: `{run['train_args']['num_train_epochs']}`",
                f"* max sequence length: `{run['train_args']['max_length']}`",
                f"* QLoRA: `{run['train_args']['qlora']}`",
                "",
                "## Dataset Freeze",
                "",
                f"* freeze artifact: `{run['repo_artifacts']['dataset_freeze']}`",
                f"* freeze ok: `{freeze['ok']}`",
                f"* train rows: `{freeze['files']['train']['rows']}`",
                f"* val rows: `{freeze['files']['val']['rows']}`",
                "",
                "## Training Result",
                "",
                f"* train runtime seconds: `{run['train_runtime_seconds']}`",
                f"* adapter saved: `{run['adapter_saved']}`",
                f"* PEFT adapter load smoke: `{run['peft_adapter_load_smoke']}`",
                "",
                "## No Large Repo Artifacts",
                "",
                "Adapters, checkpoints, full predictions, and model cache are under the external run dir, not the repository.",
                "",
            ]
        ),
    )

    badcase_lines = [
        "# D2-T1 Evaluation Report",
        "",
        f"Generated at: `{run['generated_at']}`",
        "",
        f"Status: `{status}`",
        "",
        "## local_base",
        "",
        report_table(base_metrics),
        "",
        "## local_lora",
        "",
        report_table(lora_metrics),
        "",
        "## Comparison",
        "",
        "```json",
        json.dumps(comparison, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Badcases",
        "",
    ]
    for item in lora_metrics["badcases"][:20]:
        badcase_lines.append(f"* `{item.get('id')}` failed_fields={item.get('failed_fields', [])}")
    if not lora_metrics["badcases"]:
        badcase_lines.append("* none")
    write_text(report_dir / "d2t1_evaluation_report.md", "\n".join(badcase_lines) + "\n")

    write_text(
        report_dir / "d2t1_repro_report.md",
        "\n".join(
            [
                "# D2-T1 Repro Report",
                "",
                "Run from Ubuntu WSL in the training environment:",
                "",
                "```bash",
                "source ~/venvs/tcm-device2-train-py312-cu126-final/bin/activate",
                "cd /mnt/c/Users/Administrator/Documents/TCM-Ass/TCM-Assistant",
                command,
                "```",
                "",
                "Expected tracked outputs:",
                "",
                f"* `{run['repo_artifacts']['metrics']}`",
                f"* `{run['repo_artifacts']['dataset_freeze']}`",
                "* `reports/device2/d2t1_training_report.md`",
                "* `reports/device2/d2t1_evaluation_report.md`",
                "* `reports/device2/d2t1_repro_report.md`",
                "* `reports/device2/vllm_deferred_report.md` when vLLM is unavailable",
                "",
                "Expected untracked external outputs:",
                "",
                f"* `{external_run_dir}`",
                "",
            ]
        ),
    )

    if not vllm.get("import_ok"):
        write_text(
            report_dir / "vllm_deferred_report.md",
            "\n".join(
                [
                    "# vLLM Deferred Report",
                    "",
                    "Stage: `D2-T1 optional vLLM preflight`",
                    "",
                    "Status: `serving_deferred`",
                    "",
                    "vLLM is not a hard precondition for D2-T1. Training and Transformers/PEFT evaluation are allowed to complete.",
                    "",
                    "## Failure Classification",
                    "",
                    f"* reason: `{vllm.get('failure_reason', 'unknown')}`",
                    f"* detail: `{vllm.get('error', 'unknown')}`",
                    "",
                    "## Policy",
                    "",
                    "* The training environment was not modified for vLLM.",
                    "* Do not reinstall torch/CUDA/bitsandbytes in the training environment for serving repair.",
                    "* Continue vLLM work in D2-T2 using an isolated serving environment.",
                    "",
                ]
            ),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run D2-T1 QLoRA/SFT training and Transformers/PEFT eval.")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--train-file", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--val-file", type=Path, default=DEFAULT_VAL)
    parser.add_argument("--train-messages-file", type=Path, default=DEFAULT_TRAIN_MESSAGES)
    parser.add_argument("--val-messages-file", type=Path, default=DEFAULT_VAL_MESSAGES)
    parser.add_argument("--external-root", type=Path, default=None)
    parser.add_argument("--repo-artifact-dir", type=Path, default=DEFAULT_REPO_ARTIFACT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--num-train-epochs", type=float, default=20.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--per-device-train-batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument("--logging-steps", type=int, default=5)
    parser.add_argument("--save-steps", type=int, default=25)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--eval-limit", type=int, default=0)
    parser.add_argument("--compute-dtype", choices=("bf16", "fp16"), default="bf16")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated_at = utc_now()
    run_id = args.run_id or "d2t1_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    external_root = args.external_root or Path(os.environ.get("TCM_DEVICE2_ARTIFACTS", "/mnt/e/ai_artifacts/tcm_assistant_device2"))
    external_run_dir = external_root / "d2t1" / run_id
    adapter_dir = external_run_dir / "adapter" / "final_adapter"
    full_pred_dir = external_run_dir / "predictions"
    trainer_output_dir = external_run_dir / "trainer"
    repo_pred_dir = args.repo_artifact_dir / "predictions"
    metrics_path = args.repo_artifact_dir / "d2t1_metrics.json"
    freeze_path = args.repo_artifact_dir / "d2t1_dataset_freeze.json"
    badcase_path = args.repo_artifact_dir / "d2t1_badcases.json"

    args.repo_artifact_dir.mkdir(parents=True, exist_ok=True)
    full_pred_dir.mkdir(parents=True, exist_ok=True)
    repo_pred_dir.mkdir(parents=True, exist_ok=True)

    freeze = freeze_datasets(
        {
            "train": (args.train_file, "raw"),
            "val": (args.val_file, "raw"),
            "train_messages": (args.train_messages_file, "messages"),
            "val_messages": (args.val_messages_file, "messages"),
        },
        freeze_path,
    )
    if not freeze["ok"]:
        raise SystemExit("dataset freeze failed schema validation")

    val_rows = read_jsonl(args.val_file)
    val_message_rows = {row["id"]: row for row in read_jsonl(args.val_messages_file)}
    eval_limit = args.eval_limit if args.eval_limit > 0 else None

    print("[D2-T1] loading tokenizer")
    tokenizer = load_tokenizer(args.model_path, allow_download=args.allow_download)

    print("[D2-T1] local_base generation")
    base_model = load_base_model(args.model_path, allow_download=args.allow_download, dtype=args.compute_dtype)
    base_predictions = generate_predictions(
        backend="local_base",
        model=base_model,
        tokenizer=tokenizer,
        gold_rows=val_rows,
        message_rows=val_message_rows,
        out_path=full_pred_dir / "local_base_predictions.jsonl",
        max_new_tokens=args.max_new_tokens,
        limit=eval_limit,
    )
    write_jsonl(repo_pred_dir / "local_base_sample.jsonl", base_predictions[:2])
    base_metrics = evaluate_predictions(val_rows[:eval_limit] if eval_limit else val_rows, base_predictions)
    cleanup_model(base_model)

    print("[D2-T1] QLoRA training")
    train_dataset = build_train_dataset(args.train_messages_file, tokenizer, args.max_length)
    qlora_model = load_qlora_model(args.model_path, allow_download=args.allow_download, compute_dtype=args.compute_dtype)
    training_args = TrainingArguments(
        output_dir=str(trainer_output_dir),
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_train_epochs,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=2,
        bf16=args.compute_dtype == "bf16",
        fp16=args.compute_dtype == "fp16",
        report_to="none",
        remove_unused_columns=False,
        eval_strategy="no",
    )
    trainer = Trainer(
        model=qlora_model,
        args=training_args,
        train_dataset=train_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    train_started = time.time()
    trainer.train()
    train_runtime = round(time.time() - train_started, 3)
    trainer.save_model(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))
    adapter_saved = (adapter_dir / "adapter_config.json").exists()
    cleanup_model(qlora_model)

    print("[D2-T1] local_lora PEFT generation")
    lora_base = load_base_model(args.model_path, allow_download=args.allow_download, dtype=args.compute_dtype)
    lora_model = PeftModel.from_pretrained(lora_base, str(adapter_dir), local_files_only=True)
    lora_model.eval()
    peft_smoke = True
    lora_predictions = generate_predictions(
        backend="local_lora",
        model=lora_model,
        tokenizer=tokenizer,
        gold_rows=val_rows,
        message_rows=val_message_rows,
        out_path=full_pred_dir / "local_lora_predictions.jsonl",
        max_new_tokens=args.max_new_tokens,
        limit=eval_limit,
    )
    write_jsonl(repo_pred_dir / "local_lora_sample.jsonl", lora_predictions[:2])
    lora_metrics = evaluate_predictions(val_rows[:eval_limit] if eval_limit else val_rows, lora_predictions)
    cleanup_model(lora_model)

    comparison = compare_metrics(base_metrics, lora_metrics)
    vllm = vllm_preflight()
    status = "ok_train_eval"
    cautions: list[str] = []
    if not adapter_saved:
        status = "failed"
        cautions.append("adapter was not saved")
    if not peft_smoke:
        status = "failed"
        cautions.append("PEFT adapter load smoke failed")
    if lora_metrics["schema_pass_rate"] < 1.0:
        status = "caution" if status != "failed" else status
        cautions.append("local_lora schema pass rate below 1.0")
    if comparison["exact_core_rate_delta"] <= 0:
        status = "caution" if status != "failed" else status
        cautions.append("local_lora exact core rate did not improve over local_base")
    if lora_metrics["risk_total"] and lora_metrics["risk_status_rate"] < 1.0:
        status = "caution" if status != "failed" else status
        cautions.append("risk specialty evaluation has failures")
    if lora_metrics["negation_total"] and lora_metrics["negation_risk_status_rate"] < 1.0:
        status = "caution" if status != "failed" else status
        cautions.append("negation specialty evaluation has failures")

    command = (
        "python scripts/device2/run_d2t1_train_eval.py "
        f"--model-path {args.model_path} "
        f"--run-id {run_id} "
        f"--num-train-epochs {args.num_train_epochs:g} "
        f"--max-length {args.max_length} "
        f"--compute-dtype {args.compute_dtype}"
    )

    run_payload = {
        "generated_at": generated_at,
        "stage": "D2-T1: Formal Long QLoRA/SFT Training and Transformers Evaluation",
        "status": status,
        "cautions": cautions,
        "model_path": str(args.model_path),
        "training_env": sys.prefix,
        "external_run_dir": str(external_run_dir),
        "adapter_path": str(adapter_dir),
        "adapter_saved": adapter_saved,
        "peft_adapter_load_smoke": peft_smoke,
        "train_runtime_seconds": train_runtime,
        "train_args": {
            "qlora": True,
            "num_train_epochs": args.num_train_epochs,
            "learning_rate": args.learning_rate,
            "max_length": args.max_length,
            "per_device_train_batch_size": args.per_device_train_batch_size,
            "gradient_accumulation_steps": args.gradient_accumulation_steps,
            "compute_dtype": args.compute_dtype,
        },
        "repo_artifacts": {
            "metrics": str(metrics_path.relative_to(ROOT)),
            "dataset_freeze": str(freeze_path.relative_to(ROOT)),
            "badcases": str(badcase_path.relative_to(ROOT)),
        },
        "predictions": {
            "external_full": str(full_pred_dir),
            "repo_samples": str(repo_pred_dir.relative_to(ROOT)),
        },
        "base_metrics": base_metrics,
        "lora_metrics": lora_metrics,
        "comparison": comparison,
        "vllm_preflight": vllm,
        "serving_deferred": not vllm.get("import_ok"),
        "repro_command": command,
    }
    write_json(metrics_path, run_payload)
    write_json(badcase_path, {"generated_at": generated_at, "local_lora_badcases": lora_metrics["badcases"]})
    write_reports(
        report_dir=args.report_dir,
        run=run_payload,
        freeze=freeze,
        base_metrics=base_metrics,
        lora_metrics=lora_metrics,
        comparison=comparison,
        vllm=vllm,
    )
    print(json.dumps({"status": status, "metrics": str(metrics_path), "adapter": str(adapter_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
