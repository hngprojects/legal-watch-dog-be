"""
Integration tests for audit logging service methods.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_audit_log import (
    AuditAction,
    ProjectAuditLog,
)
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.repositories.audit_repository import (
    ProjectAuditRepository,
)
from app.api.modules.v1.projects.services.audit_service import ProjectAuditService
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.password import hash_password
from app.api.utils.permissions import ADMIN_PERMISSIONS


@pytest_asyncio.fixture
async def audit_service(pg_async_session: AsyncSession) -> ProjectAuditService:
    """Create audit service instance."""
    repository = ProjectAuditRepository(pg_async_session)
    service = ProjectAuditService(repository)
    yield service
    await pg_async_session.close()


@pytest_asyncio.fixture
async def setup_audit_data(pg_async_session: AsyncSession):
    """Setup all test data in one fixture to avoid foreign key errors."""
    # Create org
    org = Organization(
        id=uuid4(),
        name=f"Test Org {uuid4()}",
        email=f"org-{uuid4()}@test.com",
        industry="Tech",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    pg_async_session.add(org)
    await pg_async_session.commit()

    # Create role
    role = Role(
        id=uuid4(),
        organization_id=org.id,
        name="Admin",
        permissions=ADMIN_PERMISSIONS,
        created_at=datetime.now(timezone.utc),
    )
    pg_async_session.add(role)
    await pg_async_session.commit()

    # Create user
    user = User(
        id=uuid4(),
        organization_id=org.id,
        role_id=role.id,
        email=f"user-{uuid4()}@test.com",
        hashed_password=hash_password("password"),
        name="Test User",
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    pg_async_session.add(user)
    await pg_async_session.commit()

    # Create project
    project = Project(
        id=uuid4(),
        org_id=org.id,
        title=f"Project {uuid4()}",
        description="Test project",
        master_prompt="Test prompt",
        created_by=user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    pg_async_session.add(project)
    await pg_async_session.commit()

    # Create audit logs
    logs = []
    for i in range(3):
        log = ProjectAuditLog(
            org_id=org.id,
            project_id=project.id,
            user_id=user.id,
            action=AuditAction.PROJECT_CREATED if i == 0 else AuditAction.PROJECT_UPDATED,
            details={"test": f"log_{i}"},
            ip_address=f"192.168.1.{i}",
            created_at=datetime.now(timezone.utc) - timedelta(hours=i),
        )
        pg_async_session.add(log)
        logs.append(log)
    
    await pg_async_session.commit()
    
    # Refresh all objects
    await pg_async_session.refresh(org)
    await pg_async_session.refresh(user)
    await pg_async_session.refresh(project)
    for log in logs:
        await pg_async_session.refresh(log)

    return {
        "org": org,
        "user": user,
        "project": project,
        "logs": logs,
    }


@pytest.mark.asyncio
async def test_get_project_audit_logs(
    audit_service: ProjectAuditService,
    setup_audit_data: dict,
):
    """Test retrieving project audit logs."""
    project = setup_audit_data["project"]
    
    logs, total = await audit_service.get_project_audit_logs(
        project_id=project.id,
        page=1,
        limit=10,
    )
    
    assert total >= 3
    assert len(logs) >= 3
    for log in logs:
        assert log.project_id == project.id
        assert log.log_id is not None


@pytest.mark.asyncio
async def test_get_project_audit_logs_with_filter(
    audit_service: ProjectAuditService,
    setup_audit_data: dict,
):
    """Test filtering logs by action."""
    project = setup_audit_data["project"]
    
    logs, total = await audit_service.get_project_audit_logs(
        project_id=project.id,
        action=AuditAction.PROJECT_CREATED,
        page=1,
        limit=10,
    )
    
    assert total >= 1
    for log in logs:
        assert log.action == AuditAction.PROJECT_CREATED


@pytest.mark.asyncio
async def test_get_organization_audit_logs(
    audit_service: ProjectAuditService,
    setup_audit_data: dict,
):
    """Test retrieving organization-wide logs."""
    org = setup_audit_data["org"]
    
    logs, total = await audit_service.get_organization_audit_logs(
        org_id=org.id,
        page=1,
        limit=100,
    )
    
    assert total >= 3
    for log in logs:
        assert log.org_id == org.id


@pytest.mark.asyncio
async def test_get_audit_log_by_id(
    audit_service: ProjectAuditService,
    setup_audit_data: dict,
):
    """Test retrieving specific log by ID."""
    org = setup_audit_data["org"]
    log_id = setup_audit_data["logs"][0].log_id
    
    log = await audit_service.get_audit_log_by_id(
        log_id=log_id,
        org_id=org.id,
    )
    
    assert log is not None
    assert log.log_id == log_id


@pytest.mark.asyncio
async def test_get_audit_statistics(
    audit_service: ProjectAuditService,
    setup_audit_data: dict,
):
    """Test audit statistics generation."""
    org = setup_audit_data["org"]
    
    stats = await audit_service.get_audit_statistics(
        org_id=org.id,
    )
    
    assert stats.total_logs >= 3
    assert isinstance(stats.by_action, dict)
    assert isinstance(stats.by_user, dict)


@pytest.mark.asyncio
async def test_log_project_created(
    audit_service: ProjectAuditService,
    setup_audit_data: dict,
):
    """Test logging project creation."""
    org = setup_audit_data["org"]
    user = setup_audit_data["user"]
    project = setup_audit_data["project"]
    
    log = await audit_service.log_project_created(
        project_id=project.id,
        org_id=org.id,
        user_id=user.id,
        details={"title": "New Project"},
        ip_address="10.0.0.1",
    )
    
    assert log is not None
    assert log.action == AuditAction.PROJECT_CREATED


@pytest.mark.asyncio
async def test_log_project_updated(
    audit_service: ProjectAuditService,
    setup_audit_data: dict,
):
    """Test logging project update."""
    org = setup_audit_data["org"]
    user = setup_audit_data["user"]
    project = setup_audit_data["project"]
    
    log = await audit_service.log_project_updated(
        project_id=project.id,
        org_id=org.id,
        user_id=user.id,
        changes={"title": {"old": "A", "new": "B"}},
    )
    
    assert log is not None
    assert log.action == AuditAction.PROJECT_UPDATED


@pytest.mark.asyncio
async def test_log_project_deleted(
    audit_service: ProjectAuditService,
    setup_audit_data: dict,
):
    """Test logging project deletion."""
    org = setup_audit_data["org"]
    user = setup_audit_data["user"]
    project = setup_audit_data["project"]
    
    log = await audit_service.log_project_deleted(
        project_id=project.id,
        org_id=org.id,
        user_id=user.id,
        details={"title": "Deleted", "deletion_type": "soft"},
    )
    
    assert log is not None
    assert log.action == AuditAction.PROJECT_DELETED