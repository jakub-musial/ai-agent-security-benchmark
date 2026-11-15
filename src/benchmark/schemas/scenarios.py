"""Pydantic model for individual benchmark attack scenarios."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .types import NonEmptyString


class Scenario(BaseModel):
    """An ordered sequence of attack prompts and its success criterion."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: NonEmptyString
    objective: Literal["domain_hijacking", "tool_misuse"]
    prompts: list[Annotated[str, Field(min_length=1, pattern=r"\S")]] = Field(
        min_length=1
    )
    success_criterion: NonEmptyString
