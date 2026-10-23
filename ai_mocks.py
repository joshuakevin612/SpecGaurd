"""
Mock implementations of Person A's AI functions.

These are placeholders that will be replaced by actual NVIDIA Nemotron calls.
They allow the backend to develop and test independently.
"""

import uuid
from typing import List
from shared_schemas import Requirement, GeneratedTest, StaticFinding, FixSuggestion


def parse_spec(spec_text: str) -> List[Requirement]:
    """
    Mock: Parse a specification and extract requirements.
    
    Person A will replace this with actual AI-powered parsing.
    """
    requirements = []
    
    # Simple mock: split by lines and create requirements
    lines = spec_text.strip().split("\n")
    for i, line in enumerate(lines):
        if line.strip():
            req = Requirement(
                id=f"req_{uuid.uuid4().hex[:8]}",
                text=line.strip(),
                category="functional",  # Default category
                measurable_criteria=f"Verify that {line.strip()}",
                ambiguous=False,
            )
            requirements.append(req)
    
    return requirements


def generate_tests(reqs: List[Requirement], code: str) -> List[GeneratedTest]:
    """
    Mock: Generate Pytest tests from requirements.
    
    Person A will replace this with actual AI-powered test generation.
    """
    tests = []
    
    for req in reqs:
        # Create a simple test template for each requirement
        test_code = f'''
def test_requirement_{req.id}():
    """Test: {req.text}"""
    # TODO: Implement test for requirement {req.id}
    assert True, "Mock test - replace with actual test"
'''
        test = GeneratedTest(
            id=f"test_{uuid.uuid4().hex[:8]}",
            requirement_id=req.id,
            pytest_code=test_code,
            description=f"Auto-generated test for: {req.text[:50]}",
        )
        tests.append(test)
    
    return tests


def analyze_code(code: str, reqs: List[Requirement]) -> List[StaticFinding]:
    """
    Mock: Perform static analysis on the code.
    
    Person A will replace this with actual AST-based analysis.
    """
    findings = []
    
    # Mock: look for simple patterns
    lines = code.split("\n")
    
    for line_num, line in enumerate(lines, 1):
        # Trivial mock: flag any TODO comments
        if "TODO" in line or "FIXME" in line:
            finding = StaticFinding(
                requirement_id="",  # Would be populated by AI
                line=line_num,
                message=f"Found TODO/FIXME: {line.strip()}",
            )
            findings.append(finding)
    
    return findings


def suggest_fixes(code: str, test_results: List) -> List[FixSuggestion]:
    """
    Mock: Suggest fixes based on test results.
    
    Person A will replace this with actual AI-powered fix generation.
    """
    fixes = []
    
    # Mock: for any failed test, suggest adding a print statement
    for result in test_results:
        if result.get("status") == "failed":
            fix = FixSuggestion(
                requirement_id=result.get("requirement_id", ""),
                explanation="Add logging to debug the failure",
                patched_code=code + "\n\n# Added debug logging\nprint('Debug info here')",
            )
            fixes.append(fix)
    
    return fixes
