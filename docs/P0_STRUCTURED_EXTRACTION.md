# P0 Structured Extraction

## Goal

P0 adds a unified turn extraction layer without removing the legacy prompt-only JSON path.

The extractor still follows the project boundary: it only extracts inquiry information into `TurnOutput`; it does not diagnose, prescribe, or decide treatment.

## Entry Point

New module:

- `app/chains/turn_extractor.py`

Primary function:

- `extract_turn(state: RunState, user_input: str, prefer_structured_output: bool = True) -> ExtractionResult`

## Return Shape

`ExtractionResult` contains:

- `success`
- `turn_output`
- `raw_text`
- `error`
- `mode`
- `json_valid`
- `schema_valid`
- `raw_llm_json_valid`
- `final_schema_pass`
- `fallback_used`

Supported modes:

- `structured_output`
- `fake_structured_output`
- `json_prompt_fallback`
- `rule_fallback`

## Extraction Order

1. Try LangChain structured output with `TurnOutput` as the Pydantic schema.
2. If the model/provider does not support structured output, fall back to the legacy JSON prompt chain in `app/chains/report_chain.py`.
3. If both LLM paths fail, return a conservative `rule_fallback` `TurnOutput`.

Every successful LLM extraction must pass `TurnOutput.model_validate()` before it can enter state merge.

## Fake Extractor For Tests

`extract_with_fake_structured_output()` provides a deterministic local extractor for P0 tests. It produces JSON text and validates it through `TurnOutput`, so tests can exercise the JSON/schema path without a real API key.

This is not a medical model and not a production extractor. It only covers small deterministic cases needed to verify graph wiring, metrics, and fallback boundaries.

## Metric Semantics

- `raw_llm_json_valid`: true only when the raw structured/fake/json-prompt text was valid JSON for the extraction path.
- `final_schema_pass`: true when the final `TurnOutput` object passed Pydantic validation, including controlled fallback objects.
- `fallback_used`: true when the result came from `rule_fallback`.

This prevents fallback-created schema objects from being counted as raw LLM JSON success.

## Fallback Guarantees

- Unsupported `with_structured_output()` does not break the CLI.
- Missing external API does not inject free text into `RunState`.
- Rule fallback may detect explicit high-risk keywords, but otherwise keeps fields unknown.
- Existing `scripts/run_report.py` and `app/chains/report_chain.py` remain available.

## Future Extension Points

- Use provider-native JSON schema when available.
- Record extraction metrics in LangSmith later.
- Route selected hard cases to the SFT/LoRA local extractor.
- Add field-level confidence when a future model supports it.

## P0.3 Real LLM Validation Notes

P0.3 keeps the legacy and fallback behavior, but makes the real LLM strategy ladder explicit:

1. `provider_native_structured_output`
2. `tool_calling_structured_output`
3. `json_prompt`
4. `rule_fallback`

The real LLM extractor reads only `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` from the environment. It never logs the API key. Error previews are shortened and redacted before being written to metadata, reports, or artifacts.

Additional metadata recorded in P0.3:

- `extractor_mode`
- `strategy`
- `raw_llm_json_valid`
- `final_schema_pass`
- `fallback_used`
- `model_name`
- `error_type`
- `error_message_preview`

If the provider cannot authenticate or does not support a structured strategy, the result remains `extractor_mode=real_llm` while `fallback_used=true` and `strategy=rule_fallback` make the fallback explicit. This prevents fallback schema success from being counted as raw LLM JSON success.
