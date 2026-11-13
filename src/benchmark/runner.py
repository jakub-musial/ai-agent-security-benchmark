"""Entry functions for the benchmark runner."""

import logging
from contextlib import AsyncExitStack
from pathlib import Path

from ..store_agent.store_agent import StoreAgent
from .config import RunnerConfig
from .environment import prepare_environment
from .models import create_model, login_chatgpt

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


async def run_benchmark(
    config: RunnerConfig,
    *,
    source_dir: str | Path = "data",
) -> None:
    """Prepare models, environments, and agents for all configured trials.

    Each model configuration is created once. ChatGPT models share a provider
    obtained by signing in when the first openai_oauth configuration is reached.
    Each scenario and repetition receives a fresh environment and StoreAgent.
    This initial stage logs preparation; scenario execution, evaluation, and
    result recording will be added in subsequent iterations.

    Args:
        config: A validated runner configuration.
        source_dir: Initial store data copied into each trial environment.
            Relative paths are resolved from the working directory.
    """
    chatgpt_provider = None

    async with AsyncExitStack() as resources:
        for model_config in config.models:
            if model_config.backend == "openai_oauth" and chatgpt_provider is None:
                chatgpt_provider = await login_chatgpt()
                await resources.enter_async_context(chatgpt_provider)

            model = create_model(model_config, chatgpt_provider=chatgpt_provider)

            async with model:
                for scenario_path in config.scenarios:
                    for repetition in range(1, config.repetitions + 1):
                        with prepare_environment(source_dir) as environment_path:
                            agent = StoreAgent(model, documents_root=environment_path)
                            logger.info(
                                "Prepared %s for model %s, scenario %s, repetition %d/%d",
                                type(agent).__name__,
                                model_config.id,
                                scenario_path,
                                repetition,
                                config.repetitions,
                            )
