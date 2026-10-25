"""Exercise NVIDIA inference without executing model-generated source code."""

import json
import os
from pathlib import Path

from .api import analyze_code, generate_tests, parse_spec
from .provider import ROOT, ProviderError


def main() -> None:
    # Explicit selection prevents accidentally consuming reserved Nebius credits.
    os.environ["SPECGUARD_PROVIDER"] = "nvidia"
    fixture = json.loads((Path(__file__).parent / "fixtures" / "divide.json").read_text("utf-8"))
    print("Checking live requirement parsing...", flush=True)
    reqs = parse_spec(fixture["spec"])
    if not reqs:
        raise ProviderError("Live parser returned no requirements for the division demo")
    print("Checking live test generation...", flush=True)
    tests = generate_tests(reqs, fixture["bad_code"])
    if not tests:
        raise ProviderError("Live generator returned no tests for the division demo")
    print("Checking ambiguity handling...", flush=True)
    vague = parse_spec("The application must be fast.")
    if not vague or not all(req.ambiguous and req.clarification_note for req in vague):
        raise ProviderError("Live parser did not flag the vague performance specification")
    findings = analyze_code(fixture["bad_code"], reqs)
    report = {
        "provider": "nvidia", "generated_code_executed": False,
        "spec": fixture["spec"], "submission": fixture["bad_code"],
        "requirements": [req.model_dump() for req in reqs],
        "tests": [test.model_dump() for test in tests],
        "static_findings": [finding.model_dump() for finding in findings],
        "ambiguous_requirements": [req.model_dump() for req in vague],
        "untested_requirement_ids": [req.id for req in reqs
                                     if req.id not in {test.requirement_id for test in tests}],
    }
    output = ROOT / "artifacts" / "nvidia-live-check.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if report["untested_requirement_ids"]:
        raise ProviderError("Live demo has coverage gaps; see artifacts/nvidia-live-check.json")
    print(f"NVIDIA live check succeeded: {len(reqs)} requirements, {len(tests)} test modules.")
    print("Vague performance requirement flagged for clarification.")
    print("Generated tests were not executed. Nebius was not used.")
    print(f"Report: {output}")


if __name__ == "__main__":
    try:
        main()
    except ProviderError as exc:
        raise SystemExit(str(exc)) from None
