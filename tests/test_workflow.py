import pytest

from shared.schemas import TestResult as Result
from specguard_ai.demo_assets import load_demo
from specguard_ai.provider import provider_name, using_provider
from specguard_ai.workflow import RunnerContractError, finish, prepare, verify


def test_unexecuted_tests_do_not_imply_passed_requirements():
    fixture = load_demo("divide")
    prepared = prepare(fixture["spec"], fixture["bad_code"])
    assert prepared.awaiting_runner
    assert all(state.state == "unverified" for state in prepared.requirement_states)


def test_ambiguous_requirements_never_trigger_runner():
    def forbidden_runner(tests, code):
        raise AssertionError("Ambiguous requirements must not be executed")

    report = verify("The application must be fast.", "", forbidden_runner)
    assert not report.verified
    assert report.requirement_states[0].state == "ambiguous"


def test_runner_adapter_completes_without_api_or_database():
    fixture = load_demo("add")

    def runner(tests, code):
        return [Result(test_id=test.id, requirement_id=test.requirement_id,
                       status="passed", output="fixture result", duration_ms=1) for test in tests]

    report = verify(fixture["spec"], fixture["good_code"], runner)
    assert report.verified
    assert report.requirement_states[0].state == "passed"
    assert not report.preparation.awaiting_runner


@pytest.mark.parametrize("fault", ["missing", "duplicate", "unknown", "wrong_requirement", "negative"])
def test_bad_runner_results_are_rejected(fault):
    fixture = load_demo("add")
    prepared = prepare(fixture["spec"], fixture["good_code"])
    result = Result(test_id="TEST-001", requirement_id="REQ-001", status="passed",
                    output="", duration_ms=0)
    results = [result]
    if fault == "missing":
        results = []
    elif fault == "duplicate":
        results = [result, result]
    elif fault == "unknown":
        result.test_id = "TEST-999"
    elif fault == "wrong_requirement":
        result.requirement_id = "REQ-999"
    else:
        result.duration_ms = -1
    with pytest.raises(RunnerContractError):
        finish(prepared, fixture["good_code"], results, bundle_sha256=prepared.bundle_sha256)


@pytest.mark.parametrize("status", ["failed", "error", "timeout", "flaky"])
def test_nonpassing_results_never_become_verified(status):
    fixture = load_demo("add")
    prepared = prepare(fixture["spec"], fixture["good_code"])
    result = Result(test_id="TEST-001", requirement_id="REQ-001", status=status,
                    output="", duration_ms=0)
    report = finish(prepared, fixture["good_code"], [result],
                    bundle_sha256=prepared.bundle_sha256, include_fixes=False)
    assert not report.verified


def test_stale_source_is_rejected():
    fixture = load_demo("add")
    prepared = prepare(fixture["spec"], fixture["good_code"])
    with pytest.raises(RunnerContractError, match="exact prepared"):
        finish(prepared, fixture["bad_code"], [], bundle_sha256=prepared.bundle_sha256)


def test_mutated_result_cannot_bypass_literal_status_validation():
    fixture = load_demo("add")
    prepared = prepare(fixture["spec"], fixture["good_code"])
    result = Result(test_id="TEST-001", requirement_id="REQ-001", status="passed", output="", duration_ms=0)
    result.status = "invented"
    with pytest.raises(RunnerContractError):
        finish(prepared, fixture["good_code"], [result], bundle_sha256=prepared.bundle_sha256)


def test_missing_test_coverage_stays_unverified(monkeypatch):
    fixture = load_demo("add")
    monkeypatch.setattr("specguard_ai.workflow.generate_tests", lambda *args: [])
    prepared = prepare(fixture["spec"], fixture["good_code"])
    report = finish(prepared, fixture["good_code"], [], bundle_sha256=prepared.bundle_sha256)
    assert not report.verified
    assert report.requirement_states[0].state == "unverified"


def test_provider_override_is_restored():
    assert provider_name() == "mock"
    with using_provider("nvidia"):
        assert provider_name() == "nvidia"
        with using_provider("mock"):
            assert provider_name() == "mock"
        assert provider_name() == "nvidia"
    assert provider_name() == "mock"
