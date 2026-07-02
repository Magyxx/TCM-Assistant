from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    WorkstationContext,
    json_dump,
    make_context,
    write_text_file,
)


def canvas_data() -> dict:
    nodes = [
        ("home", "个人 AI 工作站", 0, 0, "00_Home/Dashboard.md"),
        ("daily", "每日工作流", 420, -260, "01_Daily/Index.md"),
        ("algorithm", "算法", 420, -40, "06_Learning/算法/Index.md"),
        ("agent", "Agent", 420, 180, "06_Learning/Agent/Index.md"),
        ("projects", "项目", 840, -260, "99_System/Indexes/Project_Index.md"),
        ("engineering", "工程能力", 840, -40, "06_Learning/工程能力/Index.md"),
        ("codex", "Codex 任务记录", 840, 180, "99_System/Indexes/Codex_Task_Index.md"),
        ("reviews", "复盘", 1260, -260, "99_System/Indexes/Review_Index.md"),
        ("knowledge", "知识沉淀", 1260, -40, "99_System/Indexes/Knowledge_Index.md"),
        ("artifacts", "文档与产物", 1260, 180, "08_Artifacts/Artifact_Index.md"),
        ("views", "索引与可视化", 1680, -40, "00_Home/Dataview_Dashboard.md"),
    ]
    node_payload = [
        {
            "id": node_id,
            "type": "file",
            "file": file_path,
            "text": f"# {label}\n\n个人 AI 工作站长期模块。",
            "x": x,
            "y": y,
            "width": 320,
            "height": 160,
        }
        for node_id, label, x, y, file_path in nodes
    ]
    edge_pairs = [
        ("home", "daily"),
        ("home", "algorithm"),
        ("home", "agent"),
        ("home", "projects"),
        ("home", "engineering"),
        ("daily", "reviews"),
        ("algorithm", "knowledge"),
        ("agent", "knowledge"),
        ("engineering", "knowledge"),
        ("projects", "reviews"),
        ("projects", "artifacts"),
        ("codex", "projects"),
        ("codex", "knowledge"),
        ("reviews", "artifacts"),
        ("knowledge", "views"),
        ("artifacts", "views"),
        ("reviews", "views"),
    ]
    edges = [
        {
            "id": f"edge-{source}-{target}",
            "fromNode": source,
            "fromSide": "right",
            "toNode": target,
            "toSide": "left",
        }
        for source, target in edge_pairs
    ]
    return {"nodes": node_payload, "edges": edges}


def build_canvas(ctx: WorkstationContext):
    path = ctx.target_root / "00_Home" / "AI_Workstation.canvas"
    return write_text_file(
        path,
        json_dump(canvas_data()),
        overwrite=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Obsidian canvas for the workstation.")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    result = build_canvas(ctx)
    print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
