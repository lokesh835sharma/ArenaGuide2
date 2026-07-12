"""Shared pytest fixtures.

Every fixture forces the offline configuration: no Gemini key (so the app uses
:class:`~src.services.ai_client.OfflineModel`) and a generous rate limit so functional
tests are never throttled. Individual tests override these as needed.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from starlette.testclient import TestClient

from src.config import AppConfig
from src.main import create_app


def _config(**overrides) -> AppConfig:
    params = {
        "gemini_api_key": None,  # highest-priority override → always offline OfflineModel
        "rate_limit_capacity": 1000,
        "rate_limit_refill_per_sec": 1000.0,
        "allowed_origins": ["http://testserver"],
    }
    params.update(overrides)
    return AppConfig(**params)


@pytest.fixture
def settings() -> AppConfig:
    return _config()


@pytest.fixture
def client(settings: AppConfig) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture
def make_client() -> Callable[..., TestClient]:
    """Factory to build a TestClient with custom config (e.g. low rate limit)."""

    def _make(**overrides) -> TestClient:
        return TestClient(create_app(_config(**overrides)))

    return _make


@pytest.fixture
def base_payload() -> dict:
    """A minimal valid ``/api/assist`` request body."""
    return {
        "language": "en",
        "current_location": "concourse_lower_sw",
        "destination_intent": "restroom",
        "accessibility_needs": ["none"],
        "time_to_event": 20,
    }
