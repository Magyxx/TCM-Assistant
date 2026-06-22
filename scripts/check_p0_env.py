from __future__ import annotations

import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


CORE_MODULES = {
    "langgraph": "langgraph",
    "langchain_openai": "langchain_openai",
    "rank_bm25": "rank_bm25",
    "pydantic": "pydantic",
    "python_dotenv": "dotenv",
}

SFT_MODULES = {
    "transformers": "transformers",
    "datasets": "datasets",
    "peft": "peft",
    "accelerate": "accelerate",
    "torch": "torch",
}


def module_status(module_name: str) -> str:
    return "present" if importlib.util.find_spec(module_name) is not None else "missing"


def present_or_missing(value: str | None) -> str:
    return "present" if value else "missing"


def compute_mode(statuses: dict[str, str]) -> str:
    if statuses["pydantic"] != "present":
        return "blocked"
    real_deps = (
        statuses["langgraph"] == "present"
        and statuses["langchain_openai"] == "present"
        and statuses["rank_bm25"] == "present"
    )
    api_ready = (
        present_or_missing(os.getenv("OPENAI_API_KEY")) == "present"
        and present_or_missing(os.getenv("OPENAI_BASE_URL")) == "present"
        and present_or_missing(os.getenv("OPENAI_MODEL")) == "present"
    )
    if real_deps and api_ready:
        return "real-ready"
    if real_deps or api_ready:
        return "partial-real"
    return "fallback-only"


def main() -> None:
    dotenv_status = module_status("dotenv")
    if ENV_PATH.exists() and dotenv_status == "present":
        try:
            from dotenv import load_dotenv

            load_dotenv(ENV_PATH)
        except Exception:
            pass

    statuses = {name: module_status(module) for name, module in CORE_MODULES.items()}

    print("[P0 ENV CHECK]")
    for name, status in statuses.items():
        print(f"{name}: {status}")

    print(f".env: {'present' if ENV_PATH.exists() else 'missing'}")
    print(f"OPENAI_API_KEY: {present_or_missing(os.getenv('OPENAI_API_KEY'))}")
    print(f"OPENAI_BASE_URL: {present_or_missing(os.getenv('OPENAI_BASE_URL'))}")
    print(f"OPENAI_MODEL: {present_or_missing(os.getenv('OPENAI_MODEL'))}")

    print("[P0 OPTIONAL SFT]")
    for name, module in SFT_MODULES.items():
        print(f"{name}: {module_status(module)}")

    print(f"mode: {compute_mode(statuses)}")


if __name__ == "__main__":
    main()
