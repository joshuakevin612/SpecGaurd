"""Run real NeMo prepare/finish invocations with mocks and the reference evaluator."""

import argparse
import asyncio
import json
import os

from .demo_assets import load_demo
from .demo_evaluator import check_division
from .provider import ROOT
from .workflow import Preparation, Verification


async def check(provider: str):
    os.environ.setdefault("NAT_TELEMETRY_ENABLED", "false")
    from nat.runtime.loader import load_workflow

    fixture = load_demo("divide")
    async with load_workflow(ROOT / "configs" / f"{provider}.yml") as manager:
        request = json.dumps({"action": "prepare", "spec_text": fixture["spec"],
                              "code": fixture["bad_code"]})
        async with manager.run(request) as runner:
            prepared = Preparation.model_validate_json(await runner.result(to_type=str))
        if not prepared.tests or not prepared.awaiting_runner:
            raise ValueError("NeMo did not prepare the expected test bundle")
        # For the mock fixture only, these exact test/requirement IDs match the oracle.
        if provider == "mock":
            results = check_division(fixture["bad_code"])
            request = json.dumps({
                "action": "finish", "code": fixture["bad_code"],
                "preparation": prepared.model_dump(),
                "results": [result.model_dump() for result in results],
                "bundle_sha256": prepared.bundle_sha256,
            })
            async with manager.run(request) as runner:
                verified = Verification.model_validate_json(await runner.result(to_type=str))
            if verified.verified or not verified.fixes:
                raise ValueError("NeMo did not route failed results to the fix suggester")
            after = check_division(verified.fixes[0].patched_code)
            if not all(result.status == "passed" for result in after):
                raise ValueError("Reference repair checks failed")
            report = {"provider": provider, "prepare": prepared.model_dump(),
                      "finish": verified.model_dump(), "reference_retest": [r.model_dump() for r in after],
                      "production_sandbox_verified": False}
        else:
            report = {"provider": provider, "prepare": prepared.model_dump(),
                      "production_sandbox_verified": False}
    output = ROOT / "artifacts" / f"{provider}-nemo-check.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"NeMo {provider} workflow validated. Report: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["mock", "nvidia"], default="mock")
    args = parser.parse_args()
    asyncio.run(check(args.provider))


if __name__ == "__main__":
    main()
