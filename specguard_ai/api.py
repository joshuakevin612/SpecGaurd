"""The four synchronous Person A functions. These never execute submitted code."""

import ast
import json
import re
from pathlib import Path

from pydantic import ValidationError

from shared.schemas import FixSuggestion, GeneratedTest, Requirement, StaticFinding, TestResult

from .provider import ProviderError, provider_name, request_json
from .static_analysis import analyze
from .test_plans import PlansOutput, render, validate_call_shape
from .test_validation import InvalidGeneratedTest, validate_test
from .validation import FixesOutput, RequirementsOutput, TestsOutput, schema_error_details


def _unique(items: list) -> None:
    identifiers = [item.id for item in items]
    if len(identifiers) != len(set(identifiers)):
        raise ProviderError("Duplicate identifiers in requirements or tests")


def _fixture(spec: str) -> dict:
    for path in (Path(__file__).parent / "fixtures").glob("*.json"):
        fixture = json.loads(path.read_text("utf-8"))
        if spec.strip() == fixture["spec"].strip():
            return fixture
    raise ProviderError("Mock mode supports only bundled demo specs; select a live provider for others")


def parse_spec(spec_text: str) -> list[Requirement]:
    if not spec_text.strip():
        raise ValueError("Spec must not be empty")
    raw = ({"requirements": _fixture(spec_text)["requirements"]}
           if provider_name() == "mock"
           else request_json("parse_spec", {"spec": spec_text}))
    try:
        reqs = RequirementsOutput.model_validate(raw).requirements
    except ValidationError as exc:
        raise ProviderError(f"Invalid requirements response schema ({schema_error_details(exc)})") from None
    _unique(reqs)
    for req in reqs:
        if not req.text.strip() or " ".join(req.text.split()) not in " ".join(spec_text.split()):
            raise ProviderError("Requirement text must quote the original specification")
        if not re.fullmatch(r"REQ-\d{3,}", req.id):
            raise ProviderError("Requirement ID must use REQ-001 format")
        if req.ambiguous and (not req.clarification_note or not req.clarification_note.strip()):
            raise ProviderError("Ambiguous requirements need a clarification note")
        if not req.ambiguous and not req.measurable_criteria.strip():
            raise ProviderError("Nonambiguous requirements need measurable criteria")
    return reqs


def generate_tests(reqs: list[Requirement], code: str) -> list[GeneratedTest]:
    _unique(reqs)
    eligible = [req for req in reqs if not req.ambiguous]
    if not eligible:
        return []
    if provider_name() == "mock":
        # Match the complete fixture contract; never fabricate support for arbitrary specs.
        raw_tests = []
        wanted = [req.model_dump() for req in reqs]
        for path in (Path(__file__).parent / "fixtures").glob("*.json"):
            fixture = json.loads(path.read_text("utf-8"))
            if fixture["requirements"] == wanted:
                raw_tests = fixture["tests"]
                break
        else:
            raise ProviderError("Mock requirements do not match a bundled demo")
        raw = {"tests": raw_tests}
    else:
        # One requirement per call keeps nested Python/JSON output small and prevents
        # later requirements from disappearing in a large response. IDs are assigned
        # locally after each validated response, so they remain unique across calls.
        collected = []
        for req in eligible:
            response = request_json("plan_tests", {
                "context_requirements": [item.model_dump() for item in reqs], "code": code,
                "requirements": [req.model_dump()], "target_requirement_id": req.id,
            })
            try:
                plans = PlansOutput.model_validate(response).plans
            except ValidationError as exc:
                raise ProviderError(f"Invalid generated tests response schema ({schema_error_details(exc)})") from None
            for plan in plans:
                if plan.requirement_id != req.id:
                    raise ProviderError("Unknown/ambiguous requirement reference in test plan")
                try:
                    validate_call_shape(plan, code)
                    test = render(plan, f"TEST-{len(collected) + 1:03d}")
                except ValueError:
                    raise ProviderError("Unsupported literal in generated test plan") from None
                try:
                    validate_test(test.pytest_code)
                except ProviderError as exc:
                    raise InvalidGeneratedTest(test, str(exc)) from None
                collected.append(test)
        raw = {"tests": [test.model_dump() for test in collected]}
    try:
        tests = TestsOutput.model_validate(raw).tests
    except ValidationError as exc:
        raise ProviderError(f"Invalid generated tests response schema ({schema_error_details(exc)})") from None
    _unique(tests)
    allowed = {req.id for req in eligible}
    for test in tests:
        if not re.fullmatch(r"TEST-\d{3,}", test.id) or test.requirement_id not in allowed:
            raise ProviderError("Invalid test ID or unknown/ambiguous requirement reference")
        try:
            validate_test(test.pytest_code)
        except ProviderError as exc:
            raise InvalidGeneratedTest(test, str(exc)) from None
    return tests


