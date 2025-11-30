"""
Tests for BillingService business logic.

This module tests the core billing service methods including account creation,
payment methods, invoices, and subscription management.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.api.modules.v1.billing.models import (
    BillingAccount,
    BillingPlan,
    BillingStatus,
    InvoiceStatus,
    PlanInterval,
    PlanTier,
)
from app.api.modules.v1.billing.service.billing_service import BillingService
from app.api.modules.v1.organization.models.organization_model import Organization


@pytest.mark.asyncio
class TestBillingServiceAccountCreation:
    """Tests for billing account creation and retrieval."""

    async def test_create_billing_account_success(self, pg_async_session):
        """Test successful billing account creation with Stripe customer."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        mock_stripe_customer = {"id": "cus_test123"}

        with patch(
            "app.api.modules.v1.billing.service.billing_service.stripe_create_customer",
            new=AsyncMock(return_value=mock_stripe_customer),
        ):
            account = await service.create_billing_account(
                organization_id=org_id,
                customer_email="test@example.com",
                customer_name="Test User",
                metadata={"source": "test"},
            )

        assert account.id is not None
        assert account.organization_id == org_id
        assert account.status == BillingStatus.TRIALING
        assert account.stripe_customer_id == "cus_test123"
        assert account.trial_starts_at is not None
        assert account.trial_ends_at is not None
        assert account.currency == "USD"

        # Verify trial is 14 days
        trial_duration = (account.trial_ends_at - account.trial_starts_at).days
        assert trial_duration == 14

    async def test_create_billing_account_duplicate_organization(self, pg_async_session):
        """Test creating duplicate billing account for same org raises error."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        mock_stripe_customer = {"id": "cus_test123"}

        with patch(
            "app.api.modules.v1.billing.service.billing_service.stripe_create_customer",
            new=AsyncMock(return_value=mock_stripe_customer),
        ):
            # Create first account
            await service.create_billing_account(
                organization_id=org_id,
                customer_email="test@example.com",
            )

            # Attempt to create duplicate
            with pytest.raises(ValueError, match="Billing account already exists"):
                await service.create_billing_account(
                    organization_id=org_id,
                    customer_email="test@example.com",
                )

    async def test_create_billing_account_without_stripe_customer(self, pg_async_session):
        """Test creating billing account without Stripe customer."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        account = await service.create_billing_account(
            organization_id=org_id,
            currency="EUR",
            initial_status=BillingStatus.ACTIVE,
        )

        assert account.organization_id == org_id
        assert account.stripe_customer_id is None
        assert account.status == BillingStatus.ACTIVE
        assert account.currency == "EUR"

    async def test_create_billing_account_stripe_failure(self, pg_async_session):
        """Test billing account creation when Stripe customer creation fails."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        # Mock Stripe to return no customer ID
        mock_stripe_customer = {"id": None}

        with patch(
            "app.api.modules.v1.billing.service.billing_service.stripe_create_customer",
            new=AsyncMock(return_value=mock_stripe_customer),
        ):
            with pytest.raises(Exception, match="Stripe customer creation failed"):
                await service.create_billing_account(
                    organization_id=org_id,
                    customer_email="test@example.com",
                )

    async def test_get_billing_account_by_org(self, pg_async_session):
        """Test retrieving billing account by organization ID."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        # Create account
        created = await service.create_billing_account(organization_id=org_id)

        # Retrieve account
        retrieved = await service.get_billing_account_by_org(org_id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.organization_id == org_id

    async def test_get_billing_account_by_org_not_found(self, pg_async_session):
        """Test retrieving non-existent billing account returns None."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        account = await service.get_billing_account_by_org(org_id)

        assert account is None

    async def test_get_billing_account_by_id(self, pg_async_session):
        """Test retrieving billing account by ID."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        created = await service.create_billing_account(organization_id=org_id)

        retrieved = await service.get_billing_account_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    async def test_find_billing_account_by_customer_id(self, pg_async_session):
        """Test finding billing account by Stripe customer ID."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        mock_stripe_customer = {"id": "cus_unique123"}

        with patch(
            "app.api.modules.v1.billing.service.billing_service.stripe_create_customer",
            new=AsyncMock(return_value=mock_stripe_customer),
        ):
            created = await service.create_billing_account(
                organization_id=org_id,
                customer_email="test@example.com",
            )

        found = await service.find_billing_account_by_customer_id("cus_unique123")

        assert found is not None
        assert found.id == created.id
        assert found.stripe_customer_id == "cus_unique123"


@pytest.mark.asyncio
class TestBillingServiceUsageCheck:
    """Tests for organization usage eligibility checks."""

    async def test_is_org_allowed_usage_trialing(self, pg_async_session):
        """Test organization is allowed during trial period."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        # Create account with active trial
        await service.create_billing_account(organization_id=org_id)

        allowed, status = await service.is_org_allowed_usage(org_id)

        assert allowed is True
        assert status == BillingStatus.TRIALING

    async def test_is_org_allowed_usage_expired_trial(self, pg_async_session):
        """Test organization is blocked after trial expires."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        # Create account with expired trial
        past_date = datetime.now(timezone.utc) - timedelta(days=1)
        account = BillingAccount(
            organization_id=org_id,
            status=BillingStatus.TRIALING,
            trial_starts_at=past_date - timedelta(days=14),
            trial_ends_at=past_date,
            currency="USD",
            metadata_={},
        )
        pg_async_session.add(account)
        await pg_async_session.commit()

        allowed, status = await service.is_org_allowed_usage(org_id)

        assert allowed is False
        assert status == BillingStatus.UNPAID

    async def test_is_org_allowed_usage_active_subscription(self, pg_async_session):
        """Test organization is allowed with active subscription."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        # Create account with active status
        account = BillingAccount(
            organization_id=org_id,
            status=BillingStatus.ACTIVE,
            currency="USD",
            metadata_={},
        )
        pg_async_session.add(account)
        await pg_async_session.commit()

        allowed, status = await service.is_org_allowed_usage(org_id)

        assert allowed is True
        assert status == BillingStatus.ACTIVE

    async def test_is_org_allowed_usage_past_due(self, pg_async_session):
        """Test organization is blocked when past due."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        account = BillingAccount(
            organization_id=org_id,
            status=BillingStatus.PAST_DUE,
            currency="USD",
            metadata_={},
        )
        pg_async_session.add(account)
        await pg_async_session.commit()

        allowed, status = await service.is_org_allowed_usage(org_id)

        assert allowed is False
        assert status == BillingStatus.PAST_DUE

    async def test_is_org_allowed_usage_cancelled(self, pg_async_session):
        """Test organization is blocked when subscription is cancelled."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        account = BillingAccount(
            organization_id=org_id,
            status=BillingStatus.CANCELLED,
            currency="USD",
            metadata_={},
        )
        pg_async_session.add(account)
        await pg_async_session.commit()

        allowed, status = await service.is_org_allowed_usage(org_id)

        assert allowed is False
        assert status == BillingStatus.CANCELLED

    async def test_is_org_allowed_usage_no_account(self, pg_async_session):
        """Test organization without billing account is not allowed."""
        service = BillingService(pg_async_session)
        org_id = uuid4()

        allowed, status = await service.is_org_allowed_usage(org_id)

        assert allowed is False
        assert status is None

    async def test_is_org_allowed_usage_period_expired_with_cancel_flag(self, pg_async_session):
        """Test cancelled subscription at period end blocks access."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        past_date = datetime.now(timezone.utc) - timedelta(days=1)
        account = BillingAccount(
            organization_id=org_id,
            status=BillingStatus.ACTIVE,
            current_period_end=past_date,
            cancel_at_period_end=True,
            currency="USD",
            metadata_={},
        )
        pg_async_session.add(account)
        await pg_async_session.commit()

        allowed, status = await service.is_org_allowed_usage(org_id)

        assert allowed is False
        assert status == BillingStatus.CANCELLED


@pytest.mark.asyncio
class TestBillingServicePlans:
    """Tests for billing plan management."""

    async def test_list_active_plans(self, pg_async_session):
        """Test listing active billing plans."""
        service = BillingService(pg_async_session)

        # Create multiple plans
        plan1 = BillingPlan(
            code="essential_monthly",
            tier=PlanTier.ESSENTIAL,
            label="Essential",
            interval=PlanInterval.MONTH,
            currency="USD",
            amount=5000,
            stripe_product_id="prod_1",
            stripe_price_id="price_1",
            is_active=True,
            sort_order=1,
        )
        plan2 = BillingPlan(
            code="professional_monthly",
            tier=PlanTier.PROFESSIONAL,
            label="Professional",
            interval=PlanInterval.MONTH,
            currency="USD",
            amount=10000,
            stripe_product_id="prod_2",
            stripe_price_id="price_2",
            is_active=True,
            sort_order=2,
        )
        plan3 = BillingPlan(
            code="inactive_plan",
            tier=PlanTier.ENTERPRISE,
            label="Inactive",
            interval=PlanInterval.MONTH,
            currency="USD",
            amount=20000,
            stripe_product_id="prod_3",
            stripe_price_id="price_3",
            is_active=False,
            sort_order=3,
        )

        pg_async_session.add_all([plan1, plan2, plan3])
        await pg_async_session.commit()

        active_plans = await service.list_active_plans()

        assert len(active_plans) == 2
        assert all(plan.is_active for plan in active_plans)
        # Verify sort order
        assert active_plans[0].sort_order <= active_plans[1].sort_order

    async def test_get_plan_by_id(self, pg_async_session):
        """Test retrieving plan by ID."""
        service = BillingService(pg_async_session)

        plan = BillingPlan(
            code="test_plan",
            tier=PlanTier.ESSENTIAL,
            label="Test",
            interval=PlanInterval.MONTH,
            currency="USD",
            amount=1000,
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
        )
        pg_async_session.add(plan)
        await pg_async_session.commit()
        await pg_async_session.refresh(plan)

        retrieved = await service.get_plan_by_id(plan.id)

        assert retrieved is not None
        assert retrieved.id == plan.id
        assert retrieved.code == "test_plan"

    async def test_get_plan_by_stripe_price_id(self, pg_async_session):
        """Test retrieving plan by Stripe price ID."""
        service = BillingService(pg_async_session)

        plan = BillingPlan(
            code="test_plan",
            tier=PlanTier.ESSENTIAL,
            label="Test",
            interval=PlanInterval.MONTH,
            currency="USD",
            amount=1000,
            stripe_product_id="prod_test",
            stripe_price_id="price_unique123",
        )
        pg_async_session.add(plan)
        await pg_async_session.commit()

        retrieved = await service.get_plan_by_stripe_price_id("price_unique123")

        assert retrieved is not None
        assert retrieved.stripe_price_id == "price_unique123"


@pytest.mark.asyncio
class TestBillingServicePaymentMethods:
    """Tests for payment method management."""

    async def test_add_payment_method_success(self, pg_async_session):
        """Test adding payment method to billing account."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        # Create billing account
        account = await service.create_billing_account(organization_id=org_id)

        # Mock Stripe payment method attachment
        with patch(
            "app.api.modules.v1.billing.service.billing_service.stripe_attach_payment_method",
            new=AsyncMock(return_value={"id": "pm_test123"}),
        ):
            pm = await service.add_payment_method(
                billing_account_id=account.id,
                stripe_payment_method_id="pm_test123",
                card_brand="visa",
                last4="4242",
                exp_month=12,
                exp_year=2025,
                is_default=True,
            )

        assert pm.id is not None
        assert pm.billing_account_id == account.id
        assert pm.stripe_payment_method_id == "pm_test123"
        assert pm.card_brand == "visa"
        assert pm.last4 == "4242"
        assert pm.is_default is True

    async def test_add_payment_method_account_not_found(self, pg_async_session):
        """Test adding payment method to non-existent account fails."""
        service = BillingService(pg_async_session)
        fake_account_id = uuid4()

        with pytest.raises(ValueError, match="Billing account not found"):
            await service.add_payment_method(
                billing_account_id=fake_account_id,
                stripe_payment_method_id="pm_test123",
            )

    async def test_add_payment_method_clears_previous_default(self, pg_async_session):
        """Test adding default payment method clears previous default."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        account = await service.create_billing_account(organization_id=org_id)

        with patch(
            "app.api.modules.v1.billing.service.billing_service.stripe_attach_payment_method",
            new=AsyncMock(return_value={"id": "pm_test"}),
        ):
            # Add first payment method as default
            pm1 = await service.add_payment_method(
                billing_account_id=account.id,
                stripe_payment_method_id="pm_first",
                is_default=True,
            )

            # Add second payment method as default
            pm2 = await service.add_payment_method(
                billing_account_id=account.id,
                stripe_payment_method_id="pm_second",
                is_default=True,
            )

        # Refresh first payment method
        await pg_async_session.refresh(pm1)

        assert pm1.is_default is False
        assert pm2.is_default is True

    async def test_list_payment_methods(self, pg_async_session):
        """Test listing all payment methods for an account."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        account = await service.create_billing_account(organization_id=org_id)

        with patch(
            "app.api.modules.v1.billing.service.billing_service.stripe_attach_payment_method",
            new=AsyncMock(return_value={"id": "pm_test"}),
        ):
            await service.add_payment_method(
                billing_account_id=account.id,
                stripe_payment_method_id="pm_1",
            )
            await service.add_payment_method(
                billing_account_id=account.id,
                stripe_payment_method_id="pm_2",
            )

        payment_methods = await service.list_payment_methods(account.id)

        assert len(payment_methods) == 2

    async def test_delete_payment_method_success(self, pg_async_session):
        """Test deleting a payment method."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        account = await service.create_billing_account(organization_id=org_id)

        with patch(
            "app.api.modules.v1.billing.service.billing_service.stripe_attach_payment_method",
            new=AsyncMock(return_value={"id": "pm_test"}),
        ):
            pm = await service.add_payment_method(
                billing_account_id=account.id,
                stripe_payment_method_id="pm_delete_test",
            )

        with patch(
            "app.api.modules.v1.billing.service.billing_service.stripe_detach_payment_method",
            new=AsyncMock(return_value={"id": "pm_delete_test"}),
        ):
            deleted = await service.delete_payment_method(pm.id)

        assert deleted is True

        # Verify it's actually deleted
        retrieved = await service.get_payment_method_by_id(pm.id)
        assert retrieved is None

    async def test_delete_payment_method_not_found(self, pg_async_session):
        """Test deleting non-existent payment method returns False."""
        service = BillingService(pg_async_session)
        fake_pm_id = uuid4()

        deleted = await service.delete_payment_method(fake_pm_id)

        assert deleted is False


@pytest.mark.asyncio
class TestBillingServiceInvoices:
    """Tests for invoice management."""

    async def test_create_invoice_record(self, pg_async_session):
        """Test creating invoice record."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        account = await service.create_billing_account(organization_id=org_id)

        invoice = await service.create_invoice_record(
            billing_account_id=account.id,
            amount_due=10000,
            amount_paid=10000,
            currency="USD",
            stripe_invoice_id="in_test123",
            status=InvoiceStatus.PAID,
        )

        assert invoice.id is not None
        assert invoice.billing_account_id == account.id
        assert invoice.amount_due == 10000
        assert invoice.amount_paid == 10000
        assert invoice.stripe_invoice_id == "in_test123"
        assert invoice.status == InvoiceStatus.PAID

    async def test_mark_invoice_paid(self, pg_async_session):
        """Test marking invoice as paid."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        account = await service.create_billing_account(organization_id=org_id)

        invoice = await service.create_invoice_record(
            billing_account_id=account.id,
            amount_due=10000,
            amount_paid=0,
            status=InvoiceStatus.OPEN,
        )

        updated = await service.mark_invoice_paid(invoice.id, amount_paid=10000)

        assert updated.status == InvoiceStatus.PAID
        assert updated.amount_paid == 10000

    async def test_mark_invoice_failed(self, pg_async_session):
        """Test marking invoice as failed."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        account = await service.create_billing_account(organization_id=org_id)

        invoice = await service.create_invoice_record(
            billing_account_id=account.id,
            amount_due=10000,
            status=InvoiceStatus.OPEN,
        )

        updated = await service.mark_invoice_failed(invoice.id)

        assert updated.status == InvoiceStatus.FAILED

    async def test_get_invoices_for_account(self, pg_async_session):
        """Test retrieving invoices for an account."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        account = await service.create_billing_account(organization_id=org_id)

        # Create multiple invoices
        await service.create_invoice_record(
            billing_account_id=account.id,
            amount_due=5000,
            stripe_invoice_id="in_1",
        )
        await service.create_invoice_record(
            billing_account_id=account.id,
            amount_due=10000,
            stripe_invoice_id="in_2",
        )

        invoices = await service.get_invoices_for_account(account.id)

        assert len(invoices) == 2

    async def test_find_invoice_by_stripe_invoice_id(self, pg_async_session):
        """Test finding invoice by Stripe invoice ID."""
        service = BillingService(pg_async_session)
        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()
        await pg_async_session.refresh(org)

        account = await service.create_billing_account(organization_id=org_id)

        created = await service.create_invoice_record(
            billing_account_id=account.id,
            amount_due=10000,
            stripe_invoice_id="in_unique123",
        )

        found = await service.find_invoice_by_stripe_invoice_id("in_unique123")

        assert found is not None
        assert found.id == created.id
