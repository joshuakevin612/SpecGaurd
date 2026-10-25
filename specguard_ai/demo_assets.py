"""Export checked-in fixtures for local demos and Person B's integration tests."""

import json
from pathlib import Path

from .provider import ROOT


def load_demo(name: str) -> dict:
    if name not in {"add", "divide", "cart", "ambiguous"}:
        raise ValueError("Unknown demo")
    return json.loads((Path(__file__).parent / "fixtures" / f"{name}.json").read_text("utf-8"))


def export_demos() -> Path:
    destination = ROOT / "demos"
    for name in ("add", "divide", "cart", "ambiguous"):
        fixture = load_demo(name)
        folder = destination / name
        folder.mkdir(parents=True, exist_ok=True)
        for filename, content in {
            "spec.txt": fixture["spec"], "good.py": fixture["good_code"],
            "bad.py": fixture["bad_code"],
        }.items():
            (folder / filename).write_text(content, encoding="utf-8")
        for key in ("requirements", "tests"):
            (folder / f"expected_{key}.json").write_text(
                json.dumps(fixture[key], indent=2), encoding="utf-8")
        (folder / "request.json").write_text(json.dumps({
            "action": "prepare", "spec_text": fixture["spec"], "code": fixture["bad_code"],
        }, indent=2), encoding="utf-8")
    return destination


if __name__ == "__main__":
    print(export_demos())
