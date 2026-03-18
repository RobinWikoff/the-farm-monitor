import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


REPO_ROOT = Path(__file__).resolve().parents[1]


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_env_if_present() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env_if_present()


def _require_live_mode() -> str:
    if not _as_bool(os.getenv("RUN_LIVE_INTEGRATION_TESTS")):
        pytest.skip("Set RUN_LIVE_INTEGRATION_TESTS=true to run live integration tests.")
    api_key = os.getenv("VISUAL_CROSSING_API_KEY")
    if not api_key:
        pytest.skip("Set VISUAL_CROSSING_API_KEY via environment or .env to run live tests.")
    placeholder_values = {"your_key", "your_key_here", "changeme", "replace_me"}
    if api_key.strip().lower() in placeholder_values:
        pytest.skip("Set VISUAL_CROSSING_API_KEY to a real token before running live tests.")
    return api_key


@pytest.mark.integration
@pytest.mark.live_api
def test_live_forecast_and_current_shape(monkeypatch):
    api_key = _require_live_mode()

    original_get = app.requests.get
    call_count = {"count": 0}

    def counted_get(*args, **kwargs):
        call_count["count"] += 1
        if call_count["count"] > 1:
            raise AssertionError("Quota guard: forecast/current test exceeded one API call")
        return original_get(*args, **kwargs)

    monkeypatch.setattr(app.requests, "get", counted_get)

    forecast_df, live_temp = app.fetch_forecast_and_current.__wrapped__(api_key)

    assert call_count["count"] == 1
    assert not forecast_df.empty

    required_cols = {"Hour", "Actual", "FeelsLike", "WindSpeed", "WindDeg", "WindDir"}
    assert required_cols.issubset(set(forecast_df.columns))

    assert forecast_df["Hour"].between(0, 23).all()

    required_live_keys = {"Actual", "FeelsLike", "WindSpeed", "WindDeg", "WindDir"}
    assert required_live_keys.issubset(set(live_temp.keys()))
    assert live_temp["Actual"] is not None
    assert live_temp["FeelsLike"] is not None


@pytest.mark.integration
@pytest.mark.live_api
def test_live_historical_band_returns_24_hours(monkeypatch):
    api_key = _require_live_mode()

    original_get = app.requests.get
    call_count = {"count": 0}

    def counted_get(*args, **kwargs):
        call_count["count"] += 1
        if call_count["count"] > 1:
            raise AssertionError("Quota guard: historical test exceeded one API call")
        return original_get(*args, **kwargs)

    monkeypatch.setattr(app.requests, "get", counted_get)
    monkeypatch.setattr(app, "HISTORY_YEARS", 1)

    band = app.fetch_historical_band.__wrapped__("2025-01-15", api_key)

    assert call_count["count"] == 1
    assert not band.empty
    assert band["Hour"].nunique() == 24
    assert sorted(band["Hour"].tolist()) == list(range(24))


class _DummyContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyMetricColumn(_DummyContext):
    def metric(self, *args, **kwargs):
        return None


class _DummySidebar:
    def title(self, *args, **kwargs):
        return None

    def selectbox(self, label, options):
        return options[0]

    def radio(self, *args, **kwargs):
        return "Feels Like"


@pytest.mark.integration
def test_app_loads_without_error_in_dev_sample_mode(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("DEV_USE_SAMPLE_DATA", "true")

    monkeypatch.setattr(app.st, "secrets", {}, raising=False)
    monkeypatch.setattr(app.st, "session_state", {}, raising=False)
    monkeypatch.setattr(app.st, "sidebar", _DummySidebar(), raising=False)

    monkeypatch.setattr(app.st, "set_page_config", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "title", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "write", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "altair_chart", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.st, "spinner", lambda *args, **kwargs: _DummyContext())
    monkeypatch.setattr(app.st, "expander", lambda *args, **kwargs: _DummyContext())
    monkeypatch.setattr(app.st, "stop", lambda: (_ for _ in ()).throw(AssertionError("st.stop() should not be called")))

    def fake_columns(count):
        return tuple(_DummyMetricColumn() for _ in range(count))

    monkeypatch.setattr(app.st, "columns", fake_columns)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("requests.get should not be called in dev sample mode")

    monkeypatch.setattr(app.requests, "get", fail_if_called)

    app.run_app()
