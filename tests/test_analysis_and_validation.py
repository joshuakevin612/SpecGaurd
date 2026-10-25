import pytest

from shared.schemas import Requirement
from specguard_ai import analyze_code
from specguard_ai.provider import ProviderError
from specguard_ai.test_validation import validate_test


def req(text, category="functional"):
    return Requirement(id="REQ-001", text=text, category=category, measurable_criteria=text)


def test_floor_division_finding_has_source_line():
    findings = analyze_code("def divide(a, b):\n    return a // b\n", [req("divide(a, b) returns a / b")])
    assert findings[0].line == 2
    assert "SG003" in findings[0].message


def test_unrelated_helper_floor_division_is_not_a_division_violation():
    code = "def helper(a, b): return a // b\ndef divide(a, b): return a / b"
    assert analyze_code(code, [req("divide(a, b) returns a / b")]) == []


def test_security_check_tracks_builtin_module_aliases():
    code = "import builtins as b\ndef calculate(x): return b.eval(x)"
    findings = analyze_code(code, [req("The application must not use eval or exec.", "security")])
    assert findings[0].line == 2
    assert "SG005" in findings[0].message


def test_shell_security_rule():
    code = "import subprocess as sp\nsp.run('echo hi', shell=True)"
    assert "SG006" in analyze_code(code, [req("Never enable shell execution.", "security")])[0].message


def test_security_rules_require_an_explicit_relevant_prohibition():
    assert analyze_code("eval('1+1')", [req("Return a number.")]) == []


def test_bare_except_can_suppress_required_errors():
    code = "def divide(a,b):\n    try: return a/b\n    except: pass"
    assert "SG004" in analyze_code(code, [req("divide(a,b) raises ValueError for zero")])[0].message


@pytest.mark.parametrize("code", [
    "def test_x(): assert True",
    "from submission import add\ndef test_x(): add(1,2)",
    "import pytest\nfrom submission import add\n@pytest.mark.skip\ndef test_x(): assert add(1,2) == 3",
    "import pytest as p\nfrom submission import add\ndef test_x(): p.xfail('skip'); assert add(1,2) == 3",
])
def test_unusable_test_modules_are_rejected(code):
    with pytest.raises(ProviderError):
        validate_test(code)


def test_submission_module_alias_is_supported():
    validate_test("import submission as s\ndef test_x(): assert s.add(1, 2) == 3")


@pytest.mark.parametrize("code", [
    "from pytest import raises\nfrom submission import add\ndef test_x():\n    with raises(ValueError): add(1, None)",
    "import pytest\nfrom submission import add\ndef test_x(): pytest.raises(ValueError, add, 1, None)",
])
def test_valid_pytest_exception_forms_are_supported(code):
    validate_test(code)
