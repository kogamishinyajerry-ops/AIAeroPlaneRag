# Release Checklist

Use this checklist before tagging or demoing a new version.

## Preconditions

- `APP_VERSION`, `DOCUMENT_VERSION`, `PROMPT_VERSION`, `EMBEDDING_VERSION`, and `GRAPH_VERSION` are updated as needed.
- The expected source data exists under `data/raw/` and `data/processed/`.
- No secrets are present in tracked files.

## Local Validation

- Run `.\.venv\Scripts\python.exe scripts\quality_gate.py`
- Confirm `.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 0.0.0.0 --port 8000` starts successfully.
- Check `GET /api/v1/health` and confirm the returned versions match the release plan.
- Check `GET /api/v1/graph/nodes` and confirm graph mode is expected (`connected` or `fallback`).

## Release Notes

- Record the app version.
- Record the document version.
- Record the prompt version.
- Record the embedding version.
- Record the graph version.
- Record known limits and operational risks.

## Exit Criteria

- CI passed on the release branch.
- Quality gate passed locally.
- Health check and graph endpoint were manually spot-checked.
