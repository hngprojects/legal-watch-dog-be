import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_billing_active_allows_access(monkeypatch):
    # Mock organization and billing_info as active
    async def mock_get(*args, **kwargs):
        class Org:
            billing_info = {"is_active": True}
        return Org()
    monkeypatch.setattr("app.api.db.database.get_db", lambda: iter([None]))
    monkeypatch.setattr("app.api.modules.v1.organization.models.organization_model.Organization", mock_get)
    response = client.get("/", headers={"X-Organization-ID": "test-org-id"})
    assert response.status_code == 200
    assert "API is running" in response.text

def test_billing_expired_denies_access(monkeypatch):
    # Mock organization and billing_info as expired
    async def mock_get(*args, **kwargs):
        class Org:
            billing_info = {"is_active": False}
        return Org()
    monkeypatch.setattr("app.api.db.database.get_db", lambda: iter([None]))
    monkeypatch.setattr("app.api.modules.v1.organization.models.organization_model.Organization", mock_get)
    response = client.get("/", headers={"X-Organization-ID": "test-org-id"})
    assert response.status_code == 403
    assert "Billing expired" in response.text
