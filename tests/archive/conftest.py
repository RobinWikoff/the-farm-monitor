import os

import pytest
import requests


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


@pytest.fixture(autouse=True)
def block_external_http_in_non_live_tests(monkeypatch, request):
    is_live_test = request.node.get_closest_marker("live_api") is not None
    live_enabled = _as_bool(os.getenv("RUN_LIVE_INTEGRATION_TESTS"))
    if is_live_test and live_enabled:
        return

    def guarded_request(self, method, url, *args, **kwargs):
        raise AssertionError(f"External HTTP blocked in non-live tests: {method.upper()} {url}")

    monkeypatch.setattr(requests.sessions.Session, "request", guarded_request)
