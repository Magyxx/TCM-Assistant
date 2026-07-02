from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - old Python fallback
    ZoneInfo = None


DEFAULT_CONFIG = {
    "preview_mode": True,
    "obsidian_vault_path": "",
    "daily_dir": "01_Daily",
    "projects_dir": "02_Projects",
    "codex_tasks_dir": "03_Codex_Tasks",
    "knowledge_dir": "04_Knowledge",
    "reviews_dir": "05_Reviews",
    "artifacts_dir": "08_Artifacts",
    "system_dir": "99_System",
    "default_language": "zh-CN",
    "current_mainline": "",
    "timezone": "America/Los_Angeles",
    "safe_append_only": True,
    "allow_overwrite": False,
    "dataview_ready": True,
    "bases_ready": True,
    "generate_canvas": True,
    "generate_dashboard": True,
}

WORKSTATION_DOMAINS = ["算法", "Agent", "项目", "工程能力"]
KNOWLEDGE_DOMAINS = WORKSTATION_DOMAINS
LEARNING_DIRS = WORKSTATION_DOMAINS
CAREER_DIRS = ["Internship", "Resume", "Applications", "Interview_Prep"]
MANAGED_TOP_LEVELS = {
    "00_Home",
    "00_Inbox",
    "01_Daily",
    "02_Projects",
    "03_Codex_Tasks",
    "04_Knowledge",
    "05_Reviews",
    "06_Learning",
    "07_Career",
    "08_Artifacts",
    "99_System",
}

REQUIRED_DIRECTORIES = [
    "00_Home",
    "00_Inbox",
    "01_Daily",
    "02_Projects",
    "03_Codex_Tasks",
    "04_Knowledge",
    "05_Reviews/Daily",
    "05_Reviews/Weekly",
    "05_Reviews/Monthly",
    "05_Reviews/Project_Reviews",
    "06_Learning",
    "06_Learning/Agent/前沿研究",
    "07_Career",
    "08_Artifacts",
    "08_Artifacts/Document_Logs",
    "08_Artifacts/Documents",
    "99_System/Templates",
    "99_System/Schemas",
    "99_System/Indexes",
    "99_System/Views",
    "99_System/RAG",
    "99_System/Search",
]


@dataclass(frozen=True)
class WorkstationContext:
    repo_root: Path
    config_path: Path
    config: dict[str, Any]
    target_root: Path


@dataclass(frozen=True)
class WriteResult:
    path: Path
    action: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_config(config_path: str | Path | None = None) -> tuple[Path, dict[str, Any]]:
    root = repo_root()
    path = Path(config_path) if config_path else root / "configs" / "personal_workstation.example.json"
    if not path.is_absolute():
        path = root / path

    config = dict(DEFAULT_CONFIG)
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        config.update(loaded)
    return path, config


def make_context(config_path: str | Path | None = None) -> WorkstationContext:
    root = repo_root()
    path, config = load_config(config_path)
    preview_mode = bool(config.get("preview_mode", True))
    vault_path = str(config.get("obsidian_vault_path", "")).strip()

    if preview_mode or not vault_path:
        target = root / "artifacts" / "personal_workstation_preview"
    else:
        target = Path(vault_path).expanduser()
        if not target.is_absolute():
            target = root / target

    if not preview_mode and not vault_path:
        raise ValueError("preview_mode=false requires obsidian_vault_path.")

    return WorkstationContext(root, path, config, target)


def configured_path(ctx: WorkstationContext, key: str) -> Path:
    return ctx.target_root / str(ctx.config[key])


def today_string(ctx: WorkstationContext) -> str:
    return now(ctx).date().isoformat()


def now(ctx: WorkstationContext) -> datetime:
    timezone = str(ctx.config.get("timezone", "UTC"))
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(timezone))
        except Exception:
            pass
    return datetime.now()


def now_iso(ctx: WorkstationContext) -> str:
    return now(ctx).isoformat(timespec="seconds")


def safe_slug(value: str, fallback: str = "untitled") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value.strip())
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = cleaned.strip("._ ")
    return cleaned or fallback


def stable_id(prefix: str, value: str) -> str:
    slug = safe_slug(value).lower()
    slug = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]+", "_", slug)
    return f"{prefix}-{slug}"


def yaml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "null"
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9_\-./]+", text):
        return text
    return json.dumps(text, ensure_ascii=False)


def frontmatter(fields: dict[str, Any], tags: list[str]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {yaml_value(value)}")
    lines.append("tags:")
    for tag in tags:
        lines.append(f"  - {tag}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def ensure_directory_structure(ctx: WorkstationContext) -> list[Path]:
    created: list[Path] = []
    for rel in REQUIRED_DIRECTORIES:
        path = ctx.target_root / rel
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    for domain in KNOWLEDGE_DOMAINS:
        path = configured_path(ctx, "knowledge_dir") / domain
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    for rel in LEARNING_DIRS:
        path = ctx.target_root / "06_Learning" / rel
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    for rel in CAREER_DIRS:
        path = ctx.target_root / "07_Career" / rel
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    return created


def write_text_file(
    path: Path,
    content: str,
    *,
    overwrite: bool = False,
    unique_on_conflict: bool = False,
) -> WriteResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    final_path = path
    existed_before = final_path.exists()
    if final_path.exists() and not overwrite:
        if not unique_on_conflict:
            return WriteResult(final_path, "skipped")
        stem = final_path.stem
        suffix = final_path.suffix
        counter = 2
        while final_path.exists():
            final_path = path.with_name(f"{stem}_{counter}{suffix}")
            counter += 1
        existed_before = False
    final_path.write_text(content, encoding="utf-8", newline="\n")
    return WriteResult(final_path, "overwritten" if existed_before and overwrite else "created")


def append_text_file(path: Path, content: str) -> WriteResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed_before = path.exists()
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return WriteResult(path, "appended" if existed_before else "created")


def upsert_marked_section(text: str, marker: str, content: str) -> str:
    start = f"<!-- BEGIN {marker} -->"
    end = f"<!-- END {marker} -->"
    block = f"{start}\n{content.rstrip()}\n{end}"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if pattern.search(text):
        return pattern.sub(block, text)
    suffix = "" if text.endswith("\n") else "\n"
    return f"{text}{suffix}\n{block}\n"


def relative_to_target(ctx: WorkstationContext, path: Path) -> str:
    try:
        return path.relative_to(ctx.target_root).as_posix()
    except ValueError:
        return path.as_posix()


def read_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data: dict[str, Any] = {}
    current_list_key = None
    for raw_line in parts[1].splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_list_key:
            data.setdefault(current_list_key, []).append(line[4:].strip())
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        current_list_key = None
        if value == "":
            data[key] = []
            current_list_key = key
        elif value in {"true", "false"}:
            data[key] = value == "true"
        elif value == "null":
            data[key] = None
        elif value.startswith('"') and value.endswith('"'):
            try:
                data[key] = json.loads(value)
            except json.JSONDecodeError:
                data[key] = value.strip('"')
        else:
            data[key] = value
    return data


def markdown_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.rglob("*.md"))


def json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
