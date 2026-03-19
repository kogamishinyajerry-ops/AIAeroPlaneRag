# AeroPower-RAG v0.1.0 Release Notes

Release date: 2026-03-19

## Release Summary

This is the first formal baseline release for the repository.

The project now includes:

- a runnable FastAPI backend for traceable regulation Q&A
- structural chunking and local vector retrieval
- graph query support with JSON fallback when Neo4j has no loaded graph data
- conservative guardrail behavior when external verification is unavailable
- a minimal automated test suite and golden-set summary flow
- a local quality gate and GitHub Actions CI workflow
- release and rollback documentation for controlled iteration

## Scope Delivered

### Phase 1: Foundation stabilization

- initialized repository governance files
- removed committed secret usage from tracked configuration
- unified processed-data and Chroma paths
- repaired local Chroma startup and offline embedding fallback
- improved API health reporting

### Phase 2: Traceability and response hardening

- separated mock and real parsing modes
- added document metadata sidecars and chunk metadata enrichment
- extended API citations with document and source metadata
- changed guardrail fallback from implicit pass to conservative response handling

### Phase 3: Evaluation and graph resilience

- added graph JSON fallback for graph APIs
- added API smoke tests and evaluation tests
- added a golden-set sample and summary script
- migrated startup handling to FastAPI lifespan

### Phase 4: Delivery governance

- introduced app, prompt, embedding, graph, and document version labels
- added `scripts/quality_gate.py`
- added CI workflow under `.github/workflows/ci.yml`
- added release checklist and rollback runbook

## Version Manifest

- App version: `0.1.0`
- Document version: `ccar33-enriched-mock-v1`
- Prompt version: `rag-prompt-v1`
- Embedding version: `simple-hash-v1`
- Graph version: `ccar33-graph-export-v1`

## Validation Completed

The following checks were run for this release:

- `.\.venv\Scripts\python.exe -m pytest tests -q`
- `.\.venv\Scripts\python.exe scripts\quality_gate.py`
- manual health check verification
- manual graph fallback verification

## Current Known Limits

- the primary dataset is still based on a mock-enriched CCAR-33 sample rather than a production-grade real corpus
- graph queries fall back to JSON because Neo4j is connected but not yet populated as the system of record
- the guardrail layer remains conservative and does not yet provide a fully evaluated verifier pipeline
- CI is intentionally minimal and does not yet cover end-to-end external-service integration

## Recommended Next Release Focus

- ingest and version a real regulation source set
- expand golden-set evaluation from structure checks to retrieval and answer scoring
- populate and validate Neo4j as the primary graph backend
- formalize branch protection, tagging, and release packaging
