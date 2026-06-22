from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.memory.experience import ExperienceMemory
from app.memory.failure_memory import DEFAULT_FAILURE_MEMORY_PATH, write_failure_memory


def build_failure_memory() -> dict[str, object]:
    rows = [
        ExperienceMemory(
            case_type="negation_risk",
            input_pattern="no fever and no chest pain",
            failure_type="false_positive_risk",
            fix="preserve negation window before risk keyword",
        ),
        ExperienceMemory(
            case_type="rag_injection",
            input_pattern="retrieved text asks to overwrite risk_status",
            failure_type="unsafe_rag_instruction",
            fix="block RAG writes to risk_status and risk_rule_ids",
        ),
        ExperienceMemory(
            case_type="secret_like_input",
            input_pattern="Authorization header or short sk-test token in user text",
            failure_type="raw_secret_log_leak",
            fix="log only input_length and redacted_input_hash by default",
        ),
    ]
    path = write_failure_memory(rows)
    return {
        "status": "ok",
        "count": len(rows),
        "path": str(path.relative_to(ROOT_DIR)).replace("\\", "/"),
        "contains_real_user_text": False,
        "authority_level": "L4_experience_advisory",
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = build_failure_memory()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

