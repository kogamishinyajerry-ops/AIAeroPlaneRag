from __future__ import annotations

import json

from fastapi.testclient import TestClient


def _configure_auth():
    import src.core.config as config_module
    import src.api.dependencies.auth as auth_module

    config_module.API_KEYS.clear()
    config_module.API_KEYS.add("test-api-key-12345")
    auth_module.API_KEYS.clear()
    auth_module.API_KEYS.add("test-api-key-12345")


def _issue_token(client: TestClient) -> str:
    token_resp = client.post(
        "/api/v1/auth/token",
        json={"api_key": "test-api-key-12345"},
    )
    assert token_resp.status_code == 200, token_resp.text
    return token_resp.json()["access_token"]


def test_graph_network_filters_neighbors_and_limits_nodes(main_module, monkeypatch, tmp_path):
    import src.api.routes.graph as graph_module

    _configure_auth()

    processed_dir = tmp_path / "processed"
    kg_dir = processed_dir / "knowledge_graph"
    kg_dir.mkdir(parents=True)
    graph_file = kg_dir / "graph.json"
    graph_file.write_text(
        json.dumps(
            {
                "nodes": {
                    "compressor": {"title": "Compressor", "label": "Compressor Assembly"},
                    "surge": {"title": "Surge Margin", "label": "Margin"},
                    "turbine": {"title": "Turbine", "label": "Hot Section"},
                },
                "edges": [
                    {"source": "compressor", "target": "surge", "type": "RELATES_TO"},
                    {"source": "surge", "target": "turbine", "type": "INFLUENCES"},
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(graph_module, "PROCESSED_DATA_DIR", processed_dir)

    client = TestClient(main_module.app)
    token = _issue_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/api/v1/graph/network",
        params={"query": "compressor", "max_nodes": 10},
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()

    node_ids = {node["id"] for node in payload["nodes"]}
    assert "compressor" in node_ids
    assert "surge" in node_ids
    assert payload["query"] == "compressor"
    assert payload["total_nodes"] == len(payload["nodes"])
    assert payload["total_edges"] == len(payload["edges"])

    limited = client.get(
        "/api/v1/graph/network",
        params={"max_nodes": 10},
        headers=headers,
    )
    assert limited.status_code == 200
    limited_payload = limited.json()
    assert len(limited_payload["nodes"]) <= 10


def test_graph_nodes_reports_counts(main_module, monkeypatch, tmp_path):
    import src.api.routes.graph as graph_module

    _configure_auth()

    processed_dir = tmp_path / "processed"
    graph_file = processed_dir / "CCAR-33_graph.json"
    processed_dir.mkdir(parents=True)
    graph_file.write_text(
        json.dumps(
            {
                "nodes": {
                    "n1": {"title": "Clause 1", "label": "Regulation"},
                    "n2": {"title": "Compressor", "label": "Component"},
                },
                "edges": [{"source": "n1", "target": "n2", "type": "CONSTRAINS"}],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(graph_module, "PROCESSED_DATA_DIR", processed_dir)

    client = TestClient(main_module.app)
    token = _issue_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/graph/nodes", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["node_count"] == 2
    assert payload["edge_count"] == 1
    assert len(payload["nodes"]) == 2
