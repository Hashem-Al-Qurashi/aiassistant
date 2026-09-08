"""API router for engagement endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from backend.database import get_db
from backend.models.entities import Engagement, EngagementStatus
from backend.models.schemas import (
    CreateEngagementRequest,
    EngagementResponse,
    ListEngagementsResponse,
)

router = APIRouter()


@router.post("/engagements", response_model=EngagementResponse, status_code=status.HTTP_201_CREATED)
async def create_engagement(
    payload: CreateEngagementRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new engagement."""
    engagement = Engagement(
        name=payload.name,
        objective=payload.objective,
        org_id=payload.org_id,
        status=EngagementStatus.DISCOVERY,
    )
    db.add(engagement)
    await db.commit()
    await db.refresh(engagement)
    return engagement


@router.get("/engagements", response_model=ListEngagementsResponse)
async def list_engagements(
    org_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all engagements, optionally filtered by org."""
    stmt = select(Engagement)
    if org_id:
        stmt = stmt.where(Engagement.org_id == org_id)
    result = await db.execute(stmt)
    engagements = result.scalars().all()

    count_stmt = select(func.count()).select_from(Engagement)
    if org_id:
        count_stmt = count_stmt.where(Engagement.org_id == org_id)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    return ListEngagementsResponse(engagements=engagements, total=total)


@router.get("/engagements/{engagement_id}", response_model=EngagementResponse)
async def get_engagement(engagement_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific engagement by ID."""
    result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    engagement = result.scalar_one_or_none()
    if engagement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Engagement {engagement_id} not found",
        )
    return engagement


@router.patch("/engagements/{engagement_id}", response_model=EngagementResponse)
async def update_engagement(
    engagement_id: UUID,
    payload: CreateEngagementRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update an engagement."""
    result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    engagement = result.scalar_one_or_none()
    if engagement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Engagement {engagement_id} not found",
        )
    engagement.name = payload.name
    engagement.objective = payload.objective
    engagement.org_id = payload.org_id or engagement.org_id
    await db.commit()
    await db.refresh(engagement)
    return engagement


@router.delete("/engagements/{engagement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_engagement(engagement_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete an engagement."""
    result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    engagement = result.scalar_one_or_none()
    if engagement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Engagement {engagement_id} not found",
        )
    await db.delete(engagement)
    await db.commit()
    return None
