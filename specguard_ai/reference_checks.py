"""Check rendered literal cases against reviewed demo references, never execute test source."""

import argparse
import ast
import json

import pytest

from .provider import ROOT


def data(node):
    if isinstance(node, ast.List):
        return [data(item) for item in node.elts]
    if isinstance(node, ast.Dict):
        return {data(key): data(value) for key, value in zip(node.keys, node.values, strict=True)}
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float"
            and len(node.args) == 1 and not node.keywords
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value in {"inf", "-inf", "nan"}):
        return float(node.args[0].value)
    return ast.literal_eval(node)


def check_module(source, reference):
    observations = []
    for function in ast.parse(source).body:
        if not isinstance(function, ast.FunctionDef) or not function.name.startswith("test_"):
            continue
        body = function.body
        expected_exception = None
        if len(body) == 1 and isinstance(body[0], ast.With):
            context = body[0].items[0].context_expr
            if (not isinstance(context, ast.Call) or not isinstance(context.func, ast.Attribute)
                    or context.func.attr != "raises" or len(context.args) != 1
                    or not isinstance(context.args[0], ast.Name)):
                raise ValueError("Not a rendered exception case")
            expected_exception = {"ValueError": ValueError, "TypeError": TypeError,
                                  "ZeroDivisionError": ZeroDivisionError, "KeyError": KeyError,
                                  "IndexError": IndexError, "RuntimeError": RuntimeError,
                                  "OverflowError": OverflowError}[context.args[0].id]
            call = body[0].body[0].value
        elif len(body) == 2 and isinstance(body[0], ast.Assign) and isinstance(body[1], ast.Assert):
            call = body[0].value
            expected_node = body[1].test.comparators[0]
            approximate = isinstance(expected_node, ast.Call)
            expected = data(expected_node.args[0] if approximate else expected_node)
        else:
            raise ValueError("Not a deterministic rendered test case")
        if (not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name)
                or call.func.id != reference.__name__ or len(call.args) != 1
                or not isinstance(call.args[0], ast.Starred) or len(call.keywords) != 1
                or call.keywords[0].arg is not None):
            raise ValueError("Not a literal call to the reviewed demo reference")
        args, kwargs = data(call.args[0].value), data(call.keywords[0].value)
        try:
            actual = reference(*args, **kwargs)
            passed = expected_exception is None and actual == (pytest.approx(expected) if approximate else expected)
            detail = f"returned {actual!r}"
        except Exception as exc:
            passed = expected_exception is not None and isinstance(exc, expected_exception)
            detail = f"raised {type(exc).__name__}"
        observations.append({"case": function.name, "passed": bool(passed), "observation": detail})
    if not observations:
        raise ValueError("No rendered test cases found")
    return observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo", choices=["add", "divide", "cart"])
    args = parser.parse_args()
    # These are reviewed repository implementations, not submitted or model-generated code.
    from demos.add.good import add
    from demos.cart.good import calculate_total
    from demos.divide.good import divide

    reference = {"add": add, "divide": divide, "cart": calculate_total}[args.demo]
    directory = ROOT / "artifacts" / "bundles" / "nvidia" / args.demo
    prepared = json.loads((directory / "preparation.json").read_text("utf-8"))
    observations = []
    for test in prepared["tests"]:
        for observation in check_module(test["pytest_code"], reference):
            observations.append({"test_id": test["id"], **observation})
    passed = bool(observations) and all(item["passed"] for item in observations)
    report = {"demo": args.demo, "all_reference_cases_passed": passed,
              "generated_python_executed": False, "production_sandbox_verified": False,
              "observations": observations}
    (directory / "reference-checks.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"{args.demo}: {sum(item['passed'] for item in observations)}/{len(observations)} reference cases passed")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
