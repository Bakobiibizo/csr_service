"""
Schemas for standards-related requests and responses.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class EvidenceRequirement(BaseModel):
    """Machine-readable evidence expected before a rule may be asserted."""

    kind: Literal["content_span", "document", "metadata"] = "content_span"
    description: str = ""
    required: bool = True


class StandardRule(BaseModel):
    standard_ref: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    severity_default: Literal["info", "warning", "violation"] = "warning"
    evidence: list[EvidenceRequirement] = Field(default_factory=lambda: [EvidenceRequirement()])

    @model_validator(mode="after")
    def require_identity(self) -> "StandardRule":
        if not self.standard_ref.strip() or not self.title.strip() or not self.body.strip():
            raise ValueError("standard_ref, title, and body must be non-empty")
        return self


class StandardsSet(BaseModel):
    standards_set: str
    name: str = ""
    version: str = "1.0"
    rules: list[StandardRule]

    @model_validator(mode="after")
    def unique_refs(self) -> "StandardsSet":
        refs = [rule.standard_ref for rule in self.rules]
        if len(refs) != len(set(refs)):
            raise ValueError("standard_ref values must be unique within a standards set")
        return self


class StandardsSetInfo(BaseModel):
    id: str
    name: str
    version: str


class StandardsListResponse(BaseModel):
    standards_sets: list[StandardsSetInfo]
