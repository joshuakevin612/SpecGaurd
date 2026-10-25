"""Shared contract. Coordinate with both owners before changing these models."""

from typing import Literal, Optional

from pydantic import BaseModel


class Requirement(BaseModel):
    id: str
    text: str
    category: Literal["functional", "performance", "security", "data"]
    measurable_criteria: str
    ambiguous: bool = False
    clarification_note: Optional[str] = None


class GeneratedTest(BaseModel):
    id: str
    requirement_id: str
    pytest_code: str
    description: str


class StaticFinding(BaseModel):
    requirement_id: str
    line: int
    message: str


class TestResult(BaseModel):
    test_id: str
    requirement_id: str
    status: Literal["passed", "failed", "error", "timeout", "flaky"]
    output: str
    duration_ms: int


class FixSuggestion(BaseModel):
    requirement_id: str
    explanation: str
    patched_code: str
