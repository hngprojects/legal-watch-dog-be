import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.api.core.dependencies import plan_limits as plan_limits_mod
from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.routes import project_routes as routes
from app.api.modules.v1.users.models.users_model import User
from main import app


def test_projects_router_has_billing_guard():
    """Ensure the projects router is configured with require_billing_access."""
    deps = routes.router.dependencies

    assert any(getattr(dep, "dependency", None) == require_billing_access for dep in deps), (
        "Projects router should include require_billing_access as a dependency"
    )


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def sample_user():
    return User(
        id=uuid.uuid4(),
        email="plan-limit-user@example.com",
        first_name="Plan",
        last_name="Limit",
        is_active=True,
    )


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


_TEST_SAMPLE_USER = None


async def override_get_current_user_for_tests():
    """Return the sample user set in the test via _TEST_SAMPLE_USER."""
    return _TEST_SAMPLE_USER


async def fake_require_billing_access_for_tests(organization_id=None, db=None):
    """Skip real billing checks in this test."""
    return None


async def fake_require_project_creation_not_allowed(organization_id=None, db=None):
    """
    Simulate the 'plan limit reached' guard for projects.

    This mimics the real error message shape used by plan_limits,
    so our test can assert on the 402 and message substring.
    """
    raise HTTPException(
        status.HTTP_402_PAYMENT_REQUIRED,
        "Your current plan allows up to 1 projects. Please upgrade your plan to add more projects.",
    )


@pytest.mark.asyncio
async def test_project_creation_blocked_when_plan_limit_reached(
    client, pg_async_session, sample_user, auth_headers, monkeypatch
):
    """
    When max_projects is reached for an org, POST /organizations/{org_id}/projects
    should return 402 PAYMENT_REQUIRED.
    """

    organization = Organization(name="Plan Limit Org", is_active=True)
    pg_async_session.add(organization)
    await pg_async_session.commit()
    await pg_async_session.refresh(organization)

    existing_project = Project(
        org_id=organization.id,
        title="Existing Project",
        description="Already here",
        master_prompt=None,
    )
    pg_async_session.add(existing_project)
    await pg_async_session.commit()

    global _TEST_SAMPLE_USER
    _TEST_SAMPLE_USER = sample_user

    app.dependency_overrides[get_current_user] = override_get_current_user_for_tests
    app.dependency_overrides[require_billing_access] = fake_require_billing_access_for_tests

    app.dependency_overrides[plan_limits_mod.require_project_creation_allowed] = (
        fake_require_project_creation_not_allowed
    )

    payload = {
        "title": "Another Project",
        "description": "Should be blocked",
        "master_prompt": "Something",
    }

    response = await client.post(
        f"/api/v1/organizations/{organization.id}/projects",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED, response.text
    body = response.json()
    assert body["status_code"] == status.HTTP_402_PAYMENT_REQUIRED
    assert "plan allows up to 1 projects" in body["message"]
