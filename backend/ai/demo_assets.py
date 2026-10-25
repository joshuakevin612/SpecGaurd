"""Bundled fixtures used by the workbench demo loader."""
import json
from pathlib import Path

def load_demo(name: str) -> dict:
    if name not in {"add", "divide", "cart", "ambiguous"}:
        raise ValueError("Unknown demo")
    return json.loads((Path(__file__).parent / "fixtures" / f"{name}.json").read_text("utf-8"))
