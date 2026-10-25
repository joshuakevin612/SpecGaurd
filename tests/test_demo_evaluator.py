import pytest

from specguard_ai.demo_assets import load_demo
from specguard_ai.demo_evaluator import UnsupportedDemoCode, check_division
from specguard_ai.repair_demo import repair_demo


def test_reference_oracle_distinguishes_good_and_bad_division():
    fixture = load_demo("divide")
    assert {r.status for r in check_division(fixture["bad_code"])} == {"failed"}
    assert {r.status for r in check_division(fixture["good_code"])} == {"passed"}


@pytest.mark.parametrize("code", [
    "import os\ndef divide(a,b): return a/b",
    "def divide(a,b): return __import__('os').system('whoami')",
    "def divide(a,b):\n    while True: pass",
    "def divide(a,b): return a ** 100000000",
    "def divide(a,b): return (1).__class__",
])
def test_reference_oracle_rejects_unsupported_code_without_executing_it(code):
    with pytest.raises(UnsupportedDemoCode):
        check_division(code)


def test_mock_repair_proof_is_labelled_as_reference_checks():
    report = repair_demo("mock")
    assert report["repair_validated_on_reference_cases"]
    assert not report["generated_pytest_executed"]
    assert not report["production_sandbox_verified"]
    assert all("MOCK" in fix["explanation"] for fix in report["fixes"])
