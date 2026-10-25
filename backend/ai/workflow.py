"""Pipeline and runner adapter. All new models are internal; shared schemas stay frozen."""

import hashlib
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.shared.schemas import FixSuggestion, GeneratedTest, Requirement, StaticFinding, TestResult

from .api import analyze_code, generate_tests, parse_spec, suggest_fixes
from .provider import provider_name, using_provider

Runner = Callable[[list[GeneratedTest], str], list[TestResult]]


class RunnerContractError(ValueError):
    """The runner did not return exactly one correctly mapped result per test."""


class RequirementState(BaseModel):
    requirement_id: str
    state: Literal["ambiguous", "unverified", "passed", "failed", "error", "flaky"]
    test_ids: list[str]


class Preparation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_sha256: str
    bundle_sha256: str
    provider: Literal["mock", "nvidia", "nebius"]
    requirements: list[Requirement]
    tests: list[GeneratedTest]
    static_findings: list[StaticFinding]
    requirement_states: list[RequirementState]
    awaiting_runner: bool = True


class Verification(BaseModel):
    preparation: Preparation
    results: list[TestResult]
    requirement_states: list[RequirementState]
    fixes: list[FixSuggestion] = Field(default_factory=list)
    verified: bool = False


def requirement_states(reqs: list[Requirement], tests: list[GeneratedTest],
                       results: list[TestResult]) -> list[RequirementState]:
    by_test = {result.test_id: result for result in results}
    states = []
    for req in reqs:
        ids = [test.id for test in tests if test.requirement_id == req.id]
        statuses = [by_test[test_id].status for test_id in ids if test_id in by_test]
        if req.ambiguous:
            state = "ambiguous"
        elif not ids or len(statuses) != len(ids):
            state = "unverified"
        elif "failed" in statuses:
            state = "failed"
        elif {"error", "timeout"} & set(statuses):
            state = "error"
        elif "flaky" in statuses:
            state = "flaky"
        else:
            state = "passed"
        states.append(RequirementState(requirement_id=req.id, state=state, test_ids=ids))
    return states


def bundle_hash(code: str, tests: list[GeneratedTest]) -> str:
    import json

    value = json.dumps({"code": code, "tests": [test.model_dump() for test in tests]},
                       sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode()).hexdigest()


def prepare(spec_text: str, code: str, *, provider: str | None = None) -> Preparation:
    with using_provider(provider):
        reqs = parse_spec(spec_text)
        tests = generate_tests(reqs, code)
        return assemble_preparation(code, provider_name(), reqs, tests, analyze_code(code, reqs))


def assemble_preparation(code: str, provider: str, reqs: list[Requirement],
                         tests: list[GeneratedTest], findings: list[StaticFinding]) -> Preparation:
    return Preparation(
        source_sha256=hashlib.sha256(code.encode()).hexdigest(),
        bundle_sha256=bundle_hash(code, tests), provider=provider,
        requirements=reqs, tests=tests, static_findings=findings,
        requirement_states=requirement_states(reqs, tests, []),
    )


def validate_results(tests: list[GeneratedTest], results: list[TestResult]) -> list[TestResult]:
    expected = {test.id: test.requirement_id for test in tests}
    if len(expected) != len(tests):
        raise RunnerContractError("Prepared test identifiers must be unique")
    try:
        results = [TestResult.model_validate(result.model_dump(warnings=False)) for result in results]
    except (ValidationError, AttributeError):
        raise RunnerContractError("Runner must return validated TestResult models") from None
    seen = set()
    for result in results:
        if result.test_id in seen or result.test_id not in expected:
            raise RunnerContractError("Runner returned a duplicate or unknown test ID")
        if result.requirement_id != expected[result.test_id] or result.duration_ms < 0:
            raise RunnerContractError("Runner returned a mismatched requirement or negative duration")
        seen.add(result.test_id)
    if seen != expected.keys():
        raise RunnerContractError("Runner must return exactly one result per generated test")
    lookup = {result.test_id: result for result in results}
    return [lookup[test.id] for test in tests]


def finish(preparation: Preparation, code: str, results: list[TestResult], *,
           bundle_sha256: str, include_fixes: bool = True) -> Verification:
    """Consume B's results without regenerating tests or changing their identifiers."""
    digest = bundle_hash(code, preparation.tests)
    if (digest != preparation.bundle_sha256 or digest != bundle_sha256
            or hashlib.sha256(code.encode()).hexdigest() != preparation.source_sha256):
        raise RunnerContractError("Results must refer to the exact prepared source/test bundle")
    checked = validate_results(preparation.tests, results)
    states = requirement_states(preparation.requirements, preparation.tests, checked)
    with using_provider(preparation.provider):
        fixes = suggest_fixes(code, checked) if include_fixes else []
    return Verification(
        preparation=preparation.model_copy(update={"awaiting_runner": False}),
        results=checked, requirement_states=states, fixes=fixes,
        verified=bool(states) and all(state.state == "passed" for state in states)
        and not preparation.static_findings,
    )


def verify(spec_text: str, code: str, runner: Runner, *,
           provider: str | None = None, include_fixes: bool = True) -> Verification:
    prepared = prepare(spec_text, code, provider=provider)
    results = runner(prepared.tests, code) if prepared.tests else []
    return finish(prepared, code, results, bundle_sha256=prepared.bundle_sha256,
                  include_fixes=include_fixes)
