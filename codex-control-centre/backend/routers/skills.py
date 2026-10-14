"""Authenticated bridge to the local Skills RAG and hybrid-search service."""

from fastapi import APIRouter, HTTPException, Query

from backend.services.skills_context import SkillNotFoundError, SkillsServiceError, skills_context_service


router = APIRouter(prefix="/codex/skills", tags=["skills"])


def _unavailable(exc: SkillsServiceError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


@router.get("/stats")
async def get_skills_stats():
    try:
        return await skills_context_service.stats()
    except SkillsServiceError as exc:
        raise _unavailable(exc) from exc


@router.get("/search")
async def search_skills(
    query: str = Query(..., min_length=1, max_length=500),
    top_k: int = Query(12, ge=1, le=15),
):
    try:
        return {"results": await skills_context_service.search(query, top_k=top_k)}
    except SkillsServiceError as exc:
        raise _unavailable(exc) from exc


@router.get("/{skill_id}")
async def read_skill(skill_id: str):
    try:
        return await skills_context_service.read(skill_id)
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SkillsServiceError as exc:
        raise _unavailable(exc) from exc
