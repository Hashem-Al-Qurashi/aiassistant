"""Tests for engagement creation API."""

import pytest
from httpx import AsyncClient
from uuid import uuid4

from backend.main import app


@pytest.mark.asyncio
async def test_create_engagement_returns_201():
    """Create engagement via API returns 201 with UUID and status."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/engagements",
            json={
                "name": "Test Engagement",
                "objective": "Validate dependency tracing",
                "org_id": str(uuid4()),
            },
        )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "Test Engagement"
    assert data["status"] == "discovery"


@pytest.mark.asyncio
async def test_list_engagements_returns_paginated():
    """List engagements returns array + total count."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/engagements")
    assert response.status_code == 200
    data = response.json()
    assert "engagements" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_engagement_not_found_returns_404():
    """Getting non-existent engagement returns 404."""
    from uuid import uuid4

    fake_id = uuid4()
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(f"/api/v1/engagements/{fake_id}")
    assert response.status_code == 404
