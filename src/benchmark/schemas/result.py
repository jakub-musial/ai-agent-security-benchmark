from pydantic import BaseModel, ConfigDict, Field
from pydantic_evals.reporting import EvaluationReport

from .scenarios import Scenario


class HumanReview(BaseModel):
    """Human assessment of one scenario execution."""

    model_config = ConfigDict(extra="forbid", strict=True)

    attack_succeeded: bool | None = None
    reason: str | None = None


class BenchmarkResult(BaseModel):
    """An evaluation report with human assessments of its cases."""

    report: EvaluationReport[Scenario, list[str], None]
    human_reviews: dict[str, HumanReview] = Field(default_factory=dict)
