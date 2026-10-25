"""Local interface for offline demos and explicit cloud connection checks."""

import argparse
import json
import os
from pathlib import Path

from shared.schemas import TestResult

from .api import analyze_code, generate_tests, parse_spec, suggest_fixes
from .provider import ProviderError, provider_name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Run a bundled fixture without API calls")
    demo.add_argument("name", choices=["add", "divide", "cart", "ambiguous"], default="divide", nargs="?")
    demo.add_argument("--broken", action="store_true")
    check = sub.add_parser("check", help="Make one small, billable model request")
    check.add_argument("--provider", required=True, choices=["nebius", "nvidia"])
    inspect = sub.add_parser("inspect", help="Parse spec and generate tests; does not run code")
    inspect.add_argument("--spec", type=Path, required=True)
    inspect.add_argument("--code", type=Path, required=True)
    inspect.add_argument("--provider", choices=["mock", "nebius", "nvidia"])
    fixes = sub.add_parser("fixes", help="Suggest repairs from a JSON array of TestResults")
    fixes.add_argument("--code", type=Path, required=True)
    fixes.add_argument("--results", type=Path, required=True)
    fixes.add_argument("--provider", required=True, choices=["nebius", "nvidia"])
    args = parser.parse_args()
    if args.command == "demo":
        os.environ["SPECGUARD_PROVIDER"] = "mock"
    elif args.provider:
        os.environ["SPECGUARD_PROVIDER"] = args.provider
    try:
        if args.command == "check":
            reqs = parse_spec("Implement add(a, b) returning the sum of two integers.")
            if not reqs:
                raise ProviderError("Connection returned no requirements; check failed")
            print(f"{args.provider}: connection and schema validation succeeded.")
            return
        if args.command == "fixes":
            results = [TestResult.model_validate(item)
                       for item in json.loads(args.results.read_text("utf-8"))]
            suggestions = suggest_fixes(args.code.read_text("utf-8"), results)
            print(json.dumps([item.model_dump() for item in suggestions], indent=2))
            return
        if args.command == "demo":
            fixture = json.loads((Path(__file__).parent / "fixtures" /
                                  f"{args.name}.json").read_text("utf-8"))
            spec = fixture["spec"]
            code = fixture["bad_code" if args.broken else "good_code"]
        else:
            spec, code = args.spec.read_text("utf-8"), args.code.read_text("utf-8")
        reqs = parse_spec(spec)
        tests = generate_tests(reqs, code)
        findings = analyze_code(code, reqs)
        covered = {test.requirement_id for test in tests}
        print(json.dumps({
            "provider": provider_name(), "executed": False,
            "requirements": [item.model_dump() for item in reqs],
            "tests": [item.model_dump() for item in tests],
            "static_findings": [item.model_dump() for item in findings],
            "untested_requirement_ids": [req.id for req in reqs if req.id not in covered],
        }, indent=2))
    except (ProviderError, ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
