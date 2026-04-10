from __future__ import annotations

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


def test_optimizer_status_jobs_and_reset(main_module):
    import src.background.optimizer as optimizer_module

    _configure_auth()
    client = TestClient(main_module.app)
    token = _issue_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    status_before = client.get("/api/v1/optimizer/status", headers=headers)
    assert status_before.status_code == 200
    payload_before = status_before.json()
    assert payload_before["total_jobs"] > 0
    assert payload_before["pending"] == payload_before["total_jobs"]
    assert payload_before["running"] is False
    assert len(payload_before["jobs"]) == payload_before["total_jobs"]

    jobs_response = client.get("/api/v1/optimizer/jobs", headers=headers)
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert len(jobs) == payload_before["total_jobs"]
    assert {"id", "name", "priority", "status"} <= set(jobs[0].keys())

    first_job_id = jobs[0]["id"]
    trigger_response = client.post(
        "/api/v1/optimizer/trigger",
        headers=headers,
        json={"job_id": first_job_id},
    )
    assert trigger_response.status_code == 200
    trigger_payload = trigger_response.json()
    assert trigger_payload["status"] == "completed"
    assert trigger_payload["triggered_jobs"] == [first_job_id]

    status_after_trigger = client.get("/api/v1/optimizer/status", headers=headers)
    assert status_after_trigger.status_code == 200
    payload_after_trigger = status_after_trigger.json()
    completed_ids = {job["id"] for job in payload_after_trigger["jobs"] if job["status"] == "completed"}
    assert first_job_id in completed_ids

    original_optimizer = optimizer_module.continuous_optimizer
    reset_response = client.post("/api/v1/optimizer/reset", headers=headers)
    assert reset_response.status_code == 200
    assert reset_response.json()["status"] == "ok"

    assert optimizer_module.continuous_optimizer is not original_optimizer

    status_after_reset = client.get("/api/v1/optimizer/status", headers=headers)
    assert status_after_reset.status_code == 200
    payload_after_reset = status_after_reset.json()
    assert payload_after_reset["completed"] == 0
    assert payload_after_reset["pending"] == payload_after_reset["total_jobs"]


def test_optimizer_continuous_start_and_stop(main_module, monkeypatch):
    import asyncio
    import src.background.optimizer as optimizer_module

    _configure_auth()
    client = TestClient(main_module.app)
    token = _issue_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    scheduled = {}

    def fake_create_task(coro):
        scheduled["coro"] = coro
        optimizer_module.continuous_optimizer.running = True
        coro.close()

        class DummyTask:
            def cancel(self):
                return None

        return DummyTask()

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)

    start_response = client.post(
        "/api/v1/optimizer/continuous/start",
        headers=headers,
        json={"interval_seconds": 5, "max_iterations": 2},
    )
    assert start_response.status_code == 200
    start_payload = start_response.json()
    assert start_payload["status"] == "started"
    assert "interval=5s" in start_payload["message"]
    assert "coro" in scheduled

    already_running = client.post(
        "/api/v1/optimizer/continuous/start",
        headers=headers,
        json={"interval_seconds": 5, "max_iterations": 2},
    )
    assert already_running.status_code == 200
    assert already_running.json()["status"] == "already_running"

    stop_response = client.post("/api/v1/optimizer/continuous/stop", headers=headers)
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"
    assert optimizer_module.continuous_optimizer.running is False
