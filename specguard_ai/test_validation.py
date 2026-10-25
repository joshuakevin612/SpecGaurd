"""Reject unusable test modules. This is not a security sandbox."""

import ast

from .provider import ProviderError


class InvalidGeneratedTest(ProviderError):
    def __init__(self, test, reason):
        self.test = test
        super().__init__(f"{test.id} / {test.requirement_id}: {reason}")


def validate_test(code: str) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ProviderError(f"Generated test is not valid Python at line {exc.lineno}: {exc.msg}") from None
    functions = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
    if not functions:
        raise ProviderError("Generated module has no top-level pytest test function")
    pytest_aliases = {"pytest"}
    submission_functions = set()
    submission_modules = set()
    direct_skips = set()
    direct_raises = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "submission":
                    submission_modules.add(alias.asname or "submission")
                if alias.name == "pytest":
                    pytest_aliases.add(alias.asname or "pytest")
        if isinstance(node, ast.ImportFrom):
            if node.module == "submission":
                submission_functions.update(alias.asname or alias.name for alias in node.names)
            if node.module == "pytest":
                direct_skips.update(alias.asname or alias.name for alias in node.names
                                    if alias.name in {"skip", "xfail"})
                direct_raises.update(alias.asname or alias.name for alias in node.names
                                     if alias.name == "raises")
    has_observation = False
    calls_submission = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            if isinstance(node.test, ast.Constant):
                raise ProviderError("Generated tests must not use constant assertions")
            has_observation = True
        if isinstance(node, ast.Call):
            is_raises = (isinstance(node.func, ast.Name) and node.func.id in direct_raises) or (
                isinstance(node.func, ast.Attribute) and node.func.attr == "raises"
                and isinstance(node.func.value, ast.Name) and node.func.value.id in pytest_aliases)
            if is_raises:
                has_observation = True
                # pytest.raises(ValueError, submitted_function, args...) is valid too.
                if len(node.args) >= 2:
                    callback = node.args[1]
                    if isinstance(callback, ast.Name) and callback.id in submission_functions:
                        calls_submission = True
                    if (isinstance(callback, ast.Attribute) and isinstance(callback.value, ast.Name)
                            and callback.value.id in submission_modules):
                        calls_submission = True
            if isinstance(node.func, ast.Name):
                if node.func.id in direct_skips:
                    raise ProviderError("Generated tests must not skip or xfail")
                if node.func.id in submission_functions:
                    calls_submission = True
            if isinstance(node.func, ast.Attribute):
                root = node.func.value
                while isinstance(root, ast.Attribute):
                    root = root.value
                if isinstance(root, ast.Name):
                    if root.id in submission_modules:
                        calls_submission = True
                    if root.id in pytest_aliases:
                        if node.func.attr in {"skip", "skipif", "xfail"}:
                            raise ProviderError("Generated tests must not skip or xfail")
                        if node.func.attr == "raises":
                            has_observation = True
        # Also catch decorators such as @pytest.mark.skip without parentheses.
        if isinstance(node, ast.Attribute) and node.attr in {"skip", "skipif", "xfail"}:
            root = node.value
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in pytest_aliases:
                raise ProviderError("Generated tests must not skip or xfail")
    if not calls_submission or not has_observation:
        raise ProviderError("Generated tests must call submission and assert behavior or exceptions")
