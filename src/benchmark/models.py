"""Create Pydantic AI models from benchmark configuration."""

import uuid
import webbrowser
from pathlib import Path
from typing import cast

from openai.types.shared import ReasoningEffort
from pydantic_ai.models import Model
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import (
    OpenAIResponsesModel,
    OpenAIResponsesModelSettings,
)
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai_chatgpt import (
    OpenAIChatGPTOAuthFlow,
    OpenAIChatGPTProvider,
)
from pydantic_ai.settings import ModelSettings

from .schemas.config import ModelConfig


async def login_chatgpt(
    *,
    host_id_path: str | Path = "config/chatgpt-host-id",
) -> OpenAIChatGPTProvider:
    """Sign in once and return a provider that can be shared by multiple models.

    The browser opens Sign in with ChatGPT and the function awaits its local
    callback. Credentials stay in memory for the lifetime of the provider.
    The caller manages the provider's lifetime within a single event loop.

    Args:
        host_id_path: File storing a stable installation ID. Created on first
            use; relative to the working directory.

    Raises:
        OSError: The installation ID file cannot be read or written.
        RuntimeError: The sign-in browser cannot be opened.
    """
    host_id_file = Path(host_id_path)
    if host_id_file.exists():
        host_id = host_id_file.read_text(encoding="utf-8").strip()
    else:
        host_id_file.parent.mkdir(parents=True, exist_ok=True)
        host_id = uuid.uuid4().urn
        host_id_file.write_text(host_id, encoding="utf-8")

    flow = OpenAIChatGPTOAuthFlow(
        app_name="AI Agent Security Benchmark",
        host_id=host_id,
    )
    if not webbrowser.open(flow.authorization_url()):
        raise RuntimeError("Could not open the browser for ChatGPT sign-in")

    credentials = await flow.exchange_code_from_callback()
    return OpenAIChatGPTProvider(credentials=credentials)


def create_model(
    config: ModelConfig,
    *,
    chatgpt_provider: OpenAIChatGPTProvider | None = None,
    ollama_base_url: str = "http://localhost:11434/v1",
) -> Model:
    """Create a model with its configured generation settings.

    The caller manages model and provider lifetimes during the benchmark run.
    For Ollama, think=True maps to medium effort, think=False maps to none,
    and named thinking levels are forwarded unchanged.

    Args:
        config: A validated model configuration.
        chatgpt_provider: Provider returned by login_chatgpt. Required for the
            openai_oauth backend and reusable across multiple model instances.
        ollama_base_url: OpenAI-compatible endpoint of the Ollama server.

    Returns:
        A model ready to pass to StoreAgent.

    Raises:
        ValueError: The ChatGPT provider is missing, or the backend or its
            settings are unsupported.
    """
    if config.backend == "openai_oauth":
        if chatgpt_provider is None:
            raise ValueError(
                "The openai_oauth backend requires a ChatGPT provider. "
                "Call await login_chatgpt() and pass its result as chatgpt_provider."
            )
        if config.settings.temperature is not None:
            raise ValueError(
                "The ChatGPT plan usage backend does not support temperature"
            )

        openai_settings = OpenAIResponsesModelSettings()
        if config.settings.reasoning_effort is not None:
            openai_settings["openai_reasoning_effort"] = cast(
                ReasoningEffort, config.settings.reasoning_effort
            )

        return OpenAIResponsesModel(
            config.model,
            provider=chatgpt_provider,
            settings=openai_settings,
        )

    if config.backend == "ollama":
        ollama_settings = ModelSettings()
        if config.settings.temperature is not None:
            ollama_settings["temperature"] = config.settings.temperature

        think = config.settings.think
        if think is not None:
            if isinstance(think, bool):
                effort = "medium" if think else "none"
            else:
                effort = think
            # Ollama's OpenAI-compatible API accepts reasoning.effort.
            ollama_settings["extra_body"] = {"reasoning": {"effort": effort}}

        return OllamaModel(
            config.model,
            provider=OllamaProvider(base_url=ollama_base_url),
            settings=ollama_settings,
        )

    raise ValueError(f"Unsupported model backend: {config.backend}")
