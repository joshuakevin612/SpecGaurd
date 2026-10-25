"""Conservative, requirement-linked AST heuristics; never a runtime verdict."""

import ast
import builtins
import re

from shared.schemas import Requirement, StaticFinding


def analyze(code: str, reqs: list[Requirement]) -> list[StaticFinding]:
    eligible = [req for req in reqs if not req.ambiguous]
    if not eligible:
        return []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [StaticFinding(requirement_id=req.id, line=exc.lineno or 1,
                              message=f"SG001 Python syntax error: {exc.msg}") for req in eligible]
    functions = {node.name: node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def call_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{call_name(node.value)}.{node.attr}"
        return ""

    findings = []
    seen = set()

    def add(req: Requirement, line: int, rule: str, message: str) -> None:
        key = (req.id, line, rule)
        if key not in seen:
            seen.add(key)
            findings.append(StaticFinding(
                requirement_id=req.id, line=line,
                message=f"{rule} Potential violation: {message} Static heuristic; verify at runtime.",
            ))

    for req in eligible:
        text = req.text + " " + req.measurable_criteria
        names = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", text)) - set(dir(builtins))
        for name in sorted(names - functions.keys()):
            add(req, 1, "SG002", f"expected top-level function '{name}' is missing.")
        # Only inspect named functions for semantics; do not blame unrelated helpers.
        scoped = [node for name in names & functions.keys() for node in ast.walk(functions[name])]
        if re.search(r"\btrue division\b|\ba\s*/\s*b\b", text, re.I):
            for node in scoped:
                if isinstance(node, ast.BinOp) and isinstance(node.op, ast.FloorDiv):
                    add(req, node.lineno, "SG003", "floor division may discard a required fraction.")
        if re.search(r"\braise[sd]?\b.*\b\w*Error\b", text, re.I):
            for node in scoped:
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    add(req, node.lineno, "SG004", "a bare except can suppress required exceptions.")
        prohibited = bool(re.search(r"\b(must not|shall not|never|without|no)\b", text, re.I))
        if req.category == "security" and prohibited:
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = call_name(node.func)
                if re.search(r"\b(eval|exec|dynamic execution|arbitrary code)\b", text, re.I):
                    if name in {"eval", "exec", "builtins.eval", "builtins.exec"}:
                        add(req, node.lineno, "SG005", f"dynamic execution through {name}().")
                if re.search(r"\bshell\b", text, re.I) and name.startswith("subprocess."):
                    if any(kw.arg == "shell" and isinstance(kw.value, ast.Constant)
                           and kw.value.value is True for kw in node.keywords):
                        add(req, node.lineno, "SG006", "subprocess call explicitly enables a shell.")
    return sorted(findings, key=lambda item: (item.requirement_id, item.line, item.message))
