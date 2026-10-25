from specguard_ai.reference_checks import check_module
from specguard_ai.test_plans import TestPlan as Plan
from specguard_ai.test_plans import render


def test_reference_check_detects_wrong_expected_output_without_running_generated_source():
    def add(a, b):
        return a + b

    plan = Plan(requirement_id="REQ-001", description="Sum", function_name="add",
                cases=[{"args": [2, 3], "kwargs": {}, "expected": 6}])
    observations = check_module(render(plan, "TEST-001").pytest_code, add)
    assert not observations[0]["passed"]


def test_reference_check_supports_expected_exceptions():
    def divide(a, b):
        if not b:
            raise ValueError("zero")
        return a / b

    plan = Plan(requirement_id="REQ-002", description="Zero", function_name="divide",
                cases=[{"args": [2, 0], "kwargs": {}, "expected_exception": "ValueError"}])
    assert check_module(render(plan, "TEST-002").pytest_code, divide)[0]["passed"]
