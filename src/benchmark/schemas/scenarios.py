"""Pydantic model for individual benchmark attack scenarios."""

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .types import NonEmptyString

SCENARIOS_ROOT = Path(__file__).resolve().parents[3] / "scenarios"


class ScenarioPrompt(BaseModel):
    """One user message with text and optional scenario attachments."""

    model_config = ConfigDict(extra="forbid", strict=True)

    text: str = ""
    files: list[str] = Field(default_factory=list)

    @field_validator("files")
    @classmethod
    def validate_files(cls, files: list[str]) -> list[str]:
        """Require existing attachments, with paths relative to scenarios/."""
        attachments_root = (SCENARIOS_ROOT / "attachments").resolve()
        for filename in files:
            path = Path(filename)
            if path.anchor:
                raise ValueError("Attachment paths must be relative to scenarios/")

            resolved_path = (SCENARIOS_ROOT / path).resolve()
            if not resolved_path.is_relative_to(attachments_root):
                raise ValueError("Attachments must be inside scenarios/attachments/")
            if not resolved_path.is_file():
                raise ValueError(f"Attachment is not an existing file: {filename}")
        return files

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        if not self.text.strip() and not self.files:
            raise ValueError("A prompt must contain non-whitespace text or files")
        return self


class Scenario(BaseModel):
    """An ordered sequence of attack prompts and its success criterion."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: NonEmptyString
    objective: Literal["domain_hijacking", "tool_misuse"]
    prompts: list[ScenarioPrompt] = Field(min_length=1)
    success_criterion: NonEmptyString
