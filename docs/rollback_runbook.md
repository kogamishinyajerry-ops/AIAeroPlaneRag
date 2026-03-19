# Rollback Runbook

Use this runbook if a release introduces a regression.

## Trigger Conditions

- `scripts/quality_gate.py` fails after a release branch merge.
- `/api/v1/health` reports unexpected service degradation.
- Retrieval or graph responses no longer match the planned document version.

## Rollback Steps

1. Identify the last known good branch or commit.
2. Restore the matching environment variables for:
   - `APP_VERSION`
   - `DOCUMENT_VERSION`
   - `PROMPT_VERSION`
   - `EMBEDDING_VERSION`
   - `GRAPH_VERSION`
3. Rebuild or restore the expected `data/processed/chroma_db` contents if the index changed.
4. Restart the backend service.
5. Re-run `scripts/quality_gate.py`.
6. Verify `GET /api/v1/health` and `GET /api/v1/graph/nodes`.

## Post-Rollback Notes

- Document the regression trigger.
- Record whether the issue came from code, data, graph export, or configuration drift.
- Add a follow-up test or evaluation case before the next release.
