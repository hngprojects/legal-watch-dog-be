from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.core.dependencies.auth import TenantGuard, get_current_user
from app.api.modules.v1.jurisdictions.routes import jurisdiction_route as jurisdiction_routes_module


def _build_app_and_client():
    app = FastAPI()

    app.include_router(jurisdiction_routes_module.router, prefix="/api/v1")
    client = TestClient(app)
    return app, client


def test_routes_blocked_when_user_has_no_org():
    """
    Ensure routes protected by TenantGuard are blocked (403)
    if the current user has no organization memberships.
    """

    class FakeUser:
        id = "user-123"
        email = "fake@example.com"
        is_active = True
        is_verified = True
        organization_memberships = []

    def fake_get_current_user():
        return FakeUser()

    class FakeTenantGuard:
        def __init__(self, current_user=FakeUser()):
            self.user = current_user
            if not getattr(current_user, "organization_memberships", []):
                raise HTTPException(status_code=403, detail="No organization")
            self.org_id = None

        def verify(self, resource_org_id):
            return True

    app, client = _build_app_and_client()
    app.dependency_overrides[get_current_user] = fake_get_current_user
    app.dependency_overrides[TenantGuard] = FakeTenantGuard

    resp = client.get("/api/v1/jurisdictions/")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "No organization"

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(TenantGuard, None)


def test_routes_allow_user_with_org_and_return_data(monkeypatch):
    """If get_current_user returns a user with an organization_id, the
    router dependency should allow the request to proceed to the handler.
    We monkeypatch the service to return a serializable jurisdiction list.
    """

    org_id = uuid4()

    def fake_get_current_user():
        return SimpleNamespace(organization_id=org_id)

    async def fake_get_all(db):
        return [
            SimpleNamespace(
                id=str(uuid4()),
                project_id=str(uuid4()),
                name="J-1",
                description="desc",
            )
        ]

    app, client = _build_app_and_client()
    app.dependency_overrides[get_current_user] = fake_get_current_user

    monkeypatch.setattr(
        jurisdiction_routes_module.service,
        "get_all_jurisdictions",
        fake_get_all,
    )

    resp = client.get("/api/v1/jurisdictions/")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SUCCESS"
    assert "jurisdictions" in body["data"]
    assert isinstance(body["data"]["jurisdictions"], list)

    app.dependency_overrides.pop(get_current_user, None)
