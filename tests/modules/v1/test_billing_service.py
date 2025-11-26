from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.modules.v1.billing.services.billing_service import BillingService
from app.api.modules.v1.organization.models import Organization


# --- Helpers ---
async def create_org(pg_async_session, org_id, name, owner_email):
    org = Organization(id=org_id, name=name, owner_email=owner_email)
    pg_async_session.add(org)
    await pg_async_session.commit()
    await pg_async_session.refresh(org)
    return org


def get_mocked_billing_service(db):
    with patch.object(
        BillingService,
        "__init__",
        lambda x, db: setattr(x, "db", db) or setattr(x, "stripe_client", AsyncMock()),
    ):
        service = BillingService(db)
        mock_customer = MagicMock()
        mock_customer.id = "cus_test123"
        service.stripe_client.create_customer = AsyncMock(return_value=mock_customer)
        return service


# --- Tests ---
@pytest.mark.asyncio
async def test_get_or_create_billing_account_creates_new(pg_async_session):
    """Test that get_or_create_billing_account creates a new account"""

    org_id = uuid4()
    user_email = "test@example.com"
    org_name = "Test Org"

    # Create organization
    await create_org(pg_async_session, org_id, org_name, user_email)

    # Mocked BillingService
    service = get_mocked_billing_service(pg_async_session)

    # Create billing account
    billing_account = await service.get_or_create_billing_account(
        organization_id=org_id, user_email=user_email, organization_name=org_name
    )

    # Assertions
    assert billing_account is not None
    assert billing_account.organization_id == org_id
    assert billing_account.stripe_customer_id == "cus_test123"
    assert billing_account.status == "trialing"
    assert billing_account.trial_ends_at is not None

    # Verify trial duration
    trial_duration = (billing_account.trial_ends_at - datetime.now(tz=timezone.utc)).days
    assert trial_duration == 14 or trial_duration == 13  # Allow for timing


@pytest.mark.asyncio
async def test_get_or_create_billing_account_idempotent(pg_async_session):
    """Test that calling get_or_create twice returns same account"""

    org_id = uuid4()
    user_email = "test@example.com"

    # Create organization
    await create_org(pg_async_session, org_id, "Test Org", user_email)

    # Mocked BillingService
    service = get_mocked_billing_service(pg_async_session)

    # Create first account
    account1 = await service.get_or_create_billing_account(
        organization_id=org_id, user_email=user_email
    )

    # Call again
    account2 = await service.get_or_create_billing_account(
        organization_id=org_id, user_email=user_email
    )

    # Should return same account
    assert account1.id == account2.id

    # Stripe should only be called once
    service.stripe_client.create_customer.assert_called_once()
