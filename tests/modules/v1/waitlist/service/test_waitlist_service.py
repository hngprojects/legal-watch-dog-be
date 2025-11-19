import pytest
from app.api.modules.v1.waitlist.service.waitlist_service import WaitlistService
from app.api.modules.v1.waitlist.schemas.waitlist_schema import (
    WaitlistResponse,
    WaitlistSignup,
)



@pytest.mark.asyncio
<<<<<<< HEAD
async def test_add_to_waitlist_success(test_session):
    async for session in test_session:
        service = WaitlistService()
        response: WaitlistResponse = await service.add_to_waitlist(
            session,
            organization_email="new@company.com",
            organization_name="New Company",
        )
=======
async def test_add_to_waitlist_success(pg_async_session):
    """Test adding a new email to the waitlist successfully."""
    session = pg_async_session
    service = WaitlistService()

    waitlist_data = WaitlistSignup(
        organization_email="new@company.com", organization_name="New Company"
    )
    response: WaitlistResponse = await service.add_to_waitlist(session, waitlist_data)

    assert response.organization_email == "new@company.com"
    assert response.organization_name == "New Company"
>>>>>>> 3e5fb572ee703478e954d7f18b1da18227832267



@pytest.mark.asyncio
async def test_add_to_waitlist_duplicate(pg_async_session):
    """Test adding a duplicate email to the waitlist raises an error."""
    session = pg_async_session
    service = WaitlistService()

    waitlist_data = WaitlistSignup(
        organization_email="new@company.com", organization_name="New Company"
    )

    await service.add_to_waitlist(session, waitlist_data)

    with pytest.raises(Exception) as exc_info:
        await service.add_to_waitlist(session, waitlist_data)

    assert "Email already registered" in str(exc_info.value)
