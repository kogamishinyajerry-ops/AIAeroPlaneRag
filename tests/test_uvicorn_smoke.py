from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _request_json(url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body)


def test_uvicorn_src_main_smoke():
    root = Path(__file__).resolve().parents[1]
    port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(root),
            "API_KEY": "",
            "APP_MODE": "mock",
            "RATE_LIMIT_ENABLED": "false",
            "ZHIPU_API_KEY": "",
            "MINIMAX_API_KEY": "",
            "EMBEDDING_API_KEY": "",
            "JINA_API_KEY": "",
            "OLLAMA_API_KEY": "",
        }
    )

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        health_payload = None
        for _ in range(60):
            if process.poll() is not None:
                raise AssertionError(f"uvicorn exited early with code {process.returncode}")
            try:
                status_code, payload = _request_json(f"http://127.0.0.1:{port}/api/v1/health")
                if status_code == 200:
                    health_payload = payload
                    break
            except Exception:
                pass
            time.sleep(0.5)

        assert health_payload is not None, "health endpoint did not become ready in time"
        assert health_payload["app_version"] == "0.3.0"
        assert "vector_db" in health_payload
        assert "guardrail" in health_payload

        status_code, query_payload = _request_json(
            f"http://127.0.0.1:{port}/api/v1/query/pageindex",
            {"query": "压气机喘振裕度要求", "top_k": 1},
        )
        assert status_code == 200
        assert query_payload["responseMode"] == "pageindex"
        assert "answer" in query_payload
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
