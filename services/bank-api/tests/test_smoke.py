from __future__ import annotations

import os
import time

import pytest
import requests


API_BASE_URL = os.getenv("TEST_API_BASE_URL", "http://api-gateway:8080").rstrip("/")
BANK_API_URL = os.getenv("TEST_BANK_API_URL", "http://bank-api:8002").rstrip("/")


def wait_for_ok(url: str, timeout_seconds: int = 90) -> requests.Response:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(1)
    message = f"Service did not become ready in time: {url}"
    if last_error:
        message = f"{message}. Last error: {last_error}"
    pytest.fail(message)


def test_gateway_health() -> None:
    response = wait_for_ok(f"{API_BASE_URL}/health")
    payload = response.json()
    assert payload.get("status") == "ok"


def test_bank_api_health() -> None:
    response = wait_for_ok(f"{BANK_API_URL}/health")
    payload = response.json()
    assert payload.get("status") == "ok"


def test_swagger_docs_available() -> None:
    wait_for_ok(f"{API_BASE_URL}/health")
    response = requests.get(f"{API_BASE_URL}/docs", timeout=10)
    assert response.status_code == 200
    assert "SwaggerUIBundle" in response.text
