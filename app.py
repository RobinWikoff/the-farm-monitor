import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from contextlib import nullcontext
import pytz
import logging
import math
import os
import json
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
LAT = "40.3720"
LON = "-105.0579"
LOCAL_TZ = pytz.timezone("US/Mountain")
HISTORY_YEARS = 5

THRESHOLDS = {"Winter (Warming Focus)": 65.0, "Summer (Cooling Focus)": 70.0}

VC_BASE = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"

DEV_API_BUDGET_DEFAULTS = {
    "visual_crossing_forecast": 12,
    "visual_crossing_historical": 3,
    "open_meteo_wind": 24,
}
DEV_API_LABELS = {
    "visual_crossing_forecast": "VC forecast/current",
    "visual_crossing_historical": "VC historical band",
    "open_meteo_wind": "Open-Meteo wind",
}
DEV_API_COOLDOWN_MINUTES_DEFAULT = 30

logger = logging.getLogger(__name__)


class DevAPIBlockedError(RuntimeError):
    """Raised when dev guardrails intentionally block a live API request."""


def _get_streamlit_secrets() -> Mapping[str, Any]:
    try:
        return st.secrets
    except Exception:
        return {}


def _get_dev_near_limit_pct(
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> float:
    """Return the fraction of budget remaining below which a near-limit warning is shown."""
    raw = _get_cfg_value("DEV_GUARDRAIL_NEAR_LIMIT_PCT", secrets or {}, environ or os.environ)
    if raw is None:
        return 0.20
    try:
        pct = float(raw)
        if 0.0 <= pct <= 1.0:
            return pct
        return pct / 100.0
    except (ValueError, TypeError):
        return 0.20


def _format_dev_guardrail_sidebar_line(item: Mapping[str, Any]) -> str:
    if item["remaining"] == 0:
        indicator = "🚫 "
    elif item.get("near_limit", False):
        indicator = "⚠️ "
    else:
        indicator = ""
    line = (
        f"{indicator}{item['label']}: {item['used']}/{item['limit']} used"
        f" ({item['remaining']} remaining), {item['blocked']} blocked"
    )
    if item["cooldown_active"] and item["cooldown_until"] is not None:
        line += f" | cooldown until {item['cooldown_until'].strftime('%H:%M')}"
    return line


def _format_dev_guardrail_fallback(kind: str, exc: Exception) -> str:
    if not isinstance(exc, DevAPIBlockedError):
        if kind == "forecast":
            return "⚠️ Weather API temporarily unavailable — showing last known data."
        if kind == "historical":
            return "⚠️ Historical band temporarily unavailable."
        if kind == "wind":
            return "⚠️ Wind live refresh temporarily unavailable — showing cached or forecast wind data."
        return "⚠️ Live weather data temporarily unavailable."

    reason = str(exc)
    if "budget exhausted" in reason:
        if kind == "forecast":
            return f"⚠️ Forecast live-call budget reached for this dev session — showing last known data. {reason}"
        if kind == "historical":
            return f"⚠️ Historical live-call budget reached for this dev session. {reason}"
        if kind == "wind":
            return f"⚠️ Wind live-call budget reached for this dev session — keeping cached or forecast wind data. {reason}"
    if "cooling down until" in reason:
        if kind == "forecast":
            return f"⚠️ Forecast API cooldown active after rate limiting — showing last known data. {reason}"
        if kind == "historical":
            return f"⚠️ Historical API cooldown active after rate limiting. {reason}"
        if kind == "wind":
            return f"⚠️ Wind API cooldown active after rate limiting — keeping cached or forecast wind data. {reason}"
    if kind == "forecast":
        return f"⚠️ Forecast live API blocked by dev guardrails — showing last known data. {reason}"
    if kind == "historical":
        return f"⚠️ Historical live API blocked by dev guardrails. {reason}"
    if kind == "wind":
        return f"⚠️ Wind live API blocked by dev guardrails — keeping cached or forecast wind data. {reason}"
    return f"⚠️ Live API blocked by dev guardrails. {reason}"


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def wind_degree_to_cardinal(degrees: float | None) -> str:
    if degrees is None:
        return "Unknown"
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int(((degrees + 22.5) % 360) / 45)
    return dirs[idx]


def _get_vc_api_key() -> str:
    """Return Visual Crossing API key from Streamlit secrets or environment."""
    env_key = os.getenv("VISUAL_CROSSING_API_KEY")
    if env_key:
        return env_key
    secrets = _get_streamlit_secrets()
    try:
        return secrets["VISUAL_CROSSING_API_KEY"]
    except KeyError:
        st.error(
            "⚠️ VISUAL_CROSSING_API_KEY not found in Streamlit secrets. Add it to `.streamlit/secrets.toml`."
        )
        st.stop()


def _build_dev_sample_payload(
    now_mtn: datetime,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Create deterministic sample weather payload for local dev without external API calls."""
    rows = []
    hist_rows = []

    for h in range(24):
        base = 54.0 + 10.0 * math.sin((h - 6) * math.pi / 12.0)
        feels = base - 1.5 + 1.2 * math.sin(h * math.pi / 6.0)
        wind_speed = max(0.0, 9.0 + 4.0 * math.sin((h + 2) * math.pi / 12.0))
        wind_gust = max(wind_speed, wind_speed + 4.0 * math.sin((h + 4) * math.pi / 10.0))
        precip = max(0.0, 0.08 * math.sin((h - 3) * math.pi / 8.0))
        precip_prob = max(0.0, min(100.0, 55.0 + 35.0 * math.sin((h - 2) * math.pi / 8.0)))
        humidity = max(10.0, min(100.0, 62.0 + 22.0 * math.sin((h + 1) * math.pi / 10.0)))
        snow = precip if base <= 32.0 else 0.0
        wind_deg = (h * 15) % 360

        rows.append(
            {
                "Hour": h,
                "Actual": round(base, 1),
                "FeelsLike": round(feels, 1),
                "WindSpeed": round(wind_speed, 1),
                "WindGust": round(wind_gust, 1),
                "WindDeg": round(wind_deg, 1),
                "WindDir": wind_degree_to_cardinal(wind_deg),
                "PrecipIn": round(precip, 2),
                "PrecipProb": round(precip_prob, 1),
                "Humidity": round(humidity, 1),
                "SnowIn": round(snow, 2),
            }
        )

        hist_rows.append(
            {
                "Hour": h,
                "ActualHigh": round(base + 6.5, 1),
                "ActualLow": round(base - 6.0, 1),
                "ActualMean": round(base + 0.3, 1),
                "FeelsLikeHigh": round(feels + 6.0, 1),
                "FeelsLikeLow": round(feels - 6.2, 1),
                "FeelsLikeMean": round(feels + 0.2, 1),
                "WindSpeedHigh": round(wind_speed + 3.5, 1),
                "WindSpeedLow": round(max(0.0, wind_speed - 3.0), 1),
                "WindSpeedMean": round(wind_speed + 0.4, 1),
            }
        )

    df = pd.DataFrame(rows)
    hist_band = pd.DataFrame(hist_rows)

    current_hour = now_mtn.hour
    live_row = df[df["Hour"] == current_hour].iloc[0]
    live_temp = {
        "Actual": float(live_row["Actual"]),
        "FeelsLike": float(live_row["FeelsLike"]),
        "WindSpeed": float(live_row["WindSpeed"]),
        "WindGust": float(live_row["WindGust"]),
        "WindDeg": float(live_row["WindDeg"]),
        "WindDir": str(live_row["WindDir"]),
        "PrecipIn": float(live_row["PrecipIn"]),
        "PrecipProb": float(live_row["PrecipProb"]),
        "Humidity": float(live_row["Humidity"]),
        "SnowIn": float(live_row["SnowIn"]),
    }

    return df, live_temp, hist_band


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _get_cfg_value(name: str, secrets: Mapping[str, Any], environ: Mapping[str, str]) -> Any:
    if name in environ and environ[name] != "":
        return environ[name]
    try:
        return secrets[name]
    except Exception:
        return None


def resolve_runtime_config(
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve deterministic app runtime mode and API-call policy."""
    if secrets is None:
        secrets = {}
    if environ is None:
        environ = os.environ

    env_raw = _get_cfg_value("ENV", secrets, environ)
    env_name = str(env_raw if env_raw is not None else "prod").strip().lower()
    env_is_known = env_name in {"dev", "prod"}
    is_dev = env_name == "dev"
    is_ci = _as_bool(_get_cfg_value("CI", secrets, environ), default=False) or _as_bool(
        _get_cfg_value("GITHUB_ACTIONS", secrets, environ), default=False
    )
    run_live_tests = _as_bool(_get_cfg_value("RUN_LIVE_INTEGRATION_TESTS", secrets, environ))

    requested_sample_raw = _get_cfg_value("DEV_USE_SAMPLE_DATA", secrets, environ)
    requested_sample_default = True if is_dev else False
    dev_use_sample_requested = _as_bool(requested_sample_raw, default=requested_sample_default)
    dev_use_sample_explicit = requested_sample_raw is not None

    allow_live_raw = _get_cfg_value("DEV_ALLOW_LIVE_API", secrets, environ)
    dev_allow_live_api = _as_bool(allow_live_raw, default=False)
    dev_allow_live_api_explicit = allow_live_raw is not None

    if is_ci and run_live_tests:
        effective_data_mode = "live"
        live_api_enabled = True
        policy_reason = "CI live mode enabled by explicit RUN_LIVE_INTEGRATION_TESTS opt-in."
        profile = "ci-live-manual"
    elif is_ci:
        effective_data_mode = "sample"
        live_api_enabled = False
        policy_reason = "CI non-live mode disables live APIs by default."
        profile = "ci-non-live"
    elif is_dev and not dev_allow_live_api:
        effective_data_mode = "sample"
        live_api_enabled = False
        policy_reason = "DEV_ALLOW_LIVE_API is false; forcing sample mode in dev."
        profile = "dev-safe"
    elif is_dev and dev_allow_live_api:
        effective_data_mode = "sample" if dev_use_sample_requested else "live"
        live_api_enabled = not dev_use_sample_requested
        policy_reason = (
            "Live API enabled in dev by explicit opt-in."
            if live_api_enabled
            else "Using sample mode in dev by explicit setting."
        )
        profile = "dev-live"
    else:
        effective_data_mode = "live"
        live_api_enabled = True
        policy_reason = "Production mode uses live APIs."
        profile = "prod"

    return {
        "env": env_name,
        "env_is_known": env_is_known,
        "is_dev": is_dev,
        "is_ci": is_ci,
        "profile": profile,
        "dev_allow_live_api": dev_allow_live_api,
        "dev_allow_live_api_explicit": dev_allow_live_api_explicit,
        "dev_use_sample_requested": dev_use_sample_requested,
        "dev_use_sample_explicit": dev_use_sample_explicit,
        "run_live_tests_requested": run_live_tests,
        "effective_data_mode": effective_data_mode,
        "live_api_enabled": live_api_enabled,
        "policy_reason": policy_reason,
    }


def inspect_runtime_config(runtime: Mapping[str, Any]) -> dict[str, list[str]]:
    issues: list[str] = []
    warnings: list[str] = []
    env_name = runtime.get("env")
    env_is_known = bool(runtime.get("env_is_known", env_name in {"dev", "prod"}))
    is_dev = bool(runtime.get("is_dev"))
    is_ci = bool(runtime.get("is_ci"))
    profile = runtime.get("profile")
    effective_data_mode = runtime.get("effective_data_mode")
    live_api_enabled = runtime.get("live_api_enabled")
    dev_allow_live_api = bool(runtime.get("dev_allow_live_api"))
    dev_allow_live_api_explicit = bool(runtime.get("dev_allow_live_api_explicit"))
    dev_use_sample_requested = bool(runtime.get("dev_use_sample_requested"))
    dev_use_sample_explicit = bool(runtime.get("dev_use_sample_explicit"))
    run_live_tests_requested = bool(runtime.get("run_live_tests_requested"))

    expected_profiles = {
        "dev-safe",
        "dev-live",
        "ci-non-live",
        "ci-live-manual",
        "prod",
    }
    if profile not in expected_profiles:
        issues.append(f"Unknown runtime profile: {profile}")
    if not env_is_known:
        issues.append(f"Unsupported ENV value: {env_name}")

    if profile == "ci-non-live":
        if live_api_enabled:
            issues.append("ci-non-live must not enable live APIs.")
        if effective_data_mode != "sample":
            issues.append("ci-non-live must use sample mode.")
        if dev_allow_live_api:
            issues.append(
                "CI non-live mode cannot set DEV_ALLOW_LIVE_API=true without RUN_LIVE_INTEGRATION_TESTS=true."
            )
    elif profile == "ci-live-manual":
        if not live_api_enabled:
            issues.append("ci-live-manual must enable live APIs.")
        if effective_data_mode != "live":
            issues.append("ci-live-manual must use live mode.")
        if not run_live_tests_requested:
            issues.append("ci-live-manual requires RUN_LIVE_INTEGRATION_TESTS=true.")
        if not dev_allow_live_api:
            issues.append("ci-live-manual requires DEV_ALLOW_LIVE_API=true.")
    elif profile == "dev-safe":
        if live_api_enabled or effective_data_mode != "sample":
            issues.append("dev-safe must disable live APIs and use sample mode.")
    elif profile == "prod":
        if not live_api_enabled or effective_data_mode != "live":
            issues.append("prod must enable live APIs and use live mode.")

    if is_ci and run_live_tests_requested and dev_use_sample_requested:
        warnings.append("DEV_USE_SAMPLE_DATA is ignored in ci-live-manual mode.")
    if not is_ci and not is_dev and (dev_allow_live_api_explicit or dev_use_sample_explicit):
        warnings.append("DEV_* flags are ignored outside dev and CI profiles.")

    return {"errors": issues, "warnings": warnings}


def validate_runtime_config(runtime: Mapping[str, Any]) -> list[str]:
    return inspect_runtime_config(runtime)["errors"]


def get_runtime_config_warnings(runtime: Mapping[str, Any]) -> list[str]:
    return inspect_runtime_config(runtime)["warnings"]


def _dev_guardrail_state_path() -> str:
    cache_dir = os.path.join(".streamlit", "guardrails")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "dev_api_state.json")


def _fresh_dev_guardrail_state(date_str: str) -> dict[str, Any]:
    return {
        "date": date_str,
        "usage": {},
        "blocked": {},
        "cooldowns": {},
    }


def _load_dev_guardrail_state(date_str: str) -> dict[str, Any]:
    path = _dev_guardrail_state_path()
    if not os.path.exists(path):
        return _fresh_dev_guardrail_state(date_str)
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _fresh_dev_guardrail_state(date_str)
    if state.get("date") != date_str:
        return _fresh_dev_guardrail_state(date_str)
    state.setdefault("usage", {})
    state.setdefault("blocked", {})
    state.setdefault("cooldowns", {})
    return state


def _save_dev_guardrail_state(state: Mapping[str, Any]) -> None:
    path = _dev_guardrail_state_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def reset_dev_guardrail_usage_and_blocked(
    now: datetime | None = None,
) -> dict[str, Any]:
    """Reset usage and blocked counters for today's guardrail state."""
    current = _guardrail_now(now)
    date_str = current.strftime("%Y-%m-%d")
    state = _load_dev_guardrail_state(date_str)
    state["usage"] = {}
    state["blocked"] = {}
    _save_dev_guardrail_state(state)
    return state


def clear_dev_guardrail_cooldowns(
    now: datetime | None = None,
) -> dict[str, Any]:
    """Clear cooldown entries for today's guardrail state."""
    current = _guardrail_now(now)
    date_str = current.strftime("%Y-%m-%d")
    state = _load_dev_guardrail_state(date_str)
    state["cooldowns"] = {}
    _save_dev_guardrail_state(state)
    return state


def get_dev_guardrail_raw_state(now: datetime | None = None) -> dict[str, Any]:
    """Return today's persisted guardrail state for debugging."""
    current = _guardrail_now(now)
    date_str = current.strftime("%Y-%m-%d")
    return _load_dev_guardrail_state(date_str)


def _get_dev_budget_limits(
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, int]:
    if secrets is None:
        secrets = {}
    if environ is None:
        environ = os.environ
    limits = DEV_API_BUDGET_DEFAULTS.copy()
    env_map = {
        "visual_crossing_forecast": "DEV_BUDGET_VC_FORECAST",
        "visual_crossing_historical": "DEV_BUDGET_VC_HISTORICAL",
        "open_meteo_wind": "DEV_BUDGET_OPEN_METEO_WIND",
    }
    for key, env_name in env_map.items():
        raw = _get_cfg_value(env_name, secrets, environ)
        if raw is None:
            continue
        try:
            limits[key] = max(0, int(raw))
        except (TypeError, ValueError):
            continue
    return limits


def _get_dev_cooldown_minutes(
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    if secrets is None:
        secrets = {}
    if environ is None:
        environ = os.environ
    raw = _get_cfg_value("DEV_API_COOLDOWN_MINUTES", secrets, environ)
    try:
        return max(1, int(raw)) if raw is not None else DEV_API_COOLDOWN_MINUTES_DEFAULT
    except (TypeError, ValueError):
        return DEV_API_COOLDOWN_MINUTES_DEFAULT


def _guardrail_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(LOCAL_TZ)
    if now.tzinfo is None:
        return LOCAL_TZ.localize(now)
    return now.astimezone(LOCAL_TZ)


def check_and_record_dev_api_request(
    key: str,
    *,
    runtime: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> tuple[bool, str | None]:
    if runtime is None:
        runtime = resolve_runtime_config(secrets, environ)
    if not runtime.get("is_dev") or not runtime.get("live_api_enabled"):
        return True, None

    current = _guardrail_now(now)
    date_str = current.strftime("%Y-%m-%d")
    state = _load_dev_guardrail_state(date_str)
    limits = _get_dev_budget_limits(secrets, environ)

    cooldown_until_str = state["cooldowns"].get(key)
    if cooldown_until_str:
        try:
            cooldown_until = datetime.fromisoformat(cooldown_until_str)
        except ValueError:
            cooldown_until = None
        if cooldown_until is not None:
            if cooldown_until.tzinfo is None:
                cooldown_until = LOCAL_TZ.localize(cooldown_until)
            else:
                cooldown_until = cooldown_until.astimezone(LOCAL_TZ)
            if current < cooldown_until:
                state["blocked"][key] = int(state["blocked"].get(key, 0)) + 1
                _save_dev_guardrail_state(state)
                return (
                    False,
                    f"{DEV_API_LABELS.get(key, key)} cooling down until {cooldown_until.strftime('%H:%M')}.",
                )

    used = int(state["usage"].get(key, 0))
    limit = int(limits.get(key, 0))
    if used >= limit:
        state["blocked"][key] = int(state["blocked"].get(key, 0)) + 1
        _save_dev_guardrail_state(state)
        return False, f"{DEV_API_LABELS.get(key, key)} dev budget exhausted ({used}/{limit})."

    state["usage"][key] = used + 1
    _save_dev_guardrail_state(state)
    return True, None


def record_dev_api_cooldown(
    key: str,
    *,
    runtime: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    minutes: int | None = None,
) -> datetime | None:
    if runtime is None:
        runtime = resolve_runtime_config(secrets, environ)
    if not runtime.get("is_dev") or not runtime.get("live_api_enabled"):
        return None

    current = _guardrail_now(now)
    date_str = current.strftime("%Y-%m-%d")
    state = _load_dev_guardrail_state(date_str)
    cooldown_minutes = minutes or _get_dev_cooldown_minutes(secrets, environ)
    until = current + timedelta(minutes=cooldown_minutes)
    state["cooldowns"][key] = until.isoformat()
    _save_dev_guardrail_state(state)
    return until


def get_dev_guardrail_snapshot(
    *,
    runtime: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if runtime is None:
        runtime = resolve_runtime_config(secrets, environ)
    current = _guardrail_now(now)
    date_str = current.strftime("%Y-%m-%d")
    state = _load_dev_guardrail_state(date_str)
    limits = _get_dev_budget_limits(secrets, environ)
    near_limit_pct = _get_dev_near_limit_pct(secrets, environ)

    items = []
    for key, limit in limits.items():
        cooldown_until = None
        cooldown_str = state["cooldowns"].get(key)
        if cooldown_str:
            try:
                cooldown_until = datetime.fromisoformat(cooldown_str)
            except ValueError:
                cooldown_until = None
            if cooldown_until is not None:
                if cooldown_until.tzinfo is None:
                    cooldown_until = LOCAL_TZ.localize(cooldown_until)
                else:
                    cooldown_until = cooldown_until.astimezone(LOCAL_TZ)

        used = int(state["usage"].get(key, 0))
        remaining = max(0, int(limit) - used)
        near_limit = remaining > 0 and (remaining / int(limit)) <= near_limit_pct
        items.append(
            {
                "key": key,
                "label": DEV_API_LABELS.get(key, key),
                "used": used,
                "limit": int(limit),
                "remaining": remaining,
                "near_limit": near_limit,
                "blocked": int(state["blocked"].get(key, 0)),
                "cooldown_until": cooldown_until,
                "cooldown_active": cooldown_until is not None and current < cooldown_until,
            }
        )

    return {
        "enabled": bool(runtime.get("is_dev") and runtime.get("live_api_enabled")),
        "date": date_str,
        "cooldown_minutes": _get_dev_cooldown_minutes(secrets, environ),
        "items": items,
    }


def guarded_requests_get(
    url: str,
    *,
    params: Mapping[str, Any],
    timeout: int,
    guardrail_key: str,
) -> requests.Response:
    secrets = _get_streamlit_secrets()
    runtime = resolve_runtime_config(secrets, os.environ)
    allowed, reason = check_and_record_dev_api_request(
        guardrail_key,
        runtime=runtime,
        secrets=secrets,
        environ=os.environ,
    )
    if not allowed:
        raise DevAPIBlockedError(reason or f"{guardrail_key} blocked by dev guardrails.")

    try:
        resp = requests.get(url, params=params, timeout=timeout)
        if getattr(resp, "status_code", None) == 429:
            record_dev_api_cooldown(
                guardrail_key,
                runtime=runtime,
                secrets=secrets,
                environ=os.environ,
            )
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        status_code = getattr(getattr(e, "response", None), "status_code", None)
        if status_code == 429:
            record_dev_api_cooldown(
                guardrail_key,
                runtime=runtime,
                secrets=secrets,
                environ=os.environ,
            )
        raise


def _hist_cache_path(date_str: str) -> str:
    cache_dir = os.path.join(".streamlit", "hist_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"hist_{date_str}.csv")


def _load_hist_band_from_disk(date_str: str) -> pd.DataFrame:
    path = _hist_cache_path(date_str)
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        hist = pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError):
        return pd.DataFrame()

    required = {
        "Hour",
        "ActualHigh",
        "ActualLow",
        "ActualMean",
        "FeelsLikeHigh",
        "FeelsLikeLow",
        "FeelsLikeMean",
        "WindSpeedHigh",
        "WindSpeedLow",
        "WindSpeedMean",
    }
    if not required.issubset(set(hist.columns)):
        return pd.DataFrame()
    return hist


def _save_hist_band_to_disk(date_str: str, hist_band: pd.DataFrame) -> None:
    if hist_band is None or hist_band.empty:
        return
    path = _hist_cache_path(date_str)
    hist_band.to_csv(path, index=False)


@st.cache_data(ttl=600)
def fetch_forecast_and_current(vc_api_key: str) -> tuple[pd.DataFrame, dict]:
    """
    Fetch today's hourly forecast AND current conditions from
    Visual Crossing Timeline API in a single call.
    Returns (forecast_df, live_temp) where forecast_df has columns: Hour (int), Actual (float), FeelsLike (float).
    """
    location = f"{LAT},{LON}"
    url = f"{VC_BASE}/{location}/today"
    params = {
        "unitGroup": "us",
        "include": "hours,current",
        "elements": "datetime,temp,feelslike,windspeed,windgust,wdir,precip,precipprob,humidity,snow",
        "key": vc_api_key,
        "contentType": "json",
        "timezone": "America/Denver",
    }
    resp = guarded_requests_get(
        url,
        params=params,
        timeout=15,
        guardrail_key="visual_crossing_forecast",
    )
    resp.raise_for_status()
    data = resp.json()

    # Hourly forecast
    rows = []
    for day in data.get("days", []):
        for hour in day.get("hours", []):
            actual = hour.get("temp")
            feelslike = hour.get("feelslike")
            windspeed = hour.get("windspeed")
            windgust = hour.get("windgust")
            winddeg = hour.get("wdir")
            precip = hour.get("precip")
            precipprob = hour.get("precipprob")
            humidity = hour.get("humidity")
            snow = hour.get("snow")
            dt_str = hour.get("datetime", "")  # "HH:mm:ss"
            if dt_str and actual is not None and feelslike is not None:
                hour_int = int(dt_str.split(":")[0])
                rows.append(
                    {
                        "Hour": hour_int,
                        "Actual": round(actual, 1),
                        "FeelsLike": round(feelslike, 1),
                        "WindSpeed": round(windspeed, 1) if windspeed is not None else None,
                        "WindGust": round(windgust, 1) if windgust is not None else None,
                        "WindDeg": round(winddeg, 1) if winddeg is not None else None,
                        "WindDir": wind_degree_to_cardinal(winddeg),
                        "PrecipIn": round(precip, 2) if precip is not None else None,
                        "PrecipProb": round(precipprob, 1) if precipprob is not None else None,
                        "Humidity": round(humidity, 1) if humidity is not None else None,
                        "SnowIn": round(snow, 2) if snow is not None else None,
                    }
                )
    forecast_df = pd.DataFrame(rows)

    # Current conditions
    current = data.get("currentConditions", {})
    live_actual = current.get("temp")
    live_feelslike = current.get("feelslike")
    live_windspeed = current.get("windspeed")
    live_windgust = current.get("windgust")
    live_winddeg = current.get("wdir")
    live_precip = current.get("precip")
    live_precipprob = current.get("precipprob")
    live_humidity = current.get("humidity")
    live_snow = current.get("snow")
    if live_actual is None and not forecast_df.empty:
        live_actual = forecast_df.iloc[-1]["Actual"]
    if live_feelslike is None and not forecast_df.empty:
        live_feelslike = forecast_df.iloc[-1]["FeelsLike"]
    if live_windspeed is None and not forecast_df.empty:
        live_windspeed = forecast_df.iloc[-1]["WindSpeed"]
    if live_windgust is None and not forecast_df.empty and "WindGust" in forecast_df.columns:
        live_windgust = forecast_df.iloc[-1]["WindGust"]
    if live_winddeg is None and not forecast_df.empty:
        live_winddeg = forecast_df.iloc[-1]["WindDeg"]
    if live_precip is None and not forecast_df.empty:
        live_precip = forecast_df.iloc[-1]["PrecipIn"]
    if live_precipprob is None and not forecast_df.empty:
        live_precipprob = forecast_df.iloc[-1]["PrecipProb"]
    if live_humidity is None and not forecast_df.empty:
        live_humidity = forecast_df.iloc[-1]["Humidity"]
    if live_snow is None and not forecast_df.empty:
        live_snow = forecast_df.iloc[-1]["SnowIn"]

    live_temp = {
        "Actual": round(live_actual, 1) if live_actual is not None else None,
        "FeelsLike": round(live_feelslike, 1) if live_feelslike is not None else None,
        "WindSpeed": round(live_windspeed, 1) if live_windspeed is not None else None,
        "WindGust": round(live_windgust, 1) if live_windgust is not None else None,
        "WindDeg": round(live_winddeg, 1) if live_winddeg is not None else None,
        "WindDir": wind_degree_to_cardinal(live_winddeg) if live_winddeg is not None else "Unknown",
        "PrecipIn": round(live_precip, 2) if live_precip is not None else None,
        "PrecipProb": round(live_precipprob, 1) if live_precipprob is not None else None,
        "Humidity": round(live_humidity, 1) if live_humidity is not None else None,
        "SnowIn": round(live_snow, 2) if live_snow is not None else None,
    }

    return forecast_df, live_temp


@st.cache_data(ttl=604800)  # 7-day TTL — historical data barely changes
def fetch_historical_band(today_str: str, vc_api_key: str) -> pd.DataFrame:
    """
    Fetch the same calendar day (month/day) across the past HISTORY_YEARS years
    using the Visual Crossing Timeline API — one request per year.
    today_str format: YYYY-MM-DD — string keeps cache key stable all day.
    Returns a DataFrame with columns: Hour (int), HistHigh (float), HistLow (float), HistMean (float)
    """
    today = datetime.strptime(today_str, "%Y-%m-%d")
    all_rows = []

    for years_back in range(1, HISTORY_YEARS + 1):
        try:
            past_date = today.replace(year=today.year - years_back)
        except ValueError:
            past_date = today.replace(month=2, day=28, year=today.year - years_back)
        date_str = past_date.strftime("%Y-%m-%d")
        location = f"{LAT},{LON}"
        url = f"{VC_BASE}/{location}/{date_str}/{date_str}"
        params = {
            "unitGroup": "us",
            "include": "hours",
            "elements": "datetime,temp,feelslike,windspeed",
            "key": vc_api_key,
            "contentType": "json",
        }
        try:
            resp = guarded_requests_get(
                url,
                params=params,
                timeout=15,
                guardrail_key="visual_crossing_historical",
            )
            resp.raise_for_status()
            data = resp.json()
            for day in data.get("days", []):
                for hour in day.get("hours", []):
                    actual = hour.get("temp")
                    feelslike = hour.get("feelslike")
                    windspeed = hour.get("windspeed")
                    dt_str = hour.get("datetime", "")  # format: "HH:mm:ss"
                    if (
                        actual is not None
                        and feelslike is not None
                        and windspeed is not None
                        and dt_str
                    ):
                        hour_int = int(dt_str.split(":")[0])
                        all_rows.append(
                            {
                                "Hour": hour_int,
                                "Actual": actual,
                                "FeelsLike": feelslike,
                                "WindSpeed": windspeed,
                            }
                        )
        except (requests.RequestException, DevAPIBlockedError) as e:
            if isinstance(e, DevAPIBlockedError):
                logger.warning("Historical fetch blocked by dev guardrails on %s: %s", date_str, e)
                break
            status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code == 429:
                logger.warning(
                    "Historical fetch rate-limited on %s; stopping further yearly requests.",
                    date_str,
                )
                break
            logger.warning("Historical fetch failed for %s: %s", date_str, e)
            continue

    if not all_rows:
        return pd.DataFrame(
            columns=[
                "Hour",
                "ActualHigh",
                "ActualLow",
                "ActualMean",
                "FeelsLikeHigh",
                "FeelsLikeLow",
                "FeelsLikeMean",
            ]
        )

    hist_df = pd.DataFrame(all_rows)
    band = (
        hist_df.groupby("Hour")
        .agg(
            ActualHigh=("Actual", "max"),
            ActualLow=("Actual", "min"),
            ActualMean=("Actual", "mean"),
            FeelsLikeHigh=("FeelsLike", "max"),
            FeelsLikeLow=("FeelsLike", "min"),
            FeelsLikeMean=("FeelsLike", "mean"),
            WindSpeedHigh=("WindSpeed", "max"),
            WindSpeedLow=("WindSpeed", "min"),
            WindSpeedMean=("WindSpeed", "mean"),
        )
        .reset_index()
    )

    for c in [
        "ActualHigh",
        "ActualLow",
        "ActualMean",
        "FeelsLikeHigh",
        "FeelsLikeLow",
        "FeelsLikeMean",
        "WindSpeedHigh",
        "WindSpeedLow",
        "WindSpeedMean",
    ]:
        band[c] = band[c].round(1)

    return band


@st.cache_data(ttl=600)
def fetch_wind_openmeteo() -> tuple[pd.DataFrame, dict]:
    """Fetch hourly + current wind data from Open-Meteo and map to app wind schema."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": "windspeed_10m,winddirection_10m,windgusts_10m",
        "current": "windspeed_10m,winddirection_10m,windgusts_10m",
        "wind_speed_unit": "mph",
        "timezone": "America/Denver",
        "forecast_days": 1,
    }

    resp = guarded_requests_get(
        url,
        params=params,
        timeout=15,
        guardrail_key="open_meteo_wind",
    )
    resp.raise_for_status()
    data = resp.json()

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    speeds = hourly.get("windspeed_10m", [])
    dirs = hourly.get("winddirection_10m", [])
    gusts = hourly.get("windgusts_10m", [])

    rows = []
    for ts, speed, deg, gust in zip(times, speeds, dirs, gusts):
        try:
            hour_int = int(str(ts).split("T")[1].split(":")[0])
        except (IndexError, ValueError, AttributeError):
            continue

        rows.append(
            {
                "Hour": hour_int,
                "WindSpeed": round(speed, 1) if speed is not None else None,
                "WindGust": round(gust, 1) if gust is not None else None,
                "WindDeg": round(deg, 1) if deg is not None else None,
                "WindDir": wind_degree_to_cardinal(deg),
            }
        )

    wind_df = pd.DataFrame(rows)

    current = data.get("current", {})
    cur_speed = current.get("windspeed_10m")
    cur_deg = current.get("winddirection_10m")
    cur_gust = current.get("windgusts_10m")
    wind_current = {
        "WindSpeed": round(cur_speed, 1) if cur_speed is not None else None,
        "WindGust": round(cur_gust, 1) if cur_gust is not None else None,
        "WindDeg": round(cur_deg, 1) if cur_deg is not None else None,
        "WindDir": wind_degree_to_cardinal(cur_deg),
    }

    return wind_df, wind_current


def get_temp_trend(
    df: pd.DataFrame, live_temp: float, current_hour: int
) -> tuple[float | None, str | None]:
    """
    Compute the 1-hour temperature delta for the trend indicator.
    Compares live_temp at current_hour against the forecast value at current_hour - 1.
    Returns (delta, since_label) or (None, None) if prior hour data is unavailable.
    """
    if current_hour == 0:
        return None, None
    prior_hour = current_hour - 1
    prior_rows = df[df["Hour"] == prior_hour]
    if prior_rows.empty:
        return None, None
    prior_temp = prior_rows.iloc[0]["Temperature"]
    delta = round(live_temp - prior_temp, 1)
    since_label = f"since {prior_hour:02d}:00"
    return delta, since_label


def get_wind_trend(
    df: pd.DataFrame, live_wind_speed: float, current_hour: int
) -> tuple[float | None, str | None]:
    """Compute 1-hour wind-speed delta for the wind metric trend indicator."""
    if current_hour == 0:
        return None, None
    prior_hour = current_hour - 1
    prior_rows = df[df["Hour"] == prior_hour]
    if prior_rows.empty:
        return None, None
    prior_speed = prior_rows.iloc[0]["WindSpeed"]
    if prior_speed is None:
        return None, None
    delta = round(live_wind_speed - prior_speed, 1)
    since_label = f"since {prior_hour:02d}:00"
    return delta, since_label


def build_chart(
    df: pd.DataFrame,
    live_temp: float,
    threshold: float,
    current_hour: int,
    hist_band: pd.DataFrame,
) -> alt.LayerChart:
    """Assemble the Altair line chart with actual/forecast/target layers plus historical band."""
    plot = df.copy()
    plot.loc[plot["Hour"] == current_hour, "Temperature"] = live_temp

    plot["Status"] = (
        plot["Hour"].apply(lambda h: "Actual" if h <= current_hour else "Forecast").astype(object)
    )

    bridge = plot[plot["Hour"] == current_hour].copy().assign(Status="Forecast")

    target = pd.DataFrame(
        {
            "Hour": range(24),
            "Temperature": [threshold] * 24,
            "Status": ["Target"] * 24,
        }
    )

    full = pd.concat([plot, bridge, target], ignore_index=True)

    x = alt.X(
        "Hour:Q",
        axis=alt.Axis(
            labelFontSize=11,
            titleFontSize=14,
            labelExpr="datum.value + ':00'",
            values=list(range(24)),
            labelAngle=-45,
        ),
    )
    y = alt.Y(
        "Temperature:Q",
        scale=alt.Scale(zero=False, padding=40),
        axis=alt.Axis(labelFontSize=13, titleFontSize=14, labelExpr="datum.value + '°F'"),
    )

    color_scale = alt.Scale(
        domain=["Actual", "Forecast", "Target", "Hist Avg (5yr)"],
        range=["#00f2ff", "#ffffff", "#32CD32", "#a0c4ff"],
    )
    dash_scale = alt.Scale(
        domain=["Actual", "Forecast", "Target", "Hist Avg (5yr)"],
        range=[[0], [5, 5], [8, 4], [3, 3]],
    )

    lines = (
        alt.Chart(full)
        .mark_line(strokeWidth=4)
        .encode(
            x=x,
            y=y,
            color=alt.Color(
                "Status:N",
                scale=color_scale,
                legend=alt.Legend(
                    orient="bottom",
                    labelFontSize=12,
                    title=None,
                    columns=2,
                    columnPadding=20,
                    rowPadding=6,
                ),
            ),
            strokeDash=alt.StrokeDash("Status:N", scale=dash_scale, legend=None),
        )
    )

    dot = (
        alt.Chart(plot[plot["Hour"] == current_hour])
        .mark_circle(size=450, color="#00f2ff")
        .encode(x=x, y=y)
    )

    actuals = plot[plot["Status"] == "Actual"]
    hi = actuals["Temperature"].max()
    lo = actuals["Temperature"].min()
    first_hi_h = actuals.loc[actuals["Temperature"] == hi, "Hour"].iloc[0]
    first_lo_h = actuals.loc[actuals["Temperature"] == lo, "Hour"].iloc[0]

    def label_cfg(row):
        if row["Hour"] == current_hour:
            return ("Top", f"{row['Temperature']}°F")
        if row["Hour"] == first_hi_h:
            return ("Top", f"{row['Temperature']}°F")
        if row["Hour"] == first_lo_h:
            return ("Bottom", f"{row['Temperature']}°F")
        return ("None", "")

    plot[["Lab_Pos", "Lab_Txt"]] = plot.apply(lambda r: pd.Series(label_cfg(r)), axis=1)

    lbl_top = (
        alt.Chart(plot[plot["Lab_Pos"] == "Top"])
        .mark_text(dy=-22, fontSize=13, fontWeight="bold", color="white")
        .encode(x=x, y=y, text="Lab_Txt")
    )
    lbl_bot = (
        alt.Chart(plot[plot["Lab_Pos"] == "Bottom"])
        .mark_text(dy=22, fontSize=13, fontWeight="bold", color="white", baseline="top")
        .encode(x=x, y=y, text="Lab_Txt")
    )

    if not hist_band.empty:
        hist_area = (
            alt.Chart(hist_band)
            .mark_area(opacity=0.18, color="#a0c4ff")
            .encode(
                x=alt.X("Hour:Q"),
                y=alt.Y("HistLow:Q", title=""),
                y2=alt.Y2("HistHigh:Q"),
                tooltip=[
                    alt.Tooltip("Hour:Q", title="Hour"),
                    alt.Tooltip("HistHigh:Q", title="Hist High °F"),
                    alt.Tooltip("HistLow:Q", title="Hist Low °F"),
                    alt.Tooltip("HistMean:Q", title="Hist Mean °F"),
                ],
            )
        )
        hist_mean = (
            alt.Chart(hist_band.assign(Status="Hist Avg (5yr)"))
            .mark_line(strokeWidth=2, opacity=0.65)
            .encode(
                x=alt.X("Hour:Q"),
                y=alt.Y("HistMean:Q"),
                color=alt.Color(
                    "Status:N",
                    scale=color_scale,
                    legend=alt.Legend(
                        orient="bottom",
                        labelFontSize=12,
                        title=None,
                        columns=2,
                        columnPadding=20,
                        rowPadding=6,
                    ),
                ),
                strokeDash=alt.StrokeDash(
                    "Status:N",
                    scale=dash_scale,
                    legend=None,
                ),
            )
        )
        chart = hist_area + hist_mean + lines + dot + lbl_top + lbl_bot
    else:
        chart = lines + dot + lbl_top + lbl_bot

    return chart.properties(height=500).configure_legend(fillColor="#1e1e1e", padding=10)


def render_status_banner(
    live_temp: float, threshold: float, forecast_future: pd.DataFrame, mode: str
) -> None:
    """Show contextual warming/cooling status banner."""
    is_winter = "Winter" in mode
    delta = round(live_temp - threshold, 1)

    if is_winter:
        if live_temp >= threshold:
            st.success(
                f"It's warm outside; maybe wear shorts! {live_temp}°F (threshold {threshold}°F). -- Cool Months"
            )
        else:
            hits = forecast_future[forecast_future["Temperature"] >= threshold]
            if not hits.empty:
                forecast_hour = int(hits.iloc[0]["Hour"])
                st.info(
                    f"It's cool now and will be warm later: {live_temp}°F, warming to {threshold}°F by {forecast_hour:02d}:00. Delta {delta:+.1f}°F. -- Cool Months"
                )
            else:
                st.warning(
                    f"It's cool now and won't be warm later: {live_temp}°F is below {threshold}°F. -- Cool Months"
                )
    else:
        if live_temp <= threshold:
            st.success(
                f"It's cool outside! Windows Open: {live_temp}°F (threshold {threshold}°F). Cooling target met. -- Warm Months"
            )
        else:
            hits = forecast_future[forecast_future["Temperature"] <= threshold]
            if not hits.empty:
                forecast_hour = int(hits.iloc[0]["Hour"])
                st.info(
                    f"Its' warm out and will be cool later: {live_temp}°F, cooling to {threshold}°F by {forecast_hour:02d}:00. Delta {delta:+.1f}°F. -- Warm Months"
                )
            else:
                st.warning(
                    f"It's warm outside and won't be cool later: {live_temp}°F stays above {threshold}°F. -- Warm Months"
                )


def render_wind_banner(
    fastest_wind_speed: float | None,
    fastest_wind_hour: int | None,
) -> None:
    """Show summary banner for today's fastest forecasted wind."""
    if fastest_wind_speed is None or fastest_wind_hour is None:
        st.warning("💨 Wind information is currently unavailable.")
        return
    st.info(
        f"💨 Today's Fastest Wind Forecasted: {fastest_wind_speed} mph at {fastest_wind_hour:02d}:00."
    )


# ---------------------------------------------------------------------------
# KITTY COMFORT
# ---------------------------------------------------------------------------
KITTY_TEMP_MIN_F: float = 32.0
KITTY_TEMP_MAX_F: float = 85.0
KITTY_WIND_THRESHOLD_MPH: float = 5.0


def kitty_comfort_status(
    live_temp_f: float,
    wind_speed: float | None,
    wind_gust: float | None,
    rain_or_snow: bool,
) -> dict[str, str]:
    """Return a dict with 'temp', 'wind', and optionally 'precip' status strings.

    All inputs are the current live values.  wind_speed and wind_gust may be
    None when data is unavailable — in that case wind status is omitted.
    rain_or_snow should be True when PrecipIn > 0 or SnowIn > 0 in the most
    recent actual hour.
    """
    # Temperature status
    if live_temp_f <= KITTY_TEMP_MIN_F:
        temp_status = (
            f"Brr too cold for Kitties: {live_temp_f:.1f}°F "
            f"-- (At or below {KITTY_TEMP_MIN_F:.0f}°F, freezing)"
        )
    elif live_temp_f > KITTY_TEMP_MAX_F:
        temp_status = (
            f"Too hot for Kitties: {live_temp_f:.1f}°F -- (More than {KITTY_TEMP_MAX_F:.0f}°F)"
        )
    else:
        temp_status = (
            f"Good Temperature for Kitties: {live_temp_f:.1f}°F "
            f"-- ({KITTY_TEMP_MIN_F:.0f}°F - {KITTY_TEMP_MAX_F:.0f}°F)"
        )

    # Wind status — use the higher of speed / gust if both present
    result: dict[str, str] = {"temp": temp_status}
    effective_wind: float | None = None
    if wind_speed is not None or wind_gust is not None:
        candidates = [v for v in (wind_speed, wind_gust) if v is not None]
        effective_wind = max(candidates)

    if effective_wind is not None:
        if effective_wind > KITTY_WIND_THRESHOLD_MPH:
            result["wind"] = (
                f"Too windy for Kitties: {effective_wind:.0f} mph "
                f"-- (More than {KITTY_WIND_THRESHOLD_MPH:.0f} mph)"
            )
        else:
            result["wind"] = (
                f"Not too windy for Kitties: {effective_wind:.0f} mph "
                f"-- ({KITTY_WIND_THRESHOLD_MPH:.0f} mph or less)"
            )

    # Precipitation status — only shown when actively raining/snowing
    if rain_or_snow:
        result["precip"] = "Kitties don't like rain or snow: Yes -- (Rain or snow detected)"

    return result


def render_kitty_comfort_banner(
    live_temp_f: float,
    wind_speed: float | None,
    wind_gust: float | None,
    rain_or_snow: bool,
) -> None:
    """Render the Kitty Comfort Threshold section above the temperature area."""
    status = kitty_comfort_status(live_temp_f, wind_speed, wind_gust, rain_or_snow)

    temp_ok = KITTY_TEMP_MIN_F < live_temp_f <= KITTY_TEMP_MAX_F
    wind_ok = "wind" not in status or status["wind"].startswith("Not too windy")
    precip_ok = "precip" not in status

    all_good = temp_ok and wind_ok and precip_ok

    lines = [
        f"🌡️ {status['temp']}",
    ]
    if "wind" in status:
        lines.append(f"💨 {status['wind']}")
    if "precip" in status:
        lines.append(f"🌧️ {status['precip']}")

    body = "  \n".join(lines)

    overall_status = "Yes" if all_good else "No"
    heading = f"**Kitty Comfort Threshold: {overall_status}**"

    if all_good:
        st.success(f"{heading}  \n{body}")
    else:
        st.error(f"{heading}  \n{body}")


def build_wind_chart(
    df: pd.DataFrame, current_hour: int, hist_band: pd.DataFrame
) -> alt.LayerChart:
    wind_df = df.copy()
    if "WindGust" not in wind_df.columns:
        wind_df["WindGust"] = None
    wind_df["Status"] = (
        wind_df["Hour"]
        .apply(lambda h: "Actual" if h <= current_hour else "Forecast")
        .astype(object)
    )

    bridge = wind_df[wind_df["Hour"] == current_hour].copy().assign(Status="Forecast")
    full = pd.concat([wind_df, bridge], ignore_index=True)

    max_speed = full["WindSpeed"].dropna().max() if not full["WindSpeed"].dropna().empty else 0
    y_max = max(50, max_speed + 5)

    x = alt.X(
        "Hour:Q",
        axis=alt.Axis(
            values=list(range(24)),
            labelAngle=-45,
            labelFontSize=11,
            labelExpr="datum.value + ':00'",
        ),
    )
    y = alt.Y(
        "WindSpeed:Q",
        axis=alt.Axis(title="Wind Speed (mph)", labelFontSize=11, titleFontSize=14),
        scale=alt.Scale(domain=[0, y_max]),
    )

    color_scale = alt.Scale(
        domain=["Actual", "Forecast", "Hist Avg (5yr)"],
        range=["#00f2ff", "#ffffff", "#a0c4ff"],
    )
    dash_scale = alt.Scale(
        domain=["Actual", "Forecast", "Hist Avg (5yr)"],
        range=[[0], [5, 5], [3, 3]],
    )

    wind_line = (
        alt.Chart(full)
        .mark_line(strokeWidth=4)
        .encode(
            x=x,
            y=y,
            color=alt.Color(
                "Status:N",
                scale=color_scale,
                legend=alt.Legend(
                    orient="bottom",
                    labelFontSize=12,
                    title=None,
                    columns=2,
                    columnPadding=20,
                    rowPadding=6,
                ),
            ),
            strokeDash=alt.StrokeDash("Status:N", scale=dash_scale, legend=None),
        )
    )

    dot = (
        alt.Chart(wind_df[wind_df["Hour"] == current_hour])
        .mark_circle(size=350, color="#00f2ff")
        .encode(x=x, y=y)
    )

    gust_actuals = wind_df[(wind_df["Status"] == "Actual") & (wind_df["WindGust"].notna())]
    gust_line = (
        alt.Chart(gust_actuals)
        .mark_line(strokeWidth=2, color="#ff6b6b", opacity=0.6)
        .encode(
            x=x,
            y=alt.Y("WindGust:Q", scale=alt.Scale(domain=[0, y_max])),
            tooltip=[
                alt.Tooltip("Hour:Q", title="Hour"),
                alt.Tooltip("WindGust:Q", title="Actual Gust mph"),
            ],
        )
    )

    if not gust_actuals.empty:
        strongest_gust = gust_actuals["WindGust"].max()
        strongest_gust_hour = gust_actuals.loc[
            gust_actuals["WindGust"] == strongest_gust, "Hour"
        ].iloc[0]
        gust_labels = gust_actuals[gust_actuals["Hour"] == strongest_gust_hour].copy()
        gust_labels["Lab_Txt"] = gust_labels["WindGust"].apply(lambda value: f"{value} mph")
        gust_lbl_top = (
            alt.Chart(gust_labels)
            .mark_text(dy=-18, fontSize=12, fontWeight="bold", color="#ff9b9b")
            .encode(x=x, y=alt.Y("WindGust:Q", scale=alt.Scale(domain=[0, y_max])), text="Lab_Txt")
        )
    else:
        gust_lbl_top = alt.Chart(
            pd.DataFrame({"Hour": [], "WindGust": [], "Lab_Txt": []})
        ).mark_text()

    actuals = wind_df[wind_df["Status"] == "Actual"]
    if not actuals.empty and not actuals["WindSpeed"].dropna().empty:
        hi = actuals["WindSpeed"].max()
        first_hi_h = actuals.loc[actuals["WindSpeed"] == hi, "Hour"].iloc[0]

        def wind_label_cfg(row):
            if row["Hour"] == first_hi_h:
                return f"{row['WindSpeed']} mph"
            return ""

        wind_df["Lab_Txt"] = wind_df.apply(wind_label_cfg, axis=1)
        lbl_top = (
            alt.Chart(wind_df[wind_df["Lab_Txt"] != ""])
            .mark_text(dy=-18, fontSize=13, fontWeight="bold", color="white")
            .encode(x=x, y=y, text="Lab_Txt")
        )
    else:
        lbl_top = alt.Chart(pd.DataFrame({"Hour": [], "WindSpeed": [], "Lab_Txt": []})).mark_text()

    if not hist_band.empty and "WindSpeedMean" in hist_band.columns:
        wind_band = (
            alt.Chart(hist_band)
            .mark_area(opacity=0.18, color="#a0c4ff")
            .encode(
                x=alt.X("Hour:Q"),
                y=alt.Y("WindSpeedLow:Q"),
                y2=alt.Y2("WindSpeedHigh:Q"),
                tooltip=[
                    alt.Tooltip("Hour:Q", title="Hour"),
                    alt.Tooltip("WindSpeedHigh:Q", title="Hist High mph"),
                    alt.Tooltip("WindSpeedLow:Q", title="Hist Low mph"),
                    alt.Tooltip("WindSpeedMean:Q", title="Hist Mean mph"),
                ],
            )
        )
        wind_hist_line = (
            alt.Chart(hist_band.assign(Status="Hist Avg (5yr)"))
            .mark_line(strokeWidth=2, opacity=0.7)
            .encode(
                x=alt.X("Hour:Q"),
                y=alt.Y("WindSpeedMean:Q"),
                color=alt.Color(
                    "Status:N",
                    scale=color_scale,
                    legend=alt.Legend(
                        orient="bottom",
                        labelFontSize=12,
                        title=None,
                        columns=2,
                        columnPadding=20,
                        rowPadding=6,
                    ),
                ),
                strokeDash=alt.StrokeDash("Status:N", scale=dash_scale, legend=None),
            )
        )
        chart = wind_band + wind_hist_line + wind_line + gust_line + dot + lbl_top + gust_lbl_top
    else:
        chart = wind_line + gust_line + dot + lbl_top + gust_lbl_top

    return chart.properties(height=300).configure_legend(fillColor="#1e1e1e", padding=10)


def build_precip_chart(df: pd.DataFrame, current_hour: int) -> alt.LayerChart:
    """Build hourly precipitation chart (inches) for actual hours only."""
    precip_df = df.copy()
    precip_df["Status"] = precip_df["Hour"].apply(
        lambda h: "Actual" if h <= current_hour else "Future"
    )
    actual = precip_df[(precip_df["Status"] == "Actual") & (precip_df["PrecipIn"].notna())]

    max_precip = actual["PrecipIn"].max() if not actual.empty else 0
    y_max = max(0.3, max_precip + 0.05)

    x = alt.X(
        "Hour:Q",
        axis=alt.Axis(
            values=list(range(24)),
            labelAngle=-45,
            labelFontSize=11,
            labelExpr="datum.value + ':00'",
        ),
    )
    y = alt.Y(
        "PrecipIn:Q",
        axis=alt.Axis(title="Precipitation (in)", labelFontSize=11, titleFontSize=14),
        scale=alt.Scale(domain=[0, y_max]),
    )

    line = (
        alt.Chart(actual)
        .mark_line(strokeWidth=4, color="#4db6ff")
        .encode(
            x=x,
            y=y,
            tooltip=[
                alt.Tooltip("Hour:Q", title="Hour"),
                alt.Tooltip("PrecipIn:Q", title="Precip in"),
            ],
        )
    )

    now_dot = (
        alt.Chart(actual[actual["Hour"] == current_hour])
        .mark_circle(size=260, color="#00f2ff")
        .encode(x=x, y=y)
    )

    if not actual.empty:
        max_row = actual.loc[actual["PrecipIn"] == actual["PrecipIn"].max()].iloc[0]
        label_df = pd.DataFrame(
            [
                {
                    "Hour": max_row["Hour"],
                    "PrecipIn": max_row["PrecipIn"],
                    "Label": f"{max_row['PrecipIn']} in",
                }
            ]
        )
        label = (
            alt.Chart(label_df)
            .mark_text(dy=-16, fontSize=12, fontWeight="bold", color="#d9f2ff")
            .encode(x=x, y=y, text="Label")
        )
    else:
        label = alt.Chart(pd.DataFrame({"Hour": [], "PrecipIn": [], "Label": []})).mark_text()

    return (
        (line + now_dot + label)
        .properties(height=280)
        .configure_legend(fillColor="#1e1e1e", padding=10)
    )


# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------
def run_app() -> None:
    secrets = _get_streamlit_secrets()
    runtime = resolve_runtime_config(secrets, os.environ)
    runtime_issues = validate_runtime_config(runtime)
    runtime_warnings = get_runtime_config_warnings(runtime)
    _is_dev = runtime["is_dev"]
    _page_title = "The Farm [DEV]" if _is_dev else "The Farm"

    st.set_page_config(page_title=_page_title, page_icon="🏔️", layout="wide")
    st.title("The Farm: How's the Weather?" + (" — DEV" if _is_dev else ""))

    now_mtn = datetime.now(LOCAL_TZ)
    st.markdown(f"**Loveland, CO** | `{now_mtn.strftime('%H:%M:%S')}`")

    # Sidebar
    st.sidebar.title("Settings")
    mode = st.sidebar.selectbox("Monitoring Mode", list(THRESHOLDS.keys()))
    threshold = THRESHOLDS[mode]

    # Temperature operand toggle (actual vs feels like)
    temp_mode = st.sidebar.radio("Temperature Type", ["Feels Like", "Actual"])
    selected_temp_key = "FeelsLike" if temp_mode == "Feels Like" else "Actual"
    selected_metric_title = f"{temp_mode} Now"

    runtime_line = (
        f"Profile: {runtime['profile']} | Data mode: {runtime['effective_data_mode']} | "
        f"Live API: {'on' if runtime['live_api_enabled'] else 'off'}"
    )
    if hasattr(st.sidebar, "caption"):
        st.sidebar.caption(runtime_line)
    else:
        st.caption(runtime_line)

    if runtime_issues:
        st.error("Invalid runtime configuration: " + " | ".join(runtime_issues))
        st.stop()

    for warning_text in runtime_warnings:
        st.warning("Runtime configuration warning: " + warning_text)

    if _is_dev:
        snapshot = get_dev_guardrail_snapshot(
            runtime=runtime,
            now=now_mtn,
            secrets=secrets,
            environ=os.environ,
        )
        if hasattr(st.sidebar, "markdown"):
            st.sidebar.markdown("**Dev API Guardrails**")
        else:
            st.markdown("**Dev API Guardrails**")
        if not snapshot["enabled"]:
            line = "Inactive until dev live API is explicitly enabled."
            if hasattr(st.sidebar, "caption"):
                st.sidebar.caption(line)
            else:
                st.caption(line)
        else:
            header_line = (
                f"Daily cooldown window: {snapshot['cooldown_minutes']} minutes after a 429."
            )
            if hasattr(st.sidebar, "caption"):
                st.sidebar.caption(header_line)
            else:
                st.caption(header_line)
            for item in snapshot["items"]:
                line = _format_dev_guardrail_sidebar_line(item)
                if hasattr(st.sidebar, "caption"):
                    st.sidebar.caption(line)
                else:
                    st.caption(line)

        controls_ctx = (
            st.sidebar.expander("Guardrail Controls", expanded=False)
            if hasattr(st.sidebar, "expander")
            else nullcontext()
        )
        with controls_ctx:
            sidebar_button = st.sidebar.button if hasattr(st.sidebar, "button") else st.button
            sidebar_checkbox = (
                st.sidebar.checkbox if hasattr(st.sidebar, "checkbox") else st.checkbox
            )

            if sidebar_button("Reset usage + blocked", key="guardrail_reset_usage"):
                reset_dev_guardrail_usage_and_blocked(now=now_mtn)
                st.success("Dev guardrail usage and blocked counters reset.")
                st.rerun()

            if sidebar_button("Clear cooldowns", key="guardrail_clear_cooldowns"):
                clear_dev_guardrail_cooldowns(now=now_mtn)
                st.success("Dev guardrail cooldowns cleared.")
                st.rerun()

            if sidebar_checkbox("Show raw guardrail state", value=False, key="guardrail_show_raw"):
                raw_state = get_dev_guardrail_raw_state(now=now_mtn)
                raw_json = json.dumps(raw_state, indent=2, sort_keys=True)
                if hasattr(st.sidebar, "code"):
                    st.sidebar.code(raw_json, language="json")
                else:
                    st.code(raw_json, language="json")

    if _is_dev and not runtime["live_api_enabled"] and not runtime["dev_use_sample_requested"]:
        st.warning(
            "DEV_USE_SAMPLE_DATA=false was requested, but live API is blocked in dev unless DEV_ALLOW_LIVE_API=true."
        )

    dev_use_sample_data = runtime["effective_data_mode"] == "sample"

    if dev_use_sample_data:
        st.info(f"Using local sample weather data. {runtime['policy_reason']}")
        df, live_temp, hist_band = _build_dev_sample_payload(now_mtn)
    else:
        # Fetch data
        vc_api_key = _get_vc_api_key()
        with st.spinner("Fetching latest weather data…"):
            # Forecast + current — fall back to session state if API is rate limited
            try:
                df, live_temp = fetch_forecast_and_current(vc_api_key)
                if not df.empty:
                    st.session_state["df"] = df
                    st.session_state["live_temp"] = live_temp
            except (requests.RequestException, DevAPIBlockedError) as e:
                logger.warning("Forecast fetch failed, using cached fallback: %s", e)
                df = st.session_state.get("df", pd.DataFrame())
                live_temp = st.session_state.get("live_temp", None)
                if df.empty or live_temp is None:
                    st.error(
                        "Could not reach the weather API and no cached data is available. Please try again in a few minutes."
                    )
                    st.stop()
                else:
                    st.warning(_format_dev_guardrail_fallback("forecast", e))

            # Historical band — prefer disk cache, then API, then session fallback.
            today_str = now_mtn.strftime("%Y-%m-%d")
            hist_band = _load_hist_band_from_disk(today_str)
            if not hist_band.empty:
                st.session_state["hist_band"] = hist_band
                st.session_state["hist_band_date"] = today_str
            else:
                try:
                    hist_band = fetch_historical_band(today_str, vc_api_key)
                    if not hist_band.empty:
                        st.session_state["hist_band"] = hist_band
                        st.session_state["hist_band_date"] = today_str
                        _save_hist_band_to_disk(today_str, hist_band)
                    else:
                        session_date = st.session_state.get("hist_band_date")
                        session_hist = st.session_state.get("hist_band", pd.DataFrame())
                        if session_date == today_str and not session_hist.empty:
                            hist_band = session_hist
                        else:
                            st.caption("⚠️ Historical band temporarily unavailable.")
                except (requests.RequestException, DevAPIBlockedError) as e:
                    logger.warning("Historical band fetch failed, using cached fallback: %s", e)
                    session_date = st.session_state.get("hist_band_date")
                    session_hist = st.session_state.get("hist_band", pd.DataFrame())
                    if session_date == today_str and not session_hist.empty:
                        hist_band = session_hist
                    else:
                        st.caption(_format_dev_guardrail_fallback("historical", e))

        # Wind direction/gust source override from Open-Meteo with session-state fallback.
        try:
            wind_df_om, wind_current_om = fetch_wind_openmeteo()
            if not wind_df_om.empty:
                st.session_state["wind_df_om"] = wind_df_om
            st.session_state["wind_current_om"] = wind_current_om
        except (requests.RequestException, DevAPIBlockedError) as e:
            logger.warning("Open-Meteo wind fetch failed, using cached fallback: %s", e)
            wind_df_om = st.session_state.get("wind_df_om", pd.DataFrame())
            wind_current_om = st.session_state.get("wind_current_om", {})
            st.caption(_format_dev_guardrail_fallback("wind", e))

        if not wind_df_om.empty:
            wind_merge_cols = ["Hour", "WindSpeed", "WindGust", "WindDeg", "WindDir"]
            df = df.drop(columns=["WindSpeed", "WindGust", "WindDeg", "WindDir"], errors="ignore")
            df = df.merge(wind_df_om[wind_merge_cols], on="Hour", how="left")

        if wind_current_om:
            for key in ["WindSpeed", "WindGust", "WindDeg", "WindDir"]:
                if wind_current_om.get(key) is not None:
                    live_temp[key] = wind_current_om.get(key)

    if df.empty:
        st.warning("No forecast data available for today.")
        st.stop()

    # Choose dataset for display mode (actual or feels like)
    if selected_temp_key not in df.columns:
        st.error(
            f"Selected temperature key '{selected_temp_key}' is not available in fetched data."
        )
        st.stop()

    df_display = (
        df[["Hour", selected_temp_key]].rename(columns={selected_temp_key: "Temperature"}).copy()
    )
    selected_live_temp = live_temp.get(selected_temp_key)
    if selected_live_temp is None:
        st.error(f"Selected latest temperature value for '{selected_temp_key}' is unavailable.")
        st.stop()

    if hist_band.empty:
        hist_band_display = hist_band
    else:
        if selected_temp_key == "Actual":
            hist_band_display = hist_band[["Hour", "ActualHigh", "ActualLow", "ActualMean"]].rename(
                columns={
                    "ActualHigh": "HistHigh",
                    "ActualLow": "HistLow",
                    "ActualMean": "HistMean",
                }
            )
        else:
            hist_band_display = hist_band[
                ["Hour", "FeelsLikeHigh", "FeelsLikeLow", "FeelsLikeMean"]
            ].rename(
                columns={
                    "FeelsLikeHigh": "HistHigh",
                    "FeelsLikeLow": "HistLow",
                    "FeelsLikeMean": "HistMean",
                }
            )

    current_hour = now_mtn.hour

    # Kitty Comfort banner — above temperature section
    _kc_rain_or_snow = False
    if "PrecipIn" in df.columns or "SnowIn" in df.columns:
        _kc_actuals = df[df["Hour"] <= current_hour].copy()
        if not _kc_actuals.empty:
            _kc_latest = _kc_actuals.sort_values("Hour").iloc[-1]
            _kc_rain_or_snow = (_kc_latest.get("PrecipIn") or 0) > 0 or (
                _kc_latest.get("SnowIn") or 0
            ) > 0
    render_kitty_comfort_banner(
        live_temp_f=selected_live_temp,
        wind_speed=live_temp.get("WindSpeed"),
        wind_gust=live_temp.get("WindGust"),
        rain_or_snow=_kc_rain_or_snow,
    )

    # Metrics
    actuals = df_display[df_display["Hour"] <= current_hour].copy()
    actuals.loc[actuals["Hour"] == current_hour, "Temperature"] = selected_live_temp
    hi = actuals["Temperature"].max()
    lo = actuals["Temperature"].min()

    # 1-hour trend delta
    trend_delta, since_label = get_temp_trend(df_display, selected_live_temp, current_hour)
    if trend_delta is not None:
        delta_str = f"{trend_delta:+.1f}°F {since_label}"
    else:
        delta_str = None

    m1, m2, m3 = st.columns(3)
    m1.metric(
        selected_metric_title,
        f"{selected_live_temp}°F",
        delta=delta_str,
        delta_color="normal",
    )
    m2.metric(f"Today's High ({temp_mode})", f"{hi}°F")
    m3.metric(f"Today's Low ({temp_mode})", f"{lo}°F")
    caption_heat = (
        "apparent temperature" if selected_temp_key == "FeelsLike" else "actual air temperature"
    )
    st.caption(f"🌡️ All temperatures are shown as {caption_heat}.")

    # Status banner
    forecast_future = df_display[df_display["Hour"] >= current_hour].copy()
    forecast_future.loc[forecast_future["Hour"] == current_hour, "Temperature"] = selected_live_temp
    render_status_banner(selected_live_temp, threshold, forecast_future, mode)

    # Temperature chart
    st.altair_chart(
        build_chart(df_display, selected_live_temp, threshold, current_hour, hist_band_display),
        width="stretch",
    )

    # Wind section
    for wind_col in ["WindSpeed", "WindGust", "WindDir"]:
        if wind_col not in df.columns:
            df[wind_col] = None

    wind_df = df[["Hour", "WindSpeed", "WindGust", "WindDir"]].copy()
    selected_wind_speed = live_temp.get("WindSpeed")
    selected_wind_gust = live_temp.get("WindGust")
    selected_wind_dir = live_temp.get("WindDir")
    if (
        not wind_df.empty
        and current_hour in wind_df["Hour"].values
        and selected_wind_speed is not None
    ):
        wind_df.loc[wind_df["Hour"] == current_hour, "WindSpeed"] = selected_wind_speed
    if (
        not wind_df.empty
        and current_hour in wind_df["Hour"].values
        and selected_wind_gust is not None
    ):
        wind_df.loc[wind_df["Hour"] == current_hour, "WindGust"] = selected_wind_gust

    wind_forecast_all = wind_df[wind_df["WindSpeed"].notna()].copy()
    if wind_forecast_all.empty:
        fastest_wind_speed = None
        fastest_wind_hour = None
    else:
        fastest_wind_speed = float(wind_forecast_all["WindSpeed"].max())
        fastest_wind_hour = int(
            wind_forecast_all.loc[
                wind_forecast_all["WindSpeed"] == fastest_wind_speed, "Hour"
            ].iloc[0]
        )

    wind_actuals = wind_df[wind_df["Hour"] <= current_hour].copy()

    if wind_actuals.empty or wind_actuals["WindGust"].dropna().empty:
        strongest_gust = None
    else:
        strongest_gust = float(wind_actuals["WindGust"].max())

    render_wind_banner(fastest_wind_speed, fastest_wind_hour)

    if current_hour == 0:
        wind_delta_str = None
    else:
        prior_wind = wind_df[wind_df["Hour"] == (current_hour - 1)]
        if prior_wind.empty or selected_wind_speed is None:
            wind_delta_str = None
        else:
            prior_speed = prior_wind.iloc[0]["WindSpeed"]
            if prior_speed is None:
                wind_delta_str = None
            else:
                wind_delta = round(float(selected_wind_speed) - float(prior_speed), 1)
                wind_delta_str = f"{wind_delta:+.1f} mph since {current_hour - 1:02d}:00"

    w1, w2, w3, w4 = st.columns(4)
    w1.metric(
        "Wind Speed Now",
        f"{selected_wind_speed} mph" if selected_wind_speed is not None else "N/A",
        delta=wind_delta_str,
        delta_color="normal",
    )
    w2.metric("Wind Direction", selected_wind_dir if selected_wind_dir is not None else "N/A")
    w3.metric(
        "Today's Fastest Wind",
        f"{fastest_wind_speed} mph" if fastest_wind_speed is not None else "N/A",
    )
    w4.metric(
        "Today's Strongest Gust",
        f"{strongest_gust} mph" if strongest_gust is not None else "N/A",
    )

    # Wind chart
    if hist_band.empty:
        wind_hist_band = pd.DataFrame(
            columns=["Hour", "WindSpeedHigh", "WindSpeedLow", "WindSpeedMean"]
        )
    else:
        wind_hist_band = hist_band[["Hour", "WindSpeedHigh", "WindSpeedLow", "WindSpeedMean"]]

    st.altair_chart(build_wind_chart(wind_df, current_hour, wind_hist_band), width="stretch")

    st.write("---")

    # Precipitation section (just before Data Sources)
    for precip_col in ["PrecipIn", "PrecipProb", "Humidity", "SnowIn"]:
        if precip_col not in df.columns:
            df[precip_col] = None

    precip_df = df[["Hour", "PrecipIn", "PrecipProb", "Humidity", "SnowIn"]].copy()
    live_precip_in = live_temp.get("PrecipIn")
    live_precip_prob = live_temp.get("PrecipProb")
    live_humidity = live_temp.get("Humidity")
    live_snow_in = live_temp.get("SnowIn")

    if not precip_df.empty and current_hour in precip_df["Hour"].values:
        if live_precip_in is not None:
            precip_df.loc[precip_df["Hour"] == current_hour, "PrecipIn"] = live_precip_in
        if live_precip_prob is not None:
            precip_df.loc[precip_df["Hour"] == current_hour, "PrecipProb"] = live_precip_prob
        if live_humidity is not None:
            precip_df.loc[precip_df["Hour"] == current_hour, "Humidity"] = live_humidity
        if live_snow_in is not None:
            precip_df.loc[precip_df["Hour"] == current_hour, "SnowIn"] = live_snow_in

    precip_actual = precip_df[precip_df["Hour"] <= current_hour].copy()
    if precip_actual.empty or precip_actual["PrecipIn"].dropna().empty:
        total_precip_so_far = 0.0
    else:
        total_precip_so_far = round(float(precip_actual["PrecipIn"].fillna(0).sum()), 2)

    # Use the most recent actual datapoint in the chart series for "recently" status.
    if precip_actual.empty:
        rain_or_snow_recently = False
    else:
        latest_row = precip_actual.sort_values("Hour").iloc[-1]
        latest_precip = latest_row.get("PrecipIn")
        latest_snow = latest_row.get("SnowIn")
        rain_or_snow_recently = (latest_precip or 0) > 0 or (latest_snow or 0) > 0

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Rain or Snow Recently?", "Yes" if rain_or_snow_recently else "No")
    p2.metric("Total Accumulation So Far Today", f"{total_precip_so_far} in")
    p3.metric(
        "Forecasted Precipitation Now %",
        f"{live_precip_prob}%" if live_precip_prob is not None else "N/A",
    )
    p4.metric(
        "Relative Humidity Now %",
        f"{live_humidity}%" if live_humidity is not None else "N/A",
    )

    st.altair_chart(build_precip_chart(precip_df, current_hour), width="stretch")
    st.caption("💧 Precipitation chart shows hourly actual precipitation amount in inches.")

    # Data Sources
    st.write("---")
    with st.expander("📡 About the Data Sources"):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("""
            **🌐 Open-Meteo** *(Hourly Forecast)*

            Open-Meteo blends multiple global weather models. For forecasts it uses:
            - **NOAA's GFS (Global Forecast System)**, updated every 6 hours
            - Interpolated for coordinates `40.3720°N, 105.0579°W` at ~2.5 km grid resolution

            This is **not** a single local weather station — it's a gridded model estimate.

            **📅 Visual Crossing** *(5-Year Historical Band)*

            The shaded historical band is sourced from Visual Crossing's Timeline API, which pulls from:
            - NWS/NOAA weather station observations
            - METAR airport reports and global reanalysis data
            - Blended for accuracy at the requested coordinates
            """)
        with col_b:
            st.markdown("""
            **🏢 Visual Crossing** *(Live + Hourly Conditions)*

            Visual Crossing blends data from multiple trusted sources:
            - NWS/NOAA weather station observations
            - METAR airport reports (including nearby **KFNL** — Fort Collins/Loveland Airport)
            - High-resolution global forecast models updated continuously

            Additional fields used in this app:
            - **Precipitation amount** (`precip`, inches)
            - **Precipitation probability** (`precipprob`, %)
            - **Relative humidity** (`humidity`, %)
            - **Snow amount** (`snow`, inches)

            Live conditions and today's hourly forecast refresh every **5 minutes**.
            The 5-year historical band refreshes once daily.
            """)
        st.caption(
            "💡 All sources use gridded or blended models — readings may differ slightly from a backyard weather station at The Farm's exact location."
        )


if __name__ == "__main__":
    run_app()
