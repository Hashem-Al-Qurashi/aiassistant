"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum


class EngagementStatus(str, Enum):
    DISCOVERY = "discovery"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    RECOMMENDATIONS = "recommendations"
    DELIVERABLES = "deliverables"
    ARCHIVED = "archived"


class CreateEngagementRequest(BaseModel):
    """Request schema for creating an engagement."""
    name: str = Field(..., min_length=1, max_length=255)
    objective: Optional[str] = None
    org_id: Optional[UUID] = None


class EngagementResponse(BaseModel):
    """Response schema for engagement."""
    id: UUID
    org_id: Optional[UUID] = None
    name: str
    status: EngagementStatus
    objective: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ListEngagementsResponse(BaseModel):
    """Response for listing engagements."""
    engagements: List[EngagementResponse]
    total: int


class HealthCheck(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str
