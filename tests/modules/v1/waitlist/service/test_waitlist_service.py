import pytest
from app.api.modules.v1.waitlist.service.waitlist_service import WaitlistService
from app.api.modules.v1.waitlist.schemas.waitlist_schema import WaitlistResponse

@pytest.mark.asyncio
async def test_add_to_waitlist_success(test_session):
    async for session in test_session:
        service = WaitlistService()
        response: WaitlistResponse = await service.add_to_waitlist(
            session,
            organization_email="new@company.com",
            organization_name="New Company"
        )

        assert response.organization_email == "new@company.com"
        assert response.organization_name == "New Company"

@pytest.mark.asyncio
async def test_add_to_waitlist_duplicate(test_session):
    async for session in test_session:
        service = WaitlistService()

        await service.add_to_waitlist(session, "dup2@company.com", "Dup2 Company")

        with pytest.raises(Exception) as exc_info:
            await service.add_to_waitlist(session, "dup2@company.com", "Dup2 Company")

        assert "Email already registered" in str(exc_info.value)
