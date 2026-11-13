"""Pydantic model for individual benchmark attack scenarios."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .types import NonEmptyString


class Scenario(BaseModel):
    """An attack prompt and the criterion used to evaluate its success."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: NonEmptyString
    objective: Literal["domain_hijacking", "tool_misuse"]
    prompt: str = Field(min_length=1, pattern=r"\S")
    success_criterion: NonEmptyString
