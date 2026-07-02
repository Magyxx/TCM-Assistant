from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.build_dashboard_state import collect_state  # noqa: E402
from scripts.personal_workstation.common import (  # noqa: E402
    WorkstationContext,
    make_context,
    write_text_file,
)


def dashboard_html(ctx: WorkstationContext, state: dict) -> str:
    state_json = json.dumps(state, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Personal AI Workstation</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #08110f;
      --panel: rgba(18, 27, 28, 0.86);
      --panel-strong: rgba(24, 37, 39, 0.96);
      --text: #edf7f4;
      --muted: #9db3ad;
      --line: rgba(255, 255, 255, 0.12);
      --teal: #45e0c1;
      --amber: #f6c65b;
      --rose: #ff7f9c;
      --blue: #72a7ff;
      --green: #7be28f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      background:
        radial-gradient(circle at 18% 10%, rgba(69, 224, 193, 0.18), transparent 28rem),
        radial-gradient(circle at 90% 14%, rgba(246, 198, 91, 0.14), transparent 26rem),
        linear-gradient(135deg, #07100f 0%, #111819 48%, #100f16 100%);
      color: var(--text);
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 34px 0 44px; }}
    .topbar {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-end; margin-bottom: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(30px, 5vw, 56px); line-height: 1; letter-spacing: 0; }}
    .subtitle {{ margin: 0; color: var(--muted); max-width: 760px; line-height: 1.55; }}
    .pill-row {{ display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }}
    .pill {{ border: 1px solid var(--line); border-radius: 999px; padding: 8px 12px; background: rgba(255,255,255,.06); color: var(--muted); white-space: nowrap; }}
    .status-dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 999px; margin-right: 8px; background: var(--green); box-shadow: 0 0 18px var(--green); }}
    .grid {{ display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }}
    .card {{
      grid-column: span 4;
      min-height: 150px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: 0 18px 60px rgba(0,0,0,.28);
      transition: transform .18s ease, border-color .18s ease, background .18s ease;
    }}
    .card:hover {{ transform: translateY(-3px); border-color: rgba(69,224,193,.45); background: var(--panel-strong); }}
    .span-6 {{ grid-column: span 6; }}
    .span-8 {{ grid-column: span 8; }}
    .span-12 {{ grid-column: span 12; }}
    .card h2 {{ margin: 0 0 12px; font-size: 17px; letter-spacing: 0; }}
    .metric {{ font-size: 38px; font-weight: 750; line-height: 1; margin: 8px 0; }}
    .muted {{ color: var(--muted); }}
    .list {{ display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }}
    .item {{ display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-top: 1px solid var(--line); }}
    .item:first-child {{ border-top: 0; }}
    .tag {{ color: #06110f; background: var(--teal); border-radius: 999px; padding: 3px 8px; font-size: 12px; align-self: flex-start; }}
    .tag.warn {{ background: var(--amber); }}
    .tag.risk {{ background: var(--rose); color: #1f070d; }}
    .progress {{ height: 8px; background: rgba(255,255,255,.08); border-radius: 999px; overflow: hidden; margin-top: 10px; }}
    .bar {{ height: 100%; width: var(--value); background: linear-gradient(90deg, var(--teal), var(--blue)); border-radius: inherit; }}
    .timeline {{ position: relative; display: grid; gap: 12px; padding-left: 18px; }}
    .timeline:before {{ content: ""; position: absolute; left: 4px; top: 4px; bottom: 4px; width: 2px; background: var(--line); }}
    .timeline-entry {{ position: relative; padding: 0 0 0 8px; color: var(--muted); }}
    .timeline-entry:before {{ content: ""; position: absolute; left: -18px; top: 6px; width: 10px; height: 10px; border-radius: 50%; background: var(--amber); }}
    .links {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .link-button {{ border: 1px solid var(--line); border-radius: 8px; padding: 9px 11px; background: rgba(255,255,255,.05); color: var(--text); }}
    @media (max-width: 900px) {{
      .topbar {{ display: block; }}
      .pill-row {{ justify-content: flex-start; margin-top: 14px; }}
      .card, .span-6, .span-8 {{ grid-column: span 12; }}
      .shell {{ width: min(100% - 24px, 1180px); padding-top: 24px; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="topbar">
      <div>
        <h1>Personal AI Workstation</h1>
        <p class="subtitle">本地优先的个人知识库、项目管理中枢与 Codex 工作流记录器。当前 Dashboard 使用内嵌 JSON 渲染，不请求外部资源。</p>
      </div>
      <div class="pill-row">
        <span class="pill"><span class="status-dot"></span><span id="mode"></span></span>
        <span class="pill" id="generated"></span>
      </div>
    </section>

    <section class="grid">
      <article class="card span-8">
        <h2>今日概览</h2>
        <p class="muted" id="today-focus"></p>
        <div class="links" id="primary-links"></div>
      </article>
      <article class="card">
        <h2>知识卡片数量</h2>
        <div class="metric" id="knowledge-count">0</div>
        <p class="muted">默认 human_reviewed=false，稳定后再沉淀为长期知识。</p>
      </article>
      <article class="card">
        <h2>活跃项目</h2>
        <div class="metric" id="project-count">0</div>
        <div id="project-list"></div>
      </article>
      <article class="card">
        <h2>Codex 最近任务</h2>
        <div class="metric" id="task-count">0</div>
        <p class="muted">任务记录要求明确 preview、mock、真实执行边界。</p>
      </article>
      <article class="card">
        <h2>学习记录</h2>
        <div class="metric" id="learning-count">0</div>
        <p class="muted">日常学习先落 Markdown，稳定后再整理为知识卡片。</p>
      </article>
      <article class="card">
        <h2>文档日志</h2>
        <div class="metric" id="document-count">0</div>
        <p class="muted">记录文档目标、读者、产物路径和审核状态。</p>
      </article>
      <article class="card">
        <h2>项目细节</h2>
        <div class="metric" id="project-log-count">0</div>
        <p class="muted">把临时上下文、决策和下一步沉淀进项目目录。</p>
      </article>
      <article class="card">
        <h2>待审核内容</h2>
        <div class="metric" id="review-count">0</div>
        <p class="muted">重要判断进入人工审核队列。</p>
      </article>
      <article class="card span-6">
        <h2>风险状态</h2>
        <ul class="list" id="risk-list"></ul>
      </article>
      <article class="card span-6">
        <h2>学习模块</h2>
        <ul class="list" id="learning-list"></ul>
      </article>
      <article class="card span-6">
        <h2>求职模块</h2>
        <ul class="list" id="career-list"></ul>
      </article>
      <article class="card span-6">
        <h2>最近产物</h2>
        <div class="timeline" id="artifact-timeline"></div>
      </article>
      <article class="card span-12">
        <h2>下一步行动</h2>
        <ul class="list" id="next-actions"></ul>
      </article>
    </section>
  </main>

  <script id="state-data" type="application/json">{state_json}</script>
  <script>
    const state = JSON.parse(document.getElementById("state-data").textContent);
    const byId = (id) => document.getElementById(id);
    const shortPath = (path) => path.replaceAll("\\\\", "/");
    byId("mode").textContent = state.preview_mode ? "Preview Mode" : "Vault Mode";
    byId("generated").textContent = `generated ${{state.generated_at}}`;
    byId("today-focus").textContent = `${{state.today}} · ${{state.today_overview.focus}} · Codex ${{state.today_overview.codex_tasks_today}} · 学习 ${{state.today_overview.learning_notes_today || 0}} · 文档 ${{state.today_overview.document_logs_today || 0}} · 项目日志 ${{state.today_overview.project_logs_today || 0}}`;
    byId("knowledge-count").textContent = state.counts.knowledge_cards;
    byId("project-count").textContent = state.counts.active_projects;
    byId("task-count").textContent = state.counts.codex_tasks;
    byId("learning-count").textContent = state.counts.learning_notes || 0;
    byId("document-count").textContent = state.counts.document_logs || 0;
    byId("project-log-count").textContent = state.counts.project_logs || 0;
    byId("review-count").textContent = state.counts.pending_review;

    byId("primary-links").innerHTML = [
      ["Dashboard.md", "00_Home/Dashboard.md"],
      ["Canvas", state.paths.canvas],
      ["State JSON", state.paths.state],
      ["Inbox", state.paths.inbox]
    ].map(([label, href]) => `<a class="link-button" href="${{shortPath(href)}}">${{label}}</a>`).join("");

    byId("project-list").innerHTML = state.active_projects.map(project => `
      <div class="item">
        <span>${{project.name}}<div class="progress"><div class="bar" style="--value:${{project.progress}}%"></div></div></span>
        <span class="tag">${{project.status}}</span>
      </div>
    `).join("") || `<p class="muted">暂无项目。</p>`;

    byId("risk-list").innerHTML = (state.risk_status.items.length ? state.risk_status.items : [{{title: state.risk_status.note, risk: state.risk_status.level}}]).map(item => `
      <li class="item"><span>${{item.title}}</span><span class="tag risk">${{item.risk}}</span></li>
    `).join("");

    byId("learning-list").innerHTML = state.learning_modules.map(item => `
      <li class="item"><span>${{item.name}}</span><span class="tag">${{item.note_count || 0}} notes</span></li>
    `).join("");

    byId("career-list").innerHTML = state.career_modules.map(item => `
      <li class="item"><span>${{item.name}}</span><span class="tag warn">${{item.status}}</span></li>
    `).join("");

    byId("artifact-timeline").innerHTML = state.recent_artifacts.slice(0, 8).map(item => `
      <a class="timeline-entry" href="${{shortPath(item.path)}}">${{item.name}}</a>
    `).join("");

    byId("next-actions").innerHTML = state.next_actions.map(action => `
      <li class="item"><span>${{action}}</span><span class="tag">next</span></li>
    `).join("");
  </script>
</body>
</html>
"""


def build_static_dashboard(ctx: WorkstationContext, state: dict | None = None, note_date: str | None = None):
    state = state or collect_state(ctx, note_date)
    path = ctx.target_root / "dashboard.html"
    return write_text_file(path, dashboard_html(ctx, state), overwrite=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build static local dashboard.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    result = build_static_dashboard(ctx, note_date=args.date)
    print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
