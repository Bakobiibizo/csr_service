from typing import Literal

from pydantic import BaseModel


class StandardRule(BaseModel):
    standard_ref: str
    title: str
    body: str
    tags: list[str] = []
    severity_default: Literal["info", "warning", "violation"] = "warning"


class StandardsSet(BaseModel):
    standards_set: str
    name: str = ""
    version: str = "1.0"
    rules: list[StandardRule]


class StandardsSetInfo(BaseModel):
    id: str
    name: str
    version: str


class StandardsListResponse(BaseModel):
    standards_sets: list[StandardsSetInfo]
