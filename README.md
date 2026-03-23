# AeroPower-RAG

AeroPower-RAG is a prototype aviation knowledge system for civil aircraft engine regulations. It combines document ingestion, structural chunking, vector retrieval, knowledge graph extraction, and a guardrail layer to support traceable Q&A over CCAR-style source material.

## Current Stage

This repository is in a `v0.2` prototype hardening phase.

- The backend now exposes query, focused graph, health, indexing, and official source-catalog endpoints.
- The frontend graph view has been shifted from a full graph dump to a query-driven explanation subgraph.
- The repository now includes an official source catalog covering CAAC, FAA, and EASA entry points for v0.2 expansion.
- Several flows still rely on mock or fallback behavior when external services are unavailable.

## Environment Setup

Recommended prerequisites:

- Python 3.12+
- Neo4j 5 community edition
- Access to the required LLM and parsing APIs if you want the real ingestion path

Local setup:

```powershell
python -m venv .venv
.\\.venv\\Scripts\\activate
pip install -r requirements.txt
copy .env.example .env
```

Update `.env` with your actual service credentials before running any real ingestion or answer-generation flow.

## How To Run

Backend:

```powershell
.\\.venv\\Scripts\\python.exe -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Neo4j:

```powershell
docker compose up -d neo4j
```

Frontend:

- Open `ui/index.html` in a browser, or serve the `ui/` folder with any static file server.
- The frontend expects the backend to be reachable at `http://localhost:8000`.

Optional demo and extraction scripts:

```powershell
.\\.venv\\Scripts\\python.exe run_demo.py
.\\.venv\\Scripts\\python.exe run_extraction.py
```

## Testing And Evaluation

Run the minimal unit test suite:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest tests
```

Run the full local quality gate used by CI:

```powershell
.\\.venv\\Scripts\\python.exe scripts\\quality_gate.py
```

Run the FastAPI main-chain smoke test directly:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest tests\\test_main_api.py -q
```

Inspect the official source catalog:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/sources
```

Inspect the sample golden set template and summary stats:

```powershell
.\\.venv\\Scripts\\python.exe evaluation\\evaluate_golden_set.py --golden-set evaluation\\golden_set_sample.json
```

The `evaluation/` folder is intentionally lightweight for now. It is meant to hold golden sets, offline evaluation summaries, and later retrieval or answer-quality reports. The current summary includes `expected_top_section`, `expected_sections`, `expected_keywords`, answer-type counts, and the most common sections/keywords.

## Repository Layout

```text
.
|-- data/
|   |-- raw/              # Source documents
|   `-- processed/        # Parsed markdown, graph exports, vector DB artifacts
|   `-- catalog/          # Official source catalog and source metadata seeds
|-- src/
|   |-- knowledge_base/   # Source catalog and metadata models
|   |-- ingestion/        # Parsing and ingestion logic
|   |-- ontology/         # Entity extraction and graph access
|   `-- rag/              # Chunking, retrieval, and guardrail logic
|-- ui/                   # Static frontend
|-- docker-compose.yml    # Neo4j service definition
|-- requirements.txt      # Python dependencies
|-- run_demo.py           # End-to-end demo pipeline
|-- run_extraction.py     # Graph extraction entrypoint
|-- tests/                # Minimal unit tests
|-- evaluation/           # Golden-set templates and evaluation scripts
`-- test_glm_models.py    # LLM model probe script
```

## Known Limits

- The project still mixes real and mock paths in a few places, so the runtime behavior depends on which environment variables and services are available.
- ChromaDB persistence and data-directory handling still need hardening for production use.
- Release/version labels now exist for the app, document set, prompts, embeddings, and graph exports, but the project is still early in formal release automation.
- The guardrail layer should be treated as a prototype until it is backed by stronger evaluation and test coverage.
- The source catalog is official and curated, but only CCAR-33 sample content is currently ingested into the local retriever.
- The graph UI is now focused and query-driven, but it still runs on a lightweight custom renderer rather than a full graph visualization library.

## Release Governance

- CI runs the shared quality gate from [scripts/quality_gate.py](/D:/AIAeroPlaneRag/scripts/quality_gate.py).
- Release validation and manual checks are documented in [docs/release_checklist.md](/D:/AIAeroPlaneRag/docs/release_checklist.md).
- Rollback steps are documented in [docs/rollback_runbook.md](/D:/AIAeroPlaneRag/docs/rollback_runbook.md).
- API health responses now include `app_version`, `document_version`, `prompt_version`, `embedding_version`, and `graph_version` labels for traceability.

## Notes For Developers

- Keep secrets out of version control.
- Prefer writing new generated artifacts under `data/processed/` only when they are reproducible.
- Do not overwrite or delete raw source data unless you are intentionally regenerating a dataset.
