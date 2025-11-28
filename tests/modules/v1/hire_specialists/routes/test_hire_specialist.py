from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status

from app.api.modules.v1.hire_specialists.models.specialist_models import SpecialistHire
from app.api.modules.v1.hire_specialists.routes.specialist_routes import hire_specialist
from app.api.modules.v1.hire_specialists.schemas.specialist_schemas import SpecialistHireRequest


@pytest.mark.asyncio
async def test_hire_specialist_success():
    """
    Test the successful creation of a specialist hire request.

    Creates a mock SpecialistHireRequest and a mocked AsyncSession,
    then calls the hire_specialist endpoint and asserts that the response
    contains the correct success status and data.

    Args:
        None (pytest test function)

    Returns:
        None

    Raises:
        AssertionError: If any of the assertions about the response fail.
    """
    request_data = SpecialistHireRequest(
        company_name="TechCorp Solutions",
        company_email="contact@techcorp.com",
        industry="Immigration & Global Mobility",
        brief_description="We need assistance with EU travel compliance monitoring"
    )

    mock_db = AsyncMock()
    mock_hire_instance = SpecialistHire(
        id="123e4567-e89b-12d3-a456-426614174000",
        company_name=request_data.company_name,
        company_email=request_data.company_email,
        industry=request_data.industry,
        brief_description=request_data.brief_description,
        created_at="2025-01-15T10:30:00"
    )

    mock_db.add.return_value = None
    mock_db.commit.return_value = None
    mock_db.refresh.return_value = None

    original_class = SpecialistHire
    try:
        SpecialistHire.__new__ = lambda cls, **kwargs: mock_hire_instance

        response = await hire_specialist(request_data, db=mock_db)

        assert response.success is True
        assert "Specialist hired successfully" in response.message
        assert response.data["company_name"] == request_data.company_name
        assert response.data["company_email"] == request_data.company_email
        assert response.data["industry"] == request_data.industry
        assert "id" in response.data
        assert "created_at" in response.data

    finally:
        SpecialistHire.__new__ = original_class.__new__


@pytest.mark.asyncio
async def test_hire_specialist_failure():
    """
    Test the failure case when the database commit raises an exception.

    Uses a mock SpecialistHireRequest and a mocked AsyncSession that
    raises an exception on commit. Asserts that an HTTPException with
    status 500 is raised.

    Args:
        None (pytest test function)

    Returns:
        None

    Raises:
        HTTPException: Expected to be raised due to simulated database failure.
    """
    request_data = SpecialistHireRequest(
        company_name="FailCorp",
        company_email="fail@corp.com",
        industry="Test Industry",
        brief_description="This will fail"
    )

    mock_db = AsyncMock()
    mock_db.add.return_value = None
    mock_db.commit.side_effect = Exception("DB error")
    mock_db.rollback.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await hire_specialist(request_data, db=mock_db)

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Failed to process hire request" in exc_info.value.detail
