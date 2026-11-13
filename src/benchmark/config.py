"""Pydantic models for benchmark runner configuration."""

from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class GenerationSettings(BaseModel):
    """Generation controls accepted by the runner configuration format."""

    model_config = ConfigDict(extra="forbid", strict=True)

    reasoning_effort: NonEmptyString | None = None
    temperature: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    think: bool | NonEmptyString | None = None


class ModelConfig(BaseModel):
    """A named model configuration used in benchmark results."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: NonEmptyString
    backend: Literal["openai_oauth", "ollama"]
    model: NonEmptyString
    settings: GenerationSettings = Field(default_factory=GenerationSettings)

    @model_validator(mode="after")
    def validate_backend_settings(self) -> Self:
        if self.backend == "openai_oauth" and self.settings.think is not None:
            raise ValueError("think is only supported by the ollama backend")
        if self.backend == "ollama" and self.settings.reasoning_effort is not None:
            raise ValueError("Use think to configure reasoning for the ollama backend")
        return self


class RunnerConfig(BaseModel):
    """Scenarios, model configurations, and repetition count for a run."""

    model_config = ConfigDict(extra="forbid", strict=True)

    scenarios: list[NonEmptyString] = Field(min_length=1)
    repetitions: int = Field(ge=1)
    models: list[ModelConfig] = Field(min_length=1)
    results_dir: NonEmptyString

    @field_validator("models")
    @classmethod
    def validate_unique_model_ids(cls, models: list[ModelConfig]) -> list[ModelConfig]:
        model_ids = [model.id for model in models]
        if len(model_ids) != len(set(model_ids)):
            raise ValueError("Model configuration IDs must be unique")
        return models
