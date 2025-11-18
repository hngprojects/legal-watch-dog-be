import pytest
from app.api.modules.v1.waitlist.service.waitlist_service import WaitlistService
from app.api.modules.v1.waitlist.schemas.waitlist_schema import (
    WaitlistResponse,
    WaitlistSignup,
)


@pytest.mark.asyncio
async def test_add_to_waitlist_success(test_session):
    """Test adding a new email to the waitlist successfully."""
    session = test_session
    service = WaitlistService()

    waitlist_data = WaitlistSignup(
        organization_email="new@company.com", organization_name="New Company"
    )
    response: WaitlistResponse = await service.add_to_waitlist(session, waitlist_data)

    assert response.organization_email == "new@company.com"
    assert response.organization_name == "New Company"


@pytest.mark.asyncio
async def test_add_to_waitlist_duplicate(test_session):
    """Test adding a duplicate email to the waitlist raises an error."""
    session = test_session
    service = WaitlistService()

    waitlist_data = WaitlistSignup(
        organization_email="new@company.com", organization_name="New Company"
    )

    await service.add_to_waitlist(session, waitlist_data)

    with pytest.raises(Exception) as exc_info:
        await service.add_to_waitlist(session, waitlist_data)

    assert "Email already registered" in str(exc_info.value)