def analyze_code(code: str, reqs: list[Requirement]) -> list[StaticFinding]:
    return analyze(code, reqs)


def suggest_fixes(code: str, results: list[TestResult]) -> list[FixSuggestion]:
    failed = [result for result in results if result.status == "failed"]
    if not failed:
        return []
    if provider_name() == "mock":
        # Labelled fixture repairs support offline integration, never arbitrary inference.
        for path in (Path(__file__).parent / "fixtures").glob("*.json"):
            fixture = json.loads(path.read_text("utf-8"))
            if code.strip() == fixture["bad_code"].strip() and fixture["tests"]:
                known = {test["requirement_id"] for test in fixture["tests"]}
                return [FixSuggestion(
                    requirement_id=req_id,
                    explanation="MOCK fixture repair: known-good demo implementation; not AI inference.",
                    patched_code=fixture["good_code"],
                ) for req_id in sorted({result.requirement_id for result in failed} & known)]
        return []
    raw = request_json("suggest_fixes", {
        "code": code, "results": [result.model_dump() for result in failed],
    })
    try:
        fixes = FixesOutput.model_validate(raw).fixes
    except ValidationError as exc:
        raise ProviderError(f"Invalid fix suggestions response schema ({schema_error_details(exc)})") from None
    allowed = {result.requirement_id for result in failed}
    for fix in fixes:
        if fix.requirement_id not in allowed:
            raise ProviderError("Fix references a requirement without failed results")
        if not fix.explanation.strip() or not fix.patched_code.strip():
            raise ProviderError("Fix suggestions need an explanation and nonempty replacement code")
        try:
            patched = ast.parse(fix.patched_code)
        except SyntaxError:
            raise ProviderError("Proposed fix is not valid Python") from None
        if fix.patched_code.strip() == code.strip():
            raise ProviderError("Proposed fix does not change the submitted code")
        try:
            original = ast.parse(code)
        except SyntaxError:
            original = ast.Module(body=[], type_ignores=[])
        public = {node.name: node for node in original.body
                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and not node.name.startswith("_")}
        replacements = {node.name: node for node in patched.body
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name, node in public.items():
            replacement = replacements.get(name)
            if replacement is None or type(replacement) is not type(node):
                raise ProviderError("Proposed fix removed or changed a public function interface")
            # Preserve parameter names/kinds/default values; annotation changes are allowed.
            def signature(args):
                return ([arg.arg for arg in args.posonlyargs], [arg.arg for arg in args.args],
                        args.vararg.arg if args.vararg else None,
                        [arg.arg for arg in args.kwonlyargs], args.kwarg.arg if args.kwarg else None,
                        [ast.dump(value) for value in args.defaults],
                        [ast.dump(value) if value is not None else None for value in args.kw_defaults])
            if signature(replacement.args) != signature(node.args):
                raise ProviderError("Proposed fix changed a public function argument signature")
    return fixes
