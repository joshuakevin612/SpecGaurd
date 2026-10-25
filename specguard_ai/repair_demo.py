"""Validate a model-proposed division repair with a bounded AST reference oracle."""

import argparse
import json
from datetime import UTC, datetime

from .api import suggest_fixes
from .demo_assets import load_demo
from .demo_evaluator import UnsupportedDemoCode, check_division
from .provider import ROOT, ProviderError, using_provider


def repair_demo(provider: str) -> dict:
    fixture = load_demo("divide")
    before = check_division(fixture["bad_code"])
    with using_provider(provider):
        fixes = suggest_fixes(fixture["bad_code"], before)
    candidates = []
    seen = set()
    for fix in fixes:
        if fix.patched_code in seen:
            continue
        seen.add(fix.patched_code)
        try:
            after = check_division(fix.patched_code)
            candidates.append({"patched_code": fix.patched_code,
                               "results": [result.model_dump() for result in after],
                               "reference_checks_passed": all(r.status == "passed" for r in after)})
        except UnsupportedDemoCode as exc:
            candidates.append({"patched_code": fix.patched_code,
                               "reference_checks_passed": False, "unsupported": str(exc)})
    report = {
        "at": datetime.now(UTC).isoformat(), "provider": provider,
        "execution_mode": "bounded_division_ast_interpreter",
        "generated_pytest_executed": False, "production_sandbox_verified": False,
        "requirements": fixture["requirements"], "before": [r.model_dump() for r in before],
        "fixes": [fix.model_dump() for fix in fixes], "candidates": candidates,
        "repair_validated_on_reference_cases": any(c["reference_checks_passed"] for c in candidates),
    }
    output = ROOT / "artifacts" / f"{provider}-repair-demo.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["mock", "nvidia"], default="mock")
    args = parser.parse_args()
    report = repair_demo(args.provider)
    passed = report["repair_validated_on_reference_cases"]
    print(f"{args.provider}: reference repair validation {'passed' if passed else 'failed'}")
    print("Production pytest sandbox verification is still pending.")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except (ProviderError, UnsupportedDemoCode) as exc:
        raise SystemExit(str(exc)) from None
