from typing import Any, Literal

from pydantic import BaseModel, Field


class Observation(BaseModel):
    id: str
    span: list[int] | None = None
    severity: Literal["info", "warning", "violation"]
    category: Literal[
        "clarity", "accuracy", "structure", "accessibility", "pedagogy", "compliance", "other"
    ]
    standard_ref: str
    message: str
    suggested_fix: str | None = None
    rationale: str | None = None
    standard_excerpt: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class Meta(BaseModel):
    request_id: str
    standards_set: str
    strictness: Literal["low", "medium", "high"]
    policy_version: str
    model_id: str
    latency_ms: int = 0
    usage: Usage = Field(default_factory=Usage)


class Error(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ReviewResponse(BaseModel):
    observations: list[Observation] = Field(default_factory=list)
    meta: Meta
    errors: list[Error] = Field(default_factory=list)
