import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from shared.schemas import Requirement
from shared.schemas import TestResult as Result
from specguard_ai import analyze_code, generate_tests, parse_spec, suggest_fixes
from specguard_ai.provider import ProviderError

FIXTURES = Path(__file__).resolve().parents[1] / "specguard_ai" / "fixtures"


@pytest.mark.parametrize("name", ["add", "divide", "cart"])
def test_demo_detects_bug_and_accepts_correct_code(name, tmp_path):
    fixture = json.loads((FIXTURES / f"{name}.json").read_text("utf-8"))
    reqs = parse_spec(fixture["spec"])
    generated = generate_tests(reqs, fixture["good_code"])
    for variant, expected in [("good_code", 0), ("bad_code", 1)]:
        folder = tmp_path / variant
        folder.mkdir()
        (folder / "submission.py").write_text(fixture[variant], encoding="utf-8")
        for test in generated:
            (folder / f"test_{test.id.replace('-', '_')}.py").write_text(
                test.pytest_code, encoding="utf-8")
        # Only repository-controlled fixtures are executed locally, never user/model code.
        environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP")
                       if key in os.environ}
        environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        completed = subprocess.run([sys.executable, "-m", "pytest", "-q", str(folder)],
                                   check=False, cwd=folder, env=environment,
                                   capture_output=True, text=True, timeout=30)
        assert completed.returncode == expected, completed.stdout + completed.stderr


def test_ambiguity_has_no_tests():
    reqs = parse_spec("The application must be fast.")
    assert reqs[0].ambiguous
    assert reqs[0].clarification_note
    assert generate_tests(reqs, "") == []


def test_mock_rejects_unknown_specs():
    with pytest.raises(ProviderError, match="bundled demo"):
        parse_spec("Unknown arbitrary spec")


def test_syntax_error_maps_to_requirement():
    reqs = parse_spec("Implement add(a, b) returning the sum of two integers.")
    findings = analyze_code("def add(:", reqs)
    assert findings[0].requirement_id == "REQ-001"
    assert findings[0].line == 1


def test_missing_function_is_only_a_potential_violation():
    reqs = parse_spec("Implement add(a, b) returning the sum of two integers.")
    assert "Potential violation" in analyze_code("x = 1", reqs)[0].message
    assert analyze_code("def add(a, b): return a - b", reqs) == []


@pytest.mark.parametrize("status", ["passed", "error", "timeout", "flaky"])
def test_no_fixes_for_nonfailed_results(status, monkeypatch):
    monkeypatch.setenv("SPECGUARD_PROVIDER", "nebius")
    result = Result(test_id="TEST-001", requirement_id="REQ-001", status=status,
                    output="", duration_ms=1)
    assert suggest_fixes("x = 1", [result]) == []


def test_live_validation_rejects_unknown_test_requirement(monkeypatch):
    monkeypatch.setenv("SPECGUARD_PROVIDER", "nebius")
    monkeypatch.setattr("specguard_ai.api.request_json", lambda *args: {
        "plans": [{"requirement_id": "REQ-999", "function_name": "add", "description": "x",
                   "cases": [{"args": [1, 2], "kwargs": {}, "expected": 3}]}]
    })
    req = Requirement(id="REQ-001", text="add", category="functional", measurable_criteria="sum")
    with pytest.raises(ProviderError, match="reference"):
        generate_tests([req], "")


def test_invalid_model_json_is_not_empty_success(monkeypatch):
    monkeypatch.setenv("SPECGUARD_PROVIDER", "nebius")
    monkeypatch.setattr("specguard_ai.api.request_json", lambda *args: {"wrong_key": []})
    with pytest.raises(ProviderError, match="schema"):
        parse_spec("Do something")


def test_ambiguous_model_output_needs_clarification(monkeypatch):
    monkeypatch.setenv("SPECGUARD_PROVIDER", "nebius")
    monkeypatch.setattr("specguard_ai.api.request_json", lambda *args: {
        "requirements": [{"id": "REQ-001", "text": "fast", "category": "performance",
                          "measurable_criteria": "", "ambiguous": True}]
    })
    with pytest.raises(ProviderError, match="clarification"):
        parse_spec("fast")


def test_model_cannot_silently_rewrite_original_specification(monkeypatch):
    monkeypatch.setenv("SPECGUARD_PROVIDER", "nvidia")
    monkeypatch.setattr("specguard_ai.api.request_json", lambda *args: {
        "requirements": [{"id": "REQ-001", "text": "Invented requirement",
                          "category": "functional", "measurable_criteria": "invented"}]
    })
    with pytest.raises(ProviderError, match="original specification"):
        parse_spec("Implement add(a, b) returning the sum of two integers.")


def test_generation_batches_requirements_and_assigns_unique_ids(monkeypatch):
    fixture = json.loads((FIXTURES / "divide.json").read_text("utf-8"))
    reqs = parse_spec(fixture["spec"])
    monkeypatch.setenv("SPECGUARD_PROVIDER", "nvidia")
    seen = []

    def respond(operation, payload):
        target = payload["requirements"][0]["id"]
        seen.append(target)
        case = ({"args": [7, 2], "kwargs": {}, "expected": 3.5}
                if target == "REQ-001" else
                {"args": [5, 0], "kwargs": {}, "expected": None, "expected_exception": "ValueError"})
        return {"plans": [{"requirement_id": target, "description": "Division behavior",
                           "function_name": "divide", "cases": [case]}]}

    monkeypatch.setattr("specguard_ai.api.request_json", respond)
    tests = generate_tests(reqs, fixture["bad_code"])
    assert seen == ["REQ-001", "REQ-002"]
    assert [test.id for test in tests] == ["TEST-001", "TEST-002"]


@pytest.mark.parametrize("patch", [
    "def replacement(a, b): return a + b",
    "def add(a): return a",
    "def add(a, b): return a - b",
])
def test_model_repairs_preserve_public_interface_and_change_source(monkeypatch, patch):
    monkeypatch.setenv("SPECGUARD_PROVIDER", "nvidia")
    monkeypatch.setattr("specguard_ai.api.request_json", lambda *args: {"fixes": [{
        "requirement_id": "REQ-001", "explanation": "Fix arithmetic", "patched_code": patch,
    }]})
    result = Result(test_id="TEST-001", requirement_id="REQ-001", status="failed",
                    output="expected 5 got -1", duration_ms=0)
    with pytest.raises(ProviderError):
        suggest_fixes("def add(a, b): return a - b", [result])
