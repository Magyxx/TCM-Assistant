# P1.2 SQLite Persistence Report

Generated: 2026-06-16

## 1. What P1.2 Implemented

P1.2 adds minimal local SQLite persistence for the FastAPI runtime session layer.
The API now persists:

- session metadata
- the latest complete `RunState` JSON per session
- turn history with user input and a compact response summary

The existing FastAPI endpoints remain unchanged:

- `GET /health`
- `POST /sessions`
- `POST /sessions/{session_id}/turn`
- `GET /sessions/{session_id}/state`
- `GET /sessions/{session_id}/report`

`POST /sessions/{session_id}/turn` loads the session and state from SQLite,
runs the existing LangGraph workflow, then saves the turn row and updated
state in one SQLite transaction.

## 2. What P1.2 Did Not Implement

P1.2 did not add or change any product capability beyond local API session
persistence.

Not introduced:

- MemoryManager
- Embedding or vector storage
- RAG expansion
- Tool Registry
- multi-agent workflow
- Web UI
- user system
- permission system
- production deployment design
- SQLAlchemy, Alembic, or an ORM
- diagnosis, prescription, or treatment-plan output

The existing P0 safety boundary is unchanged.

## 3. SQLite Schema

P1.2 uses Python standard-library `sqlite3` and three tables.

```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    stage TEXT,
    mode TEXT,
    rag_enabled INTEGER
);

CREATE TABLE IF NOT EXISTS session_states (
    session_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    user_input TEXT NOT NULL,
    response_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    UNIQUE(session_id, turn_index)
);
```

`state_json` stores the complete `RunState` as JSON. P1.2 does not decompose
state into additional domain tables.

## 4. API Compatibility

The P1.1 response models and endpoint paths are preserved.

`GET /health` still returns the P1.1-compatible contract:

```json
{
  "status": "ok",
  "service": "TCM-Assistant",
  "stage": "P1.1",
  "mode": "agentic_workflow",
  "diagnosis_system": false
}
```

The internal storage behavior changed from process-only in-memory sessions to
SQLite-backed sessions. The in-memory cache remains only as a short-lived
runtime convenience and is not the source of truth.

## 5. Local DB Path

The SQLite path is configured with:

```bash
TCM_API_DB_PATH=./.runtime/tcm_assistant.sqlite3
```

Default path:

```text
.runtime/tcm_assistant.sqlite3
```

Runtime database files are ignored by Git via `.gitignore`.

## 6. Secret Handling

P1.2 does not save API keys, secrets, or tokens intentionally. Persisted text is
redacted for common secret-like patterns such as `sk-...` and
`OPENAI_API_KEY=...`.

The new persistence tests scan the SQLite database and WAL/SHM sidecar files for
the sample secret values used in the test.

## 7. Safety Boundary

P1.2 does not add diagnosis, prescription, treatment-plan, or medical
decision-making behavior. It only stores and reloads the same state that the
P1.1 API already returned from the existing P0/P1.1 workflow.

## 8. Test Results

Validated commands in this environment:

```powershell
python -m py_compile app\api\sqlite_store.py app\api\session_runtime.py scripts\run_api_persistence_demo.py tests\test_p1_2_sqlite_persistence.py
python -m unittest tests.test_p1_2_sqlite_persistence
python -m unittest tests.test_p1_1_api_minimal
python -m unittest tests.test_p0_risk_rules
python -m unittest tests.test_p0_turn_extractor
python -m unittest tests.test_p0_consultation_graph
python -m unittest tests.test_p0_hybrid_rag
python -m unittest tests.test_p0_report_safety
python -m unittest discover -s tests
python scripts\run_api_persistence_demo.py
python scripts\validate_real_extractor.py --case "最近胃胀，饭后明显，睡眠一般"
python scripts\run_graph_demo.py --extractor real_llm
python scripts\eval_report.py --mode graph --extractor real_llm --failed-only
python scripts\eval_sft_extract.py --pred-file data\sft\processed\sft_report_turn_extract_val.jsonl
git diff --check
```

Results:

- P1.2 SQLite persistence tests: 8 tests OK
- P1.1 API minimal tests: 9 tests OK
- P0 risk rules: 13 tests OK
- P0 turn extractor: 9 tests OK
- P0 consultation graph: 13 tests OK
- P0 hybrid RAG: 6 tests OK
- P0 report safety: 6 tests OK
- Full unittest discovery: 64 tests OK
- Persistence demo: session/state/turn restored after cache clear
- real LLM extractor sample: OK, `strategy=json_prompt`, `fallback_used=False`
- real LLM graph demo: OK, `final_schema_pass=True`, `fallback_used=False`
- real LLM report eval: 20/20
- SFT eval: 4/4
- `git diff --check`: OK, no whitespace errors; Windows LF/CRLF warnings only

`python -m pytest tests\test_p1_2_sqlite_persistence.py` could not run because
`pytest` is not installed in the current environment. The equivalent unittest
suite was run instead.

## 9. P0 and P1.1 Regression Status

Required regression commands:

```powershell
python -m unittest tests.test_p0_risk_rules
python -m unittest tests.test_p0_turn_extractor
python -m unittest tests.test_p0_consultation_graph
python -m unittest tests.test_p0_hybrid_rag
python -m unittest tests.test_p0_report_safety
python -m unittest tests.test_p1_1_api_minimal
```

P1.1 has passed after the SQLite changes. P0 regression results are green after
the final regression pass for this patch.

Summary:

- P0 unit regressions: passed
- P1.1 API regression: passed
- P1.2 persistence tests: passed
- real LLM sample and eval: passed after non-sandbox network access was approved
- SFT eval: passed

## 10. Next Step Recommendation

After the full P0/P1.1/P1.2 regression pass stays green and `git diff --check`
is clean, P1.2 can be considered complete. The next stage can be P1.3, still
under the same safety boundary, with scope decided separately.
