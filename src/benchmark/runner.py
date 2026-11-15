"""Entry functions for the benchmark runner."""

import logging
from contextlib import AsyncExitStack
from pathlib import Path

from pydantic_evals import Case, Dataset

from ..store_agent.store_agent import StoreAgent
from .environment import prepare_environment
from .models import create_model, login_chatgpt
from .schemas.config import RunnerConfig
from .schemas.scenarios import Scenario

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

    dataset = Dataset[Scenario, list[str], None](
        name="store-agent-security-benchmark",
        cases=[Case(name=scenario.id, inputs=scenario) for scenario in scenarios],
    )
    chatgpt_provider = None

    async with AsyncExitStack() as resources:
        for model_config in config.models:
            if model_config.backend == "openai_oauth" and chatgpt_provider is None:
                chatgpt_provider = await login_chatgpt()
                await resources.enter_async_context(chatgpt_provider)

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
                        responses: list[str] = []
                        for turn, prompt in enumerate(scenario.prompts, start=1):
                            logger.info(
                                "Scenario %s, turn %s/%s",
                                scenario.id,
                                turn,
                                len(scenario.prompts),
                            )
                            result = await agent.run(prompt)
                            responses.append(result.output)
                        return responses

                report = await dataset.evaluate(
                    run_scenario,
                    name=model_config.id,
                    repeat=config.repetitions,
                    max_concurrency=1,
                    progress=True,
                )
                report.print(include_output=True)
