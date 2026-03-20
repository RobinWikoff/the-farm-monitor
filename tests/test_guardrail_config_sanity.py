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
