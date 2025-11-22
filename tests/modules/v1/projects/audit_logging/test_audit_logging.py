# tests/modules/projects/test_audit_logging.py
"""
Tests for Audit Logging
"""

import pytest
from app.api.modules.v1.projects.service.audit_service import ProjectAuditService
from sqlmodel import Session

from app.api.modules.v1.projects.models.project_audit_log import AuditAction
from app.api.modules.v1.projects.repositories.audit_repository import (
    ProjectAuditRepository,
)


@pytest.fixture
def audit_service(db_session: Session):
    """Fixture to create audit service"""
    repository = ProjectAuditRepository(db_session)
    return ProjectAuditService(repository)


class TestAuditLogging:
    """Test suite for audit logging functionality"""

    def test_log_project_created(self, audit_service, db_session):
        """Test logging project creation"""
        # Arrange
        project_id = 1
        org_id = 1
        user_id = 10
        details = {
            "title": "GDPR Monitoring",
            "master_prompt": "Monitor GDPR compliance changes",
        }

        # Act
        log = audit_service.log_project_created(
            project_id=project_id,
            org_id=org_id,
            user_id=user_id,
            details=details,
            ip_address="192.168.1.1",
        )

        # Assert
        assert log.log_id is not None
        assert log.project_id == project_id
        assert log.action == AuditAction.PROJECT_CREATED
        assert log.details == details
        assert log.ip_address == "192.168.1.1"

    def test_log_jurisdiction_created(self, audit_service):
        """Test logging jurisdiction creation"""
        log = audit_service.log_jurisdiction_created(
            jurisdiction_id=1,
            project_id=1,
            org_id=1,
            user_id=10,
            details={"name": "California", "parent_id": None},
        )

        assert log.action == AuditAction.JURISDICTION_CREATED
        assert log.jurisdiction_id == 1

    def test_log_master_prompt_updated(self, audit_service):
        """Test logging master prompt update"""
        old_prompt = "Old monitoring prompt"
        new_prompt = "New improved monitoring prompt"

        log = audit_service.log_master_prompt_updated(
            project_id=1,
            org_id=1,
            user_id=10,
            old_prompt=old_prompt,
            new_prompt=new_prompt,
        )

        assert log.action == AuditAction.MASTER_PROMPT_UPDATED
        assert log.details["old_prompt"] == old_prompt
        assert log.details["new_prompt"] == new_prompt

    def test_log_source_assigned(self, audit_service):
        """Test logging source assignment"""
        log = audit_service.log_source_assigned(
            source_id=1,
            jurisdiction_id=1,
            project_id=1,
            org_id=1,
            user_id=10,
            details={
                "source_url": "https://leginfo.legislature.ca.gov",
                "source_type": "government_website",
            },
        )

        assert log.action == AuditAction.SOURCE_ASSIGNED
        assert log.source_id == 1

    def test_get_project_audit_logs(self, audit_service, db_session):
        """Test retrieving project audit logs"""
        # Create test logs
        for i in range(5):
            audit_service.log_project_created(
                project_id=1, org_id=1, user_id=10, details={"test": f"log_{i}"}
            )

        # Retrieve logs
        logs, total = audit_service.repository.get_project_audit_logs(
            project_id=1, page=1, limit=10
        )

        assert total == 5
        assert len(logs) == 5

    def test_filter_by_action(self, audit_service):
        """Test filtering logs by action type"""
        # Create different types of logs
        audit_service.log_project_created(
            project_id=1, org_id=1, user_id=10, details={}
        )
        audit_service.log_project_updated(
            project_id=1,
            org_id=1,
            user_id=10,
            changes={"title": {"old": "A", "new": "B"}},
        )

        # Filter for created only
        logs, total = audit_service.repository.get_project_audit_logs(
            project_id=1, action=AuditAction.PROJECT_CREATED
        )

        assert total == 1
        assert logs[0].action == AuditAction.PROJECT_CREATED

    def test_organization_audit_logs(self, audit_service):
        """Test retrieving organization-wide logs"""
        # Create logs for different projects in same org
        audit_service.log_project_created(
            project_id=1, org_id=1, user_id=10, details={}
        )
        audit_service.log_project_created(
            project_id=2, org_id=1, user_id=10, details={}
        )
        audit_service.log_jurisdiction_created(
            jurisdiction_id=1, project_id=1, org_id=1, user_id=10, details={}
        )

        # Get all org logs
        logs, total = audit_service.repository.get_organization_audit_logs(
            org_id=1, page=1, limit=100
        )

        assert total == 3


class TestAuditEndpoints:
    """Test API endpoints"""

    def test_get_project_audit_logs_endpoint(self, client, auth_headers):
        """Test GET /audit/projects/{project_id}"""
        response = client.get("/api/v1/projects/audit/projects/1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data

    def test_get_organization_logs_admin_only(self, client, user_headers):
        """Test that non-admins cannot access org-wide logs"""
        response = client.get(
            "/api/v1/projects/audit/organization",
            headers=user_headers,  # Non-admin user
        )

        assert response.status_code == 403

    def test_export_audit_logs_csv(self, client, admin_headers):
        """Test CSV export"""
        response = client.get(
            "/api/v1/projects/audit/export?format=csv", headers=admin_headers
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv"

    def test_audit_statistics(self, client, admin_headers):
        """Test audit statistics endpoint"""
        response = client.get(
            "/api/v1/projects/audit/statistics", headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_logs" in data
        assert "by_action" in data
        assert "by_user" in data
