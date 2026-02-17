# Tasks: Publish Array Default Hydration

## 1. Reproduce + lock failing behavior

- [x] 1.1 (flock-repo-jyr.1) Add/confirm backend failing test for missing array `default_factory` defaults in `/api/artifact-types`
- [x] 1.2 (flock-repo-jyr.2) Add/confirm frontend failing test for empty array textarea prefill when schema default is absent

## 2. Backend schema enrichment (primary fix)

- [x] 2.1 (flock-repo-jyr.3) Add helper in `ControlRoutesComponent` to inject array defaults from `model_fields` + `get_default(call_default_factory=True)`
- [x] 2.2 (flock-repo-jyr.4) Apply helper to both artifact type routes (`artifact-types` and `artifact_types`)
- [x] 2.3 (flock-repo-jyr.5) Guardrails: list-check first, skip on exceptions/non-serializable values, never override existing schema defaults

## 3. Frontend verification

- [x] 3.1 (flock-repo-jyr.6) Add/extend `PublishControl.test.tsx` to verify array defaults prefill textarea (newline-joined)
- [x] 3.2 (flock-repo-jyr.7) Verify no regression for scalar defaults and submit conversion logic

## 4. Validation

- [x] 4.1 (flock-repo-jyr.8) `uv run python -m pytest tests/test_dashboard_service.py -k "artifact_types and (hydrates or normalizes or parity)" -v`
- [x] 4.2 (flock-repo-jyr.9) `cd src/flock/frontend && npm test -- PublishControl.test.tsx`
- [x] 4.3 (flock-repo-jyr.10) Optional manual smoke: run dashboard, select artifact with list defaults, verify prefill in UI

## 5. Docs/changelog

- [x] 5.1 (flock-repo-jyr.11) Add changelog note: dashboard publish now honors list defaults from `default_factory`
