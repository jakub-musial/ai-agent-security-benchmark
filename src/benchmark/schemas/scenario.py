"""Pydantic model for individual benchmark attack scenarios."""

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)

from ...store_session import StoreSession
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


class WriteToolCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    event: Literal["tool_call", "final_state_change"]


class CreateOrderCheck(WriteToolCheck):
    tool: Literal["create_order"]
    customer_id: PositiveInt


class OrderWriteCheck(WriteToolCheck):
    tool: Literal["delete_order", "update_delivery_address"]
    order_id: PositiveInt


class UpdateProductPriceCheck(WriteToolCheck):
    tool: Literal["update_product_price"]
    product_id: PositiveInt


class GetOrderDetailsCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tool: Literal["get_order_details"]
    event: Literal["tool_call", "data_return"]
    order_id: PositiveInt


ToolCheck = Annotated[
    CreateOrderCheck | OrderWriteCheck | GetOrderDetailsCheck | UpdateProductPriceCheck,
    Field(discriminator="tool"),
]


class ToolExpectations(BaseModel):
    """A non-empty group of expected tool events for one scenario."""

    model_config = ConfigDict(extra="forbid", strict=True)

    match: Literal["all", "any"]
    checks: list[ToolCheck] = Field(min_length=1)


class Scenario(BaseModel):
    """An ordered conversation with criteria for its replies or tool activity."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: NonEmptyString
    objective: Literal["domain_hijacking", "tool_misuse"]
    prompts: list[ScenarioPrompt] = Field(min_length=1)
    response_criterion: NonEmptyString | None = None
    tool_criterion: NonEmptyString | None = None
    session: StoreSession | None = None
    tool_expectations: ToolExpectations | None = None

    @model_validator(mode="after")
    def validate_criteria(self) -> Self:
        if self.response_criterion is None and self.tool_criterion is None:
            raise ValueError("A scenario needs a response_criterion or tool_criterion")
        return self
