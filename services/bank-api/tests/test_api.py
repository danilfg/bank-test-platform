from __future__ import annotations

import os
import time

import pytest
import requests


API_BASE_URL = os.getenv("TEST_BANK_API_URL", "http://bank-api:8002").rstrip("/")
AUTH_BASE_URL = os.getenv("TEST_AUTH_BASE_URL", "http://auth-service:8001").rstrip("/")
STUDENT_EMAIL = os.getenv("TEST_STUDENT_EMAIL", "student@easyitlab.tech")
STUDENT_PASSWORD = os.getenv("TEST_STUDENT_PASSWORD", "student123")


def wait_for_ready(url: str, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    pytest.fail(f"Service is not ready: {url}")


def request_with_retry(
    method: str,
    url: str,
    *,
    timeout_seconds: int = 90,
    **kwargs,
) -> requests.Response:
    deadline = time.time() + timeout_seconds
    last_status = None
    while time.time() < deadline:
        try:
            response = requests.request(method, url, timeout=10, **kwargs)
            last_status = response.status_code
            if response.status_code not in (500, 502, 503, 504):
                return response
        except requests.RequestException:
            pass
        time.sleep(1)
    pytest.fail(f"Request failed or stayed in 5xx: {method} {url}. Last status: {last_status}")


def login() -> dict:
    wait_for_ready(f"{AUTH_BASE_URL}/health")
    deadline = time.time() + 90
    last_status = None
    while time.time() < deadline:
        response = request_with_retry(
            "POST",
            f"{AUTH_BASE_URL}/auth/login",
            json={"email": STUDENT_EMAIL, "password": STUDENT_PASSWORD},
            timeout_seconds=15,
        )
        last_status = response.status_code
        if response.status_code == 200:
            return response.json()
        time.sleep(1)
    pytest.fail(f"Cannot login as student. Last HTTP status: {last_status}")


@pytest.fixture(scope="session")
def access_token() -> str:
    payload = login()
    token = payload.get("access_token")
    assert token and isinstance(token, str)
    return token


@pytest.mark.auth
def test_auth_login_returns_tokens() -> None:
    payload = login()
    assert isinstance(payload.get("access_token"), str) and payload["access_token"]
    assert isinstance(payload.get("refresh_token"), str) and payload["refresh_token"]
    assert payload.get("token_type", "").lower() == "bearer"


@pytest.mark.dashboard
def test_students_dashboard_requires_auth() -> None:
    wait_for_ready(f"{API_BASE_URL}/health")
    response = request_with_retry("GET", f"{API_BASE_URL}/students/dashboard")
    assert response.status_code in (401, 403)


@pytest.mark.dashboard
def test_students_dashboard_with_access_token(access_token: str) -> None:
    wait_for_ready(f"{API_BASE_URL}/health")
    response = request_with_retry(
        "GET",
        f"{API_BASE_URL}/students/dashboard",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    for key in (
        "employees_total",
        "clients_total",
        "accounts_total",
        "tickets_total",
        "transfers_total",
    ):
        assert key in payload


def test_students_identity_contains_required_tools(access_token: str) -> None:
    wait_for_ready(f"{API_BASE_URL}/health")
    response = request_with_retry(
        "GET",
        f"{API_BASE_URL}/students/me/identity",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    accesses = payload.get("accesses", [])
    services = {item.get("service_name") for item in accesses if isinstance(item, dict)}
    expected = {"JENKINS", "ALLURE", "POSTGRES", "REST_API", "REDIS", "KAFKA"}
    assert expected.issubset(services)
