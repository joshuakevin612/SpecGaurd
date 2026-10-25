"""Opt-in, bounded NVIDIA + Docker demo gate; incurs provider usage."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
    from backend.runner.pytest_runner import PytestRunner
    from specguard_ai.api import suggest_fixes
    from specguard_ai.budget import run_budget
    from specguard_ai.demo_assets import load_demo
    from specguard_ai.provider import using_provider
    from specguard_ai.workflow import prepare

    os.environ['SPECGUARD_TIMEOUT_SECONDS'] = '20'
    demo = load_demo('add')
    runner = PytestRunner()
    with run_budget(100) as budget, using_provider('nvidia'):
        prepared = prepare(demo['spec'], demo['bad_code'], provider='nvidia')
        bad = runner.run_tests(prepared.tests, demo['bad_code'], deadline=budget.deadline)
        good = runner.run_tests(prepared.tests, demo['good_code'], deadline=budget.deadline)
        fixes = suggest_fixes(demo['bad_code'], bad)
        repaired = runner.run_tests(prepared.tests, fixes[0].patched_code,
                                    deadline=budget.deadline) if fixes else []
    passed = (any(r.status == 'failed' for r in bad) and bool(good)
              and all(r.status == 'passed' for r in good) and bool(repaired)
              and all(r.status == 'passed' for r in repaired))
    report = {'provider': 'nvidia', 'model': os.getenv('NVIDIA_MODEL'),
              'code_model': os.getenv('NVIDIA_CODE_MODEL'), 'tests': len(prepared.tests),
              'bad': [r.model_dump() for r in bad], 'good': [r.model_dump() for r in good],
              'repaired': [r.model_dump() for r in repaired], 'passed': passed,
              'runtime': runner.runtime or 'Docker default (not gVisor)'}
    output = ROOT / 'artifacts/release-live-smoke.json'
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'live_smoke_passed': passed, 'tests': len(prepared.tests), 'report': str(output)}))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
