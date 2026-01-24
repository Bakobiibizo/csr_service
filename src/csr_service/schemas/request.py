
"""
Schemas for review requests and related data.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ReviewOptions(BaseModel):
    return_rationale: bool = True
    return_excerpts: bool = True
    max_observations: int = Field(default=25, ge=1, le=100)
    min_confidence: float = Field(default=0.55, ge=0.0, le=1.0)


class ReviewRequest(BaseModel):
    request_id: str | None = None
    content: str
    standards_set: str
    strictness: Literal["low", "medium", "high"] = "medium"
    options: ReviewOptions = Field(default_factory=ReviewOptions)
