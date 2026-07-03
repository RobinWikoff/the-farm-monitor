from pathlib import Path

import app


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "tests.yml"


def test_unknown_env_value_is_rejected():
    runtime = app.resolve_runtime_config(secrets={}, environ={"ENV": "staging"})

    issues = app.validate_runtime_config(runtime)

    assert "Unsupported ENV value: staging" in issues


def test_prod_warns_when_dev_flags_are_present():
    runtime = app.resolve_runtime_config(
        secrets={},
        environ={
            "ENV": "prod",
            "DEV_ALLOW_LIVE_API": "true",
            "DEV_USE_SAMPLE_DATA": "true",
        },
    )

    warnings = app.get_runtime_config_warnings(runtime)

    assert "DEV_* flags are ignored outside dev and CI profiles." in warnings


def test_ci_live_manual_requires_explicit_dev_allow_live_api():
    runtime = app.resolve_runtime_config(
        secrets={},
        environ={
            "CI": "true",
            "RUN_LIVE_INTEGRATION_TESTS": "true",
            "DEV_ALLOW_LIVE_API": "false",
            "ENV": "dev",
        },
    )

    issues = app.validate_runtime_config(runtime)

    assert "ci-live-manual requires DEV_ALLOW_LIVE_API=true." in issues


def test_ci_live_manual_warns_when_sample_requested():
    runtime = app.resolve_runtime_config(
        secrets={},
        environ={
            "CI": "true",
            "RUN_LIVE_INTEGRATION_TESTS": "true",
            "DEV_ALLOW_LIVE_API": "true",
            "DEV_USE_SAMPLE_DATA": "true",
            "ENV": "dev",
        },
    )

    warnings = app.get_runtime_config_warnings(runtime)

    assert "DEV_USE_SAMPLE_DATA is ignored in ci-live-manual mode." in warnings


def test_non_live_workflow_pins_safe_guardrail_envs():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "name: Unit and integration tests (non-live)" in workflow
    assert 'CI: "true"' in workflow
    assert 'DEV_ALLOW_LIVE_API: "false"' in workflow
    assert 'DEV_USE_SAMPLE_DATA: "true"' in workflow


def test_live_workflow_pins_explicit_live_guardrail_envs_and_logging():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "name: Live API integration tests (manual)" in workflow
    assert 'RUN_LIVE_INTEGRATION_TESTS: "true"' in workflow
    assert 'DEV_ALLOW_LIVE_API: "true"' in workflow
    assert 'DEV_USE_SAMPLE_DATA: "false"' in workflow
    assert "Log effective runtime profile" in workflow


# ---------------------------------------------------------------------------
# Prod profile validation — Slice B (issue-58)
# ---------------------------------------------------------------------------


def test_prod_profile_clean_runtime_has_no_errors():
    """A clean prod runtime must pass validation with no errors."""
    runtime = app.resolve_runtime_config(secrets={}, environ={"ENV": "prod"})

    assert runtime["profile"] == "prod"
    issues = app.validate_runtime_config(runtime)

    assert issues == []


def test_prod_profile_clean_runtime_has_no_warnings():
    """A clean prod runtime (no DEV_* flags) emits no warnings."""
    runtime = app.resolve_runtime_config(secrets={}, environ={"ENV": "prod"})

    warnings = app.get_runtime_config_warnings(runtime)

    assert warnings == []


def test_prod_profile_sample_mode_forced_raises_error():
    """validate_runtime_config must flag prod when sample data is forced via env."""
    # prod ignores DEV_USE_SAMPLE_DATA — but if the resolved runtime somehow
    # arrives with sample mode, the validator must catch it.
    runtime = app.resolve_runtime_config(
        secrets={},
        environ={"ENV": "prod", "DEV_USE_SAMPLE_DATA": "true"},
    )

    # prod profile always resolves to live mode regardless of DEV_USE_SAMPLE_DATA
    assert runtime["effective_data_mode"] == "live"
    issues = app.validate_runtime_config(runtime)
    assert issues == []


def test_prod_profile_inspect_returns_correct_shape():
    """inspect_runtime_config result for prod has expected keys."""
    runtime = app.resolve_runtime_config(secrets={}, environ={"ENV": "prod"})

    result = app.inspect_runtime_config(runtime)

    assert "errors" in result
    assert "warnings" in result
    assert isinstance(result["errors"], list)
    assert isinstance(result["warnings"], list)


def test_prod_profile_live_api_and_mode_asserted():
    """prod must have live_api_enabled=True and effective_data_mode='live'."""
    runtime = app.resolve_runtime_config(secrets={}, environ={"ENV": "prod"})

    assert runtime["live_api_enabled"] is True
    assert runtime["effective_data_mode"] == "live"


def test_dev_live_profile_clean_runtime_has_no_errors():
    """A correctly configured dev-live runtime must also pass validation."""
    runtime = app.resolve_runtime_config(
        secrets={},
        environ={"ENV": "dev", "DEV_ALLOW_LIVE_API": "true"},
    )

    assert runtime["profile"] == "dev-live"
    issues = app.validate_runtime_config(runtime)

    assert issues == []


def test_dev_safe_profile_clean_runtime_has_no_errors():
    """A dev-safe runtime (no live flag) must pass validation."""
    runtime = app.resolve_runtime_config(
        secrets={},
        environ={"ENV": "dev"},
    )

    assert runtime["profile"] == "dev-safe"
    issues = app.validate_runtime_config(runtime)

    assert issues == []
