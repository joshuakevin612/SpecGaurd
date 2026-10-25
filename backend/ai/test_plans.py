"""Validated model test cases rendered into Python without model-written source."""

import ast
import inspect
import keyword
import math
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.shared.schemas import GeneratedTest


class TestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    args: list[Any]
    kwargs: dict[str, Any]
    expected: Any = None
    expected_exception: Literal["ValueError", "TypeError", "ZeroDivisionError", "KeyError",
                                "IndexError", "RuntimeError", "OverflowError"] | None = None
    comparison: Literal["equal", "approx"] = "equal"

    @model_validator(mode="after")
    def explicit_expectation(self):
        if self.expected_exception is None and "expected" not in self.model_fields_set:
            raise ValueError("Successful cases must explicitly specify expected output")
        return self


class TestPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_id: str
    description: str = Field(min_length=1)
    function_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    cases: list[TestCase] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def valid_identifier(self):
        if keyword.iskeyword(self.function_name):
            raise ValueError("Function name cannot be a Python keyword")
        for case in self.cases:
            if any(not key.isidentifier() or keyword.iskeyword(key) for key in case.kwargs):
                raise ValueError("Keyword argument names must be valid identifiers")
        return self


class PlansOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plans: list[TestPlan] = Field(max_length=4)


def literal(value: Any, depth: int = 0) -> str:
    if depth > 12:
        raise ValueError("Test value nesting is too deep")
    if value is None or isinstance(value, (str, bool, int)):
        return repr(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Use explicit __float__ tags for nonfinite test inputs")
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(literal(item, depth + 1) for item in value) + "]"
    if isinstance(value, dict):
        if (set(value) == {"__float__"} and isinstance(value["__float__"], str)
                and value["__float__"] in {"nan", "inf", "-inf"}):
            return f"float({value['__float__']!r})"
        return "{" + ", ".join(f"{literal(key, depth + 1)}: {literal(item, depth + 1)}"
                                for key, item in value.items()) + "}"
    raise ValueError("Unsupported test value type")


def render(plan: TestPlan, test_id: str) -> GeneratedTest:
    if not re.fullmatch(r"TEST-\d{3,}", test_id):
        raise ValueError("Invalid generated test ID")
    source = ["import pytest", f"from submission import {plan.function_name}", ""]
    suffix = test_id.replace("-", "_")
    for index, case in enumerate(plan.cases, 1):
        source.append(f"def test_{suffix}_case_{index:03d}():")
        call = f"{plan.function_name}(*{literal(case.args)}, **{literal(case.kwargs)})"
        if case.expected_exception:
            source.extend([f"    with pytest.raises({case.expected_exception}):", f"        {call}"])
        else:
            expected = literal(case.expected)
            if case.comparison == "approx":
                expected = f"pytest.approx({expected})"
            source.extend([f"    actual = {call}", f"    assert actual == {expected}"])
        source.append("")
    return GeneratedTest(id=test_id, requirement_id=plan.requirement_id,
                         description=plan.description, pytest_code="\n".join(source))


def validate_call_shape(plan: TestPlan, code: str) -> None:
    """Check argument binding from AST declarations without importing the submission."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return  # Syntax errors are separately reported by static analysis.
    fn = next((node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name == plan.function_name), None)
    if fn is None:
        return  # A required-but-missing function is a legitimate test target.
    params = []
    positional = fn.args.posonlyargs + fn.args.args
    first_default = len(positional) - len(fn.args.defaults)
    for index, arg in enumerate(positional):
        kind = (inspect.Parameter.POSITIONAL_ONLY if index < len(fn.args.posonlyargs)
                else inspect.Parameter.POSITIONAL_OR_KEYWORD)
        params.append(inspect.Parameter(arg.arg, kind, default=(None if index >= first_default
                                                                else inspect.Parameter.empty)))
    if fn.args.vararg:
        params.append(inspect.Parameter(fn.args.vararg.arg, inspect.Parameter.VAR_POSITIONAL))
    for arg, default in zip(fn.args.kwonlyargs, fn.args.kw_defaults, strict=True):
        params.append(inspect.Parameter(arg.arg, inspect.Parameter.KEYWORD_ONLY,
                                        default=None if default else inspect.Parameter.empty))
    if fn.args.kwarg:
        params.append(inspect.Parameter(fn.args.kwarg.arg, inspect.Parameter.VAR_KEYWORD))
    signature = inspect.Signature(params)
    for case in plan.cases:
        try:
            signature.bind(*case.args, **case.kwargs)
        except TypeError as exc:
            raise ValueError(f"Test arguments do not match {plan.function_name}: {exc}") from None
