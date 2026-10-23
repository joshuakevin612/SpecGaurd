"""
Verification pipeline service.

Orchestrates the end-to-end verification workflow:
1. Parse spec
2. Generate tests
3. Analyze code
4. Run tests
5. Suggest fixes
6. Store results
"""

import uuid
from typing import List
from shared_schemas import Requirement, GeneratedTest, TestResult
from backend.database.db import (
    ProjectDB,
    RequirementDB,
    GeneratedTestDB,
    TestResultDB,
    StaticFindingDB,
    FixSuggestionDB,
)
from backend.services.ai_mocks import (
    parse_spec,
    generate_tests,
    analyze_code,
    suggest_fixes,
)
from backend.runner.pytest_runner import PytestRunner


class VerificationService:
    """Orchestrates the complete verification workflow."""

    def __init__(self, use_docker: bool = False):
        """
        Initialize the verification service.
        
        Args:
            use_docker: Whether to run tests in Docker
        """
        self.runner = PytestRunner(use_docker=use_docker)

    def verify(
        self,
        project_id: str,
        specification: str,
        source_code: str,
        use_docker: bool = False,
    ) -> dict:
        """
        Run a complete verification on a project.
        
        Args:
            project_id: ID of the project
            specification: The specification text
            source_code: The source code to verify
            use_docker: Whether to use Docker for test execution
        
        Returns:
            Dict with verification results summary
        """
        # Step 1: Parse specification
        requirements = parse_spec(specification)
        
        # Store requirements in database
        for req in requirements:
            RequirementDB.create_requirement(
                req_id=req.id,
                project_id=project_id,
                text=req.text,
                category=req.category,
                measurable_criteria=req.measurable_criteria,
                ambiguous=req.ambiguous,
                clarification_note=req.clarification_note,
            )

        # Step 2: Generate tests
        generated_tests = generate_tests(requirements, source_code)
        
        # Store generated tests
        for test in generated_tests:
            GeneratedTestDB.create_test(
                test_id=test.id,
                project_id=project_id,
                requirement_id=test.requirement_id,
                pytest_code=test.pytest_code,
                description=test.description,
            )

        # Step 3: Analyze code (static analysis)
        static_findings = analyze_code(source_code, requirements)
        
        for finding in static_findings:
            StaticFindingDB.create_finding(
                project_id=project_id,
                requirement_id=finding.requirement_id,
                line_number=finding.line,
                message=finding.message,
            )

        # Step 4: Run tests
        test_results = self.runner.run_tests(generated_tests, source_code)
        
        # Store test results
        for result in test_results:
            TestResultDB.create_result(
                project_id=project_id,
                test_id=result.test_id,
                requirement_id=result.requirement_id,
                status=result.status,
                output=result.output,
                duration_ms=result.duration_ms,
            )

        # Step 5: Suggest fixes for failed tests
        failed_results = [r for r in test_results if r.status in ["failed", "error"]]
        if failed_results:
            fix_suggestions = suggest_fixes(source_code, [r.dict() for r in failed_results])
            
            for suggestion in fix_suggestions:
                FixSuggestionDB.create_suggestion(
                    project_id=project_id,
                    requirement_id=suggestion.requirement_id,
                    explanation=suggestion.explanation,
                    patched_code=suggestion.patched_code,
                )

        # Compile summary
        passed = len([r for r in test_results if r.status == "passed"])
        failed = len([r for r in test_results if r.status == "failed"])
        errors = len([r for r in test_results if r.status == "error"])
        timeouts = len([r for r in test_results if r.status == "timeout"])
        flaky = len([r for r in test_results if r.status == "flaky"])

        return {
            "project_id": project_id,
            "requirements_count": len(requirements),
            "tests_count": len(generated_tests),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "timeouts": timeouts,
            "flaky": flaky,
            "total_results": len(test_results),
        }

    def retest(self, project_id: str, updated_code: str) -> dict:
        """
        Re-run verification after code has been updated.
        
        Args:
            project_id: ID of the project
            updated_code: The updated source code
        
        Returns:
            Dict with new verification results
        """
        # Get the project and previous requirements
        project = ProjectDB.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        requirements = RequirementDB.get_requirements(project_id)
        tests = GeneratedTestDB.get_tests(project_id)

        # Convert DB rows back to Requirement and GeneratedTest objects
        reqs = [
            Requirement(
                id=req["id"],
                text=req["text"],
                category=req["category"],
                measurable_criteria=req["measurable_criteria"],
                ambiguous=req["ambiguous"],
                clarification_note=req["clarification_note"],
            )
            for req in requirements
        ]

        gen_tests = [
            GeneratedTest(
                id=test["id"],
                requirement_id=test["requirement_id"],
                pytest_code=test["pytest_code"],
                description=test["description"],
            )
            for test in tests
        ]

        # Run tests with updated code
        test_results = self.runner.run_tests(gen_tests, updated_code)

        # Store new results
        for result in test_results:
            TestResultDB.create_result(
                project_id=project_id,
                test_id=result.test_id,
                requirement_id=result.requirement_id,
                status=result.status,
                output=result.output,
                duration_ms=result.duration_ms,
            )

        # Compile summary
        passed = len([r for r in test_results if r.status == "passed"])
        failed = len([r for r in test_results if r.status == "failed"])
        errors = len([r for r in test_results if r.status == "error"])
        timeouts = len([r for r in test_results if r.status == "timeout"])
        flaky = len([r for r in test_results if r.status == "flaky"])

        return {
            "project_id": project_id,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "timeouts": timeouts,
            "flaky": flaky,
            "total_results": len(test_results),
        }
