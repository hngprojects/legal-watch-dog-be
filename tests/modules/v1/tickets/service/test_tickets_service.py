import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.api.modules.v1.tickets.service.ticket_service import TicketService

from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.tickets.models.ticket_model import Ticket
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_invite_users_to_ticket_success():
    """Test successfully inviting users to a ticket"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()

    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    current_user_id = uuid.uuid4()
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()

    current_user = User(id=current_user_id, email="current@example.com", name="Current User")

    organization = Organization(id=org_id, name="Test Org")

    ticket = Ticket(
        id=ticket_id,
        organization_id=org_id,
        title="Test Ticket",
        description="Test Description",
    )
    ticket.invited_users = []
    ticket.organization = organization
    ticket.project = None
    ticket.created_by_user = current_user

    user1 = User(
        id=user1_id, email="user1@example.com", name="User One", is_verified=True, is_active=True
    )
    user2 = User(
        id=user2_id, email="user2@example.com", name="User Two", is_verified=True, is_active=True
    )

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = ticket

    current_user_result = MagicMock()
    current_user_result.scalar_one.return_value = current_user

    users_result = MagicMock()
    users_result.scalars.return_value.all.return_value = [user1, user2]

    db.execute.side_effect = [ticket_result, current_user_result, users_result]

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.TenantGuard"
    ) as mock_tenant_guard:
        mock_tenant_instance = MagicMock()
        mock_tenant_instance.get_membership = AsyncMock()
        mock_tenant_guard.return_value = mock_tenant_instance

        with patch(
            "app.api.modules.v1.tickets.service.ticket_service.check_user_permission"
        ) as mock_check_permission:
            mock_check_permission.return_value = True

            with patch(
                "app.api.modules.v1.tickets.service.ticket_service.send_email"
            ) as mock_send_email:
                mock_send_email.return_value = AsyncMock()

                service = TicketService(db)
                result = await service.invite_users_to_ticket(
                    ticket_id=ticket_id,
                    emails=["user1@example.com", "user2@example.com"],
                    current_user_id=current_user_id,
                )

                assert len(result.invited) == 2
                assert result.invited[0].email == "user1@example.com"
                assert result.invited[1].email == "user2@example.com"
                assert len(result.already_invited) == 0
                assert len(result.not_found) == 0
                assert db.add.call_count == 2
                db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_invite_users_to_ticket_not_found():
    """Test inviting users to a non-existent ticket"""
    db = MagicMock()
    db.execute = AsyncMock()

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = None
    db.execute.return_value = ticket_result

    service = TicketService(db)

    with pytest.raises(ValueError, match="Ticket not found"):
        await service.invite_users_to_ticket(
            ticket_id=uuid.uuid4(),
            emails=["user@example.com"],
            current_user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_invite_users_to_ticket_user_not_member():
    """Test inviting users when current user is not a member of the organization"""
    db = MagicMock()
    db.execute = AsyncMock()

    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    current_user_id = uuid.uuid4()

    current_user = User(id=current_user_id, email="current@example.com", name="Current User")
    organization = Organization(id=org_id, name="Test Org")

    ticket = Ticket(
        id=ticket_id,
        organization_id=org_id,
        title="Test Ticket",
    )
    ticket.invited_users = []
    ticket.organization = organization

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = ticket

    current_user_result = MagicMock()
    current_user_result.scalar_one.return_value = current_user

    db.execute.side_effect = [ticket_result, current_user_result]

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.TenantGuard"
    ) as mock_tenant_guard:
        mock_tenant_instance = MagicMock()
        mock_tenant_instance.get_membership = AsyncMock(side_effect=ValueError("Not a member"))
        mock_tenant_guard.return_value = mock_tenant_instance

        service = TicketService(db)

        with pytest.raises(ValueError, match="You must be a member of the organization"):
            await service.invite_users_to_ticket(
                ticket_id=ticket_id,
                emails=["user@example.com"],
                current_user_id=current_user_id,
            )


@pytest.mark.asyncio
async def test_invite_users_to_ticket_no_permission():
    """Test inviting users when current user lacks permission"""
    db = MagicMock()
    db.execute = AsyncMock()

    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    current_user_id = uuid.uuid4()

    current_user = User(id=current_user_id, email="current@example.com", name="Current User")
    organization = Organization(id=org_id, name="Test Org")

    ticket = Ticket(
        id=ticket_id,
        organization_id=org_id,
        title="Test Ticket",
    )
    ticket.invited_users = []
    ticket.organization = organization

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = ticket

    current_user_result = MagicMock()
    current_user_result.scalar_one.return_value = current_user

    db.execute.side_effect = [ticket_result, current_user_result]

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.TenantGuard"
    ) as mock_tenant_guard:
        mock_tenant_instance = MagicMock()
        mock_tenant_instance.get_membership = AsyncMock()
        mock_tenant_guard.return_value = mock_tenant_instance

        with patch(
            "app.api.modules.v1.tickets.service.ticket_service.check_user_permission"
        ) as mock_check_permission:
            mock_check_permission.return_value = False

            service = TicketService(db)

            with pytest.raises(ValueError, match="You do not have permission to invite users"):
                await service.invite_users_to_ticket(
                    ticket_id=ticket_id,
                    emails=["user@example.com"],
                    current_user_id=current_user_id,
                )


@pytest.mark.asyncio
async def test_invite_users_to_ticket_already_invited():
    """Test inviting users who are already invited"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()

    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    current_user_id = uuid.uuid4()
    user1_id = uuid.uuid4()

    current_user = User(id=current_user_id, email="current@example.com", name="Current User")
    organization = Organization(id=org_id, name="Test Org")

    user1 = User(
        id=user1_id, email="user1@example.com", name="User One", is_verified=True, is_active=True
    )

    ticket = Ticket(
        id=ticket_id,
        organization_id=org_id,
        title="Test Ticket",
    )
    ticket.invited_users = [user1]
    ticket.organization = organization
    ticket.project = None

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = ticket

    current_user_result = MagicMock()
    current_user_result.scalar_one.return_value = current_user

    users_result = MagicMock()
    users_result.scalars.return_value.all.return_value = [user1]

    db.execute.side_effect = [ticket_result, current_user_result, users_result]

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.TenantGuard"
    ) as mock_tenant_guard:
        mock_tenant_instance = MagicMock()
        mock_tenant_instance.get_membership = AsyncMock()
        mock_tenant_guard.return_value = mock_tenant_instance

        with patch(
            "app.api.modules.v1.tickets.service.ticket_service.check_user_permission"
        ) as mock_check_permission:
            mock_check_permission.return_value = True

            service = TicketService(db)
            result = await service.invite_users_to_ticket(
                ticket_id=ticket_id,
                emails=["user1@example.com"],
                current_user_id=current_user_id,
            )

            assert len(result.invited) == 0
            assert len(result.already_invited) == 1
            assert result.already_invited[0] == "user1@example.com"
            assert len(result.not_found) == 0
            db.add.assert_not_called()
            db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_invite_users_to_ticket_users_not_found():
    """Test inviting users who are not in the organization"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()

    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    current_user_id = uuid.uuid4()

    current_user = User(id=current_user_id, email="current@example.com", name="Current User")
    organization = Organization(id=org_id, name="Test Org")

    ticket = Ticket(
        id=ticket_id,
        organization_id=org_id,
        title="Test Ticket",
    )
    ticket.invited_users = []
    ticket.organization = organization
    ticket.project = None

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = ticket

    current_user_result = MagicMock()
    current_user_result.scalar_one.return_value = current_user

    users_result = MagicMock()
    users_result.scalars.return_value.all.return_value = []

    db.execute.side_effect = [ticket_result, current_user_result, users_result]

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.TenantGuard"
    ) as mock_tenant_guard:
        mock_tenant_instance = MagicMock()
        mock_tenant_instance.get_membership = AsyncMock()
        mock_tenant_guard.return_value = mock_tenant_instance

        with patch(
            "app.api.modules.v1.tickets.service.ticket_service.check_user_permission"
        ) as mock_check_permission:
            mock_check_permission.return_value = True

            service = TicketService(db)
            result = await service.invite_users_to_ticket(
                ticket_id=ticket_id,
                emails=["nonexistent@example.com"],
                current_user_id=current_user_id,
            )

            assert len(result.invited) == 0
            assert len(result.already_invited) == 0
            assert len(result.not_found) == 1
            assert result.not_found[0] == "nonexistent@example.com"
            db.add.assert_not_called()
            db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_invite_users_to_ticket_mixed_results():
    """Test inviting users with mixed results (invited, already invited, not found)"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()

    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    current_user_id = uuid.uuid4()
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()
    user3_id = uuid.uuid4()

    current_user = User(id=current_user_id, email="current@example.com", name="Current User")
    organization = Organization(id=org_id, name="Test Org")

    user1 = User(
        id=user1_id, email="user1@example.com", name="User One", is_verified=True, is_active=True
    )
    user2 = User(
        id=user2_id, email="user2@example.com", name="User Two", is_verified=True, is_active=True
    )
    user3 = User(
        id=user3_id, email="user3@example.com", name="User Three", is_verified=True, is_active=True
    )

    ticket = Ticket(
        id=ticket_id,
        organization_id=org_id,
        title="Test Ticket",
    )
    ticket.invited_users = [user2]
    ticket.organization = organization
    ticket.project = None
    ticket.created_by_user = current_user

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = ticket

    current_user_result = MagicMock()
    current_user_result.scalar_one.return_value = current_user

    users_result = MagicMock()
    users_result.scalars.return_value.all.return_value = [user1, user2, user3]

    db.execute.side_effect = [ticket_result, current_user_result, users_result]

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.TenantGuard"
    ) as mock_tenant_guard:
        mock_tenant_instance = MagicMock()
        mock_tenant_instance.get_membership = AsyncMock()
        mock_tenant_guard.return_value = mock_tenant_instance

        with patch(
            "app.api.modules.v1.tickets.service.ticket_service.check_user_permission"
        ) as mock_check_permission:
            mock_check_permission.return_value = True

            with patch(
                "app.api.modules.v1.tickets.service.ticket_service.send_email"
            ) as mock_send_email:
                mock_send_email.return_value = AsyncMock()

                service = TicketService(db)
                result = await service.invite_users_to_ticket(
                    ticket_id=ticket_id,
                    emails=[
                        "user1@example.com",
                        "user2@example.com",
                        "user3@example.com",
                        "user4@example.com",
                    ],
                    current_user_id=current_user_id,
                )

                assert len(result.invited) == 2
                assert result.invited[0].email == "user1@example.com"
                assert result.invited[1].email == "user3@example.com"
                assert len(result.already_invited) == 1
                assert result.already_invited[0] == "user2@example.com"
                assert len(result.not_found) == 1
                assert result.not_found[0] == "user4@example.com"
                assert db.add.call_count == 2
                db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_invitation_email_called():
    """Test that invitation emails are sent for invited users"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()

    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    current_user_id = uuid.uuid4()
    user1_id = uuid.uuid4()

    current_user = User(id=current_user_id, email="current@example.com", name="Current User")
    organization = Organization(id=org_id, name="Test Org")

    user1 = User(
        id=user1_id, email="user1@example.com", name="User One", is_verified=True, is_active=True
    )

    mock_priority = MagicMock()
    mock_priority.value = "high"

    mock_status = MagicMock()
    mock_status.value = "open"

    ticket = Ticket(
        id=ticket_id,
        organization_id=org_id,
        title="Test Ticket",
        description="Test Description",
    )
    ticket.priority = mock_priority
    ticket.status = mock_status
    ticket.invited_users = []
    ticket.organization = organization
    ticket.project = None
    ticket.created_by_user = current_user

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = ticket

    current_user_result = MagicMock()
    current_user_result.scalar_one.return_value = current_user

    users_result = MagicMock()
    users_result.scalars.return_value.all.return_value = [user1]

    db.execute.side_effect = [ticket_result, current_user_result, users_result]

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.TenantGuard"
    ) as mock_tenant_guard:
        mock_tenant_instance = MagicMock()
        mock_tenant_instance.get_membership = AsyncMock()
        mock_tenant_guard.return_value = mock_tenant_instance

        with patch(
            "app.api.modules.v1.tickets.service.ticket_service.check_user_permission"
        ) as mock_check_permission:
            mock_check_permission.return_value = True

            with patch(
                "app.api.modules.v1.tickets.service.ticket_service.send_email"
            ) as mock_send_email:
                mock_send_email.return_value = AsyncMock()

                service = TicketService(db)
                await service.invite_users_to_ticket(
                    ticket_id=ticket_id,
                    emails=["user1@example.com"],
                    current_user_id=current_user_id,
                )

                mock_send_email.assert_called_once()
                call_kwargs = mock_send_email.call_args[1]
                assert call_kwargs["template_name"] == "ticket_invitation_email"
                assert call_kwargs["recipient"] == "user1@example.com"
                assert "Test Ticket" in call_kwargs["subject"]
