from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.build_rag_manifest import build_rag_data  # noqa: E402
from scripts.personal_workstation.common import (  # noqa: E402
    WorkstationContext,
    json_dump,
    make_context,
    now_iso,
    write_text_file,
)


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[\w\u4e00-\u9fff]{2,}", text.lower())
    seen = set()
    result = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result[:80]


def build_search_records(ctx: WorkstationContext) -> tuple[dict, list[dict]]:
    manifest, sources, chunks = build_rag_data(ctx)
    chunk_by_source: dict[str, list[str]] = {}
    for chunk in chunks:
        chunk_by_source.setdefault(chunk["source_id"], []).append(chunk["text"])
    records = []
    for source in sources:
        text = " ".join(chunk_by_source.get(source["id"], []))
        title = source.get("topic") or source.get("title") or source.get("project") or Path(source["path"]).stem
        records.append(
            {
                "id": source["id"],
                "title": title,
                "path": source["path"],
                "type": source["type"],
                "project": source.get("project"),
                "topic": source.get("topic"),
                "title": source.get("title"),
                "date": source.get("date"),
                "human_reviewed": source.get("human_reviewed", False),
                "preview": source.get("preview", True),
                "tokens": tokenize(f"{title} {source['path']} {text}"),
                "excerpt": text[:360],
            }
        )
    index = {
        "generated_at": now_iso(ctx),
        "source": "personal_workstation.build_search_index",
        "preview": bool(ctx.config.get("preview_mode", True)),
        "network_used": False,
        "record_count": len(records),
        "rag_source_count": manifest["source_count"],
        "rag_chunk_count": manifest["chunk_count"],
    }
    return index, records


def search_html(ctx: WorkstationContext, index: dict, records: list[dict]) -> str:
    payload = json.dumps({"index": index, "records": records}, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Workstation Local Search</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #09100f;
      --panel: rgba(20, 29, 31, .92);
      --line: rgba(255,255,255,.12);
      --text: #eef8f5;
      --muted: #9db2ad;
      --accent: #5ee6c7;
      --warn: #f7c767;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      background: linear-gradient(135deg, #07100f, #151b1d 55%, #111018);
      color: var(--text);
    }}
    main {{ width: min(1080px, calc(100% - 28px)); margin: 0 auto; padding: 34px 0; }}
    h1 {{ margin: 0 0 10px; font-size: 38px; letter-spacing: 0; }}
    .muted {{ color: var(--muted); line-height: 1.55; }}
    .searchbar {{ display: grid; grid-template-columns: 1fr auto; gap: 10px; margin: 22px 0; }}
    input {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,.06);
      color: var(--text);
      padding: 14px 15px;
      font-size: 16px;
      outline: none;
    }}
    button {{
      border: 1px solid rgba(94,230,199,.38);
      border-radius: 8px;
      background: rgba(94,230,199,.16);
      color: var(--text);
      padding: 0 18px;
      font-size: 15px;
      cursor: pointer;
    }}
    .stats {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }}
    .pill {{ border: 1px solid var(--line); border-radius: 999px; padding: 7px 11px; color: var(--muted); }}
    .results {{ display: grid; gap: 12px; }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 16px;
      transition: transform .15s ease, border-color .15s ease;
    }}
    .card:hover {{ transform: translateY(-2px); border-color: rgba(94,230,199,.45); }}
    .card h2 {{ font-size: 18px; margin: 0 0 6px; }}
    .meta {{ color: var(--muted); font-size: 13px; margin-bottom: 10px; }}
    a {{ color: var(--accent); text-decoration: none; }}
    mark {{ background: rgba(247,199,103,.28); color: var(--text); border-radius: 3px; padding: 0 2px; }}
    @media (max-width: 640px) {{ .searchbar {{ grid-template-columns: 1fr; }} button {{ padding: 12px; }} }}
  </style>
</head>
<body>
  <main>
    <h1>Local Search</h1>
    <p class="muted">本地静态搜索，不联网，不调用模型。搜索范围来自 RAG-ready manifest。</p>
    <div class="searchbar">
      <input id="query" placeholder="搜索项目、Codex 任务、知识卡片、复盘..." autofocus>
      <button id="clear">清空</button>
    </div>
    <div class="stats" id="stats"></div>
    <section class="results" id="results"></section>
  </main>
  <script id="search-data" type="application/json">{payload}</script>
  <script>
    const payload = JSON.parse(document.getElementById("search-data").textContent);
    const query = document.getElementById("query");
    const results = document.getElementById("results");
    const stats = document.getElementById("stats");
    const clear = document.getElementById("clear");

    function escapeHtml(value) {{
      return value.replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c]));
    }}
    function terms(value) {{
      return value.toLowerCase().match(/[\\w\\u4e00-\\u9fff]{{2,}}/g) || [];
    }}
    function score(record, words) {{
      if (!words.length) return 1;
      const haystack = `${{record.title}} ${{record.path}} ${{record.excerpt}} ${{record.tokens.join(" ")}}`.toLowerCase();
      return words.reduce((total, word) => total + (haystack.includes(word) ? 1 : 0), 0);
    }}
    function highlight(text, words) {{
      let escaped = escapeHtml(text || "");
      for (const word of words) {{
        escaped = escaped.replace(new RegExp(`(${{word.replace(/[.*+?^${{}}()|[\\]\\\\]/g, "\\\\$&")}})`, "ig"), "<mark>$1</mark>");
      }}
      return escaped;
    }}
    function render() {{
      const words = terms(query.value);
      const ranked = payload.records
        .map(record => ({{ record, score: score(record, words) }}))
        .filter(item => words.length ? item.score > 0 : true)
        .sort((a, b) => b.score - a.score || a.record.path.localeCompare(b.record.path))
        .slice(0, 50);
      stats.innerHTML = [
        `records ${{payload.index.record_count}}`,
        `chunks ${{payload.index.rag_chunk_count}}`,
        `results ${{ranked.length}}`,
        payload.index.preview ? "preview" : "vault"
      ].map(item => `<span class="pill">${{item}}</span>`).join("");
      results.innerHTML = ranked.map(item => {{
        const record = item.record;
        return `<article class="card">
          <h2><a href="../../${{escapeHtml(record.path)}}">${{highlight(record.title, words)}}</a></h2>
          <div class="meta">${{escapeHtml(record.type)}} · ${{escapeHtml(record.path)}} · reviewed=${{record.human_reviewed}}</div>
          <div class="muted">${{highlight(record.excerpt, words)}}</div>
        </article>`;
      }}).join("") || `<p class="muted">没有匹配结果。</p>`;
    }}
    query.addEventListener("input", render);
    clear.addEventListener("click", () => {{ query.value = ""; render(); query.focus(); }});
    render();
  </script>
</body>
</html>
"""


def build_search_index(ctx: WorkstationContext):
    search_dir = ctx.target_root / "99_System" / "Search"
    index, records = build_search_records(ctx)
    return [
        write_text_file(search_dir / "search_index.json", json_dump({"index": index, "records": records}), overwrite=True),
        write_text_file(search_dir / "search.html", search_html(ctx, index, records), overwrite=True),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build local static search index and page.")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    for result in build_search_index(ctx):
        print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
