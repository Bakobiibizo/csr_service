"""GET /v1/standards endpoint listing available standards sets."""

from fastapi import APIRouter, Request

from ..schemas.standards import StandardsListResponse, StandardsSetInfo

router = APIRouter(prefix="/v1")


@router.get("/standards", response_model=StandardsListResponse)
async def list_standards(request: Request) -> StandardsListResponse:
    standards_sets = getattr(request.app.state, "standards_sets", {})
    infos = [
        StandardsSetInfo(id=ss.standards_set, name=ss.name or ss.standards_set, version=ss.version)
        for ss in standards_sets.values()
    ]
    return StandardsListResponse(standards_sets=infos)
