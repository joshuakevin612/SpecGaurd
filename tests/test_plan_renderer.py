import ast

import pytest
from pydantic import ValidationError

from specguard_ai.test_plans import TestPlan as Plan
from specguard_ai.test_plans import literal, render, validate_call_shape
from specguard_ai.test_validation import validate_test


def test_source_strings_stay_quoted_data():
    plan = Plan(requirement_id="REQ-001", description="Literal strings",
                function_name="echo", cases=[{
                    "args": ["'); __import__('os').system('bad'); #"],
                    "kwargs": {}, "expected": "safe",
                }])
    generated = render(plan, "TEST-001")
    validate_test(generated.pytest_code)
    tree = ast.parse(generated.pytest_code)
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id == "__import__" for node in ast.walk(tree))


def test_exception_and_nonfinite_cases_render_valid_pytest():
    plan = Plan(requirement_id="REQ-003", description="Reject nonfinite price",
                function_name="calculate_total", cases=[{
                    "args": [[{"price": {"__float__": "inf"}, "quantity": 1}]],
                    "kwargs": {}, "expected": None, "expected_exception": "ValueError",
                }])
    code = render(plan, "TEST-003").pytest_code
    validate_test(code)
    assert "float('inf')" in code
    assert "pytest.raises(ValueError)" in code


@pytest.mark.parametrize("name", ["import", "x.y", "f();oops", "__import__"])
def test_function_identifier_cannot_inject_source(name):
    with pytest.raises(ValidationError):
        Plan(requirement_id="REQ-001", description="x", function_name=name,
             cases=[{"args": [], "kwargs": {}, "expected": None}])


def test_nonfinite_values_need_explicit_tags():
    with pytest.raises(ValueError):
        literal(float("nan"))


def test_exception_cases_may_omit_an_unused_expected_value():
    plan = Plan(requirement_id="REQ-001", description="Zero divisor", function_name="divide",
                cases=[{"args": [1, 0], "kwargs": {}, "expected_exception": "ValueError"}])
    validate_test(render(plan, "TEST-001").pytest_code)


def test_successful_cases_cannot_omit_expected_output():
    with pytest.raises(ValidationError, match="explicitly"):
        Plan(requirement_id="REQ-001", description="Sum", function_name="add",
             cases=[{"args": [1, 2], "kwargs": {}}])


def test_missing_required_arguments_are_rejected_without_importing_code():
    plan = Plan(requirement_id="REQ-001", description="Empty cart", function_name="calculate_total",
                cases=[{"args": [], "kwargs": {}, "expected": 0}])
    with pytest.raises(ValueError, match="arguments do not match"):
        validate_call_shape(plan, "def calculate_total(items, discount_percent=0): return 0")


def test_list_valued_arguments_bind_with_correct_nesting():
    plan = Plan(requirement_id="REQ-001", description="Empty cart", function_name="calculate_total",
                cases=[{"args": [[]], "kwargs": {}, "expected": 0}])
    validate_call_shape(plan, "def calculate_total(items, discount_percent=0): return 0")
