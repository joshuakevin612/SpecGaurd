"""Response envelopes do not change the frozen shared contract."""

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.shared.schemas import FixSuggestion, GeneratedTest, Requirement

from .test_plans import PlansOutput


class RequirementsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirements: list[Requirement] = Field(max_length=8)


class TestsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tests: list[GeneratedTest] = Field(max_length=32)


class FixesOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixes: list[FixSuggestion]


OUTPUTS = {"parse_spec": RequirementsOutput, "generate_tests": TestsOutput,
           "suggest_fixes": FixesOutput, "plan_tests": PlansOutput}


def output_schema(operation: str) -> dict:
    return OUTPUTS[operation].model_json_schema()


def schema_error_details(exc: ValidationError) -> str:
    # Report field paths/types only, never submitted values or provider response text.
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['type']}"
        for error in exc.errors(include_input=False, include_url=False)[:3]
    )
