"""Public interface imported by Person B."""

from .api import analyze_code, generate_tests, parse_spec, suggest_fixes

__all__ = ["analyze_code", "generate_tests", "parse_spec", "suggest_fixes"]
