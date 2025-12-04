from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class ApiKey(SQLModel, table=True):
    __tablename__ = "api_keys"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    key_hash: str = Field(index=True, unique=True)

    # The organization this key belongs to
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)

    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    description: Optional[str] = Field(default=None, max_length=500)
