"""Part intake API router (Epic 14).

Endpoints
---------
POST /intake/match         — free-text description → candidates + code + storage hints
POST /intake/suggest-code  — just generate a unique part code from a description
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.database import get_db_session
from makervault.schemas.intake import (
    IntakeMatchRequest,
    IntakeMatchResponse,
    SuggestCodeRequest,
    SuggestCodeResponse,
)
from makervault.services.intake_service import run_intake_match, suggest_part_code

router = APIRouter(prefix="/intake", tags=["intake"])


@router.post(
    "/match",
    response_model=IntakeMatchResponse,
    summary="Match a free-text description against existing parts",
)
async def intake_match(
    body: IntakeMatchRequest,
    db: AsyncSession = Depends(get_db_session),
) -> IntakeMatchResponse:
    """Given a plain-English description (e.g. *"10k resistor 0603"*), return:

    * **candidates** — ranked existing parts that may already be this part
    * **suggested_part_code** — a unique, human-readable code if creating a new part
    * **storage_suggestions** — likely storage locations based on historical patterns
    * **normalised_tokens** — tokens extracted from the description (for transparency)
    """
    result = await run_intake_match(
        description=body.description,
        db=db,
        category_id=body.category_id,
    )
    return IntakeMatchResponse.model_validate(result)


@router.post(
    "/suggest-code",
    response_model=SuggestCodeResponse,
    summary="Suggest a unique part code for a description",
)
async def intake_suggest_code(
    body: SuggestCodeRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SuggestCodeResponse:
    """Generate a unique, human-readable part code from *description*.

    This is a standalone endpoint for callers that only need the code
    suggestion without the full intake-match workflow.
    """
    code = await suggest_part_code(body.description, db)
    return SuggestCodeResponse(suggested_part_code=code)
