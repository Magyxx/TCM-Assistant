# P11-M3 Workflow Main Path

P11-M3 audits the post-LoRA workflow path. The goal is to verify the mainline
chain, not to replace the existing graph implementation.

## Main Path

The P9 main path is exposed by `app.graph.runner.run_p9m1_graph` and executes:

1. `normalize_input`
2. `extract_turn`
3. `validate_turn`
4. `merge_state`
5. `risk_rule_check`
6. `decide_next`
7. `ask_followup`
8. `retrieve_knowledge`
9. `generate_report`
10. `safety_check`
11. `export_result`

The required P11-M3 path is therefore present:

`user_input -> extract candidate -> schema validate -> state update -> risk check -> next_action/report readiness`

## Runtime Contract

`sequential_fallback` is the required runtime and must always work. LangGraph is
optional:

- if installed, `use_langgraph=True` may run the same node sequence through
  LangGraph
- if unavailable, verification records an explicit skip reason

## Schema And State Boundary

Extractor output is only a candidate until `validate_turn` succeeds. Authoritative
state is updated by `merge_state` after validation. The state update is recorded
in trace events and the exported result.

## Risk Authority

Final risk authority remains with `risk_rule_check`. `local_lora` and
`local_vllm` candidates cannot bypass the workflow path or clear high-risk
signals directly.

## Audit Artifacts

The graph emits:

- in-memory `trace` entries for node ordering
- `graph_events` entries for replay/audit
- `artifacts/p11/workflow_path_contract.json` from the verifier

## Verification

Run:

```powershell
python -m compileall -q app scripts tests
python -m unittest discover -s tests
python scripts/verify_p11_workflow_path.py --json --output artifacts/p11/workflow_path_contract.json
```
