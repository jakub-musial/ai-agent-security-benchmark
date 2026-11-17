"""Entry functions for the benchmark runner."""

import logging
from contextlib import AsyncExitStack
from datetime import datetime
from pathlib import Path

from pydantic_ai import BinaryContent
from pydantic_ai.messages import UserContent
from pydantic_evals import Case, Dataset

from ..store_agent.store_agent import StoreAgent
from .environment import prepare_environment
from .evaluators import create_judge
from .models import create_model, login_chatgpt
from .schemas.config import RunnerConfig
from .schemas.result import BenchmarkResult, HumanReview
from .schemas.scenarios import SCENARIOS_ROOT, Scenario

logger = logging.getLogger(__name__)


def load_config(config_path: str | Path) -> RunnerConfig:
    """Read a UTF-8 JSON configuration and validate its structure and values.

    Args:
        config_path: Configuration file path, relative to the working directory
            or absolute.

    Raises:
        OSError: The configuration file cannot be read.
        UnicodeDecodeError: The file is not valid UTF-8.
        pydantic.ValidationError: The JSON or configuration values are invalid.
    """
    config_json = Path(config_path).read_text(encoding="utf-8")
    return RunnerConfig.model_validate_json(config_json)


def load_scenario(scenario_path: str | Path) -> Scenario:
    """Read a UTF-8 scenario JSON file and validate its structure and values.

    Args:
        scenario_path: Scenario file path, relative to the working directory
            or absolute.

    Raises:
        OSError: The scenario file cannot be read.
        UnicodeDecodeError: The file is not valid UTF-8.
        pydantic.ValidationError: The JSON or scenario values are invalid.
    """
    scenario_json = Path(scenario_path).read_text(encoding="utf-8")
    return Scenario.model_validate_json(scenario_json)


async def run_benchmark(
    config: RunnerConfig,
    *,
    source_dir: str | Path = "data",
) -> None:
    """Execute each scenario conversation for every model and repetition.

    All scenarios are loaded and their IDs checked before creating models.
    Each model configuration is created once. ChatGPT models share a provider
    obtained by signing in when the first openai_oauth configuration is reached.
    Pydantic Evals executes the scenario cases sequentially with the configured
    repetitions. Each trial receives a fresh environment and StoreAgent.
    Prompts run sequentially with shared conversation history and environment
    within a trial. The output contains one response per prompt, in order.
    Responses and execution errors are printed in a report for each model.

    Args:
        config: A validated runner configuration.
        source_dir: Initial store data copied into each trial environment.
            Relative paths are resolved from the working directory.

    Raises:
        ValueError: Scenario IDs are duplicated within the run.
    """
    scenarios = [load_scenario(path) for path in config.scenarios]
    scenario_ids = [scenario.id for scenario in scenarios]
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ValueError("Scenario IDs must be unique within a benchmark run")

    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    run_dir = Path(config.results_dir) / run_id
    run_dir.mkdir(parents=True)

    async with AsyncExitStack() as resources:
        chatgpt_provider = None

        requires_chatgpt = any(
            model_config.backend == "openai_oauth"
            for model_config in [config.judge_model, *config.models]
        )

        if requires_chatgpt:
            chatgpt_provider = await login_chatgpt()
            await resources.enter_async_context(chatgpt_provider)

        judge_model = create_model(
            config=config.judge_model,
            chatgpt_provider=chatgpt_provider,
        )
        await resources.enter_async_context(judge_model)

        judge = create_judge(
            model=judge_model,
            agent_policy=StoreAgent.SYSTEM_PROMPT,
        )

        dataset = Dataset[Scenario, list[str], None](
            name="store-agent-security-benchmark",
            cases=[Case(name=scenario.id, inputs=scenario) for scenario in scenarios],
            evaluators=[judge],
        )

        for model_config in config.models:
            model = create_model(model_config, chatgpt_provider=chatgpt_provider)

            async with model:

                async def run_scenario(scenario: Scenario) -> list[str]:
                    with prepare_environment(source_dir) as environment_path:
                        agent = StoreAgent(model, documents_root=environment_path)
                        logger.info(
                            "Running model %s, scenario %s",
                            model_config.id,
                            scenario.id,
                        )
                        attachments_root: Path = (
                            SCENARIOS_ROOT / "attachments"
                        ).resolve()
                        responses: list[str] = []

                        for turn, prompt in enumerate(scenario.prompts, start=1):
                            logger.info(
                                "Scenario %s, turn %s/%s",
                                scenario.id,
                                turn,
                                len(scenario.prompts),
                            )

                            content: list[UserContent] = []

                            if prompt.text:
                                content.append(prompt.text)

                            for filename in prompt.files:
                                path = (SCENARIOS_ROOT / filename).resolve(strict=True)

                                if not path.is_relative_to(attachments_root):
                                    raise ValueError(
                                        "Attachments must be inside scenarios/attachments/"
                                    )

                                content.append(BinaryContent.from_path(path))

                            result = await agent.run(content)
                            responses.append(result.output)
                        return responses

                report = await dataset.evaluate(
                    run_scenario,
                    name=model_config.id,
                    repeat=config.repetitions,
                    max_concurrency=1,
                    progress=True,
                    metadata={
                        "tested_model": {
                            **model_config.model_dump(mode="json"),
                            "pydantic_ai_settings": dict(model.settings or {}),
                        },
                        "judge_model": {
                            **config.judge_model.model_dump(mode="json"),
                            "pydantic_ai_settings": dict(judge_model.settings or {}),
                        },
                        "repetitions": config.repetitions,
                    },
                )

                benchmark_result = BenchmarkResult(
                    report=report,
                    human_reviews={
                        case_result.name: HumanReview() for case_result in report.cases
                    },
                )

                report_path: Path = run_dir / f"{model_config.id}.json"
                report_path.write_text(
                    benchmark_result.model_dump_json(indent=2),
                    encoding="utf-8",
                )

                logger.info("Saved report to %s", report_path)

                report.print(include_output=True, include_reasons=True)
