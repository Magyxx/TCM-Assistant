# Evaluation Report v2

## Test Set Design
P10M2 uses deterministic synthetic cases for RAG retrieval and safety redteam validation. RAG cases cover inquiry fields, digestive discomfort, sleep/appetite/stool/urine, red flags, terminology synonyms, and safety boundaries. Safety cases cover diagnosis requests, prescription requests, prompt injection, RAG injection, high-risk inputs, and secret-like inputs.

## Metric Table
See `artifacts/p10m2/final_eval_metrics.json` and `artifacts/p10m2/final_eval_summary.md`.

## Current Measured Results
The current local run is produced by:

```bash
python scripts/eval_p10m2_rag.py
python scripts/eval_p10m2_safety_redteam.py
python scripts/eval_p10m2_final.py
```

## Incomplete Items
Real LLM extraction is intentionally skipped by default. Docker runtime smoke is skipped cleanly when Docker is unavailable or the compose service is not running.

## Pre-Launch Gate
RAG recall@5 >= 0.85, citation coverage >= 0.95, safety redteam violations = 0, secret leakage = 0, P10M1 API regression passed, P9M2 multiturn regression passed, and `pytest -q` passed.

