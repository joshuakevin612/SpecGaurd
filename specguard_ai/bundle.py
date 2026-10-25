"""Write a runner-ready bundle without executing uploaded or generated Python."""

import argparse
import json
from datetime import UTC, datetime

from .demo_assets import load_demo
from .provider import ROOT, ProviderError
from .test_validation import InvalidGeneratedTest
from .workflow import prepare


def export_bundle(demo: str, provider: str):
    fixture = load_demo(demo)
    directory = ROOT / "artifacts" / "bundles" / provider / demo
    directory.mkdir(parents=True, exist_ok=True)
    try:
        prepared = prepare(fixture["spec"], fixture["bad_code"], provider=provider)
    except InvalidGeneratedTest as exc:
        rejected = directory / "rejected_test.json"
        rejected.write_text(exc.test.model_dump_json(indent=2), encoding="utf-8")
        raise ProviderError(f"{exc}; diagnostic test saved to {rejected}") from None
    (directory / "submission.py").write_text(fixture["bad_code"], encoding="utf-8")
    (directory / "spec.txt").write_text(fixture["spec"], encoding="utf-8")
    (directory / "preparation.json").write_text(prepared.model_dump_json(indent=2), encoding="utf-8")
    for stale in ("rejected_test.json", "reference-checks.json"):
        (directory / stale).unlink(missing_ok=True)
    tests = directory / "tests"
    tests.mkdir(exist_ok=True)
    # Dedicated directory holds only files from this export; old modules must not run.
    for old in tests.glob("test_TEST_*.py"):
        old.unlink()
    for test in prepared.tests:
        filename = f"test_{test.id.replace('-', '_')}.py"
        (tests / filename).write_text(test.pytest_code, encoding="utf-8")
    (directory / "manifest.json").write_text(json.dumps({
        "at": datetime.now(UTC).isoformat(),
        "provider": provider, "bundle_sha256": prepared.bundle_sha256,
        "source_sha256": prepared.source_sha256, "generated_tests_executed": False,
        "tests": [{"file": f"tests/test_{test.id.replace('-', '_')}.py",
                   "test_id": test.id, "requirement_id": test.requirement_id}
                  for test in prepared.tests],
        "ambiguous_requirement_ids": [req.id for req in prepared.requirements if req.ambiguous],
        "uncovered_requirement_ids": [req.id for req in prepared.requirements
                                      if not req.ambiguous and req.id not in
                                      {test.requirement_id for test in prepared.tests}],
    }, indent=2), encoding="utf-8")
    return directory, prepared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo", choices=["add", "divide", "cart", "ambiguous"])
    parser.add_argument("--provider", choices=["mock", "nvidia"], default="mock")
    args = parser.parse_args()
    directory, prepared = export_bundle(args.demo, args.provider)
    print(f"Bundle: {directory}")
    print(f"{len(prepared.requirements)} requirements; {len(prepared.tests)} unexecuted test modules")


if __name__ == "__main__":
    try:
        main()
    except ProviderError as exc:
        raise SystemExit(str(exc)) from None
