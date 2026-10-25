"""NeMo Agent Toolkit step registrations and a two-phase verification workflow."""

import asyncio
import json
from typing import Literal

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.component_ref import FunctionRef
from nat.data_models.function import FunctionBaseConfig
from pydantic import BaseModel, ConfigDict

from shared.schemas import FixSuggestion, GeneratedTest, Requirement, StaticFinding, TestResult

from .api import analyze_code, generate_tests, parse_spec, suggest_fixes
from .provider import using_provider
from .workflow import Preparation, assemble_preparation, finish


class StepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spec_text: str = ""
    code: str = ""
    requirements: list[Requirement] = []
    results: list[TestResult] = []


class WorkflowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["prepare", "finish"] = "prepare"
    spec_text: str = ""
    code: str
    preparation: Preparation | None = None
    results: list[TestResult] | None = None
    bundle_sha256: str | None = None


class SpecGuardStepConfig(FunctionBaseConfig, name="specguard_step"):
    operation: Literal["parse_spec", "generate_tests", "analyze_code", "suggest_fixes"]
    provider: Literal["mock", "nvidia", "nebius"] = "mock"


@register_function(config_type=SpecGuardStepConfig)
async def register_step(config: SpecGuardStepConfig, builder: Builder):
    def perform(value: StepInput):
        with using_provider(config.provider):
            if config.operation == "parse_spec":
                result = parse_spec(value.spec_text)
            elif config.operation == "generate_tests":
                result = generate_tests(value.requirements, value.code)
            elif config.operation == "analyze_code":
                result = analyze_code(value.code, value.requirements)
            else:
                result = suggest_fixes(value.code, value.results)
        return json.dumps([item.model_dump() for item in result])

    async def respond(message: str) -> str:
        value = StepInput.model_validate_json(message)
        return await asyncio.to_thread(perform, value)

    yield FunctionInfo.from_fn(respond, description=f"SpecGuard {config.operation}")


class SpecGuardWorkflowConfig(FunctionBaseConfig, name="specguard_workflow"):
    provider: Literal["mock", "nvidia", "nebius"] = "mock"
    parser: FunctionRef = "parse_requirements"
    generator: FunctionRef = "generate_tests"
    analyzer: FunctionRef = "analyze_code"
    fixer: FunctionRef = "suggest_fixes"


@register_function(config_type=SpecGuardWorkflowConfig)
async def register_workflow(config: SpecGuardWorkflowConfig, builder: Builder):
    refs = [config.parser, config.generator, config.analyzer, config.fixer]
    for ref in refs:
        step_config = builder.get_function_config(ref)
        if step_config.provider != config.provider:
            raise ValueError("All SpecGuard steps must use the workflow's selected provider")
    parser, generator, analyzer, fixer = [await builder.get_function(ref) for ref in refs]

    async def respond(message: str) -> str:
        value = WorkflowInput.model_validate_json(message)
        if value.action == "prepare":
            if value.preparation is not None or value.results is not None:
                raise ValueError("Preparation must not include prior results")
            reqs = [Requirement.model_validate(item) for item in json.loads(await parser.ainvoke(
                StepInput(spec_text=value.spec_text).model_dump_json()))]
            payload = StepInput(code=value.code, requirements=reqs).model_dump_json()
            generated = await generator.ainvoke(payload)
            analyzed = await analyzer.ainvoke(payload)
            prepared = assemble_preparation(
                value.code, config.provider, reqs,
                [GeneratedTest.model_validate(item) for item in json.loads(generated)],
                [StaticFinding.model_validate(item) for item in json.loads(analyzed)],
            )
            return prepared.model_dump_json()
        if value.preparation is None or value.results is None or value.bundle_sha256 is None:
            raise ValueError("Finish needs preparation, results and bundle_sha256")
        if value.preparation.provider != config.provider:
            raise ValueError("Finish must use the provider from the original preparation")
        verified = finish(value.preparation, value.code, value.results,
                          bundle_sha256=value.bundle_sha256, include_fixes=False)
        if any(result.status == "failed" for result in verified.results):
            response = await fixer.ainvoke(StepInput(code=value.code, results=value.results).model_dump_json())
            verified.fixes = [FixSuggestion.model_validate(item) for item in json.loads(response)]
        return verified.model_dump_json()

    yield FunctionInfo.from_fn(respond, description=(
        "Prepare requirements/tests/static analysis, then resume with sandbox results for fixes."
    ))
