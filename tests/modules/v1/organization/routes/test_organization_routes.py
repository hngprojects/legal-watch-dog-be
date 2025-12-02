"""
This module contains unit tests for the organization routes in the v1 API.

It covers various scenarios for organization-related API endpoints,
including creation, retrieval, update, and deletion of organizations,
as well as handling of associated users and permissions.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.api.modules.v1.organization.routes.organization_route import (
    get_organization,
    get_organization_invitations,
    update_organization,
)
from app.api.modules.v1.organization.schemas.organization_schema import (
    UpdateOrganizationRequest,
)
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_get_organization_success():
    """Test successful retrieval of organization details."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_org_details = {
        "id": str(org_id),
        "name": "Test Org",
        "industry": "Tech",
        "is_active": True,
        "created_at": "2023-01-01T00:00:00",
        "updated_at": "2023-01-01T00:00:00",
        "projects_count": 5,
        "location": "New York",
        "plan": "Enterprise",
        "logo_url": "http://example.com/logo.png",
        "settings": {},
        "billing_info": {},
    }

    with (
        patch(
            "app.api.modules.v1.organization.routes.organization_route.check_user_permission",
            new_callable=AsyncMock,
        ) as mock_check_perm,
        patch(
            "app.api.modules.v1.organization.routes.organization_route.OrganizationService.get_organization_details",
            new_callable=AsyncMock,
        ) as mock_get_details,
    ):
        mock_check_perm.return_value = True
        mock_get_details.return_value = mock_org_details

        response = await get_organization(
            organization_id=org_id,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert response.status_code == status.HTTP_200_OK
        body = json.loads(response.body)
        assert body["status"] == "SUCCESS"
        assert body["data"]["projects_count"] == 5
        assert body["data"]["location"] == "New York"


@pytest.mark.asyncio
async def test_update_organization_success():
    """Test successful update of organization details."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    org_id = uuid.uuid4()

    payload = UpdateOrganizationRequest(
        name="Updated Org",
        industry="Finance",
        is_active=True,
    )

    mock_updated_org_data = {
        "id": str(org_id),
        "name": payload.name,
        "industry": payload.industry,
        "is_active": payload.is_active,
        "created_at": "2023-01-01T00:00:00",
        "updated_at": "2023-01-02T00:00:00",
        "settings": {},
        "billing_info": {"status": "active", "current_plan": {"tier": "pro"}},
        "user_role": "Admin",
        "location": None,
        "plan": "pro",
        "logo_url": None,
        "projects_count": 0,
    }

    with patch(
        "app.api.modules.v1.organization.routes.organization_route.OrganizationService",
    ) as mock_org_service:
        mock_instance = mock_org_service.return_value
        mock_instance.update_organization = AsyncMock(return_value=mock_updated_org_data)

        response = await update_organization(
            organization_id=org_id,
            payload=payload,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert response.status_code == status.HTTP_200_OK
        body = json.loads(response.body)
        assert body["status"] == "SUCCESS"
        data = body["data"]
        assert data["name"] == "Updated Org"
        assert data["industry"] == "Finance"
        assert data["plan"] == "pro"
        assert data["billing_info"]["status"] == "active"
        assert data["billing_info"]["current_plan"]["tier"] == "pro"
        assert body["data"]["name"] == "Updated Org"
        assert body["data"]["industry"] == "Finance"


@pytest.mark.asyncio
async def test_get_organization_invitations_success():
    """Test successful retrieval of organization invitations."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_invitations_data = {
        "invitations": [
            {
                "id": str(uuid.uuid4()),
                "organization_id": str(org_id),
                "organization_name": "Test Org",
                "invited_email": "invitee@example.com",
                "inviter_id": str(mock_current_user.id),
                "inviter_name": "Inviter User",
                "inviter_email": "inviter@example.com",
                "role_id": str(uuid.uuid4()),
                "role_name": "Member",
                "status": "pending",
                "is_expired": False,
                "expires_at": "2023-01-02T00:00:00",
                "accepted_at": None,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
            }
        ],
        "total": 1,
        "page": 1,
        "limit": 10,
        "total_pages": 1,
    }

    with patch(
        "app.api.modules.v1.organization.routes.organization_route.OrganizationService",
    ) as mock_org_service:
        mock_instance = mock_org_service.return_value
        mock_instance.get_organization_invitations = AsyncMock(return_value=mock_invitations_data)

        response = await get_organization_invitations(
            organization_id=org_id,
            status_filter="pending",
            page=1,
            limit=10,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert response.status_code == status.HTTP_200_OK
        body = json.loads(response.body)
        assert body["status"] == "SUCCESS"
        assert len(body["data"]["invitations"]) == 1
        assert body["data"]["invitations"][0]["invited_email"] == "invitee@example.com"
        assert body["data"]["invitations"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_invite_user_invalid_domain():
    """Test that inviting a user with a non-company email fails."""
    # This test relies on the schema validation which happens before the route handler
    # We can test the schema directly or mock the validator if we want to test the route integration
    # For integration testing, we would need to mock is_company_email or use a real one

    from pydantic import ValidationError

    from app.api.modules.v1.organization.schemas.invitation_schema import InvitationCreate

    with patch(
        "app.api.modules.v1.organization.schemas.invitation_schema.is_company_email"
    ) as mock_validator:
        mock_validator.return_value = False

        with pytest.raises(ValidationError) as excinfo:
            InvitationCreate(invited_email="test@qmail.com", role_name="Member")

        assert "Only company email addresses are allowed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_cancel_invitation_success():
    """Test successful cancellation of an invitation."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    org_id = uuid.uuid4()
    invitation_id = uuid.uuid4()

    # Mock invitation object
    mock_invitation = MagicMock()
    mock_invitation.id = invitation_id
    mock_invitation.organization_id = org_id
    mock_invitation.status.value = "cancelled"
    mock_invitation.invited_email = "invitee@example.com"

    # Mock db.get to return the invitation
    # The route calls db.get(Invitation, invitation_id)
    # We need to make sure db.get returns our mock invitation
    mock_db.get.return_value = mock_invitation

    with (
        patch(
            "app.api.modules.v1.organization.routes.organization_route.check_user_permission",
            new_callable=AsyncMock,
        ) as mock_check_perm,
        patch(
            "app.api.modules.v1.organization.service.invitation_service.InvitationCRUD.cancel_invitation",
            new_callable=AsyncMock,
        ) as mock_cancel,
    ):
        mock_check_perm.return_value = True
        mock_cancel.return_value = mock_invitation

        from app.api.modules.v1.organization.routes.organization_route import cancel_invitation

        response = await cancel_invitation(
            organization_id=org_id,
            invitation_id=invitation_id,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert response.status_code == status.HTTP_200_OK
        body = json.loads(response.body)
        assert body["status"] == "SUCCESS"
        assert body["message"] == "Invitation cancelled successfully"
